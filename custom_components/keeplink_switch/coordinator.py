"""DataUpdateCoordinator for Keeplink Switch."""
import logging
import hashlib
import re
import aiohttp
import async_timeout
import time
import copy
from bs4 import BeautifulSoup
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    DOMAIN,
    ENDPOINT_INFO,
    ENDPOINT_PANEL,
    ENDPOINT_TRUNK,
    ENDPOINT_PSE_SYSTEM,
    ENDPOINT_PSE_PORT,
    ENDPOINT_PORT_SETTINGS,
    ENDPOINT_PORT_STATS,
)

_LOGGER = logging.getLogger(__name__)


class KeeplinkCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the switch."""

    def __init__(self, hass, session, host, username, password, scan_interval, poe_scan_interval):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password
        self.session = session
        self.mac_address = None
        self.device_info = {}

        # Intervals tracking
        self.scan_interval = scan_interval
        self.poe_scan_interval = poe_scan_interval
        self.last_general_update = 0
        self.last_poe_update = 0

        # Auth Hash Calculation
        auth_str = f"{username}{password}"
        self.auth_cookie = hashlib.md5(auth_str.encode()).hexdigest()

        # The engine needs to tick at the fastest required speed
        fastest_interval = min(scan_interval, poe_scan_interval)

        super().__init__(
            hass,
            _LOGGER,
            name=f"Keeplink Switch ({host})",
            update_interval=timedelta(seconds=fastest_interval),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoints smartly based on time."""
        current_time = time.time()
        data = copy.deepcopy(self.data) if self.data else {
            "ports": {},
            "interfaces": {},
            "trunks": {},
        }
        data.setdefault("ports", {})
        data.setdefault("interfaces", {})
        data.setdefault("trunks", {})

        update_general = (current_time - self.last_general_update) >= (self.scan_interval - 2)
        update_poe = (current_time - self.last_poe_update) >= (self.poe_scan_interval - 2)

        headers = {
            "Referer": f"http://{self.host}/login.cgi",
            "User-Agent": "HomeAssistant/1.0",
        }
        cookies = {"admin": self.auth_cookie}

        try:
            async with async_timeout.timeout(30):

                # --- POE DATA FETCH (Strictly Physical Ports 1-8) ---
                if update_poe:
                    poe_sys_data = await self._fetch_page(
                        ENDPOINT_PSE_SYSTEM, headers, cookies, self._parse_pse_system
                    )
                    data.update(poe_sys_data)

                    poe_port_data = await self._fetch_page(
                        ENDPOINT_PSE_PORT, headers, cookies, self._parse_pse_port
                    )

                    # Abort setup if PoE data is missing during a cold boot
                    if not poe_port_data or not poe_port_data.get("ports"):
                        raise UpdateFailed("PoE controller is still booting and hasn't populated port data.")

                    self._deep_merge_ports(data, poe_port_data)
                    self.last_poe_update = current_time

                # --- GENERAL DATA FETCH ---
                if update_general:
                    # 1. Fetch System Info
                    info_data = await self._fetch_page(ENDPOINT_INFO, headers, cookies, self._parse_info)

                    # RECOVERY LOGIC: If we didn't get a MAC, the switch might be locked/rebooted.
                    if "mac" not in info_data:
                        _LOGGER.warning(f"MAC not found on {self.host}. Attempting auto-login recovery...")
                        await self._async_login(headers, cookies)
                        cookies = {"admin": self.auth_cookie}
                        info_data = await self._fetch_page(ENDPOINT_INFO, headers, cookies, self._parse_info)

                    data.update(info_data)

                    # 2. Fetch Physical Panel Link State (panel.cgi) - Works for all physical ports 1..9
                    panel_data = await self._fetch_page(ENDPOINT_PANEL, headers, cookies, self._parse_panel)
                    self._deep_merge_ports(data, panel_data)

                    # 3. Fetch Trunk Group Configuration (trunk.cgi?page=group)
                    trunk_data = await self._fetch_page(ENDPOINT_TRUNK, headers, cookies, self._parse_trunk_group)
                    data["trunks"] = trunk_data

                    # 4. Fetch Logical Interface Settings & Stats (Fresh dict so trunk changes clear stale keys)
                    interfaces_dict = {}
                    settings_data = await self._fetch_page(
                        ENDPOINT_PORT_SETTINGS, headers, cookies, self._parse_port_settings
                    )
                    self._deep_merge_interfaces(interfaces_dict, settings_data.get("interfaces", {}))

                    stats_data = await self._fetch_page(
                        ENDPOINT_PORT_STATS, headers, cookies, self._parse_port_stats
                    )
                    self._deep_merge_interfaces(interfaces_dict, stats_data.get("interfaces", {}))

                    data["interfaces"] = interfaces_dict

                    # 5. Synchronize physical ports with their trunk membership and standalone stats
                    for port_num, p_dict in data["ports"].items():
                        # Identify if this physical port belongs to an active Trunk
                        assigned_trunk = None
                        for trunk_id, t_info in trunk_data.items():
                            if t_info.get("active") and port_num in t_info.get("member_list", []):
                                assigned_trunk = trunk_id
                                break
                        p_dict["trunk_group"] = assigned_trunk

                        # If standalone (not in a trunk), sync L2 settings/stats into ports[port_num] for backward compatibility
                        if port_num in interfaces_dict:
                            p_dict.update(interfaces_dict[port_num])
                        else:
                            # Port is inside a trunk; clear standalone L2 keys so they don't stay stale
                            for stale_key in (
                                "admin_state",
                                "config_speed",
                                "speed",
                                "config_flow",
                                "flow_control",
                                "tx_packets",
                                "rx_packets",
                                "tx_errors",
                                "rx_errors",
                            ):
                                p_dict.pop(stale_key, None)

                    self.last_general_update = current_time

                    # Build Device Info once MAC is confirmed
                    if "mac" in data:
                        self.mac_address = data["mac"]
                        self.device_info = {
                            "manufacturer": "Keeplink",
                            "model": data.get("model", "Unknown Model"),
                            "sw_version": data.get("firmware", "Unknown"),
                            "hw_version": data.get("hardware", "Unknown"),
                        }
                    else:
                        raise UpdateFailed("MAC address not found. Switch is still booting or auth rejected.")

            return data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    def _deep_merge_ports(self, main_data, new_data):
        """Safely merges new physical port attributes without erasing existing ones."""
        if "ports" not in main_data:
            main_data["ports"] = {}

        if "ports" in new_data:
            for port, info in new_data["ports"].items():
                if port not in main_data["ports"]:
                    main_data["ports"][port] = {}
                main_data["ports"][port].update(info)

    def _deep_merge_interfaces(self, target_interfaces, new_interfaces):
        """Safely merges logical interface attributes (ports 1..9 and Trunk1/Trunk2)."""
        for iface_id, info in new_interfaces.items():
            if iface_id not in target_interfaces:
                target_interfaces[iface_id] = {}
            target_interfaces[iface_id].update(info)

    async def _async_login(self, headers, cookies):
        """Simulate an exact browser login sequence based on the switch's md5.js logic."""
        login_url = f"http://{self.host}/login.cgi"

        auth_str = f"{self.username}{self.password}"
        response_hash = hashlib.md5(auth_str.encode("utf-8")).hexdigest()

        payload = {
            "username": self.username,
            "password": self.password,
            "language": "EN",
            "Response": response_hash,
        }

        login_cookies = {"admin": response_hash}

        login_headers = {
            "Host": self.host,
            "Origin": f"http://{self.host}",
            "Referer": f"http://{self.host}/login.cgi",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            _LOGGER.debug(f"Executing explicit POST login for {self.host} with Response Hash: {response_hash}")
            async with self.session.post(
                login_url, data=payload, headers=login_headers, cookies=login_cookies, timeout=5
            ) as response:
                await response.text()

            await self.session.get(f"http://{self.host}/", headers=login_headers, cookies=login_cookies, timeout=5)
            self.auth_cookie = response_hash

        except Exception as e:
            _LOGGER.warning(f"Auto-login sequence encountered an issue on {self.host}: {e}")

    async def _fetch_page(self, endpoint, headers, cookies, parser_func):
        """Helper to fetch and parse a single page smoothly."""
        url = f"http://{self.host}/{endpoint}"
        response = await self.session.get(url, headers=headers, cookies=cookies, allow_redirects=True)
        html = await response.text()
        return parser_func(html)

    # -------------------------------------------------------------------------
    # PARSERS (Reading data from the switch)
    # -------------------------------------------------------------------------

    def _parse_info(self, html):
        """Parse System Info (info.cgi)."""
        soup = BeautifulSoup(html, "html.parser")
        data = {}
        rows = soup.find_all("tr")
        for row in rows:
            cols = row.find_all(["th", "td"])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)

                if "Device Model" in key:
                    data["model"] = value
                elif "Firmware Version" in key:
                    data["firmware"] = value
                elif "MAC Address" in key:
                    data["mac"] = value
                elif "Hardware Version" in key:
                    data["hardware"] = value
                elif "IP Address" in key:
                    data["ip_address"] = value
                elif "Netmask" in key:
                    data["netmask"] = value
                elif "Gateway" in key:
                    data["gateway"] = value
                elif "Firmware Date" in key:
                    data["firmware_date"] = value
        return data

    def _parse_panel(self, html):
        """Parse physical RJ45 and Fiber/SFP+ link status from panel.cgi."""
        soup = BeautifulSoup(html, "html.parser")
        data = {"ports": {}}

        tables = soup.find_all("table")
        for i in range(0, len(tables) - 1, 2):
            num_tds = [
                td.get_text(strip=True)
                for td in tables[i].find_all("td")
                if td.get_text(strip=True).isdigit()
            ]
            imgs = [img.get("src", "") for img in tables[i + 1].find_all("img")]

            for port_str, img_src in zip(num_tds, imgs):
                try:
                    port_num = int(port_str)
                except ValueError:
                    continue

                # Fiber ports use 'Fiber_up_X.png' (Up) vs 'Fiber_down_X.png' (Down)
                # RJ45 ports use 'RJ45_up_1.png' (Up) vs 'RJ45_up_0.png' (Down)
                if "Fiber" in img_src:
                    is_up = "_up_" in img_src
                else:
                    is_up = "_1." in img_src

                data["ports"][port_num] = {
                    "is_link_up": is_up,
                    "physical_status": "Connected" if is_up else "Disconnected",
                    "panel_icon": img_src,
                }
        return data

    def _parse_trunk_group(self, html):
        """Parse Trunk Group Setting (trunk.cgi?page=group)."""
        soup = BeautifulSoup(html, "html.parser")
        trunks = {
            "Trunk1": {
                "active": False,
                "type": "Inactive",
                "member_ports": "None",
                "aggregated_ports": "None",
                "member_list": [],
            },
            "Trunk2": {
                "active": False,
                "type": "Inactive",
                "member_ports": "None",
                "aggregated_ports": "None",
                "member_list": [],
            },
        }

        remove_form = soup.find("form", action=re.compile(r"group_remove"))
        if not remove_form:
            return trunks

        for row in remove_form.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) >= 4 and cols[0].startswith("Trunk"):
                trunk_id = cols[0].replace(" ", "")
                trunk_type = cols[1]
                member_ports = cols[2] if cols[2] else "None"
                agg_ports = cols[3] if cols[3] else "None"

                trunks[trunk_id] = {
                    "active": True,
                    "type": trunk_type,
                    "member_ports": member_ports,
                    "aggregated_ports": agg_ports,
                    "member_list": self._expand_port_range(member_ports),
                }
        return trunks

    def _expand_port_range(self, port_str):
        """Expand Keeplink port string like '2-3' or '2,4-5' into integer list [2, 3]."""
        result = []
        if not port_str or port_str == "None":
            return result
        for part in port_str.split(","):
            part = part.strip()
            if "-" in part:
                try:
                    start, end = map(int, part.split("-"))
                    result.extend(list(range(start, end + 1)))
                except ValueError:
                    pass
            elif part.isdigit():
                result.append(int(part))
        return result

    def _parse_pse_system(self, html):
        """Parse Total PoE Power (pse_system.cgi)."""
        soup = BeautifulSoup(html, "html.parser")
        data = {}
        input_tag = soup.find("input", {"name": "pse_con_pwr"})
        if input_tag and input_tag.get("value"):
            try:
                data["poe_total_power"] = float(input_tag["value"])
            except ValueError:
                pass
        return data

    def _parse_pse_port(self, html):
        """Parse Per-Port PoE Data (pse_port.cgi)."""
        soup = BeautifulSoup(html, "html.parser")
        data = {"ports": {}}
        tables = soup.find_all("table")
        if len(tables) < 2:
            return data

        data_table = tables[1]
        rows = data_table.find_all("tr")

        for row in rows[1:]:
            cols = row.find_all("td")
            if len(cols) >= 7:
                port_name = cols[0].get_text(strip=True)
                try:
                    port_num = int(port_name.replace("Port ", ""))
                except ValueError:
                    continue

                def parse_val(text):
                    return float(text) if text != "-" else 0.0

                data["ports"][port_num] = {
                    "power": parse_val(cols[4].get_text(strip=True)),
                    "voltage": parse_val(cols[5].get_text(strip=True)),
                    "current": parse_val(cols[6].get_text(strip=True)),
                    "enabled": "Enable" in cols[1].get_text(strip=True),
                }
        return data

    def _parse_port_settings(self, html):
        """Parse Port and Trunk Settings like Speed and Flow Control (port.cgi)."""
        soup = BeautifulSoup(html, "html.parser")
        data = {"interfaces": {}}

        # 1. Extract form portid values (e.g., Port 1 -> 0, Port 9 -> 8, Trunk1 -> 10, Trunk2 -> 11)
        portid_map = {}
        for select in soup.find_all("select", attrs={"name": "portid"}):
            for opt in select.find_all("option"):
                label = opt.get_text(strip=True)
                val = opt.get("value")
                if label.startswith("Port "):
                    try:
                        iface_key = int(label.replace("Port ", "").strip())
                    except ValueError:
                        continue
                elif label.startswith("Trunk"):
                    iface_key = label.replace(" ", "")
                else:
                    continue
                if val is not None:
                    portid_map[iface_key] = val

        # 2. Extract settings from summary table
        tables = soup.find_all("table")
        if not tables:
            return data

        target_table = tables[-1]
        for row in target_table.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) >= 6:
                port_text = cols[0].get_text(strip=True)
                if port_text.startswith("Port "):
                    try:
                        iface_key = int(port_text.replace("Port ", "").strip())
                    except ValueError:
                        continue
                elif port_text.startswith("Trunk"):
                    iface_key = port_text.replace(" ", "")
                else:
                    continue

                # Default fallback portid if not in dropdown
                default_portid = (
                    str(iface_key - 1)
                    if isinstance(iface_key, int)
                    else ("10" if iface_key == "Trunk1" else "11")
                )

                data["interfaces"][iface_key] = {
                    "portid": portid_map.get(iface_key, default_portid),
                    "admin_state": cols[1].get_text(strip=True) == "Enable",
                    "config_speed": cols[2].get_text(strip=True),
                    "speed": cols[3].get_text(strip=True),
                    "config_flow": cols[4].get_text(strip=True) == "On",
                    "flow_control": cols[5].get_text(strip=True),
                }
        return data

    def _parse_port_stats(self, html):
        """Parse Link Status and Traffic Counters for Ports and Trunks (port.cgi?page=stats)."""
        soup = BeautifulSoup(html, "html.parser")
        data = {"interfaces": {}}
        tables = soup.find_all("table")
        if not tables:
            return data

        target_table = tables[0]
        for row in target_table.find_all("tr"):
            cols = row.find_all(["td"])
            if len(cols) >= 7:
                port_text = cols[0].get_text(strip=True)
                if port_text.startswith("Port "):
                    try:
                        iface_key = int(port_text.replace("Port ", "").strip())
                    except ValueError:
                        continue
                elif port_text.startswith("Trunk"):
                    iface_key = port_text.replace(" ", "")
                else:
                    continue

                link_status = cols[2].get_text(strip=True)

                def parse_bigint(text_content):
                    if "-" in text_content:
                        parts = text_content.split("-")
                        try:
                            return (int(parts[0]) * 4294967296) + int(parts[1])
                        except ValueError:
                            return 0
                    try:
                        return int(text_content)
                    except ValueError:
                        return 0

                def parse_int(text_content):
                    try:
                        return int(text_content)
                    except ValueError:
                        return 0

                data["interfaces"][iface_key] = {
                    "is_link_up": "Link Up" in link_status,
                    "tx_packets": parse_bigint(cols[3].get_text(strip=True)),
                    "tx_errors": parse_int(cols[4].get_text(strip=True)),
                    "rx_packets": parse_bigint(cols[5].get_text(strip=True)),
                    "rx_errors": parse_int(cols[6].get_text(strip=True)),
                }
        return data

    # -------------------------------------------------------------------------
    # ACTIONS (Sending commands to the switch)
    # -------------------------------------------------------------------------

    async def async_set_poe_state(self, port_num, state):
        """Send command to toggle PoE power for a specific physical port."""
        port_id = int(port_num) - 1
        state_val = "1" if state else "0"

        url = f"http://{self.host}/{ENDPOINT_PSE_PORT}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PSE_PORT}",
            "User-Agent": "HomeAssistant/1.0",
        }
        cookies = {"admin": self.auth_cookie}

        payload = {
            "portid": port_id,
            "state": state_val,
            "submit": "Apply",
            "cmd": "poe",
        }

        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            self.last_poe_update = 0
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set PoE state for port {port_num}: {err}")

    async def async_set_port_settings(self, iface_key, state=None, speed_val=None, flow=None):
        """Send command to update Admin State, Flow Control, and Speed/Duplex for a Port or Trunk."""
        current = self.data.get("interfaces", {}).get(iface_key)
        if not current:
            _LOGGER.warning(
                f"Interface {iface_key} is currently inactive or part of a Trunk Group and cannot be configured directly."
            )
            return

        # Use parsed form portid (0..8 for Port 1..9, 10 for Trunk1, 11 for Trunk2)
        port_id = current.get("portid")
        if port_id is None:
            port_id = (
                str(iface_key - 1)
                if isinstance(iface_key, int)
                else ("10" if iface_key == "Trunk1" else "11")
            )

        new_state = "1" if (state if state is not None else current.get("admin_state", True)) else "0"
        new_flow = "1" if (flow if flow is not None else current.get("config_flow", False)) else "0"

        if speed_val is None:
            speed_map = {
                "Auto": "0",
                "10M Half": "1",
                "10 Half": "1",
                "10M Full": "2",
                "10 Full": "2",
                "100M Half": "3",
                "100 Half": "3",
                "100M Full": "4",
                "100 Full": "4",
                "1000M Full": "5",
                "1000Full": "5",
                "1G Full": "5",
                "2500M Full": "6",
                "2.5G Full": "6",
                "10G Full": "8",
            }
            new_speed = speed_map.get(current.get("config_speed", "Auto"), "0")
        else:
            new_speed = str(speed_val)

        url = f"http://{self.host}/{ENDPOINT_PORT_SETTINGS}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PORT_SETTINGS}",
            "User-Agent": "HomeAssistant/1.0",
        }
        cookies = {"admin": self.auth_cookie}

        payload = {
            "portid": port_id,
            "state": new_state,
            "speed_duplex": new_speed,
            "flow": new_flow,
            "submit": "   Apply   ",
            "cmd": "port",
        }

        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            self.last_general_update = 0
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set port settings for {iface_key}: {err}")

    async def async_clear_port_stats(self):
        """Send command to clear Tx/Rx traffic statistics."""
        url = f"http://{self.host}/{ENDPOINT_PORT_STATS}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PORT_STATS}",
            "User-Agent": "HomeAssistant/1.0",
        }
        cookies = {"admin": self.auth_cookie}

        payload = {
            "submit": "   Clear   ",
            "cmd": "stats",
        }

        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            self.last_general_update = 0
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to clear statistics: {err}")

    async def async_reboot_switch(self):
        """Send command to Reboot the switch hardware."""
        url = f"http://{self.host}/reboot.cgi"
        headers = {
            "Referer": url,
            "User-Agent": "HomeAssistant/1.0",
        }
        cookies = {"admin": self.auth_cookie}

        payload = {
            "cmd": "reboot",
        }

        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            _LOGGER.info(f"Reboot command sent to Keeplink Switch ({self.host})")
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to send reboot command: {err}")
"""DataUpdateCoordinator for Keeplink Switch."""
import logging
import hashlib
import aiohttp
import async_timeout
from bs4 import BeautifulSoup
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from homeassistant.exceptions import ConfigEntryAuthFailed

from .const import (
    DOMAIN, 
    ENDPOINT_INFO, 
    ENDPOINT_PSE_SYSTEM, 
    ENDPOINT_PSE_PORT,
    ENDPOINT_PORT_SETTINGS,
    ENDPOINT_PORT_STATS
)

_LOGGER = logging.getLogger(__name__)

class KeeplinkCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the switch."""

    def __init__(self, hass, session, host, username, password, scan_interval):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password
        self.session = session
        self.mac_address = None
        self.device_info = {}

        # Auth Hash Calculation
        auth_str = f"{username}{password}"
        self.auth_cookie = hashlib.md5(auth_str.encode()).hexdigest()

        super().__init__(
            hass,
            _LOGGER,
            name=f"Keeplink Switch ({host})",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoints."""
        data = {"ports": {}}
        headers = {
            "Referer": f"http://{self.host}/login.cgi",
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}

        try:
            async with async_timeout.timeout(20):
                # 1. Info and PoE System
                data.update(await self._fetch_page(ENDPOINT_INFO, headers, cookies, self._parse_info))
                
                poe_sys_data = await self._fetch_page(ENDPOINT_PSE_SYSTEM, headers, cookies, self._parse_pse_system)
                data.update(poe_sys_data)

                # 2. PoE Port Data (FIXED KEYS HERE)
                poe_port_data = await self._fetch_page(ENDPOINT_PSE_PORT, headers, cookies, self._parse_pse_port)
                self._deep_merge_ports(data, poe_port_data)

                # 3. Port Settings (Speed/Duplex)
                settings_data = await self._fetch_page(ENDPOINT_PORT_SETTINGS, headers, cookies, self._parse_port_settings)
                self._deep_merge_ports(data, settings_data)

                # 4. Port Stats (Link/Traffic)
                stats_data = await self._fetch_page(ENDPOINT_PORT_STATS, headers, cookies, self._parse_port_stats)
                self._deep_merge_ports(data, stats_data)

                # Update Device Info
                if "mac" in data:
                    self.mac_address = data["mac"]
                    self.device_info = {
                        "manufacturer": "Keeplink",
                        "model": data.get("model", "Unknown Model"),
                        "sw_version": data.get("firmware", "Unknown"),
                        "hw_version": data.get("hardware", "Unknown"),
                    }
            
            return data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    def _deep_merge_ports(self, main_data, new_data):
        """Helper to merge port data."""
        if "ports" not in main_data:
            main_data["ports"] = {}
            
        if "ports" in new_data:
            for port, info in new_data["ports"].items():
                if port not in main_data["ports"]:
                    main_data["ports"][port] = {}
                main_data["ports"][port].update(info)

    async def _fetch_page(self, endpoint, headers, cookies, parser_func):
        """Helper to fetch and parse a single page."""
        url = f"http://{self.host}/{endpoint}"
        response = await self.session.get(url, headers=headers, cookies=cookies)
        if "login.cgi" in str(response.url): raise ConfigEntryAuthFailed("Authentication failed.")
        html = await response.text()
        return parser_func(html)

    # --- PARSERS ---

    def _parse_info(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all(['th', 'td'])
            if len(cols) == 2:
                key = cols[0].get_text(strip=True)
                value = cols[1].get_text(strip=True)
                if "Device Model" in key: data["model"] = value
                elif "Firmware Version" in key: data["firmware"] = value
                elif "MAC Address" in key: data["mac"] = value
                elif "Hardware Version" in key: data["hardware"] = value
                elif "IP Address" in key: data["ip_address"] = value
                elif "Netmask" in key: data["netmask"] = value
                elif "Gateway" in key: data["gateway"] = value
                elif "Firmware Date" in key: data["firmware_date"] = value
        return data

    def _parse_pse_system(self, html):
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        input_tag = soup.find('input', {'name': 'pse_con_pwr'})
        if input_tag and input_tag.get('value'):
            try:
                data["poe_total_power"] = float(input_tag['value'])
            except ValueError:
                pass
        return data

    def _parse_pse_port(self, html):
        """Parse pse_port.cgi"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}} 
        tables = soup.find_all('table')
        if len(tables) < 2: return data
        data_table = tables[1]
        rows = data_table.find_all('tr')
        for row in rows[1:]:
            cols = row.find_all('td')
            if len(cols) >= 7:
                port_name = cols[0].get_text(strip=True)
                try:
                    port_num = int(port_name.replace("Port ", ""))
                except ValueError: continue
                
                def parse_val(text): return float(text) if text != "-" else 0.0
                
                # FIX: Using simple keys 'power', 'voltage', 'current', 'enabled'
                data["ports"][port_num] = {
                    "power": parse_val(cols[4].get_text(strip=True)),
                    "voltage": parse_val(cols[5].get_text(strip=True)),
                    "current": parse_val(cols[6].get_text(strip=True)),
                    "enabled": "Enable" in cols[1].get_text(strip=True)
                }
        return data

    def _parse_port_settings(self, html):
        """Parse port.cgi"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}}
        tables = soup.find_all('table')
        if not tables: return data
        target_table = tables[-1]
        rows = target_table.find_all('tr')
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                port_text = cols[0].get_text(strip=True)
                if "Port" not in port_text: continue
                try: port_num = int(port_text.replace("Port ", ""))
                except ValueError: continue

                # Extract the Configured and Actual states
                admin_state = cols[1].get_text(strip=True)
                config_speed = cols[2].get_text(strip=True)
                actual_speed = cols[3].get_text(strip=True)
                config_flow = cols[4].get_text(strip=True)
                actual_flow = cols[5].get_text(strip=True)

                data["ports"][port_num] = {
                    "admin_state": admin_state == "Enable",
                    "config_speed": config_speed,
                    "speed": actual_speed,
                    "config_flow": config_flow == "On",
                    "flow_control": actual_flow
                }
        return data

    async def async_set_port_settings(self, port_num, state=None, speed_val=None, flow=None):
        """Send command to update Port Settings."""
        port_id = port_num - 1
        
        # Get current settings to fill missing fields in the payload
        current = self.data.get("ports", {}).get(port_num, {})
        
        # 1. Resolve State
        if state is None:
            new_state = "1" if current.get("admin_state", True) else "0"
        else:
            new_state = "1" if state else "0"
            
        # 2. Resolve Flow Control
        if flow is None:
            new_flow = "1" if current.get("config_flow", False) else "0"
        else:
            new_flow = "1" if flow else "0"
            
        # 3. Resolve Speed (Convert HTML text back to numeric value)
        if speed_val is None:
            speed_map = {
                "Auto": "0", "10M Half": "1", "10M Full": "2", 
                "100M Half": "3", "100M Full": "4", "1000M Full": "5", "1G Full": "5",
                "2500M Full": "6", "2.5G Full": "6", "10G Full": "8"
            }
            curr_cfg = current.get("config_speed", "Auto")
            new_speed = speed_map.get(curr_cfg, "0")
        else:
            new_speed = str(speed_val)

        url = f"http://{self.host}/{ENDPOINT_PORT_SETTINGS}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PORT_SETTINGS}",
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        # Full payload expected by the switch
        payload = {
            "portid": port_id,
            "state": new_state,
            "speed_duplex": new_speed,
            "flow": new_flow,
            "submit": "   Apply   ",
            "cmd": "port"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set port settings: {err}")

    def _parse_port_stats(self, html):
        """Parse port.cgi?page=stats"""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}}
        tables = soup.find_all('table')
        if not tables: return data
        target_table = tables[0]
        rows = target_table.find_all('tr')
        for row in rows:
            cols = row.find_all(['td'])
            if len(cols) >= 7:
                port_text = cols[0].get_text(strip=True)
                if "Port" not in port_text: continue
                try: port_num = int(port_text.replace("Port ", ""))
                except ValueError: continue

                link_status = cols[2].get_text(strip=True)
                
                def parse_bigint(text_content):
                    if "-" in text_content:
                        parts = text_content.split("-")
                        try:
                            high = int(parts[0])
                            low = int(parts[1])
                            return (high * 4294967296) + low
                        except ValueError: return 0
                    return 0

                data["ports"][port_num] = {
                    "is_link_up": "Link Up" in link_status,
                    "tx_packets": parse_bigint(cols[3].get_text(strip=True)),
                    "rx_packets": parse_bigint(cols[5].get_text(strip=True)),
                    "tx_errors": int(cols[4].get_text(strip=True)),
                    "rx_errors": int(cols[6].get_text(strip=True))
                }
        return data
    
    async def async_clear_port_stats(self):
        """Send command to Clear Port Statistics."""
        # The form action is port.cgi?page=stats
        url = f"http://{self.host}/{ENDPOINT_PORT_STATS}"
        
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PORT_STATS}",
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        # Payload observed: submit=+++Clear+++&cmd=stats
        # In Python, we use the actual string "   Clear   " and let the library encode the spaces to +
        payload = {
            "submit": "   Clear   ", 
            "cmd": "stats"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            # Force immediate refresh so the sensors go back to 0 immediately
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to clear statistics: {err}")

    async def async_reboot_switch(self):
        """Send command to Reboot the switch."""
        url = f"http://{self.host}/reboot.cgi"
        
        headers = {
            "Referer": url,
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        # Expected Payload from the HTML form
        payload = {
            "cmd": "reboot"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            _LOGGER.info(f"Reboot command sent to Keeplink Switch ({self.host})")
            
            # We don't force a data refresh here because the switch is going offline!
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to send reboot command: {err}")

    async def async_set_poe_state(self, port_num, state):
        """Set PoE State."""
        port_id = port_num - 1 
        state_val = "1" if state else "0"
        url = f"http://{self.host}/{ENDPOINT_PSE_PORT}"
        headers = {"Referer": f"http://{self.host}/{ENDPOINT_PSE_PORT}", "User-Agent": "HomeAssistant/1.0"}
        cookies = {"admin": self.auth_cookie}
        payload = {"portid": port_id, "state": state_val, "submit": "Apply", "cmd": "poe"}
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set PoE state for port {port_num}: {err}")

    
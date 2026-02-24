"""DataUpdateCoordinator for Keeplink Switch."""
import logging
import hashlib
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
        
        # Load existing data so we don't overwrite attributes we aren't fetching this cycle
        data = copy.deepcopy(self.data) if self.data else {"ports": {}}

        # Check if we need to update General Data / PoE Data (added a 2s buffer for execution variance)
        update_general = (current_time - self.last_general_update) >= (self.scan_interval - 2)
        update_poe = (current_time - self.last_poe_update) >= (self.poe_scan_interval - 2)

        headers = {
            "Referer": f"http://{self.host}/login.cgi",
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}

        try:
            async with async_timeout.timeout(30):
                
                # --- POE DATA FETCH ---
                if update_poe:
                    _LOGGER.debug(f"Fetching PoE Data for {self.host}")
                    
                    # 1. Fetch Total System PoE Power
                    poe_sys_data = await self._fetch_page(ENDPOINT_PSE_SYSTEM, headers, cookies, self._parse_pse_system)
                    data.update(poe_sys_data)

                    # 2. Fetch Per-Port PoE Data
                    poe_port_data = await self._fetch_page(ENDPOINT_PSE_PORT, headers, cookies, self._parse_pse_port)
                    self._deep_merge_ports(data, poe_port_data)
                    
                    # Update our timer
                    self.last_poe_update = current_time

                # --- GENERAL DATA FETCH ---
                if update_general:
                    _LOGGER.debug(f"Fetching General Data for {self.host}")
                    
                    # 1. Fetch System Info (Firmware, MAC, IP, etc.)
                    data.update(await self._fetch_page(ENDPOINT_INFO, headers, cookies, self._parse_info))
                    
                    # 2. Fetch Port Settings (Speed/Duplex/Flow Control)
                    settings_data = await self._fetch_page(ENDPOINT_PORT_SETTINGS, headers, cookies, self._parse_port_settings)
                    self._deep_merge_ports(data, settings_data)

                    # 3. Fetch Port Stats (Link Status, Tx/Rx Packets, Errors)
                    stats_data = await self._fetch_page(ENDPOINT_PORT_STATS, headers, cookies, self._parse_port_stats)
                    self._deep_merge_ports(data, stats_data)
                    
                    # Update our timer
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
            
            return data

        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with API: {err}")

    def _deep_merge_ports(self, main_data, new_data):
        """Safely merges new port attributes without erasing existing ones."""
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
        
        if "login.cgi" in str(response.url): 
            raise ConfigEntryAuthFailed("Authentication failed.")
            
        html = await response.text()
        return parser_func(html)

    # -------------------------------------------------------------------------
    # PARSERS (Reading data from the switch)
    # -------------------------------------------------------------------------

    def _parse_info(self, html):
        """Parse System Info (info.cgi)."""
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
        """Parse Total PoE Power (pse_system.cgi)."""
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
        """Parse Per-Port PoE Data (pse_port.cgi)."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}} 
        tables = soup.find_all('table')
        if len(tables) < 2: 
            return data
            
        data_table = tables[1]
        rows = data_table.find_all('tr')
        
        for row in rows[1:]:
            cols = row.find_all('td')
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
                    "enabled": "Enable" in cols[1].get_text(strip=True)
                }
        return data

    def _parse_port_settings(self, html):
        """Parse Port Settings like Speed and Flow Control (port.cgi)."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}}
        tables = soup.find_all('table')
        if not tables: 
            return data
            
        target_table = tables[-1]
        rows = target_table.find_all('tr')
        
        for row in rows:
            cols = row.find_all('td')
            if len(cols) >= 6:
                port_text = cols[0].get_text(strip=True)
                if "Port" not in port_text: 
                    continue
                try: 
                    port_num = int(port_text.replace("Port ", ""))
                except ValueError: 
                    continue

                data["ports"][port_num] = {
                    "admin_state": cols[1].get_text(strip=True) == "Enable",
                    "config_speed": cols[2].get_text(strip=True),
                    "speed": cols[3].get_text(strip=True),
                    "config_flow": cols[4].get_text(strip=True) == "On",
                    "flow_control": cols[5].get_text(strip=True)
                }
        return data

    def _parse_port_stats(self, html):
        """Parse Link Status and Traffic Counters (port.cgi?page=stats)."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}}
        tables = soup.find_all('table')
        if not tables: 
            return data
            
        target_table = tables[0]
        rows = target_table.find_all('tr')
        
        for row in rows:
            cols = row.find_all(['td'])
            if len(cols) >= 7:
                port_text = cols[0].get_text(strip=True)
                if "Port" not in port_text: 
                    continue
                try: 
                    port_num = int(port_text.replace("Port ", ""))
                except ValueError: 
                    continue

                link_status = cols[2].get_text(strip=True)
                
                # Math conversion for 64-bit integer values displayed in HTML
                def parse_bigint(text_content):
                    if "-" in text_content:
                        parts = text_content.split("-")
                        try: 
                            return (int(parts[0]) * 4294967296) + int(parts[1])
                        except ValueError: 
                            return 0
                    return 0

                data["ports"][port_num] = {
                    "is_link_up": "Link Up" in link_status,
                    "tx_packets": parse_bigint(cols[3].get_text(strip=True)),
                    "rx_packets": parse_bigint(cols[5].get_text(strip=True)),
                    "tx_errors": int(cols[4].get_text(strip=True)),
                    "rx_errors": int(cols[6].get_text(strip=True))
                }
        return data

    # -------------------------------------------------------------------------
    # ACTIONS (Sending commands to the switch)
    # -------------------------------------------------------------------------

    async def async_set_poe_state(self, port_num, state):
        """Send command to toggle PoE power for a specific port."""
        port_id = port_num - 1 
        state_val = "1" if state else "0"
        
        url = f"http://{self.host}/{ENDPOINT_PSE_PORT}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PSE_PORT}", 
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        payload = {
            "portid": port_id, 
            "state": state_val, 
            "submit": "Apply", 
            "cmd": "poe"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            # Force immediate PoE refresh so the UI updates instantly
            self.last_poe_update = 0 
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set PoE state for port {port_num}: {err}")

    async def async_set_port_settings(self, port_num, state=None, speed_val=None, flow=None):
        """Send command to update Admin State, Flow Control, and Speed/Duplex."""
        port_id = port_num - 1
        
        # Pull current config to fill in the blanks
        current = self.data.get("ports", {}).get(port_num, {})
        
        # Resolve State
        new_state = "1" if (state if state is not None else current.get("admin_state", True)) else "0"
        
        # Resolve Flow Control
        new_flow = "1" if (flow if flow is not None else current.get("config_flow", False)) else "0"
            
        # Resolve Speed
        if speed_val is None:
            speed_map = {
                "Auto": "0", "10M Half": "1", "10M Full": "2", "100M Half": "3", 
                "100M Full": "4", "1000M Full": "5", "1G Full": "5", 
                "2500M Full": "6", "2.5G Full": "6", "10G Full": "8"
            }
            new_speed = speed_map.get(current.get("config_speed", "Auto"), "0")
        else:
            new_speed = str(speed_val)

        url = f"http://{self.host}/{ENDPOINT_PORT_SETTINGS}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PORT_SETTINGS}", 
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
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
            # Force immediate General refresh so the UI updates instantly
            self.last_general_update = 0 
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set port settings: {err}")

    async def async_clear_port_stats(self):
        """Send command to clear Tx/Rx traffic statistics."""
        url = f"http://{self.host}/{ENDPOINT_PORT_STATS}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PORT_STATS}", 
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        payload = {
            "submit": "   Clear   ", 
            "cmd": "stats"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            # Force immediate General refresh to show 0 packets
            self.last_general_update = 0 
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to clear statistics: {err}")

    async def async_reboot_switch(self):
        """Send command to Reboot the switch hardware."""
        url = f"http://{self.host}/reboot.cgi"
        headers = {
            "Referer": url, 
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        payload = {
            "cmd": "reboot"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            _LOGGER.info(f"Reboot command sent to Keeplink Switch ({self.host})")
            # We explicitly DO NOT refresh data here because the switch is offline
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to send reboot command: {err}")
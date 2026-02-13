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

from .const import DOMAIN, ENDPOINT_INFO, ENDPOINT_PSE_SYSTEM, ENDPOINT_PSE_PORT

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
        data = {}
        headers = {
            "Referer": f"http://{self.host}/login.cgi",
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}

        try:
            async with async_timeout.timeout(20): # Increased timeout for multiple requests
                # 1. Fetch System Info
                data.update(await self._fetch_page(ENDPOINT_INFO, headers, cookies, self._parse_info))
                
                # 2. Fetch Total PoE Consumption
                data.update(await self._fetch_page(ENDPOINT_PSE_SYSTEM, headers, cookies, self._parse_pse_system))
                
                # 3. Fetch Port PoE Data
                data.update(await self._fetch_page(ENDPOINT_PSE_PORT, headers, cookies, self._parse_pse_port))

                # Update Device Info if MAC is found
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

    async def _fetch_page(self, endpoint, headers, cookies, parser_func):
        """Helper to fetch and parse a single page."""
        url = f"http://{self.host}/{endpoint}"
        response = await self.session.get(url, headers=headers, cookies=cookies)
        
        if "login.cgi" in str(response.url):
             raise ConfigEntryAuthFailed("Authentication failed.")
        
        html = await response.text()
        return parser_func(html)

    def _parse_info(self, html):
        """Parse info.cgi."""
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
        """Parse pse_system.cgi for Total Power."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        # The value is in an input tag: <input name="pse_con_pwr" value="9.435">
        input_tag = soup.find('input', {'name': 'pse_con_pwr'})
        if input_tag and input_tag.get('value'):
            try:
                data["poe_total_power"] = float(input_tag['value'])
            except ValueError:
                pass
        return data

    def _parse_pse_port(self, html):
        """Parse pse_port.cgi for Per-Port Data."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {"ports": {}} 
        
        # Find the second table (the one with data, not the form)
        tables = soup.find_all('table')
        if len(tables) < 2:
            return data
            
        data_table = tables[1] # The second table has the port list
        rows = data_table.find_all('tr')
        
        # Skip header row
        for row in rows[1:]:
            cols = row.find_all('td')
            # Columns: 0=PortName, 1=State(Enable/Disable), 2=PowerOn/Off, 3=Type, 4=Power(W), 5=Volt(V), 6=Current(mA)
            if len(cols) >= 7:
                port_name = cols[0].get_text(strip=True) # "Port 1"
                try:
                    port_num = int(port_name.replace("Port ", ""))
                except ValueError:
                    continue
                
                # Parse Values (handle "-" for off ports)
                def parse_val(text):
                    return float(text) if text != "-" else 0.0

                power_w = parse_val(cols[4].get_text(strip=True))
                voltage_v = parse_val(cols[5].get_text(strip=True))
                current_ma = parse_val(cols[6].get_text(strip=True))
                state_enabled = "Enable" in cols[1].get_text(strip=True)
                
                data["ports"][port_num] = {
                    "power": power_w,
                    "voltage": voltage_v,
                    "current": current_ma,
                    "enabled": state_enabled
                }
        return data

    async def async_set_poe_state(self, port_num, state):
        """Send POST request to enable/disable PoE."""
        # Port 1 is ID 0, Port 2 is ID 1, etc.
        port_id = port_num - 1 
        state_val = "1" if state else "0"
        
        url = f"http://{self.host}/{ENDPOINT_PSE_PORT}"
        headers = {
            "Referer": f"http://{self.host}/{ENDPOINT_PSE_PORT}", # Important!
            "User-Agent": "HomeAssistant/1.0"
        }
        cookies = {"admin": self.auth_cookie}
        
        # Payload: portid=3&state=0&submit=Apply&cmd=poe
        payload = {
            "portid": port_id,
            "state": state_val,
            "submit": "Apply",
            "cmd": "poe"
        }
        
        try:
            await self.session.post(url, headers=headers, cookies=cookies, data=payload)
            # Force immediate refresh after change
            await self.async_request_refresh()
        except aiohttp.ClientError as err:
            _LOGGER.error(f"Failed to set PoE state for port {port_num}: {err}")
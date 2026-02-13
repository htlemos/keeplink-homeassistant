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

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class KeeplinkCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the switch."""

    def __init__(self, hass, session, host, username, password):
        """Initialize."""
        self.host = host
        self.username = username
        self.password = password
        self.session = session
        self.mac_address = None # Store MAC specifically for device ID
        self.device_info = {}   # Store static info for the registry

        # Calculate Auth Hash
        auth_str = f"{username}{password}"
        self.auth_cookie = hashlib.md5(auth_str.encode()).hexdigest()

        super().__init__(
            hass,
            _LOGGER,
            name=f"Keeplink Switch ({host})",
            update_interval=timedelta(seconds=60),
        )

    async def _async_update_data(self):
        """Fetch data from API endpoint."""
        try:
            url = f"http://{self.host}/info.cgi"
            headers = {
                "Referer": f"http://{self.host}/login.cgi",
                "User-Agent": "HomeAssistant/1.0"
            }
            cookies = {"admin": self.auth_cookie}

            async with async_timeout.timeout(10):
                response = await self.session.get(url, headers=headers, cookies=cookies)
                
                if "login.cgi" in str(response.url):
                     raise ConfigEntryAuthFailed("Authentication failed.")
                
                html = await response.text()
                
            data = self._parse_data(html)
            
            # Save MAC and Info for Device Registry
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

    def _parse_data(self, html):
        """Parse HTML."""
        soup = BeautifulSoup(html, 'html.parser')
        data = {}
        rows = soup.find_all('tr')
        for row in rows:
            cols = row.find_all(['th', 'td'])
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
        return data
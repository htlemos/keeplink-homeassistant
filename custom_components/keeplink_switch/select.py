"""Select platform for Keeplink Switch."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch selects."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    selects = []
    if "ports" in coordinator.data:
        for port_num in coordinator.data["ports"]:
            selects.append(KeeplinkPortSpeedSelect(coordinator, port_num))

    async_add_entities(selects)

class KeeplinkPortSpeedSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Port Speed/Duplex Select."""

    def __init__(self, coordinator, port_num):
        """Initialize the select."""
        super().__init__(coordinator)
        self.port_num = port_num
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_speed_select"
        self._attr_name = f"Keeplink Port {port_num} Speed"
        self._attr_icon = "mdi:transit-connection-variant"
        
        # Dynamically set options based on Port type (Port 9 is SFP+)
        if port_num == 9:
            self._attr_options = ["Auto", "100M/Full", "1000M/Full", "2500M/Full", "10G/Full"]
        else:
            self._attr_options = ["Auto", "10M/Half", "10M/Full", "100M/Half", "100M/Full", "1000M/Full", "2500M/Full"]

        # Map UI dropdown strings to payload integers
        self._val_map = {
            "Auto": 0, 
            "10M/Half": 1, 
            "10M/Full": 2, 
            "100M/Half": 3, 
            "100M/Full": 4, 
            "1000M/Full": 5, 
            "2500M/Full": 6, 
            "10G/Full": 8
        }
        
        # Map HTML text strings from the switch to our UI dropdown strings
        self._html_map = {
            "Auto": "Auto",
            "10 Half": "10M/Half", 
            "10 Full": "10M/Full",
            "100 Half": "100M/Half", 
            "100 Full": "100M/Full",
            "1000Full": "1000M/Full",
            "2.5G Full": "2500M/Full",
            "10G Full": "10G/Full"
        }

    @property
    def current_option(self):
        """Return the current selected option."""
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num, {})
        cfg_speed = port_data.get("config_speed", "Auto")
        
        # Translate HTML string to UI String. Default to "Auto" if not found.
        return self._html_map.get(cfg_speed, "Auto")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        speed_val = self._val_map[option]
        await self.coordinator.async_set_port_settings(self.port_num, speed_val=speed_val)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})
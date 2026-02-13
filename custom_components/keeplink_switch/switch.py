"""Switch platform for Keeplink Switch PoE Control."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    switches = []
    if "ports" in coordinator.data:
        for port_num, port_data in coordinator.data["ports"].items():
            # FIX: Only create PoE Switch if the port supports PoE (has 'enabled' state)
            if "enabled" in port_data:
                switches.append(KeeplinkPoESwitch(coordinator, port_num))

    async_add_entities(switches)

class KeeplinkPoESwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Port PoE Switch."""

    def __init__(self, coordinator, port_num):
        """Initialize the switch."""
        super().__init__(coordinator)
        self.port_num = port_num
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_poe_switch"
        self._attr_name = f"Keeplink Port {port_num} PoE"
        self._attr_icon = "mdi:ethernet"

    @property
    def is_on(self):
        """Return true if switch is on."""
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num)
        if port_data:
            return port_data.get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        """Turn the switch on."""
        await self.coordinator.async_set_poe_state(self.port_num, True)

    async def async_turn_off(self, **kwargs):
        """Turn the switch off."""
        await self.coordinator.async_set_poe_state(self.port_num, False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
        )
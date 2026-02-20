"""Switch platform for Keeplink Switch."""
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
            
            # 1. Admin State Switch (Applies to all ports)
            switches.append(KeeplinkPortAdminSwitch(coordinator, port_num))
            
            # 2. Flow Control Switch (Applies to all ports)
            switches.append(KeeplinkPortFlowSwitch(coordinator, port_num))
            
            # 3. PoE Switch (Only for ports that have PoE data)
            if "enabled" in port_data:
                switches.append(KeeplinkPoESwitch(coordinator, port_num))

    async_add_entities(switches)

# ... (Keep your existing KeeplinkPoESwitch class here) ...

class KeeplinkPortAdminSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Port Admin State Switch."""
    def __init__(self, coordinator, port_num):
        super().__init__(coordinator)
        self.port_num = port_num
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_admin_state"
        self._attr_name = f"Keeplink Port {port_num} State"
        self._attr_icon = "mdi:network-port"

    @property
    def is_on(self):
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num, {})
        return port_data.get("admin_state", True)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.port_num, state=True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.port_num, state=False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})

class KeeplinkPortFlowSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Port Flow Control Switch."""
    def __init__(self, coordinator, port_num):
        super().__init__(coordinator)
        self.port_num = port_num
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_flow_control"
        self._attr_name = f"Keeplink Port {port_num} Flow Control"
        self._attr_icon = "mdi:sync"

    @property
    def is_on(self):
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num, {})
        return port_data.get("config_flow", False)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.port_num, flow=True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.port_num, flow=False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})
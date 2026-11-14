"""Switch platform for Keeplink Switch."""
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch switches."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    switches = []
    # 1. Physical Ports (1..9)
    if "ports" in coordinator.data:
        for port_num, port_data in sorted(coordinator.data["ports"].items()):
            # Admin State & Flow Control (Automatically disabled/unavailable when port is inside a Trunk)
            switches.append(KeeplinkPortAdminSwitch(coordinator, port_num))
            switches.append(KeeplinkPortFlowSwitch(coordinator, port_num))

            # PoE Switch (Strictly Physical - Remains active even when port is inside a Trunk!)
            if "enabled" in port_data:
                switches.append(KeeplinkPoESwitch(coordinator, port_num))

    # 2. Logical Trunk Groups (Trunk1, Trunk2)
    for trunk_id in ["Trunk1", "Trunk2"]:
        switches.append(KeeplinkPortAdminSwitch(coordinator, trunk_id))
        switches.append(KeeplinkPortFlowSwitch(coordinator, trunk_id))

    async_add_entities(switches)


class KeeplinkPoESwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Physical Port PoE Switch."""

    def __init__(self, coordinator, port_num):
        super().__init__(coordinator)
        self.port_num = port_num
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_poe_switch"
        self._attr_name = f"Keeplink Port {port_num} PoE"
        self._attr_icon = "mdi:ethernet"

    @property
    def is_on(self):
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num)
        if port_data:
            return port_data.get("enabled", False)
        return False

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_poe_state(self.port_num, True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_poe_state(self.port_num, False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})


class KeeplinkPortAdminSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Port or Trunk Admin State Switch."""

    def __init__(self, coordinator, iface_key):
        super().__init__(coordinator)
        self.iface_key = iface_key
        if isinstance(iface_key, str) and iface_key.startswith("Trunk"):
            clean_name = iface_key.replace("Trunk", "Trunk ")
            uid_prefix = iface_key.lower()
        else:
            clean_name = f"Port {iface_key}"
            uid_prefix = f"port{iface_key}"

        self._attr_unique_id = f"{coordinator.mac_address}_{uid_prefix}_admin_state"
        self._attr_name = f"Keeplink {clean_name} State"
        self._attr_icon = "mdi:network-port"

    @property
    def available(self) -> bool:
        """Mark unavailable if physical port is absorbed into a Trunk or Trunk is inactive."""
        if not super().available:
            return False
        return self.iface_key in self.coordinator.data.get("interfaces", {})

    @property
    def is_on(self):
        iface_data = self.coordinator.data.get("interfaces", {}).get(self.iface_key, {})
        return iface_data.get("admin_state", True)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.iface_key, state=True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.iface_key, state=False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})


class KeeplinkPortFlowSwitch(CoordinatorEntity, SwitchEntity):
    """Representation of a Port or Trunk Flow Control Switch."""

    def __init__(self, coordinator, iface_key):
        super().__init__(coordinator)
        self.iface_key = iface_key
        if isinstance(iface_key, str) and iface_key.startswith("Trunk"):
            clean_name = iface_key.replace("Trunk", "Trunk ")
            uid_prefix = iface_key.lower()
        else:
            clean_name = f"Port {iface_key}"
            uid_prefix = f"port{iface_key}"

        self._attr_unique_id = f"{coordinator.mac_address}_{uid_prefix}_flow_control"
        self._attr_name = f"Keeplink {clean_name} Flow Control"
        self._attr_icon = "mdi:sync"

    @property
    def available(self) -> bool:
        """Mark unavailable if physical port is absorbed into a Trunk or Trunk is inactive."""
        if not super().available:
            return False
        return self.iface_key in self.coordinator.data.get("interfaces", {})

    @property
    def is_on(self):
        iface_data = self.coordinator.data.get("interfaces", {}).get(self.iface_key, {})
        return iface_data.get("config_flow", False)

    async def async_turn_on(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.iface_key, flow=True)

    async def async_turn_off(self, **kwargs):
        await self.coordinator.async_set_port_settings(self.iface_key, flow=False)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})
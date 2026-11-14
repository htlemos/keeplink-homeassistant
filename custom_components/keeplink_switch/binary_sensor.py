"""Binary sensor platform for Keeplink Switch Ports and Trunks."""
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    sensors = []
    # 1. Physical Port Link Binary Sensors (Ports 1..9 via panel.cgi)
    if "ports" in coordinator.data:
        for port_num in sorted(coordinator.data["ports"].keys()):
            sensors.append(KeeplinkPortBinarySensor(coordinator, port_num))

    # 2. Logical Trunk Link Binary Sensors (Trunk1 and Trunk2)
    for trunk_id in ["Trunk1", "Trunk2"]:
        sensors.append(KeeplinkTrunkBinarySensor(coordinator, trunk_id))

    async_add_entities(sensors)


class KeeplinkPortBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Physical Port Link Status (Works even when inside a Trunk)."""

    def __init__(self, coordinator, port_num):
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self.port_num = port_num
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_link"
        self._attr_name = f"Keeplink Port {port_num} Link"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:ethernet-cable"

    @property
    def is_on(self):
        """Return true if the physical port link is up (from panel.cgi)."""
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num)
        if port_data:
            return port_data.get("is_link_up", False)
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num, {})
        trunk_group = port_data.get("trunk_group")

        attributes = {
            "trunk_group": trunk_group if trunk_group else "None",
        }

        if trunk_group:
            # Port is aggregated in a Trunk; pull logical speed from the Trunk interface
            trunk_iface = self.coordinator.data.get("interfaces", {}).get(trunk_group, {})
            attributes["speed"] = f"Aggregated ({trunk_group}: {trunk_iface.get('speed', 'Unknown')})"
            attributes["flow_control"] = trunk_iface.get("flow_control", "Unknown")
        else:
            attributes["speed"] = port_data.get("speed", "Unknown")
            attributes["flow_control"] = port_data.get("flow_control", "Unknown")
            attributes["tx_packets"] = port_data.get("tx_packets", 0)
            attributes["rx_packets"] = port_data.get("rx_packets", 0)
            attributes["tx_errors"] = port_data.get("tx_errors", 0)
            attributes["rx_errors"] = port_data.get("rx_errors", 0)

        if "power" in port_data:
            attributes["poe_power_w"] = port_data["power"]
            attributes["poe_voltage_v"] = port_data["voltage"]
            attributes["poe_current_ma"] = port_data["current"]

        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
        )


class KeeplinkTrunkBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Logical Trunk Group Link & Traffic Status."""

    def __init__(self, coordinator, trunk_id):
        """Initialize the trunk binary sensor."""
        super().__init__(coordinator)
        self.trunk_id = trunk_id
        clean_name = trunk_id.replace("Trunk", "Trunk ")
        self._attr_unique_id = f"{coordinator.mac_address}_{trunk_id.lower()}_link"
        self._attr_name = f"Keeplink {clean_name} Link"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:lan"

    @property
    def available(self) -> bool:
        """Return True if coordinator is available and this Trunk Group is configured."""
        if not super().available:
            return False
        trunk_info = self.coordinator.data.get("trunks", {}).get(self.trunk_id, {})
        return trunk_info.get("active", False)

    @property
    def is_on(self):
        """Return true if the trunk link is up."""
        iface_data = self.coordinator.data.get("interfaces", {}).get(self.trunk_id)
        if iface_data:
            return iface_data.get("is_link_up", False)
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes for the Trunk Group."""
        trunk_info = self.coordinator.data.get("trunks", {}).get(self.trunk_id, {})
        iface_data = self.coordinator.data.get("interfaces", {}).get(self.trunk_id, {})

        return {
            "trunk_type": trunk_info.get("type", "Inactive"),
            "member_ports": trunk_info.get("member_ports", "None"),
            "aggregated_ports": trunk_info.get("aggregated_ports", "None"),
            "speed": iface_data.get("speed", "Unknown"),
            "flow_control": iface_data.get("flow_control", "Unknown"),
            "tx_packets": iface_data.get("tx_packets", 0),
            "rx_packets": iface_data.get("rx_packets", 0),
            "tx_errors": iface_data.get("tx_errors", 0),
            "rx_errors": iface_data.get("rx_errors", 0),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
        )
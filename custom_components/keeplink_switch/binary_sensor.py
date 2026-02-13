"""Binary sensor platform for Keeplink Switch Ports."""
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
    if "ports" in coordinator.data:
        for port_num in coordinator.data["ports"]:
            sensors.append(KeeplinkPortBinarySensor(coordinator, port_num))

    async_add_entities(sensors)

class KeeplinkPortBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Representation of a Physical Port Link Status."""

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
        """Return true if the binary sensor is on (Link Up)."""
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num)
        if port_data:
            return port_data.get("is_link_up", False)
        return False

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num, {})
        
        attributes = {
            "speed": port_data.get("speed", "Unknown"),
            "flow_control": port_data.get("flow_control", "Unknown"),
            "tx_packets": port_data.get("tx_packets", 0),
            "rx_packets": port_data.get("rx_packets", 0),
            "tx_errors": port_data.get("tx_errors", 0),
            "rx_errors": port_data.get("rx_errors", 0),
        }
        
        # Adicionar info de PoE se disponível e relevante
        if "poe_power" in port_data:
            attributes["poe_power_w"] = port_data["poe_power"]
            attributes["poe_voltage_v"] = port_data["poe_voltage"]
            attributes["poe_current_ma"] = port_data["poe_current"]
            
        return attributes

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
        )
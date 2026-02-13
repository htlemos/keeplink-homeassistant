"""Sensor platform for Keeplink Switch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Define the sensors we want to create
    sensors = [
        KeeplinkSensor(coordinator, "model", "Model", "mdi:switch"),
        KeeplinkSensor(coordinator, "firmware", "Firmware", "mdi:chip"),
        KeeplinkSensor(coordinator, "mac", "MAC Address", "mdi:network"),
        KeeplinkSensor(coordinator, "hardware", "Hardware Version", "mdi:expansion-card"),
    ]
    
    async_add_entities(sensors)

class KeeplinkSensor(CoordinatorEntity, SensorEntity):
    """Representation of a Keeplink Sensor."""

    def __init__(self, coordinator, key, name, icon):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._key = key
        self._name = name
        self._icon = icon
        
        # Unique ID: MAC Address + Sensor Key (e.g., AA:BB:CC:DD:EE:FF_firmware)
        # This ensures multiple switches don't conflict
        self._attr_unique_id = f"{coordinator.mac_address}_{key}"

    @property
    def name(self):
        """Return the friendly name (e.g., 'Keeplink Switch Firmware')."""
        return f"Keeplink Switch {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._key)

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def device_info(self) -> DeviceInfo:
        """Return device registry information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
            name=f"Keeplink Switch ({self.coordinator.host})",
            manufacturer="Keeplink",
            model=self.coordinator.device_info.get("model"),
            sw_version=self.coordinator.device_info.get("sw_version"),
            hw_version=self.coordinator.device_info.get("hw_version"),
            configuration_url=f"http://{self.coordinator.host}",
        )
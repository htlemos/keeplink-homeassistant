"""Sensor platform for Keeplink Switch."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
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
        self._attr_unique_id = f"{coordinator.host}_{key}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Keeplink {self._name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self._key)

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self._icon

"""Sensor platform for Keeplink Switch."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfElectricCurrent

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    sensors = [
        # System Info
        KeeplinkSensor(coordinator, "model", "Model", "mdi:switch"),
        KeeplinkSensor(coordinator, "firmware", "Firmware", "mdi:chip"),
        KeeplinkSensor(coordinator, "mac", "MAC Address", "mdi:network"),
        KeeplinkSensor(coordinator, "hardware", "Hardware Version", "mdi:expansion-card"),
        KeeplinkSensor(coordinator, "ip_address", "IP Address", "mdi:ip-network"),
        KeeplinkSensor(coordinator, "netmask", "Netmask", "mdi:subnet-mask"),
        KeeplinkSensor(coordinator, "gateway", "Gateway", "mdi:router"),
        KeeplinkSensor(coordinator, "firmware_date", "Firmware Date", "mdi:calendar-clock"),
        
        # Total PoE Power
        KeeplinkPoETotalSensor(coordinator)
    ]
    
    # Add Per-Port Sensors dynamically
    # We check the first batch of data to see how many ports we have
    if "ports" in coordinator.data:
        for port_num in coordinator.data["ports"]:
            sensors.append(KeeplinkPortSensor(coordinator, port_num, "power"))
            sensors.append(KeeplinkPortSensor(coordinator, port_num, "voltage"))
            sensors.append(KeeplinkPortSensor(coordinator, port_num, "current"))

    async_add_entities(sensors)

class KeeplinkSensor(CoordinatorEntity, SensorEntity):
    """Representation of a General Info Sensor."""
    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self._key = key
        self._name = name
        self._icon = icon
        self._attr_unique_id = f"{coordinator.mac_address}_{key}"

    @property
    def name(self): return f"Keeplink {self._name}"
    
    @property
    def native_value(self): return self.coordinator.data.get(self._key)
    
    @property
    def icon(self): return self._icon
    
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
            name=f"Keeplink Switch ({self.coordinator.host})",
            manufacturer="Keeplink",
            model=self.coordinator.device_info.get("model"),
            sw_version=self.coordinator.device_info.get("sw_version"),
            hw_version=self.coordinator.device_info.get("hw_version"),
            configuration_url=f"http://{self.coordinator.host}",
        )

class KeeplinkPoETotalSensor(KeeplinkSensor):
    """Specific Sensor for Total PoE Consumption."""
    def __init__(self, coordinator):
        super().__init__(coordinator, "poe_total_power", "PoE Total Power", "mdi:lightning-bolt")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        # UPDATE: Set precision to 3 decimals
        self._attr_suggested_display_precision = 3

class KeeplinkPortSensor(CoordinatorEntity, SensorEntity):
    """Sensor for Port Specific Data (Power, Voltage, Current)."""
    def __init__(self, coordinator, port_num, metric):
        super().__init__(coordinator)
        self.port_num = port_num
        self.metric = metric # 'power', 'voltage', 'current'
        
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_{metric}"
        self._attr_name = f"Keeplink Port {port_num} PoE {metric.capitalize()}"
        
        if metric == "power":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_icon = "mdi:flash"
            # UPDATE: Set precision to 3 decimals
            self._attr_suggested_display_precision = 3
        elif metric == "voltage":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_icon = "mdi:sine-wave"
            self._attr_suggested_display_precision = 1 # Optional: nice to have 1 decimal for Volts
        elif metric == "current":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
            self._attr_icon = "mdi:current-ac"
            self._attr_suggested_display_precision = 0 # Optional: mA usually doesn't need decimals

    @property
    def native_value(self):
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num)
        if port_data:
            return port_data.get(self.metric)
        return None

    @property
    def device_info(self) -> DeviceInfo:
        # Link to the main device
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
        )
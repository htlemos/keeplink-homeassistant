"""Sensor platform for Keeplink Switch."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass, RestoreSensor
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.const import UnitOfPower, UnitOfElectricPotential, UnitOfElectricCurrent, UnitOfEnergy
from homeassistant.util import dt as dt_util
from homeassistant.core import callback

from .const import (
    DOMAIN, 
    CONF_CREATE_TOTAL_ENERGY, 
    CONF_CREATE_PORT_ENERGY, 
    CONF_UTILITY_CYCLES
)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # 1. Base Sensors
    sensors = [
        KeeplinkSensor(coordinator, "model", "Model", "mdi:switch"),
        KeeplinkSensor(coordinator, "firmware", "Firmware", "mdi:chip"),
        KeeplinkSensor(coordinator, "mac", "MAC Address", "mdi:network"),
        KeeplinkSensor(coordinator, "hardware", "Hardware Version", "mdi:expansion-card"),
        KeeplinkSensor(coordinator, "ip_address", "IP Address", "mdi:ip-network"),
        KeeplinkSensor(coordinator, "netmask", "Netmask", "mdi:subnet-mask"),
        KeeplinkSensor(coordinator, "gateway", "Gateway", "mdi:router"),
        KeeplinkSensor(coordinator, "firmware_date", "Firmware Date", "mdi:calendar-clock"),
        KeeplinkPoETotalSensor(coordinator)
    ]
    
    # Check config for Energy generation
    create_total_energy = entry.data.get(CONF_CREATE_TOTAL_ENERGY, False)
    create_port_energy = entry.data.get(CONF_CREATE_PORT_ENERGY, False)
    utility_cycles = entry.data.get(CONF_UTILITY_CYCLES, [])

    # 2. Total Energy Sensors
    if create_total_energy:
        sensors.append(KeeplinkEnergySensor(coordinator, is_total=True))
        for cycle in utility_cycles:
            sensors.append(KeeplinkUtilitySensor(coordinator, is_total=True, cycle=cycle))

    # 3. Per-Port Dynamic Sensors
    if "ports" in coordinator.data:
        for port_num, port_data in coordinator.data["ports"].items():
            if "power" in port_data:
                # Add basic PoE sensors (Disabled by default)
                sensors.append(KeeplinkPortSensor(coordinator, port_num, "power"))
                sensors.append(KeeplinkPortSensor(coordinator, port_num, "voltage"))
                sensors.append(KeeplinkPortSensor(coordinator, port_num, "current"))
                
                # Add Energy & Utility sensors for this port if enabled
                if create_port_energy:
                    sensors.append(KeeplinkEnergySensor(coordinator, is_total=False, port_num=port_num))
                    for cycle in utility_cycles:
                        sensors.append(KeeplinkUtilitySensor(coordinator, is_total=False, port_num=port_num, cycle=cycle))

    async_add_entities(sensors)

# --- Standard Sensors (Unchanged) ---
class KeeplinkSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, key, name, icon):
        super().__init__(coordinator)
        self._key = key
        self._name = name
        self._icon = icon
        self._attr_unique_id = f"{coordinator.mac_address}_{key}"
        if key in ["model", "firmware", "mac", "hardware", "ip_address", "netmask", "gateway", "firmware_date"]:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self): return f"Keeplink {self._name}"
    @property
    def native_value(self): return self.coordinator.data.get(self._key)
    @property
    def icon(self): return self._icon
    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})

class KeeplinkPoETotalSensor(KeeplinkSensor):
    def __init__(self, coordinator):
        super().__init__(coordinator, "poe_total_power", "PoE Total Power", "mdi:lightning-bolt")
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_suggested_display_precision = 3

class KeeplinkPortSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, port_num, metric):
        super().__init__(coordinator)
        self.port_num = port_num
        self.metric = metric
        self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_{metric}"
        self._attr_name = f"Keeplink Port {port_num} PoE {metric.capitalize()}"
        self._attr_entity_registry_enabled_default = False
        
        if metric == "power":
            self._attr_device_class = SensorDeviceClass.POWER
            self._attr_native_unit_of_measurement = UnitOfPower.WATT
            self._attr_icon = "mdi:flash"
            self._attr_suggested_display_precision = 3
        elif metric == "voltage":
            self._attr_device_class = SensorDeviceClass.VOLTAGE
            self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
            self._attr_icon = "mdi:sine-wave"
        elif metric == "current":
            self._attr_device_class = SensorDeviceClass.CURRENT
            self._attr_native_unit_of_measurement = UnitOfElectricCurrent.MILLIAMPERE
            self._attr_icon = "mdi:current-ac"

    @property
    def native_value(self):
        port_data = self.coordinator.data.get("ports", {}).get(self.port_num)
        return port_data.get(self.metric) if port_data else None

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})


# --- NEW: Energy & Utility Sensors (Riemann Sum Integration & Resets) ---
class KeeplinkEnergySensor(CoordinatorEntity, RestoreSensor):
    """Calculates accumulated energy (kWh) from Power (W) using Left Riemann sum."""
    
    def __init__(self, coordinator, is_total=True, port_num=None):
        super().__init__(coordinator)
        self.is_total = is_total
        self.port_num = port_num
        
        # State variables for Riemann sum
        self._state = 0.0
        self._last_update_time = None
        self._last_power_w = 0.0

        if is_total:
            self._attr_unique_id = f"{coordinator.mac_address}_total_energy"
            self._attr_name = "Keeplink Total PoE Energy"
        else:
            self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_energy"
            self._attr_name = f"Keeplink Port {port_num} PoE Energy"

        self._attr_device_class = SensorDeviceClass.ENERGY
        # TOTAL_INCREASING allows the HA Energy Dashboard to handle resets seamlessly
        self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
        self._attr_icon = "mdi:lightning-bolt-circle"
        self._attr_suggested_display_precision = 4

    async def async_added_to_hass(self):
        """Restore previous state when Home Assistant restarts."""
        await super().async_added_to_hass()
        last_state = await self.async_get_last_sensor_data()
        if last_state and last_state.native_value is not None:
            try:
                self._state = float(last_state.native_value)
            except ValueError:
                self._state = 0.0

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator and apply Left Riemann Sum."""
        now = dt_util.utcnow()
        
        # Fetch current power
        if self.is_total:
            current_power = self.coordinator.data.get("poe_total_power", 0.0)
        else:
            port_data = self.coordinator.data.get("ports", {}).get(self.port_num, {})
            current_power = port_data.get("power", 0.0)

        # Left Riemann Sum Math: kWh = (Last Power * Delta Hours) / 1000
        if self._last_update_time is not None:
            delta_seconds = (now - self._last_update_time).total_seconds()
            delta_hours = delta_seconds / 3600.0
            
            # Use _last_power_w (Left method) for calculation
            added_kwh = (self._last_power_w * delta_hours) / 1000.0
            self._state += added_kwh

        # Update tracking variables
        self._last_update_time = now
        self._last_power_w = current_power

        super()._handle_coordinator_update()

    @property
    def native_value(self):
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})


class KeeplinkUtilitySensor(KeeplinkEnergySensor):
    """Energy Sensor that resets based on Daily, Monthly, or Yearly cycles."""
    
    def __init__(self, coordinator, is_total, port_num=None, cycle="daily"):
        # Initialize the base energy sensor to handle the math
        super().__init__(coordinator, is_total, port_num)
        self.cycle = cycle
        
        if is_total:
            self._attr_unique_id = f"{coordinator.mac_address}_total_energy_{cycle}"
            self._attr_name = f"Keeplink Total PoE Energy ({cycle.capitalize()})"
        else:
            self._attr_unique_id = f"{coordinator.mac_address}_port{port_num}_energy_{cycle}"
            self._attr_name = f"Keeplink Port {port_num} PoE Energy ({cycle.capitalize()})"
            
        self._attr_icon = "mdi:chart-timeline"

    @callback
    def _handle_coordinator_update(self) -> None:
        """Check for cycle boundary crossings before accumulating energy."""
        now = dt_util.now() # Use local time for utility resets!
        
        if self._last_update_time is not None:
            last_local = dt_util.as_local(self._last_update_time)
            
            # Detect Boundary Crossing and Reset to 0
            if self.cycle == "daily" and now.day != last_local.day:
                self._state = 0.0
            elif self.cycle == "monthly" and now.month != last_local.month:
                self._state = 0.0
            elif self.cycle == "yearly" and now.year != last_local.year:
                self._state = 0.0

        # Now let the parent class do the normal Riemann math
        super()._handle_coordinator_update()
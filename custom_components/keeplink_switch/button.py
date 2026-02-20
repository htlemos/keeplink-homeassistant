"""Button platform for Keeplink Switch."""
from homeassistant.components.button import ButtonEntity, ButtonDeviceClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo, EntityCategory

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    buttons = [
        KeeplinkClearStatsButton(coordinator),
        KeeplinkRebootButton(coordinator)
    ]
    
    async_add_entities(buttons)


class KeeplinkClearStatsButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Clear Stats Button."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac_address}_clear_stats"
        self._attr_name = "Keeplink Clear Statistics"
        self._attr_icon = "mdi:delete-sweep"
        
        # Move to the Diagnostic section
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_clear_port_stats()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})


class KeeplinkRebootButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Reboot Switch Button."""
    def __init__(self, coordinator):
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac_address}_reboot"
        self._attr_name = "Keeplink Reboot Device"
        self._attr_device_class = ButtonDeviceClass.RESTART
        self._attr_icon = "mdi:restart"
        
        # Move to the Configuration section (adds a warning prompt in some HA views)
        self._attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_reboot_switch()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})
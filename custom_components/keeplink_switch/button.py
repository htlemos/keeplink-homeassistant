"""Button platform for Keeplink Switch."""
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch buttons."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Create a single button for the device
    async_add_entities([KeeplinkClearStatsButton(coordinator)])

class KeeplinkClearStatsButton(CoordinatorEntity, ButtonEntity):
    """Representation of a Clear Stats Button."""

    def __init__(self, coordinator):
        """Initialize the button."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.mac_address}_clear_stats"
        self._attr_name = "Keeplink Clear Statistics"
        self._attr_icon = "mdi:delete-sweep"

    async def async_press(self) -> None:
        """Handle the button press."""
        await self.coordinator.async_clear_port_stats()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.mac_address)},
        )
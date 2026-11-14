"""Select platform for Keeplink Switch."""
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the Keeplink Switch selects."""
    coordinator = hass.data[DOMAIN][entry.entry_id]

    selects = []
    # 1. Physical Ports (1..9)
    if "ports" in coordinator.data:
        for port_num in sorted(coordinator.data["ports"].keys()):
            selects.append(KeeplinkPortSpeedSelect(coordinator, port_num))

    # 2. Logical Trunk Groups (Trunk1, Trunk2)
    for trunk_id in ["Trunk1", "Trunk2"]:
        selects.append(KeeplinkPortSpeedSelect(coordinator, trunk_id))

    async_add_entities(selects)


class KeeplinkPortSpeedSelect(CoordinatorEntity, SelectEntity):
    """Representation of a Port or Trunk Speed/Duplex Select."""

    def __init__(self, coordinator, iface_key):
        """Initialize the select."""
        super().__init__(coordinator)
        self.iface_key = iface_key

        if isinstance(iface_key, str) and iface_key.startswith("Trunk"):
            clean_name = iface_key.replace("Trunk", "Trunk ")
            uid_prefix = iface_key.lower()
        else:
            clean_name = f"Port {iface_key}"
            uid_prefix = f"port{iface_key}"

        self._attr_unique_id = f"{coordinator.mac_address}_{uid_prefix}_speed_select"
        self._attr_name = f"Keeplink {clean_name} Speed"
        self._attr_icon = "mdi:transit-connection-variant"

        # Dynamically set options based on interface type (Port 9 is SFP+)
        if iface_key == 9:
            self._attr_options = ["Auto", "100M/Full", "1000M/Full", "2500M/Full", "10G/Full"]
        else:
            self._attr_options = [
                "Auto",
                "10M/Half",
                "10M/Full",
                "100M/Half",
                "100M/Full",
                "1000M/Full",
                "2500M/Full",
            ]

        self._val_map = {
            "Auto": 0,
            "10M/Half": 1,
            "10M/Full": 2,
            "100M/Half": 3,
            "100M/Full": 4,
            "1000M/Full": 5,
            "2500M/Full": 6,
            "10G/Full": 8,
        }

        self._html_map = {
            "Auto": "Auto",
            "10 Half": "10M/Half",
            "10 Full": "10M/Full",
            "100 Half": "100M/Half",
            "100 Full": "100M/Full",
            "1000Full": "1000M/Full",
            "2.5G Full": "2500M/Full",
            "10G Full": "10G/Full",
        }

    @property
    def available(self) -> bool:
        """Mark unavailable if physical port is absorbed into a Trunk or Trunk is inactive."""
        if not super().available:
            return False
        return self.iface_key in self.coordinator.data.get("interfaces", {})

    @property
    def current_option(self):
        """Return the current selected option."""
        iface_data = self.coordinator.data.get("interfaces", {}).get(self.iface_key, {})
        cfg_speed = iface_data.get("config_speed", "Auto")
        return self._html_map.get(cfg_speed, "Auto")

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        speed_val = self._val_map[option]
        await self.coordinator.async_set_port_settings(self.iface_key, speed_val=speed_val)

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(identifiers={(DOMAIN, self.coordinator.mac_address)})
"""The Keeplink Switch integration."""
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL, CONF_POE_SCAN_INTERVAL, DEFAULT_POE_SCAN_INTERVAL
from .coordinator import KeeplinkCoordinator

PLATFORMS = ["sensor", "switch", "binary_sensor", "button", "select"]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Keeplink Switch from a config entry."""
    
    session = async_get_clientsession(hass)
    scan_interval = entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    poe_scan_interval = entry.data.get(CONF_POE_SCAN_INTERVAL, DEFAULT_POE_SCAN_INTERVAL)

    coordinator = KeeplinkCoordinator(
        hass, 
        session, 
        entry.data[CONF_HOST], 
        entry.data[CONF_USERNAME], 
        entry.data[CONF_PASSWORD],
        scan_interval,
        poe_scan_interval # Pass the new parameter
    )

    # Attempt an initial login to "wake up" the switch web server
#    await coordinator._async_login()

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Migrate v1.3.0 Trunk Group sensors from Diagnostic to primary Sensors section
    ent_reg = er.async_get(hass)
    for trunk_id in ("trunk1", "trunk2"):
        for metric in ("type", "member_ports", "aggregated_ports"):
            uid = f"{coordinator.mac_address}_{trunk_id}_{metric}"
            entity_id = ent_reg.async_get_entity_id("sensor", DOMAIN, uid)
            if entity_id:
                ent_reg.async_update_entity(entity_id, entity_category=None)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))


    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
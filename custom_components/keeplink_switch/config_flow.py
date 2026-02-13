"""Config flow for Keeplink Switch integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD

from .const import (
    DOMAIN, 
    CONF_SCAN_INTERVAL, 
    DEFAULT_SCAN_INTERVAL
)

_LOGGER = logging.getLogger(__name__)

class KeeplinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Keeplink Switch."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        # ERROR FIX: Do NOT pass config_entry here. HA attaches it automatically now.
        return KeeplinkOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            
            # Ensure scan_interval is saved as an int
            if CONF_SCAN_INTERVAL in user_input:
                user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])

            return self.async_create_entry(
                title=f"Keeplink ({user_input[CONF_HOST]})", 
                data=user_input
            )

        # Default Schema
        data_schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_USERNAME, default="admin"): str,
            vol.Required(CONF_PASSWORD, default="admin"): str,
            vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

class KeeplinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the Cogwheel configuration."""

    # ERROR FIX: 'def __init__' removed entirely. 
    # Home Assistant now injects 'self.config_entry' automatically.

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update the entry with new data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=user_input
            )
            return self.async_create_entry(title="", data=None)

        # Pre-fill the form with existing values
        # We access self.config_entry directly (it is now auto-populated)
        current_host = self.config_entry.data.get(CONF_HOST, "")
        current_user = self.config_entry.data.get(CONF_USERNAME, "admin")
        current_pass = self.config_entry.data.get(CONF_PASSWORD, "admin")
        current_scan = self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        options_schema = vol.Schema({
            vol.Required(CONF_HOST, default=current_host): str,
            vol.Required(CONF_USERNAME, default=current_user): str,
            vol.Required(CONF_PASSWORD, default=current_pass): str,
            vol.Required(CONF_SCAN_INTERVAL, default=current_scan): int,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
        )
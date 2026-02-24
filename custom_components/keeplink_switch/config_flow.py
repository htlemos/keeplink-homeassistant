"""Config flow for Keeplink Switch integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.const import CONF_HOST, CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.selector import SelectSelector, SelectSelectorConfig, SelectSelectorMode

from .const import (
    DOMAIN, 
    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL,
    CONF_POE_SCAN_INTERVAL, DEFAULT_POE_SCAN_INTERVAL,
    CONF_CREATE_TOTAL_ENERGY, DEFAULT_CREATE_TOTAL_ENERGY,
    CONF_CREATE_PORT_ENERGY, DEFAULT_CREATE_PORT_ENERGY,
    CONF_UTILITY_CYCLES, DEFAULT_UTILITY_CYCLES
)

_LOGGER = logging.getLogger(__name__)

def get_schema(data: dict) -> vol.Schema:
    """Helper to generate the schema with current values."""
    return vol.Schema({
        vol.Required(CONF_HOST, default=data.get(CONF_HOST, "")): str,
        vol.Required(CONF_USERNAME, default=data.get(CONF_USERNAME, "admin")): str,
        vol.Required(CONF_PASSWORD, default=data.get(CONF_PASSWORD, "admin")): str,
        vol.Required(CONF_SCAN_INTERVAL, default=data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
        vol.Required(CONF_POE_SCAN_INTERVAL, default=data.get(CONF_POE_SCAN_INTERVAL, DEFAULT_POE_SCAN_INTERVAL)): int,
        
        # New Energy Options
        vol.Optional(CONF_CREATE_TOTAL_ENERGY, default=data.get(CONF_CREATE_TOTAL_ENERGY, DEFAULT_CREATE_TOTAL_ENERGY)): bool,
        vol.Optional(CONF_CREATE_PORT_ENERGY, default=data.get(CONF_CREATE_PORT_ENERGY, DEFAULT_CREATE_PORT_ENERGY)): bool,
        vol.Optional(CONF_UTILITY_CYCLES, default=data.get(CONF_UTILITY_CYCLES, DEFAULT_UTILITY_CYCLES)): SelectSelector(
            SelectSelectorConfig(
                options=["daily", "monthly", "yearly"],
                multiple=True,
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="utility_cycles"
            )
        ),
    })

class KeeplinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Keeplink Switch."""
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KeeplinkOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self._async_abort_entries_match({CONF_HOST: user_input[CONF_HOST]})
            
            # Ensure intervals are saved as integers
            if CONF_SCAN_INTERVAL in user_input:
                user_input[CONF_SCAN_INTERVAL] = int(user_input[CONF_SCAN_INTERVAL])
            if CONF_POE_SCAN_INTERVAL in user_input:
                user_input[CONF_POE_SCAN_INTERVAL] = int(user_input[CONF_POE_SCAN_INTERVAL])

            return self.async_create_entry(title=f"Keeplink ({user_input[CONF_HOST]})", data=user_input)

        return self.async_show_form(step_id="user", data_schema=get_schema({}))

class KeeplinkOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for the Cogwheel configuration."""
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
            return self.async_create_entry(title="", data=None)

        return self.async_show_form(step_id="init", data_schema=get_schema(self.config_entry.data))
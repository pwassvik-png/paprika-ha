"""Config flow for Paprika integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_RECEIPT,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Required(CONF_RECEIPT): str,
        vol.Optional(
            CONF_UPDATE_INTERVAL,
            default=DEFAULT_UPDATE_INTERVAL_MINUTES,
        ): vol.All(int, vol.Range(min=5, max=180)),
    }
)


class PaprikaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paprika."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
        self._abort_if_unique_id_configured()

        data = {
            CONF_EMAIL: user_input[CONF_EMAIL],
            CONF_PASSWORD: user_input[CONF_PASSWORD],
            CONF_RECEIPT: user_input[CONF_RECEIPT],
        }

        options = {
            CONF_UPDATE_INTERVAL: user_input.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
            )
        }

        return self.async_create_entry(title="Paprika", data=data, options=options)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return PaprikaOptionsFlowHandler(config_entry)


class PaprikaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Paprika options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle options configuration."""
        if user_input is None:
            update_interval = self.config_entry.options.get(
                CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
            )
            schema = vol.Schema(
                {
                    vol.Optional(
                        CONF_UPDATE_INTERVAL,
                        default=update_interval,
                    ): vol.All(int, vol.Range(min=5, max=180)),
                }
            )
            return self.async_show_form(step_id="user", data_schema=schema)

        return self.async_create_entry(title="", data=user_input)

"""Config flow for Paprika integration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .api import PaprikaApiError, PaprikaAuth, PaprikaAuthError, PaprikaClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(
            CONF_UPDATE_INTERVAL,
            default=DEFAULT_UPDATE_INTERVAL_MINUTES,
        ): vol.All(int, vol.Range(min=5, max=180)),
    }
)
STEP_PASSWORD_SCHEMA = vol.Schema({vol.Required(CONF_PASSWORD): str})


class PaprikaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Paprika."""

    VERSION = 1

    async def _async_check(self, email: str, password: str) -> str | None:
        """Log in once; return an error key, or None when it worked."""
        client = PaprikaClient(self.hass, PaprikaAuth(email=email, password=password))
        try:
            await client.async_validate_login()
        except PaprikaAuthError:
            return "invalid_auth"
        except PaprikaApiError:
            return "cannot_connect"
        return None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_EMAIL].lower())
            self._abort_if_unique_id_configured()
            error = await self._async_check(user_input[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error is None:
                return self.async_create_entry(
                    title="Paprika",
                    data={
                        CONF_EMAIL: user_input[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                    options={
                        CONF_UPDATE_INTERVAL: user_input.get(
                            CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
                        )
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> FlowResult:
        """Paprika stopped accepting the stored password."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Ask for the new password."""
        return await self._async_step_password(
            "reauth_confirm", self._get_reauth_entry(), user_input
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Change the password from the integration's menu."""
        return await self._async_step_password(
            "reconfigure", self._get_reconfigure_entry(), user_input
        )

    async def _async_step_password(
        self,
        step_id: str,
        entry: config_entries.ConfigEntry,
        user_input: dict[str, Any] | None,
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            error = await self._async_check(entry.data[CONF_EMAIL], user_input[CONF_PASSWORD])
            if error is None:
                # Only email and password are kept; a receipt from older
                # versions is dropped since the API does not need it.
                return self.async_update_reload_and_abort(
                    entry,
                    data={
                        CONF_EMAIL: entry.data[CONF_EMAIL],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                    },
                )
            errors["base"] = error

        return self.async_show_form(
            step_id=step_id,
            data_schema=STEP_PASSWORD_SCHEMA,
            description_placeholders={"email": entry.data[CONF_EMAIL]},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the options flow."""
        return PaprikaOptionsFlowHandler()


class PaprikaOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Paprika options.

    `self.config_entry` is provided by Home Assistant; assigning it (as older
    versions did) fails on current releases.
    """

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

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
        return self.async_show_form(step_id="init", data_schema=schema)

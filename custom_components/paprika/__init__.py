"""Paprika Recipe Manager integration."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .api import PaprikaAuth, PaprikaClient, PaprikaApiError
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_RECEIPT,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import PaprikaDataUpdateCoordinator
from .util import resolve_credentials


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Paprika from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    email, password, receipt = await hass.async_add_executor_job(
        resolve_credentials,
        entry.data,
        Path(hass.config.path("secrets.yaml")),
    )

    if not email or not password or not receipt:
        raise ConfigEntryNotReady("Paprika credentials saknas (email/lösenord/kvitto).")

    auth = PaprikaAuth(email=email, password=password, receipt=receipt)
    client = PaprikaClient(hass, auth)

    update_interval = entry.options.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
    )
    coordinator = PaprikaDataUpdateCoordinator(
        hass,
        client=client,
        update_interval=timedelta(minutes=update_interval),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except PaprikaApiError as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_update_options))
    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update for a config entry."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Paprika config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.entry_id in hass.data.get(DOMAIN, {}):
        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)

    return unload_ok

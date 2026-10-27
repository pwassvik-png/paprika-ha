"""Paprika Recipe Manager integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.storage import Store

from .api import PaprikaApiError, PaprikaAuth, PaprikaClient
from .const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_MINUTES,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import PaprikaDataUpdateCoordinator
from .recipes import RecipeStore
from .services import async_register_services, async_unregister_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Paprika from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    auth = PaprikaAuth(email=entry.data[CONF_EMAIL], password=entry.data[CONF_PASSWORD])
    client = PaprikaClient(hass, auth)

    update_interval = entry.options.get(
        CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL_MINUTES
    )
    storage: Store = Store(hass, 1, f"{DOMAIN}_recipes_{entry.entry_id}")
    recipes = RecipeStore(
        client,
        on_change=lambda snapshot: storage.async_delay_save(lambda: snapshot, 30),
    )
    recipes.restore(await storage.async_load())
    coordinator = PaprikaDataUpdateCoordinator(
        hass,
        client=client,
        recipes=recipes,
        update_interval=timedelta(minutes=update_interval),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except PaprikaApiError as err:
        raise ConfigEntryNotReady from err

    hass.data[DOMAIN][entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
        "recipes": recipes,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_register_services(hass)
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
            async_unregister_services(hass)

    return unload_ok

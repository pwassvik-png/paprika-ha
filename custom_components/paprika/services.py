"""Paprika recipe services: search, get, create and update."""

from __future__ import annotations

from typing import Any, Dict

import voluptuous as vol

from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.util import dt as dt_util

from .api import PaprikaApiError
from .const import DOMAIN
from .recipes import (
    LINE_FIELDS,
    TEXT_FIELDS,
    RecipeError,
    RecipeStore,
    apply_fields,
    full,
    new_recipe,
    resolve,
    search,
    summarize,
)

SERVICE_SEARCH = "search_recipes"
SERVICE_GET = "get_recipe"
SERVICE_CREATE = "create_recipe"
SERVICE_UPDATE = "update_recipe"
SERVICES = (SERVICE_SEARCH, SERVICE_GET, SERVICE_CREATE, SERVICE_UPDATE)

_lines = vol.Any(cv.string, [cv.string])
RECIPE_FIELDS = {
    **{vol.Optional(key): cv.string for key in TEXT_FIELDS if key != "name"},
    **{vol.Optional(key): _lines for key in LINE_FIELDS},
    vol.Optional("categories"): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional("rating"): vol.All(vol.Coerce(int), vol.Range(min=0, max=5)),
    vol.Optional("favorite"): cv.boolean,
}

SEARCH_SCHEMA = vol.Schema(
    {
        vol.Optional("query", default=""): cv.string,
        vol.Optional("in_ingredients", default=False): cv.boolean,
        vol.Optional("include_trash", default=False): cv.boolean,
        vol.Optional("limit", default=20): vol.All(vol.Coerce(int), vol.Range(min=1, max=500)),
    }
)
GET_SCHEMA = vol.Schema({vol.Required("recipe"): cv.string})
CREATE_SCHEMA = vol.Schema({vol.Required("name"): cv.string, **RECIPE_FIELDS})
UPDATE_SCHEMA = vol.Schema(
    {vol.Required("recipe"): cv.string, vol.Optional("name"): cv.string, **RECIPE_FIELDS}
)


def _store(hass: HomeAssistant) -> RecipeStore:
    entries = hass.data.get(DOMAIN) or {}
    if not entries:
        raise HomeAssistantError("Paprika är inte inläst")
    return next(iter(entries.values()))["recipes"]


async def _refreshed_store(hass: HomeAssistant) -> RecipeStore:
    store = _store(hass)
    try:
        await store.async_refresh()
    except PaprikaApiError as err:
        raise HomeAssistantError(f"Kunde inte hämta recept: {err}") from err
    return store


def _resolve(store: RecipeStore, ref: str) -> Dict[str, Any]:
    try:
        return resolve(store.recipes, ref)
    except RecipeError as err:
        raise ServiceValidationError(str(err)) from err


def _fields(call: ServiceCall) -> Dict[str, Any]:
    return {k: v for k, v in call.data.items() if k != "recipe"}


async def _save(store: RecipeStore, recipe: Dict[str, Any]) -> None:
    try:
        await store.async_save(recipe)
    except PaprikaApiError as err:
        raise HomeAssistantError(f"Kunde inte spara receptet: {err}") from err


def async_register_services(hass: HomeAssistant) -> None:
    """Register the recipe services once for the domain."""
    if hass.services.has_service(DOMAIN, SERVICE_SEARCH):
        return

    async def handle_search(call: ServiceCall) -> ServiceResponse:
        store = await _refreshed_store(hass)
        hits = search(
            store.recipes,
            call.data["query"],
            in_ingredients=call.data["in_ingredients"],
            include_trash=call.data["include_trash"],
        )
        return {
            "count": len(hits),
            "recipes": [summarize(r, store.categories) for r in hits[: call.data["limit"]]],
        }

    async def handle_get(call: ServiceCall) -> ServiceResponse:
        store = await _refreshed_store(hass)
        return full(_resolve(store, call.data["recipe"]), store.categories)

    async def handle_create(call: ServiceCall) -> ServiceResponse:
        store = await _refreshed_store(hass)
        try:
            recipe = new_recipe(
                dict(call.data),
                store.categories,
                dt_util.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err
        await _save(store, recipe)
        return full(recipe, store.categories)

    async def handle_update(call: ServiceCall) -> ServiceResponse:
        store = await _refreshed_store(hass)
        current = _resolve(store, call.data["recipe"])
        try:
            recipe = apply_fields(current, _fields(call), store.categories)
        except RecipeError as err:
            raise ServiceValidationError(str(err)) from err
        await _save(store, recipe)
        return full(recipe, store.categories)

    hass.services.async_register(
        DOMAIN, SERVICE_SEARCH, handle_search, SEARCH_SCHEMA, SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_GET, handle_get, GET_SCHEMA, SupportsResponse.ONLY
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE, handle_create, CREATE_SCHEMA, SupportsResponse.OPTIONAL
    )
    hass.services.async_register(
        DOMAIN, SERVICE_UPDATE, handle_update, UPDATE_SCHEMA, SupportsResponse.OPTIONAL
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    for service in SERVICES:
        hass.services.async_remove(DOMAIN, service)

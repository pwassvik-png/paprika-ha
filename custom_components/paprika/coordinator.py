"""DataUpdateCoordinator for Paprika."""

from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PaprikaClient, PaprikaApiError
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)


class PaprikaDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Any]]):
    """Coordinator to handle Paprika polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: PaprikaClient,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        self._client = client

        super().__init__(
            hass,
            LOGGER,
            name=f"{DOMAIN}_data",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> Dict[str, Any]:
        """Fetch data from Paprika."""
        try:
            (
                status,
                meals,
                menu_items,
                groceries,
                meal_types,
                recipes,
                pantry,
            ) = await asyncio.gather(
                self._client.async_fetch_status(),
                self._client.async_fetch_meals(),
                self._client.async_fetch_menu_items(),
                self._client.async_fetch_groceries(),
                self._client.async_fetch_meal_types(),
                self._client.async_fetch_recipes(),
                self._client.async_fetch_pantry(),
            )
        except PaprikaApiError as err:
            raise UpdateFailed(f"Paprika update failed: {err}") from err

        return {
            "status": status,
            "meals": meals,
            "menu_items": menu_items,
            "groceries": groceries,
            "meal_types": meal_types,
            "recipes": recipes,
            "pantry": pantry,
        }

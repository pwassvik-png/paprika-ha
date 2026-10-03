"""Sensor platform for Paprika."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, List, Tuple, Dict

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .util import resolve_meal_time_windows


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Paprika sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]

    entities: list[SensorEntity] = [
        PaprikaNextMealSensor(coordinator, entry.entry_id),
        PaprikaMealCountSensor(coordinator, entry.entry_id),
        PaprikaRecipeTotalSensor(coordinator, entry.entry_id),
        PaprikaGroceryListSensor(coordinator, entry.entry_id),
        PaprikaRecipePreviewSensor(coordinator, entry.entry_id),
    ]

    async_add_entities(entities)


@dataclass
class PaprikaSensorDescription(SensorEntityDescription):
    """Describes Paprika sensors."""

    entity_category: EntityCategory | None = EntityCategory.DIAGNOSTIC


class PaprikaBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for Paprika sensors."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry_id: str, description: PaprikaSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    def coordinator_data(self) -> dict[str, Any]:
        """Return typed coordinator data."""
        return self.coordinator.data or {}


class PaprikaNextMealSensor(PaprikaBaseSensor):
    """Sensor that exposes the next upcoming meal."""

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize sensor."""
        description = PaprikaSensorDescription(
            key="next_meal",
            name="Next Meal",
            icon="mdi:food",
            entity_category=None,
        )
        super().__init__(coordinator, entry_id, description)

    @property
    def native_value(self) -> Any:
        """Return the name of the next meal."""
        next_meal = self._get_next_meal()
        if not next_meal:
            return None
        meal_dt, meal = next_meal
        return meal.get("recipe") or meal.get("name")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes about the next meal."""
        next_meal = self._get_next_meal()
        if not next_meal:
            return {}

        meal_dt, meal = next_meal
        return {
            "scheduled": meal_dt.isoformat(),
            "date": meal_dt.date().isoformat(),
            "meal_type": meal.get("type"),
            "recipe_uid": meal.get("recipe_uid"),
            "raw_name": meal.get("name"),
            "order_flag": meal.get("order_flag"),
        }

    def _get_next_meal(self) -> Optional[tuple[datetime, dict[str, Any]]]:
        """Return the next meal tuple (datetime, meal)."""
        meals = self.coordinator.data.get("meals", [])
        meal_types = _meal_type_index(self.coordinator.data.get("meal_types"))
        today = dt_util.now().date()

        candidates: list[tuple[datetime, dict[str, Any]]] = []
        for meal in meals:
            if meal.get("deleted"):
                continue
            window = resolve_meal_time_windows(meal, meal_types)
            if not window:
                continue
            start, _ = window
            if start.date() < today:
                continue
            candidates.append(
                (
                    start,
                    meal,
                )
            )

        if not candidates:
            return None

        candidates.sort(
            key=lambda item: (
                item[0].date(),
                item[1].get("type") or 0,
                item[1].get("order_flag") or 0,
            )
        )
        chosen_dt, chosen_meal = candidates[0]
        return chosen_dt, chosen_meal


class PaprikaMealCountSensor(PaprikaBaseSensor):
    """Sensor counting meals planned for today."""

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize sensor."""
        description = PaprikaSensorDescription(
            key="meal_count_today",
            name="Meal Count Today",
            icon="mdi:counter",
            entity_category=None,
        )
        super().__init__(coordinator, entry_id, description)

    @property
    def native_value(self) -> Any:
        """Return number of meals scheduled for the current day."""
        meals = self.coordinator.data.get("meals", [])
        meal_types = _meal_type_index(self.coordinator.data.get("meal_types"))
        today = dt_util.now().date()
        count = 0
        for meal in meals:
            window = resolve_meal_time_windows(meal, meal_types)
            if not window:
                continue
            start, _ = window
            if start.date() == today:
                count += 1
        return count

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose today's meals list for UI templates."""
        meals = self.coordinator.data.get("meals", [])
        meal_types = _meal_type_index(self.coordinator.data.get("meal_types"))
        today = dt_util.now().date()
        todays: list[dict[str, Any]] = []
        for meal in meals:
            if meal.get("deleted"):
                continue
            window = resolve_meal_time_windows(meal, meal_types)
            if not window:
                continue
            start, _ = window
            if start.date() == today:
                todays.append(
                    {
                        "name": meal.get("recipe") or meal.get("name"),
                        "raw_name": meal.get("name"),
                        "recipe_uid": meal.get("recipe_uid"),
                        "meal_type": meal.get("type"),
                        "order_flag": meal.get("order_flag"),
                        "scheduled": start.isoformat(),
                    }
                )

        todays.sort(
            key=lambda item: (item.get("meal_type") or 0, item.get("order_flag") or 0)
        )
        return {"meals": todays}


def _meal_type_index(meal_types: Optional[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Create lookup dictionary for Paprika meal types."""
    if not meal_types:
        return {}
    return {
        entry["uid"]: entry
        for entry in meal_types
        if entry.get("uid")
    }


class PaprikaRecipeTotalSensor(PaprikaBaseSensor):
    """Sensor exposing total recipe count."""

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize sensor."""
        description = PaprikaSensorDescription(
            key="recipe_total",
            name="Recipe Total",
            icon="mdi:book-open-page-variant",
        )
        super().__init__(coordinator, entry_id, description)

    @property
    def native_value(self) -> Any:
        """Return total number of recipes stored in Paprika."""
        status = self.coordinator.data.get("status") or {}
        return status.get("recipes")


class PaprikaGroceryListSensor(PaprikaBaseSensor):
    """Sensor exposing active Paprika grocery list items."""

    def __init__(self, coordinator, entry_id: str) -> None:
        description = PaprikaSensorDescription(
            key="grocery_items",
            name="Grocery Items",
            icon="mdi:cart",
            entity_category=None,
        )
        super().__init__(coordinator, entry_id, description)

    @property
    def native_value(self) -> Any:
        """Return number of active grocery items."""
        return len(self._active_items())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a trimmed list of grocery entries."""
        entries = [
            {
                "name": item.get("name"),
                "aisle": item.get("aisle"),
                "quantity": item.get("quantity"),
                "recipe": item.get("recipe"),
                "list_uid": item.get("list_uid"),
                "uid": item.get("uid"),
            }
            for item in self._active_items()[:25]
        ]
        return {"items": entries, "total": len(self._active_items())}

    def _active_items(self) -> list[dict[str, Any]]:
        groceries = self.coordinator.data.get("groceries") or []
        return [
            item
            for item in groceries
            if not item.get("deleted") and not item.get("purchased")
        ]


class PaprikaRecipePreviewSensor(PaprikaBaseSensor):
    """Sensor exposing Paprika recipe details."""

    def __init__(self, coordinator, entry_id: str) -> None:
        description = PaprikaSensorDescription(
            key="recipe_preview",
            name="Recipe Preview",
            icon="mdi:book-open-variant",
        )
        super().__init__(coordinator, entry_id, description)

    @property
    def native_value(self) -> Any:
        """Return total recipes (mirror of status for quick glance)."""
        status = self.coordinator.data.get("status") or {}
        return status.get("recipes")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Expose a subset of recipe metadata for dashboards."""
        recipes = self.coordinator.data.get("recipes") or []
        preview = [
            {
                "name": recipe.get("name"),
                "category": recipe.get("categories"),
                "uid": recipe.get("uid"),
                "photo": recipe.get("photo"),
            }
            for recipe in recipes[:15]
        ]
        return {"recipes": preview}

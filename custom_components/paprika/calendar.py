"""Calendar platform for Paprika."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
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
    """Set up Paprika calendar entity."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    async_add_entities([PaprikaCalendar(coordinator, entry.entry_id)])


class PaprikaCalendar(CoordinatorEntity, CalendarEntity):
    """Calendar entity exposing Paprika meal plan."""

    _attr_name = "Paprika Meal Plan"

    def __init__(self, coordinator, entry_id: str) -> None:
        """Initialize calendar."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming calendar event."""
        now = dt_util.now()
        events = self._build_events()
        for event in events:
            if event.end >= now:
                return event
        return events[-1] if events else None

    async def async_get_events(
        self,
        hass: HomeAssistant,
        start_date: datetime,
        end_date: datetime,
    ) -> List[CalendarEvent]:
        """Return events within the requested range."""
        events = self._build_events()
        return [
            event
            for event in events
            if event.start <= end_date and event.end >= start_date
        ]

    def _build_events(self) -> List[CalendarEvent]:
        """Build sorted event list from all meal entries."""
        events: List[CalendarEvent] = []
        meals = self.coordinator.data.get("meals", [])
        meal_types = _meal_type_index(self.coordinator.data.get("meal_types"))
        for meal in meals:
            window = resolve_meal_time_windows(meal, meal_types)
            if not window:
                continue
            start, end = window
            events.append(self._meal_to_event(start, end, meal))
        events.sort(key=lambda event: event.start)
        return events

    def _meal_to_event(self, start: datetime, end: datetime, meal: dict[str, Any]) -> CalendarEvent:
        """Convert a meal dictionary to CalendarEvent."""
        summary = meal.get("recipe") or meal.get("name") or "Meal"
        return CalendarEvent(
            start=start,
            end=end,
            summary=summary,
            description=meal.get("name"),
            location=None,
        )


def _meal_type_index(meal_types: Optional[List[Dict[str, Any]]]) -> Dict[str, Dict[str, Any]]:
    """Create lookup dictionary for Paprika meal types."""
    if not meal_types:
        return {}
    return {entry["uid"]: entry for entry in meal_types if entry.get("uid")}

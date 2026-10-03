"""To-do platform for Paprika groceries."""

from __future__ import annotations

from typing import Iterable, List

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Paprika to-do list."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    client = data["client"]

    async_add_entities([PaprikaTodoList(coordinator, client, entry.entry_id)])


class PaprikaTodoList(CoordinatorEntity, TodoListEntity):
    """Paprika grocery list entity."""

    _attr_name = "Paprika Groceries"

    def __init__(self, coordinator, client, entry_id: str) -> None:
        """Initialize to-do list."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry_id}_groceries"
        self._attr_todo_items = self._build_todo_items()

    def _build_todo_items(self) -> List[TodoItem]:
        """Build the active Paprika grocery items exposed to Home Assistant."""
        items = []
        for grocery in self.coordinator.data.get("groceries", []):
            if grocery.get("deleted") or grocery.get("purchased"):
                continue
            items.append(
                TodoItem(
                    summary=grocery.get("name") or "Item",
                    uid=grocery.get("uid"),
                    status=TodoItemStatus.NEEDS_ACTION,
                    description=grocery.get("aisle"),
                )
            )
        return items

    @callback
    def _handle_coordinator_update(self) -> None:
        """Refresh the cached to-do items for HA 2026.8 and later."""
        self._attr_todo_items = self._build_todo_items()
        super()._handle_coordinator_update()

    async def async_get_items(self) -> List[TodoItem]:
        """Return active to-do items for compatibility with older HA releases."""
        return self._build_todo_items()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new item."""
        raise NotImplementedError

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Update an existing item."""
        raise NotImplementedError

    async def async_delete_todo_items(self, uids: Iterable[str]) -> None:
        """Delete items by UID."""
        raise NotImplementedError

"""To-do platform for Paprika groceries."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List
import uuid

from homeassistant.components.todo import (
    TodoItem,
    TodoItemStatus,
    TodoListEntity,
    TodoListEntityFeature,
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
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
    )

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

    def _groceries(self) -> List[Dict[str, Any]]:
        return self.coordinator.data.get("groceries", [])

    def _find(self, uid: str | None) -> Dict[str, Any]:
        for grocery in self._groceries():
            if grocery.get("uid") == uid:
                return dict(grocery)
        raise ValueError(f"Okänd Paprika-vara: {uid}")

    async def _save(self, groceries: List[Dict[str, Any]]) -> None:
        await self._client.async_save_groceries(groceries)
        # Show the change at once; the refresh is debounced for 10 s and then
        # picks up what the server filled in (e.g. aisle).
        saved = {g["uid"]: g for g in groceries}
        merged = [saved.pop(g.get("uid"), g) for g in self._groceries()]
        merged.extend(saved.values())
        self.coordinator.async_set_updated_data(
            {**self.coordinator.data, "groceries": merged}
        )
        await self.coordinator.async_request_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Create a new grocery on the same list as the existing ones."""
        name = item.summary or ""
        list_uid = next(
            (g.get("list_uid") for g in self._groceries() if g.get("list_uid")),
            None,
        )
        grocery = {
            "uid": str(uuid.uuid4()).upper(),
            "recipe_uid": None,
            "name": name,
            "order_flag": 0,
            "purchased": False,
            "aisle": "",
            "ingredient": name,
            "recipe": None,
            "instruction": "",
            "quantity": "",
            "separate": False,
            "aisle_uid": None,
            "list_uid": list_uid,
        }
        await self._save([grocery])

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Rename an item or mark it as purchased."""
        grocery = self._find(item.uid)
        if item.summary:
            grocery["name"] = item.summary
        grocery["purchased"] = item.status == TodoItemStatus.COMPLETED
        await self._save([grocery])

    async def async_delete_todo_items(self, uids: Iterable[str]) -> None:
        """Delete items by UID.

        Paprika's sync API has no real delete (DELETE returns 404 and a
        `deleted` flag is ignored), so removing an item marks it purchased.
        """
        groceries = [self._find(uid) for uid in uids]
        for grocery in groceries:
            grocery["purchased"] = True
        await self._save(groceries)

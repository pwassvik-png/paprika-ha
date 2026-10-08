"""To-do platform for Paprika groceries and pantry (köksskåp)."""

from __future__ import annotations

from datetime import date, datetime
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
from homeassistant.util import dt as dt_util

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

    async_add_entities(
        [
            PaprikaTodoList(coordinator, client, entry.entry_id),
            PaprikaPantryList(coordinator, client, entry.entry_id),
        ]
    )


def _merge_into_coordinator(
    coordinator, key: str, saved: List[Dict[str, Any]]
) -> None:
    """Show saved items at once; the refresh is debounced for 10 s and then
    picks up what the server filled in (e.g. aisle).

    Items flagged `deleted` are dropped from the local copy.
    """
    by_uid = {item["uid"]: item for item in saved}
    merged = [by_uid.pop(item.get("uid"), item) for item in coordinator.data.get(key, [])]
    merged.extend(by_uid.values())
    merged = [item for item in merged if not item.get("deleted")]
    coordinator.async_set_updated_data({**coordinator.data, key: merged})


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
        _merge_into_coordinator(self.coordinator, "groceries", groceries)
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


def _parse_expiration(item: Dict[str, Any]) -> date | None:
    value = item.get("expiration_date")
    if not item.get("has_expiration") or not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _format_expiration(due: date | datetime | None) -> str | None:
    if due is None:
        return None
    if isinstance(due, datetime):
        due = due.date()
    return due.strftime("%Y-%m-%d 00:00:00")


class PaprikaPantryList(CoordinatorEntity, TodoListEntity):
    """Paprika pantry (köksskåp) as a to-do list.

    Checked means out of stock, the description is the quantity and the due
    date is the expiration date.
    """

    _attr_name = "Paprika Pantry"
    _attr_icon = "mdi:fridge-outline"
    _attr_supported_features = (
        TodoListEntityFeature.CREATE_TODO_ITEM
        | TodoListEntityFeature.UPDATE_TODO_ITEM
        | TodoListEntityFeature.DELETE_TODO_ITEM
        | TodoListEntityFeature.SET_DESCRIPTION_ON_ITEM
        | TodoListEntityFeature.SET_DUE_DATE_ON_ITEM
    )

    def __init__(self, coordinator, client, entry_id: str) -> None:
        """Initialize pantry list."""
        super().__init__(coordinator)
        self._client = client
        self._attr_unique_id = f"{entry_id}_pantry"
        self._attr_todo_items = self._build_todo_items()

    def _pantry(self) -> List[Dict[str, Any]]:
        return self.coordinator.data.get("pantry", [])

    def _build_todo_items(self) -> List[TodoItem]:
        """Build pantry items, in stock first, sorted by name."""
        pantry = sorted(
            self._pantry(),
            key=lambda p: (not p.get("in_stock"), (p.get("ingredient") or "").lower()),
        )
        return [
            TodoItem(
                summary=item.get("ingredient") or "Vara",
                uid=item.get("uid"),
                status=TodoItemStatus.NEEDS_ACTION
                if item.get("in_stock")
                else TodoItemStatus.COMPLETED,
                description=item.get("quantity") or None,
                due=_parse_expiration(item),
            )
            for item in pantry
        ]

    @callback
    def _handle_coordinator_update(self) -> None:
        self._attr_todo_items = self._build_todo_items()
        super()._handle_coordinator_update()

    async def async_get_items(self) -> List[TodoItem]:
        return self._build_todo_items()

    def _find(self, uid: str | None) -> Dict[str, Any]:
        for item in self._pantry():
            if item.get("uid") == uid:
                return dict(item)
        raise ValueError(f"Okänd vara i köksskåpet: {uid}")

    async def _save(self, items: List[Dict[str, Any]]) -> None:
        await self._client.async_save_pantry(items)
        _merge_into_coordinator(self.coordinator, "pantry", items)
        await self.coordinator.async_request_refresh()

    async def async_create_todo_item(self, item: TodoItem) -> None:
        """Add an in-stock item, bought today."""
        expiration = _format_expiration(item.due)
        await self._save(
            [
                {
                    "uid": str(uuid.uuid4()).upper(),
                    "ingredient": item.summary or "",
                    "quantity": item.description or "",
                    "aisle": "",
                    "aisle_uid": None,
                    "in_stock": item.status != TodoItemStatus.COMPLETED,
                    "purchase_date": dt_util.now().strftime("%Y-%m-%d 00:00:00"),
                    "expiration_date": expiration,
                    "has_expiration": expiration is not None,
                    "location_uid": None,
                    "notes": None,
                }
            ]
        )

    async def async_update_todo_item(self, item: TodoItem) -> None:
        """Rename, change quantity or expiration, or toggle in stock.

        HA passes the whole item with the changes applied, so empty fields
        mean they were cleared.
        """
        pantry_item = self._find(item.uid)
        if item.summary:
            pantry_item["ingredient"] = item.summary
        pantry_item["quantity"] = item.description or ""
        pantry_item["in_stock"] = item.status != TodoItemStatus.COMPLETED
        expiration = _format_expiration(item.due)
        pantry_item["expiration_date"] = expiration
        pantry_item["has_expiration"] = expiration is not None
        await self._save([pantry_item])

    async def async_delete_todo_items(self, uids: Iterable[str]) -> None:
        """Delete for real; unlike groceries, pantry honours `deleted`."""
        items = [self._find(uid) for uid in uids]
        for item in items:
            item["deleted"] = True
        await self._save(items)

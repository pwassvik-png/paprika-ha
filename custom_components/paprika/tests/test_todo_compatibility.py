"""Regression tests for HA 2026.8 to-do entity updates."""
from dataclasses import dataclass
from pathlib import Path
import importlib.util
import sys
import types
import unittest

# Stub only the HA surface used by todo.py.
@dataclass
class TodoItem:
    summary: str | None = None
    uid: str | None = None
    status: str | None = None
    description: str | None = None

class TodoItemStatus:
    COMPLETED = "completed"
    NEEDS_ACTION = "needs_action"

class TodoListEntity:
    _attr_todo_items = None

class CoordinatorEntity:
    def __init__(self, coordinator):
        self.coordinator = coordinator
    def _handle_coordinator_update(self):
        self.super_update_called = True

mods = {
    "homeassistant": types.ModuleType("homeassistant"),
    "homeassistant.components": types.ModuleType("homeassistant.components"),
    "homeassistant.components.todo": types.ModuleType("homeassistant.components.todo"),
    "homeassistant.config_entries": types.ModuleType("homeassistant.config_entries"),
    "homeassistant.core": types.ModuleType("homeassistant.core"),
    "homeassistant.helpers": types.ModuleType("homeassistant.helpers"),
    "homeassistant.helpers.entity_platform": types.ModuleType("homeassistant.helpers.entity_platform"),
    "homeassistant.helpers.update_coordinator": types.ModuleType("homeassistant.helpers.update_coordinator"),
    "custom_components": types.ModuleType("custom_components"),
    "custom_components.paprika": types.ModuleType("custom_components.paprika"),
    "custom_components.paprika.const": types.ModuleType("custom_components.paprika.const"),
}
mods["homeassistant.components.todo"].TodoItem = TodoItem
mods["homeassistant.components.todo"].TodoItemStatus = TodoItemStatus
mods["homeassistant.components.todo"].TodoListEntity = TodoListEntity
mods["homeassistant.config_entries"].ConfigEntry = object
mods["homeassistant.core"].HomeAssistant = object
mods["homeassistant.core"].callback = lambda func: func
mods["homeassistant.helpers.entity_platform"].AddEntitiesCallback = object
mods["homeassistant.helpers.update_coordinator"].CoordinatorEntity = CoordinatorEntity
mods["custom_components.paprika.const"].DOMAIN = "paprika"
sys.modules.update(mods)

spec = importlib.util.spec_from_file_location(
    "custom_components.paprika.todo", Path(__file__).parents[1] / "todo.py"
)
todo = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = todo
spec.loader.exec_module(todo)

class Coordinator:
    def __init__(self, groceries): self.data = {"groceries": groceries}


class TodoCompatibilityTests(unittest.TestCase):
    def test_initializes_only_active_items_for_ha_todo_state(self):
        coordinator = Coordinator([
            {"uid":"1","name":"Mjölk","aisle":"Mejeri","purchased":False,"deleted":False},
            {"uid":"2","name":"Kaffe","aisle":"Dryck","purchased":True,"deleted":False},
            {"uid":"3","name":"Bröd","aisle":"Bageri","purchased":False,"deleted":True},
        ])
        entity = todo.PaprikaTodoList(coordinator, object(), "entry")
        self.assertEqual([item.summary for item in entity._attr_todo_items], ["Mjölk"])
        self.assertEqual(entity._attr_todo_items[0].status, TodoItemStatus.NEEDS_ACTION)

    def test_refreshes_items_when_coordinator_updates(self):
        coordinator = Coordinator([])
        entity = todo.PaprikaTodoList(coordinator, object(), "entry")
        coordinator.data["groceries"] = [
            {"uid":"4","name":"Ris","aisle":"Skafferi","purchased":False,"deleted":False}
        ]
        entity._handle_coordinator_update()
        self.assertEqual([item.summary for item in entity._attr_todo_items], ["Ris"])
        self.assertTrue(entity.super_update_called)


if __name__ == "__main__":
    unittest.main()

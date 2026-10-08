"""Paprika recipes: cache, search and the shape we read and write.

Kept free of Home Assistant imports so the logic can be tested on its own.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any, Callable, Dict, Iterable, List, Optional
import uuid

# Fields a create/update call may set directly on the Paprika recipe.
TEXT_FIELDS = (
    "name",
    "description",
    "servings",
    "prep_time",
    "cook_time",
    "total_time",
    "difficulty",
    "notes",
    "nutritional_info",
    "source",
    "source_url",
    "image_url",
)
LINE_FIELDS = ("ingredients", "directions")

# Paprika answers 429 when hammered; a full fetch is 230+ requests.
FETCH_CONCURRENCY = 2


class RecipeError(Exception):
    """A recipe could not be found, was ambiguous or had invalid input."""


def compute_hash(recipe: Dict[str, Any]) -> str:
    """Hash the recipe the way the apps use it: a changed hash means "re-sync"."""
    body = {k: v for k, v in recipe.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest().upper()


def _lines(text: Optional[str]) -> List[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _join(value: Any) -> str:
    """Accept a string or a list of lines."""
    if isinstance(value, (list, tuple)):
        return "\n".join(str(v) for v in value)
    return str(value or "")


def summarize(recipe: Dict[str, Any], categories: Dict[str, str]) -> Dict[str, Any]:
    """Short form used in search results."""
    return {
        "uid": recipe.get("uid"),
        "name": recipe.get("name"),
        "categories": [categories.get(c, c) for c in recipe.get("categories") or []],
        "rating": recipe.get("rating") or 0,
        "favorite": bool(recipe.get("on_favorites")),
        "servings": recipe.get("servings") or "",
        "total_time": recipe.get("total_time") or "",
    }


def full(recipe: Dict[str, Any], categories: Dict[str, str]) -> Dict[str, Any]:
    """Full form returned by get_recipe, with ingredients and steps as lists."""
    out = summarize(recipe, categories)
    out.update(
        {
            "ingredients": _lines(recipe.get("ingredients")),
            "directions": _lines(recipe.get("directions")),
            "description": recipe.get("description") or "",
            "notes": recipe.get("notes") or "",
            "prep_time": recipe.get("prep_time") or "",
            "cook_time": recipe.get("cook_time") or "",
            "source": recipe.get("source") or "",
            "source_url": recipe.get("source_url") or "",
            "photo_url": recipe.get("photo_url") or recipe.get("image_url") or "",
            "in_trash": bool(recipe.get("in_trash")),
        }
    )
    return out


def search(
    recipes: Iterable[Dict[str, Any]],
    query: str,
    *,
    in_ingredients: bool = False,
    include_trash: bool = False,
) -> List[Dict[str, Any]]:
    """Case-insensitive substring search on name (and optionally ingredients).

    Name matches come before ingredient matches; each group is sorted by name.
    """
    needle = query.strip().casefold()
    by_name, by_ingredient = [], []
    for recipe in recipes:
        if recipe.get("in_trash") and not include_trash:
            continue
        if needle in (recipe.get("name") or "").casefold():
            by_name.append(recipe)
        elif in_ingredients and needle in (recipe.get("ingredients") or "").casefold():
            by_ingredient.append(recipe)

    def key(recipe: Dict[str, Any]) -> str:
        return (recipe.get("name") or "").casefold()

    return sorted(by_name, key=key) + sorted(by_ingredient, key=key)


def resolve(recipes: Iterable[Dict[str, Any]], ref: str) -> Dict[str, Any]:
    """Find one recipe by uid, exact name, or a name fragment matching only one."""
    recipes = list(recipes)
    for recipe in recipes:
        if recipe.get("uid") == ref:
            return recipe
    wanted = ref.strip().casefold()
    exact = [r for r in recipes if (r.get("name") or "").casefold() == wanted]
    active = [r for r in exact if not r.get("in_trash")]
    if len(active) == 1 or (not active and len(exact) == 1):
        return (active or exact)[0]
    if len(exact) > 1:
        raise RecipeError(f"Flera recept heter '{ref}', ange uid")
    partial = search(recipes, ref)
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise RecipeError(f"Hittar inget recept som matchar '{ref}'")
    names = ", ".join(r.get("name") or "?" for r in partial[:5])
    raise RecipeError(f"'{ref}' matchar flera recept: {names}")


def category_uids(names: Iterable[str], categories: Dict[str, str]) -> List[str]:
    """Map category names (case-insensitive) to uids; unknown names are errors."""
    by_name = {name.casefold(): uid for uid, name in categories.items()}
    uids, unknown = [], []
    for name in names:
        uid = by_name.get(name.strip().casefold())
        (uids if uid else unknown).append(uid or name)
    if unknown:
        raise RecipeError(
            f"Okänd kategori: {', '.join(unknown)}. Finns: {', '.join(sorted(categories.values()))}"
        )
    return uids


def apply_fields(
    recipe: Dict[str, Any], fields: Dict[str, Any], categories: Dict[str, str]
) -> Dict[str, Any]:
    """Return a copy of `recipe` with the given service fields applied."""
    recipe = dict(recipe)
    for key in TEXT_FIELDS:
        if key in fields:
            recipe[key] = str(fields[key] or "")
    for key in LINE_FIELDS:
        if key in fields:
            recipe[key] = _join(fields[key])
    if "categories" in fields:
        recipe["categories"] = category_uids(fields["categories"], categories)
    if "rating" in fields:
        recipe["rating"] = int(fields["rating"])
    if "favorite" in fields:
        recipe["on_favorites"] = bool(fields["favorite"])
    if not (recipe.get("name") or "").strip():
        raise RecipeError("Receptet måste ha ett namn")
    recipe["hash"] = compute_hash(recipe)
    return recipe


def new_recipe(
    fields: Dict[str, Any], categories: Dict[str, str], created: str
) -> Dict[str, Any]:
    """Build a complete new Paprika recipe from service fields."""
    base = {
        "uid": str(uuid.uuid4()).upper(),
        "name": "",
        "ingredients": "",
        "directions": "",
        "description": "",
        "notes": "",
        "nutritional_info": "",
        "servings": "",
        "difficulty": "",
        "prep_time": "",
        "cook_time": "",
        "total_time": "",
        "source": "",
        "source_url": "",
        "image_url": None,
        "photo": None,
        "photo_hash": None,
        "photo_large": None,
        "photo_url": None,
        "scale": None,
        "categories": [],
        "rating": 0,
        "in_trash": False,
        "is_pinned": False,
        "on_favorites": False,
        "on_grocery_list": False,
        "created": created,
    }
    return apply_fields(base, fields, categories)


class RecipeStore:
    """Cache of full recipes, refreshed only where Paprika's hash changed.

    `on_change` gets a snapshot (see `restore`) whenever the cache changed,
    so it can be persisted and a restart does not fetch every recipe again.
    """

    def __init__(
        self, client, on_change: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> None:
        self._client = client
        self._on_change = on_change
        self._recipes: Dict[str, Dict[str, Any]] = {}
        self.categories: Dict[str, str] = {}
        self._lock = asyncio.Lock()

    @property
    def recipes(self) -> List[Dict[str, Any]]:
        return list(self._recipes.values())

    def snapshot(self) -> Dict[str, Any]:
        return {"recipes": dict(self._recipes), "categories": dict(self.categories)}

    def restore(self, data: Optional[Dict[str, Any]]) -> None:
        if data:
            self._recipes = dict(data.get("recipes") or {})
            self.categories = dict(data.get("categories") or {})

    def _changed(self) -> None:
        if self._on_change:
            self._on_change(self.snapshot())

    async def async_refresh(self, index: Optional[List[Dict[str, Any]]] = None) -> None:
        """Bring the cache up to date with the server.

        `index` is the `sync/recipes/` list if the caller already has it.
        Recipes fetched before an error are kept; the first error is raised
        after the rest have been tried.
        """
        async with self._lock:
            if index is None:
                index, categories = await asyncio.gather(
                    self._client.async_fetch_recipes(),
                    self._client.async_fetch_categories(),
                )
            else:
                categories = await self._client.async_fetch_categories()
            categories = {c["uid"]: c.get("name") or "" for c in categories}
            changed = categories != self.categories
            self.categories = categories
            wanted = {item["uid"]: item.get("hash") for item in index}
            for uid in set(self._recipes) - set(wanted):
                del self._recipes[uid]
                changed = True
            stale = [
                uid
                for uid, hash_ in wanted.items()
                if self._recipes.get(uid, {}).get("hash") != hash_
            ]
            semaphore = asyncio.Semaphore(FETCH_CONCURRENCY)

            async def fetch(uid: str) -> None:
                async with semaphore:
                    self._recipes[uid] = await self._client.async_fetch_recipe(uid)

            results = await asyncio.gather(
                *(fetch(uid) for uid in stale), return_exceptions=True
            )
            errors = [r for r in results if isinstance(r, BaseException)]
            if changed or len(errors) < len(stale):
                self._changed()
            if errors:
                raise errors[0]

    async def async_save(self, recipe: Dict[str, Any]) -> None:
        await self._client.async_save_recipe(recipe)
        self._recipes[recipe["uid"]] = recipe
        self._changed()

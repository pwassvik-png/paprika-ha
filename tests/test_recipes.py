"""Tests for the HA-free recipe logic."""
from pathlib import Path
import importlib.util
import sys
import unittest

spec = importlib.util.spec_from_file_location(
    "paprika_recipes", Path(__file__).parents[1] / "custom_components" / "paprika" / "recipes.py"
)
recipes = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = recipes
spec.loader.exec_module(recipes)

CATS = {"C1": "Gryta", "C2": "Vegetariskt"}


def recipe(uid, name, **extra):
    r = {"uid": uid, "name": name, "ingredients": "", "directions": "",
         "categories": [], "in_trash": False, "rating": 0, "on_favorites": False}
    r.update(extra)
    r["hash"] = recipes.compute_hash(r)
    return r


GRYTA = recipe("G", "Kycklinggryta", ingredients="500 g kyckling\n\n2 dl grädde",
               directions="Bryn.\nKoka.", categories=["C1"], rating=4)
SOPPA = recipe("S", "Linssoppa", ingredients="2 dl linser\n1 kycklingbuljongtärning",
               categories=["C2"])
GAMMAL = recipe("T", "Kycklingsallad", in_trash=True)
ALL = [SOPPA, GRYTA, GAMMAL]


class SearchTests(unittest.TestCase):
    def test_name_match_skips_trash(self):
        self.assertEqual([r["uid"] for r in recipes.search(ALL, "kyckling")], ["G"])

    def test_ingredient_matches_come_after_name_matches(self):
        hits = recipes.search(ALL, "KYCKLING", in_ingredients=True)
        self.assertEqual([r["uid"] for r in hits], ["G", "S"])

    def test_include_trash(self):
        hits = recipes.search(ALL, "kyckling", include_trash=True)
        self.assertEqual([r["uid"] for r in hits], ["G", "T"])

    def test_empty_query_lists_all_active_sorted(self):
        self.assertEqual([r["uid"] for r in recipes.search(ALL, "")], ["G", "S"])


class ResolveTests(unittest.TestCase):
    def test_by_uid_even_in_trash(self):
        self.assertIs(recipes.resolve(ALL, "T"), GAMMAL)

    def test_by_exact_name_ignoring_case(self):
        self.assertIs(recipes.resolve(ALL, "linssoppa"), SOPPA)

    def test_by_unique_fragment(self):
        self.assertIs(recipes.resolve(ALL, "gryta"), GRYTA)

    def test_exact_name_prefers_active_copy(self):
        old = recipe("X", "Linssoppa", in_trash=True)
        self.assertIs(recipes.resolve(ALL + [old], "Linssoppa"), SOPPA)

    def test_ambiguous_and_missing_raise(self):
        with self.assertRaisesRegex(recipes.RecipeError, "flera"):
            recipes.resolve(ALL, "a")
        with self.assertRaisesRegex(recipes.RecipeError, "Hittar inget"):
            recipes.resolve(ALL, "pizza")


class ShapeTests(unittest.TestCase):
    def test_full_splits_lines_and_names_categories(self):
        out = recipes.full(GRYTA, CATS)
        self.assertEqual(out["ingredients"], ["500 g kyckling", "2 dl grädde"])
        self.assertEqual(out["directions"], ["Bryn.", "Koka."])
        self.assertEqual(out["categories"], ["Gryta"])
        self.assertEqual(out["rating"], 4)


class WriteTests(unittest.TestCase):
    def test_new_recipe_is_complete_and_hashed(self):
        r = recipes.new_recipe(
            {"name": "Pannkakor", "ingredients": ["3 dl mjöl", "6 dl mjölk"],
             "directions": "Vispa.", "categories": ["vegetariskt"], "rating": 5},
            CATS, "2026-10-08 12:00:00",
        )
        self.assertEqual(r["ingredients"], "3 dl mjöl\n6 dl mjölk")
        self.assertEqual(r["categories"], ["C2"])
        self.assertEqual(r["created"], "2026-10-08 12:00:00")
        self.assertEqual(r["uid"], r["uid"].upper())
        self.assertFalse(r["in_trash"])
        self.assertEqual(r["hash"], recipes.compute_hash(r))

    def test_update_keeps_other_fields_and_changes_hash(self):
        r = recipes.apply_fields(GRYTA, {"servings": "6", "favorite": True}, CATS)
        self.assertEqual(r["servings"], "6")
        self.assertTrue(r["on_favorites"])
        self.assertEqual(r["ingredients"], GRYTA["ingredients"])
        self.assertNotEqual(r["hash"], GRYTA["hash"])
        self.assertNotIn("servings", GRYTA)

    def test_unknown_category_and_empty_name_raise(self):
        with self.assertRaisesRegex(recipes.RecipeError, "Okänd kategori: Pizza"):
            recipes.apply_fields(GRYTA, {"categories": ["Pizza"]}, CATS)
        with self.assertRaisesRegex(recipes.RecipeError, "namn"):
            recipes.new_recipe({"name": " "}, CATS, "x")


class Client:
    def __init__(self, index):
        self.index, self.fetched, self.saved = index, [], []
    async def async_fetch_recipes(self):
        return [{"uid": r["uid"], "hash": r["hash"]} for r in self.index]
    async def async_fetch_categories(self):
        return [{"uid": k, "name": v} for k, v in CATS.items()]
    async def async_fetch_recipe(self, uid):
        self.fetched.append(uid)
        return next(r for r in self.index if r["uid"] == uid)
    async def async_save_recipe(self, r):
        self.saved.append(r)


class StoreTests(unittest.IsolatedAsyncioTestCase):
    async def test_refetches_only_changed_and_drops_removed(self):
        client = Client([GRYTA, SOPPA])
        store = recipes.RecipeStore(client)
        await store.async_refresh()
        self.assertEqual(sorted(client.fetched), ["G", "S"])
        self.assertEqual(store.categories, CATS)

        changed = recipes.apply_fields(SOPPA, {"servings": "4"}, CATS)
        client.index = [changed]
        client.fetched = []
        await store.async_refresh()
        self.assertEqual(client.fetched, ["S"])
        self.assertEqual([r["servings"] for r in store.recipes], ["4"])

    async def test_keeps_fetched_recipes_when_some_fail(self):
        client = Client([GRYTA, SOPPA])
        real_fetch = client.async_fetch_recipe

        async def flaky(uid):
            if uid == "S":
                raise RuntimeError("429")
            return await real_fetch(uid)

        client.async_fetch_recipe = flaky
        snapshots = []
        store = recipes.RecipeStore(client, on_change=snapshots.append)
        with self.assertRaisesRegex(RuntimeError, "429"):
            await store.async_refresh()
        self.assertEqual([r["uid"] for r in store.recipes], ["G"])
        self.assertEqual(list(snapshots[-1]["recipes"]), ["G"])

    async def test_restored_cache_is_not_refetched(self):
        first = recipes.RecipeStore(Client([GRYTA, SOPPA]))
        await first.async_refresh()
        client = Client([GRYTA, SOPPA])
        snapshots = []
        store = recipes.RecipeStore(client, on_change=snapshots.append)
        store.restore(first.snapshot())
        await store.async_refresh()
        self.assertEqual(client.fetched, [])
        self.assertEqual(snapshots, [])
        self.assertEqual(len(store.recipes), 2)

    async def test_save_reports_change(self):
        snapshots = []
        store = recipes.RecipeStore(Client([]), on_change=snapshots.append)
        new = recipes.new_recipe({"name": "Ny"}, CATS, "x")
        await store.async_save(new)
        self.assertIn(new["uid"], snapshots[-1]["recipes"])

    async def test_uses_index_from_caller(self):
        client = Client([GRYTA, SOPPA])
        store = recipes.RecipeStore(client)
        await store.async_refresh([{"uid": "S", "hash": SOPPA["hash"]}])
        self.assertEqual(client.fetched, ["S"])
        self.assertEqual(store.categories, CATS)

    async def test_saved_recipe_is_not_refetched(self):
        client = Client([GRYTA])
        store = recipes.RecipeStore(client)
        await store.async_refresh()
        new = recipes.new_recipe({"name": "Ny"}, CATS, "x")
        await store.async_save(new)
        client.index = [GRYTA, new]
        client.fetched = []
        await store.async_refresh()
        self.assertEqual(client.fetched, [])
        self.assertEqual(client.saved, [new])


if __name__ == "__main__":
    unittest.main()

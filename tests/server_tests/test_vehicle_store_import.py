import tempfile
import unittest
from pathlib import Path

from server.importers.z21_parser import Z21Importer
from server.vehicle_store import VehicleStore


class VehicleStoreImportTest(unittest.TestCase):
  def test_import_batch_replaces_z21_data_without_losing_manual_categories(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      manual_category = store.create_category({"name": "收藏"})
      imported = store.replace_imported_z21_data(
        {
          "file_name": "HO.z21",
          "vehicles_imported": 1,
          "functions_imported": 1,
          "consists_imported": 0,
          "images_imported": 0,
          "warnings": [],
        },
        [{
          "id": "z21-vehicle-1",
          "source": "z21",
          "source_vehicle_id": "1",
          "name": "Z21 车",
          "address": 33,
          "category_ids": ["z21-category-7"],
        }],
        [{
          "id": "z21-category-7",
          "source": "z21",
          "source_category_id": "7",
          "name": "货运",
        }],
        [{
          "vehicle_id": "z21-vehicle-1",
          "function_number": 0,
          "label": "灯",
          "icon_name": "main_beam",
        }],
        [],
      )
      self.assertEqual(imported["vehicles_imported"], 1)
      self.assertEqual(store.list_categories()[0]["name"], "收藏")
      self.assertEqual(store.get_vehicle("z21-vehicle-1")["categories"][0]["name"], "货运")

  def test_import_batch_replaces_only_same_track_mode_z21_data(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      store.replace_imported_z21_data(
        {"file_name": "HO.z21", "track_mode": "ho", "vehicles_imported": 1},
        [{
          "id": "z21-ho-vehicle-1",
          "source": "z21",
          "source_vehicle_id": "1",
          "name": "HO 车",
          "address": 3,
          "track_mode": "ho",
          "category_ids": ["z21-ho-category-1"],
        }],
        [{"id": "z21-ho-category-1", "source": "z21", "track_mode": "ho", "name": "HO 分类"}],
        [],
        [],
      )
      store.replace_imported_z21_data(
        {"file_name": "N.z21", "track_mode": "n", "vehicles_imported": 1},
        [{
          "id": "z21-n-vehicle-1",
          "source": "z21",
          "source_vehicle_id": "1",
          "name": "N 车",
          "address": 4,
          "track_mode": "n",
          "category_ids": ["z21-n-category-1"],
        }],
        [{"id": "z21-n-category-1", "source": "z21", "track_mode": "n", "name": "N 分类"}],
        [],
        [],
      )
      store.replace_imported_z21_data(
        {"file_name": "HO.z21", "track_mode": "ho", "vehicles_imported": 1},
        [{
          "id": "z21-ho-vehicle-2",
          "source": "z21",
          "source_vehicle_id": "2",
          "name": "HO 新车",
          "address": 5,
          "track_mode": "ho",
          "category_ids": ["z21-ho-category-2"],
        }],
        [{"id": "z21-ho-category-2", "source": "z21", "track_mode": "ho", "name": "HO 新分类"}],
        [],
        [],
      )
      vehicles = store.list_vehicles()
      self.assertEqual([vehicle["name"] for vehicle in vehicles], ["HO 新车", "N 车"])
      self.assertIsNone(store.get_vehicle("z21-ho-vehicle-1"))
      self.assertEqual(store.get_vehicle("z21-n-vehicle-1")["track_mode"], "n")

  def test_z21_categories_are_shared_by_name_across_track_modes(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      store.replace_imported_z21_data(
        {"file_name": "HO.z21", "track_mode": "ho", "vehicles_imported": 1},
        [{
          "id": "z21-ho-vehicle-1",
          "source": "z21",
          "source_vehicle_id": "1",
          "name": "HO 车",
          "address": 3,
          "track_mode": "ho",
          "category_ids": ["z21-ho-category-1"],
        }],
        [{"id": "z21-ho-category-1", "source": "z21", "track_mode": "ho", "name": "内燃机车", "source_category_id": "1"}],
        [],
        [],
      )
      store.replace_imported_z21_data(
        {"file_name": "N.z21", "track_mode": "n", "vehicles_imported": 1},
        [{
          "id": "z21-n-vehicle-1",
          "source": "z21",
          "source_vehicle_id": "1",
          "name": "N 车",
          "address": 4,
          "track_mode": "n",
          "category_ids": ["z21-n-category-2"],
        }],
        [{"id": "z21-n-category-2", "source": "z21", "track_mode": "n", "name": "内燃机车", "source_category_id": "2"}],
        [],
        [],
      )
      categories = [category for category in store.list_categories() if category["name"] == "内燃机车"]
      self.assertEqual(len(categories), 1)
      self.assertEqual(store.get_vehicle("z21-ho-vehicle-1")["category_ids"], [categories[0]["id"]])
      self.assertEqual(store.get_vehicle("z21-n-vehicle-1")["category_ids"], [categories[0]["id"]])

  def test_existing_z21_category_duplicates_are_merged_by_name_on_initialize(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      db_path = Path(temp_dir) / "vehicles.sqlite3"
      store = VehicleStore(db_path)
      ho = store.create_vehicle({"id": "z21-ho-vehicle-1", "source": "z21", "name": "HO", "address": 3, "track_mode": "ho"})
      n = store.create_vehicle({"id": "z21-n-vehicle-1", "source": "z21", "name": "N", "address": 4, "track_mode": "n"})
      with store._connect() as con:
        con.execute(
          "INSERT INTO categories (id, source, source_category_id, track_mode, name, description, sort_order, created_at, updated_at) VALUES (?, 'z21', ?, ?, ?, '', 0, 'old', 'old')",
          ("z21-ho-category-1", "1", "ho", "内燃机车"),
        )
        con.execute(
          "INSERT INTO categories (id, source, source_category_id, track_mode, name, description, sort_order, created_at, updated_at) VALUES (?, 'z21', ?, ?, ?, '', 0, 'old', 'old')",
          ("z21-n-category-2", "2", "n", "内燃机车"),
        )
        con.execute("INSERT INTO vehicle_categories (vehicle_id, category_id) VALUES (?, ?)", (ho["id"], "z21-ho-category-1"))
        con.execute("INSERT INTO vehicle_categories (vehicle_id, category_id) VALUES (?, ?)", (n["id"], "z21-n-category-2"))

      migrated = VehicleStore(db_path)
      categories = [category for category in migrated.list_categories() if category["name"] == "内燃机车"]
      self.assertEqual(len(categories), 1)
      self.assertEqual(migrated.get_vehicle(ho["id"])["category_ids"], [categories[0]["id"]])
      self.assertEqual(migrated.get_vehicle(n["id"])["category_ids"], [categories[0]["id"]])

  def test_real_z21_import_persists_categories_and_float_function_times(self):
    sample = Path("tests/fixtures/z21/HO.z21")
    self.assertTrue(sample.exists(), f"fixture is missing: {sample}")
    with tempfile.TemporaryDirectory() as temp_dir:
      result = Z21Importer(Path(temp_dir) / "vehicle-images").import_file(sample)
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      store.replace_imported_z21_data(
        result.summary,
        result.vehicles,
        result.categories,
        result.functions,
        result.consists,
      )
      categories = store.list_categories()
      vehicles = store.list_vehicles()
      self.assertEqual(len(categories), result.summary["categories_imported"])
      self.assertGreater(sum(1 for vehicle in vehicles if vehicle.get("category_ids")), 0)
      self.assertTrue(all(category["track_mode"] == "" for category in categories if category["source"] == "z21"))
      first_categorized = next(vehicle for vehicle in vehicles if vehicle.get("category_ids"))
      self.assertGreater(len(first_categorized["categories"]), 0)


if __name__ == "__main__":
  unittest.main()

import tempfile
import unittest
from pathlib import Path

from server.importers.base import ConfigImportResult, ImportSource
from server.vehicle_store import VehicleStore


class ImportPersistenceContractTest(unittest.TestCase):
  def test_import_persistence_lives_inside_vehicle_store(self):
    vehicle_store_source = Path("server/vehicle_store.py").read_text(encoding="utf-8")
    importer_sources = "\n".join(
      path.read_text(encoding="utf-8")
      for path in Path("server/importers").glob("*.py")
    )

    self.assertIn("def _persist_import_result(", vehicle_store_source)
    self.assertIn("self._persist_import_result", vehicle_store_source)
    self.assertNotIn("_insert_vehicle(", importer_sources)
    self.assertNotIn("_replace_vehicle_functions(", importer_sources)
    self.assertNotIn("_upsert_import_category(", importer_sources)

  def test_replace_imported_config_data_uses_source_format_not_z21_method(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="sample", label="Sample"),
        vehicles=[{
          "id": "sample-vehicle-3",
          "source": "sample",
          "source_vehicle_id": "3",
          "track_mode": "ho",
          "name": "Sample 3",
          "address": 3,
          "type": 0,
        }],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "sample.config", "track_mode": "ho"},
        warnings=[],
        errors=[],
      )

      store.replace_imported_config_data(result)
      vehicles = store.list_vehicles()

      self.assertEqual(len(vehicles), 1)
      self.assertEqual(vehicles[0]["source_format"], "sample_layout_config")
      self.assertEqual(vehicles[0]["source_key"], "sample")

  def test_shared_category_strategy_is_source_format_agnostic(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(
          format="sample_layout_config",
          key="sample",
          label="Sample",
          category_merge_strategy="shared_by_normalized_name",
        ),
        vehicles=[
          {
            "id": "sample-ho-3",
            "source_vehicle_id": "3",
            "track_mode": "ho",
            "name": "HO 3",
            "address": 3,
            "type": 0,
            "category_ids": ["sample-ho-cat"],
          },
          {
            "id": "sample-n-3",
            "source_vehicle_id": "3",
            "track_mode": "n",
            "name": "N 3",
            "address": 3,
            "type": 0,
            "category_ids": ["sample-n-cat"],
          },
        ],
        functions=[],
        categories=[
          {"id": "sample-ho-cat", "track_mode": "ho", "name": "内燃机车", "source_category_id": "1"},
          {"id": "sample-n-cat", "track_mode": "n", "name": "内燃机车", "source_category_id": "2"},
        ],
        consists=[],
        summary={"file_name": "sample.config", "track_mode": ""},
        warnings=[],
        errors=[],
      )

      store.replace_imported_config_data(result)
      categories = store.list_categories()

      self.assertEqual(len(categories), 1)
      self.assertEqual(categories[0]["source_format"], "sample_layout_config")
      self.assertEqual(categories[0]["source_key"], "sample")
      self.assertEqual(store.get_vehicle("sample-ho-3")["category_ids"], [categories[0]["id"]])
      self.assertEqual(store.get_vehicle("sample-n-3")["category_ids"], [categories[0]["id"]])

  def test_replace_scope_limits_replacement_to_declared_track_modes(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      first_result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="sample", label="Sample"),
        vehicles=[
          {"id": "sample-ho-old", "source_vehicle_id": "3", "track_mode": "ho", "name": "旧 HO", "address": 3, "type": 0},
          {"id": "sample-n-keep", "source_vehicle_id": "4", "track_mode": "n", "name": "保留 N", "address": 4, "type": 0},
        ],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "sample.config", "track_mode": ""},
        warnings=[],
        errors=[],
      )
      replacement_result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="sample", label="Sample"),
        vehicles=[{"id": "sample-ho-new", "source_vehicle_id": "5", "track_mode": "ho", "name": "新 HO", "address": 5, "type": 0}],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "sample.config", "track_mode": ""},
        warnings=[],
        errors=[],
        replace_scope={"track_modes": ["ho"]},
      )

      store.replace_imported_config_data(first_result)
      store.replace_imported_config_data(replacement_result)
      names = {vehicle["name"] for vehicle in store.list_vehicles()}

      self.assertEqual(names, {"新 HO", "保留 N"})
      self.assertIsNone(store.get_vehicle("sample-ho-old"))
      self.assertIsNotNone(store.get_vehicle("sample-n-keep"))

  def test_replacement_without_replace_scope_does_not_infer_track_mode_from_summary(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      first_result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="sample", label="Sample"),
        vehicles=[
          {"id": "sample-ho-old", "source_vehicle_id": "3", "track_mode": "ho", "name": "旧 HO", "address": 3, "type": 0},
          {"id": "sample-n-old", "source_vehicle_id": "4", "track_mode": "n", "name": "旧 N", "address": 4, "type": 0},
        ],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "sample.config", "track_mode": ""},
        warnings=[],
        errors=[],
      )
      replacement_result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="sample", label="Sample"),
        vehicles=[{"id": "sample-ho-new", "source_vehicle_id": "5", "track_mode": "ho", "name": "新 HO", "address": 5, "type": 0}],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "sample.config", "track_mode": "ho"},
        warnings=[],
        errors=[],
      )

      store.replace_imported_config_data(first_result)
      store.replace_imported_config_data(replacement_result)
      names = {vehicle["name"] for vehicle in store.list_vehicles()}

      self.assertEqual(names, {"新 HO"})
      self.assertIsNone(store.get_vehicle("sample-ho-old"))
      self.assertIsNone(store.get_vehicle("sample-n-old"))

  def test_replacement_defaults_to_same_source_key(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      alpha_result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="alpha", label="Alpha"),
        vehicles=[{"id": "alpha-old", "source_vehicle_id": "3", "track_mode": "ho", "name": "Alpha Old", "address": 3, "type": 0}],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "alpha.config", "track_mode": "ho"},
        warnings=[],
        errors=[],
      )
      beta_result = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="beta", label="Beta"),
        vehicles=[{"id": "beta-keep", "source_vehicle_id": "4", "track_mode": "ho", "name": "Beta Keep", "address": 4, "type": 0}],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "beta.config", "track_mode": "ho"},
        warnings=[],
        errors=[],
      )
      alpha_replacement = ConfigImportResult(
        format="sample_layout_config",
        source=ImportSource(format="sample_layout_config", key="alpha", label="Alpha"),
        vehicles=[{"id": "alpha-new", "source_vehicle_id": "5", "track_mode": "ho", "name": "Alpha New", "address": 5, "type": 0}],
        functions=[],
        categories=[],
        consists=[],
        summary={"file_name": "alpha.config", "track_mode": "ho"},
        warnings=[],
        errors=[],
      )

      store.replace_imported_config_data(alpha_result)
      store.replace_imported_config_data(beta_result)
      store.replace_imported_config_data(alpha_replacement)
      names = {vehicle["name"] for vehicle in store.list_vehicles()}

      self.assertEqual(names, {"Alpha New", "Beta Keep"})
      self.assertIsNone(store.get_vehicle("alpha-old"))
      self.assertIsNotNone(store.get_vehicle("beta-keep"))


if __name__ == "__main__":
  unittest.main()

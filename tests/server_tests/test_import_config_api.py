import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from server.app_state import AppStateStore
from server.importers.base import ConfigImportRequest, ConfigImportResult, ImportFormatDescriptor, ImportSource
from server.importers.registry import ImportRegistry
from tests.server_tests.controller_test_env import temporary_vehicle_router


class FakeImporter:
  descriptor = ImportFormatDescriptor(format="fake_layout_config", label="Fake", extensions=[".fake"])

  def __init__(self):
    self.last_request = None

  def import_bytes(self, request: ConfigImportRequest) -> ConfigImportResult:
    self.last_request = request
    return ConfigImportResult(
      format=request.format,
      source=ImportSource(format=request.format, key="fake", label="Fake"),
      vehicles=[{"id": "fake-1", "name": "Fake Loco", "address": 3, "type": 0}],
      functions=[],
      categories=[],
      consists=[],
      summary={"vehicles_imported": 1, "file_name": request.file_name},
      warnings=[],
      errors=[],
    )


class ImportConfigApiTest(unittest.TestCase):
  def test_registry_rejects_unknown_format(self):
    registry = ImportRegistry()
    with self.assertRaises(ValueError):
      registry.get("missing_layout_config")

  def test_import_config_uses_requested_format(self):
    with TemporaryDirectory() as temp_dir:
      state_store = AppStateStore(Path(temp_dir) / "app-state.json")
      registry = ImportRegistry()
      registry.register(FakeImporter())
      with temporary_vehicle_router(
        state_store=state_store,
        image_dir=Path(temp_dir) / "images",
        import_registry=registry,
      ) as (router, vehicle_store, state):
        body, status = router.import_config_bytes("fake_layout_config", "demo.fake", b"fake-bytes", state)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["summary"]["vehicles_imported"], 1)
        self.assertEqual(vehicle_store.list_vehicles()[0]["id"], "fake-1")
        self.assertEqual(state_store.load()["vehicles"], [])

  def test_import_config_passes_options_to_importer(self):
    with TemporaryDirectory() as temp_dir:
      state_store = AppStateStore(Path(temp_dir) / "app-state.json")
      registry = ImportRegistry()
      importer = FakeImporter()
      registry.register(importer)
      with temporary_vehicle_router(
        state_store=state_store,
        image_dir=Path(temp_dir) / "images",
        import_registry=registry,
      ) as (router, _vehicle_store, state):
        body, status = router.import_config_bytes(
          "fake_layout_config",
          "demo.fake",
          b"fake-bytes",
          state,
          options={"track_mode": "ho", "replace": "same_track_mode"},
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(importer.last_request.options, {"track_mode": "ho", "replace": "same_track_mode"})

  def test_import_config_with_vehicle_store_accepts_non_z21_format(self):
    with TemporaryDirectory() as temp_dir:
      state_store = AppStateStore(Path(temp_dir) / "app-state.json")
      registry = ImportRegistry()
      registry.register(FakeImporter())
      with temporary_vehicle_router(
        state_store=state_store,
        image_dir=Path(temp_dir) / "images",
        import_registry=registry,
      ) as (router, vehicle_store, _default_state):
        state = state_store.load()
        body, status = router.import_config_bytes("fake_layout_config", "demo.fake", b"fake-bytes", state)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        vehicles = vehicle_store.list_vehicles()
        self.assertEqual(vehicles[0]["source_format"], "fake_layout_config")
        self.assertEqual(vehicles[0]["source_key"], "fake")


if __name__ == "__main__":
  unittest.main()

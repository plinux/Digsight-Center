import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from server.api import ApiRouter
from server.app_state import AppStateStore
from server.importers.base import ConfigImportRequest, ConfigImportResult, ImportFormatDescriptor
from server.importers.registry import ImportRegistry


class FakeImporter:
  descriptor = ImportFormatDescriptor(format="fake_layout_config", label="Fake", extensions=[".fake"])

  def import_bytes(self, request: ConfigImportRequest) -> ConfigImportResult:
    return ConfigImportResult(
      format=request.format,
      vehicles=[{"id": "fake-1", "name": "Fake Loco", "address": 3, "type": 0}],
      functions=[],
      categories=[],
      consists=[],
      images=[],
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
      router = ApiRouter(state_store, image_dir=Path(temp_dir) / "images", import_registry=registry)
      state = state_store.load()
      body, status = router.import_config_bytes("fake_layout_config", "demo.fake", b"fake-bytes", state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(payload["data"]["summary"]["vehicles_imported"], 1)
      self.assertEqual(state["vehicles"][0]["id"], "fake-1")


if __name__ == "__main__":
  unittest.main()

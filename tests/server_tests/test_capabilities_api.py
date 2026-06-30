import json
import tempfile
import unittest
from pathlib import Path

from server import models
from server.api import ApiRouter
from server.app_state import AppStateStore, default_state
from server.controllers.example import ExampleControllerAdapter
from server.controllers.registry import ControllerRegistry
from server.importers.example import ExampleConfigImporter
from server.importers.registry import ImportRegistry


class CapabilitiesApiTest(unittest.TestCase):
  def test_capabilities_payload_exposes_controller_and_import_descriptors(self):
    router = ApiRouter(None)
    body, status = router.handle_json(
      "GET",
      "/api/capabilities",
      b"",
      default_state(),
    )

    self.assertEqual(status, 200)
    payload = json.loads(body)
    self.assertTrue(payload["ok"])
    data = payload["data"]
    self.assertEqual(data["default_controller_kind"], "digsight_controller")
    self.assertEqual(data["default_import_format"], "z21_layout_config")
    self.assertEqual([item["kind"] for item in data["controllers"]], ["digsight_controller"])
    self.assertEqual([item["format"] for item in data["import_formats"]], ["z21_layout_config"])
    self.assertNotIn("example_controller", [item["kind"] for item in data["controllers"]])
    self.assertNotIn("example_layout_config", [item["format"] for item in data["import_formats"]])
    self.assertEqual(data["controllers"][0]["kind"], "digsight_controller")
    self.assertEqual(data["controllers"][0]["label"], "动芯 拾Pro")
    self.assertEqual(data["controllers"][0]["display_name"], "动芯 拾Pro")
    self.assertEqual(data["controllers"][0]["protocol"], "DXDCNet")
    self.assertEqual(data["controllers"][0]["default_ip"], models.CONTROLLER_DEFAULT_IP)
    self.assertTrue(data["controllers"][0]["capabilities"]["track_power"])
    self.assertTrue(data["controllers"][0]["capabilities"]["dc_control"])
    self.assertEqual(data["controllers"][0]["transport_descriptor"], {
      "kind": "udp",
      "defaults": {
        "udp_port": 12000,
        "local_udp_port": 6667,
        "udp_checksum_algorithm": "xor",
      },
      "metadata": {
        "checksum_algorithms": ["xor"],
        "allow_zero_local_udp_port": False,
      },
      "endpoint_readiness": {
        "required_paths": ["transport.udp_port"],
      },
    })
    self.assertEqual(data["controllers"][0]["endpoint_readiness"], {
      "required_paths": ["transport.udp_port"],
    })
    self.assertEqual(data["import_formats"][0]["format"], "z21_layout_config")
    self.assertIn(".z21", data["import_formats"][0]["extensions"])
    self.assertEqual(data["import_formats"][0]["function_icon_mapping_files"], ["/config/function-icon-mappings/z21.json"])

  def test_capabilities_controller_label_comes_from_controller_config_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / "Digsight_D9000.json").write_text(json.dumps({
        "display_name": "展厅控制器",
        "protocol": "DXDCNet",
        "ip": "0.0.0.0",
        "transport": {
          "kind": "udp",
          "udp_port": 12000,
          "local_udp_port": 6667,
          "udp_checksum_algorithm": "xor",
        },
      }), encoding="utf-8")
      state_store = AppStateStore(root / "data" / "app-state.json")
      state = state_store.load()
      router = ApiRouter(state_store)

      body, status = router.handle_json(
        "GET",
        "/api/capabilities",
        b"",
        state,
      )

      self.assertEqual(status, 200)
      data = json.loads(body)["data"]
      self.assertEqual(data["controllers"][0]["label"], "展厅控制器")
      self.assertEqual(data["controllers"][0]["display_name"], "展厅控制器")
      self.assertEqual(data["controllers"][0]["protocol"], "DXDCNet")

  def test_capabilities_default_import_format_comes_from_registry(self):
    registry = ImportRegistry()
    registry.register(ExampleConfigImporter(), default=True)
    router = ApiRouter(None, import_registry=registry)
    body, status = router.handle_json(
      "GET",
      "/api/capabilities",
      b"",
      default_state(),
    )

    self.assertEqual(status, 200)
    payload = json.loads(body)
    self.assertEqual(payload["data"]["default_import_format"], "example_layout_config")
    self.assertEqual(payload["data"]["import_formats"][0]["format"], "example_layout_config")

  def test_capabilities_default_controller_kind_comes_from_registry(self):
    registry = ControllerRegistry()
    registry.register(ExampleControllerAdapter(), default=True)
    router = ApiRouter(None, controller_registry=registry)
    body, status = router.handle_json(
      "GET",
      "/api/capabilities",
      b"",
      default_state(),
    )

    self.assertEqual(status, 200)
    payload = json.loads(body)
    self.assertEqual(payload["data"]["default_controller_kind"], "example_controller")
    self.assertEqual(payload["data"]["controllers"][0]["kind"], "example_controller")


if __name__ == "__main__":
  unittest.main()

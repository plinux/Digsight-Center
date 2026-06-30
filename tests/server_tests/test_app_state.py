import json
import inspect
import sqlite3
import threading
import tempfile
import unittest
from pathlib import Path

from server import models
from server.app_state import AppStateStore, default_state
from server.controllers.example import ExampleControllerAdapter
from server.udp_transport_config import normalize_transport_config
from server.controllers.registry import ControllerRegistry, default_controller_registry
from server.vehicle_store import VehicleStore
from tests.server_tests.controller_test_env import CustomDefaultsControllerAdapter


def digsight_config_file_name() -> str:
  return default_controller_registry().config_file_name("digsight_controller")


def digsight_config_relative_path() -> str:
  return f"config/controllers/{digsight_config_file_name()}"


class AppStateStoreTest(unittest.TestCase):
  def test_default_track_profiles_use_target_field_names(self):
    for profile in models.default_track_profiles().values():
      self.assertIn("target_voltage_v", profile)
      self.assertIn("target_current_limit_ma", profile)
      self.assertIn("max_target_voltage_v", profile)
      self.assertIn("max_target_current_limit_ma", profile)
      self.assertNotIn("voltage_v", profile)
      self.assertNotIn("current_limit_ma", profile)
      self.assertNotIn("max_voltage_v", profile)
      self.assertNotIn("max_current_limit_ma", profile)

  def test_default_controller_config_includes_field_descriptions(self):
    config = AppStateStore.default_controller_config(default_controller_registry(), "digsight_controller")
    descriptions = config["field_descriptions"]
    expected_paths = [
      "display_name",
      "ip",
      "protocol",
      "settings",
      "transport.kind",
      "transport.udp_port",
      "transport.local_udp_port",
      "transport.udp_checksum_algorithm",
      "track_profiles.<mode>.target_voltage_v",
      "track_profiles.<mode>.target_current_limit_ma",
      "track_profiles.<mode>.max_target_voltage_v",
      "track_profiles.<mode>.max_target_current_limit_ma",
      "track_profiles.<mode>.output_value",
      "track_profiles.<mode>.current_param",
    ]
    for path in expected_paths:
      self.assertIn(path, descriptions)
      self.assertIsInstance(descriptions[path], str)
      self.assertGreater(len(descriptions[path]), 0)
    self.assertIn("目标", descriptions["track_profiles.<mode>.target_voltage_v"])
    self.assertIn("不是实时电流", descriptions["track_profiles.<mode>.target_current_limit_ma"])

  def test_example_controller_default_config_uses_example_field_descriptions(self):
    registry = ControllerRegistry()
    registry.register(ExampleControllerAdapter(), default=True)

    config = AppStateStore.default_controller_config(registry, "example_controller")
    descriptions = config["field_descriptions"]
    description_text = "\n".join(descriptions.values())

    self.assertIn("transport.endpoint", descriptions)
    self.assertIn("端点", description_text)
    for controller_specific_text in ("DXDCNet", "动芯", "D9000", "12000", "6667", "0x81"):
      self.assertNotIn(controller_specific_text, description_text)

  def test_default_state_uses_selected_controller_field_descriptions(self):
    registry = ControllerRegistry()
    registry.register(ExampleControllerAdapter(), default=True)

    state = default_state(registry)
    description_text = "\n".join(state["controller"]["field_descriptions"].values())

    self.assertEqual(state["controller"]["kind"], "example_controller")
    self.assertIn("端点", description_text)
    self.assertNotIn("DXDCNet", description_text)

  def test_unregistered_controller_default_config_uses_protocol_neutral_transport(self):
    config = AppStateStore.default_controller_config(default_controller_registry(), "future_controller")

    self.assertEqual(config["transport"], {"kind": "unconfigured"})
    self.assertNotIn("udp_port", config["transport"])
    self.assertNotIn("local_udp_port", config["transport"])
    self.assertNotIn("udp_checksum_algorithm", config["transport"])

  def test_creates_default_state(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      state = store.load()
      self.assertEqual(state["schema_version"], 1)
      self.assertEqual(state["controller"]["ip"], models.CONTROLLER_DEFAULT_IP)
      self.assertEqual(state["controller"]["track_mode"], "n")
      self.assertEqual(state["controller"]["udp_port"], 12000)
      self.assertEqual(state["controller"]["local_udp_port"], 6667)
      self.assertEqual(state["controller"]["udp_checksum_algorithm"], "xor")
      self.assertEqual(state["vehicles"], [])

  def test_missing_controller_config_file_is_generated_from_vehicle_store_defaults(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      db_path = root / "data" / "vehicles.sqlite3"
      app_state_path = root / "data" / "app-state.json"
      vehicle_store = VehicleStore(db_path)
      generated_payload = AppStateStore.default_controller_config(default_controller_registry(), "digsight_controller")
      generated_payload["ip"] = "192.0.2.88"
      generated_payload["settings"] = {"source": "database-default"}
      con = sqlite3.connect(db_path)
      try:
        con.execute(
          "UPDATE controller_default_configs SET config_json = ? WHERE kind = ?",
          (json.dumps(generated_payload, ensure_ascii=False, sort_keys=True), "digsight_controller"),
        )
        con.commit()
      finally:
        con.close()

      state = AppStateStore(app_state_path, vehicle_store=vehicle_store).load()

      config_path = root / "config" / "controllers" / digsight_config_file_name()
      self.assertTrue(config_path.exists())
      config = json.loads(config_path.read_text(encoding="utf-8"))
      self.assertEqual(config["ip"], "192.0.2.88")
      self.assertEqual(config["settings"], {"source": "database-default"})
      self.assertEqual(state["controller"]["ip"], "192.0.2.88")

  def test_controller_config_is_saved_in_per_controller_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      store = AppStateStore(path)
      state = store.load()
      state["controller"]["ip"] = "192.0.2.44"
      state["controller"]["transport"].update({
        "udp_port": 21105,
        "local_udp_port": 6668,
        "udp_checksum_algorithm": "xor",
      })
      state["controller"]["display_name"] = "动芯 拾Pro 测试"
      state["controller"]["protocol"] = "DXDCNet"
      state["controller"]["settings"] = {"screen_brightness": 8}

      store.save(state)

      controller_config = json.loads((root / "config" / "controllers" / digsight_config_file_name()).read_text(encoding="utf-8"))
      self.assertEqual(controller_config["ip"], "192.0.2.44")
      self.assertEqual(controller_config["transport"]["udp_port"], 21105)
      self.assertEqual(controller_config["transport"]["local_udp_port"], 6668)
      self.assertEqual(controller_config["transport"]["udp_checksum_algorithm"], "xor")
      self.assertEqual(controller_config["display_name"], "动芯 拾Pro 测试")
      self.assertEqual(controller_config["protocol"], "DXDCNet")
      self.assertEqual(controller_config["settings"], {"screen_brightness": 8})
      self.assertIn("field_descriptions", controller_config)
      self.assertIn("track_profiles.<mode>.target_voltage_v", controller_config["field_descriptions"])

      app_state = json.loads(path.read_text(encoding="utf-8"))
      self.assertNotIn("ip", app_state["controller"])
      self.assertNotIn("udp_port", app_state["controller"])
      self.assertNotIn("local_udp_port", app_state["controller"])
      self.assertNotIn("udp_checksum_algorithm", app_state["controller"])
      self.assertNotIn("display_name", app_state["controller"])
      self.assertNotIn("protocol", app_state["controller"])
      self.assertNotIn("settings", app_state["controller"])
      self.assertNotIn("field_descriptions", app_state["controller"])
      self.assertNotIn("transport", app_state["controller"])
      self.assertNotIn("track_profiles", app_state["controller"])

  def test_controller_config_for_kind_reads_controller_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / digsight_config_file_name()).write_text(json.dumps({
        "ip": "192.0.2.55",
        "transport": {
          "kind": "udp",
          "udp_port": 21105,
          "local_udp_port": 6668,
          "udp_checksum_algorithm": "xor",
        },
        "display_name": "动芯 拾Pro",
        "protocol": "DXDCNet",
        "settings": {"screen_brightness": 7},
      }), encoding="utf-8")
      store = AppStateStore(path)

      config = store.controller_config_for_kind("digsight_controller")

      self.assertEqual(config["ip"], "192.0.2.55")
      self.assertEqual(config["transport"]["udp_port"], 21105)
      self.assertEqual(config["transport"]["local_udp_port"], 6668)
      self.assertEqual(config["protocol"], "DXDCNet")
      self.assertEqual(config["settings"], {"screen_brightness": 7})

  def test_controller_config_repairs_invalid_field_descriptions(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / digsight_config_file_name()).write_text(json.dumps({
        "field_descriptions": "broken",
        "ip": "192.0.2.50",
      }), encoding="utf-8")
      store = AppStateStore(path)

      config = store.controller_config_for_kind("digsight_controller")

      self.assertIsInstance(config["field_descriptions"], dict)
      self.assertIn("track_profiles.<mode>.target_current_limit_ma", config["field_descriptions"])

  def test_load_uses_config_file_for_selected_controller_kind(self):
    registry = ControllerRegistry()
    registry.register(CustomDefaultsControllerAdapter(), default=True)
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      path.parent.mkdir()
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      path.write_text(json.dumps({
        "controller": {
          "kind": "custom_defaults_controller",
        }
      }), encoding="utf-8")
      (config_dir / "custom-controller-settings.json").write_text(json.dumps({
        "ip": "192.0.2.45",
        "settings": {"vendor": "custom"},
        "display_name": "自定义控制器",
        "protocol": "CustomProtocol",
        "transport": {
          "kind": "udp",
          "udp_port": 21105,
          "local_udp_port": 0,
          "udp_checksum_algorithm": "none",
        },
      }), encoding="utf-8")

      state = AppStateStore(path, controller_registry=registry).load()

      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertEqual(state["controller"]["ip"], "192.0.2.45")
      self.assertEqual(state["controller"]["settings"], {"vendor": "custom"})
      self.assertEqual(state["controller"]["display_name"], "自定义控制器")
      self.assertEqual(state["controller"]["protocol"], "CustomProtocol")
      self.assertEqual(state["controller"]["udp_port"], 21105)
      self.assertEqual(state["controller"]["local_udp_port"], 0)
      self.assertEqual(state["controller"]["udp_checksum_algorithm"], "none")

  def test_save_uses_registry_controller_config_file_name(self):
    registry = ControllerRegistry()
    registry.register(CustomDefaultsControllerAdapter(), default=True)
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      store = AppStateStore(path, controller_registry=registry)
      state = store.load()
      state["controller"]["ip"] = "192.0.2.55"
      state["controller"]["transport"].update({
        "udp_port": 21106,
        "local_udp_port": 0,
        "udp_checksum_algorithm": "none",
      })

      store.save(state)

      custom_path = root / "config" / "controllers" / "custom-controller-settings.json"
      fallback_path = root / "config" / "controllers" / "custom_defaults_controller.json"
      controller_config = json.loads(custom_path.read_text(encoding="utf-8"))
      self.assertFalse(fallback_path.exists())
      self.assertEqual(controller_config["ip"], "192.0.2.55")
      self.assertEqual(controller_config["transport"]["udp_port"], 21106)
      self.assertEqual(controller_config["transport"]["local_udp_port"], 0)

  def test_missing_app_state_does_not_overwrite_existing_controller_config(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / digsight_config_file_name()).write_text(json.dumps({
        "ip": "192.0.2.46",
        "transport": {
          "kind": "udp",
          "udp_port": 12000,
          "local_udp_port": 6667,
          "udp_checksum_algorithm": "xor",
        },
        "settings": {"screen_brightness": 6},
      }), encoding="utf-8")

      state = AppStateStore(path).load()

      self.assertEqual(state["controller"]["ip"], "192.0.2.46")
      self.assertEqual(state["controller"]["settings"], {"screen_brightness": 6})
      controller_config = json.loads((config_dir / digsight_config_file_name()).read_text(encoding="utf-8"))
      self.assertEqual(controller_config["ip"], "192.0.2.46")

  def test_load_malformed_controller_config_reports_resettable_error_without_rewrite(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      config_path = config_dir / digsight_config_file_name()
      config_path.write_text("{broken controller config", encoding="utf-8")

      state = AppStateStore(path).load()

      self.assertEqual(state["controller"]["ip"], models.CONTROLLER_DEFAULT_IP)
      self.assertEqual(config_path.read_text(encoding="utf-8"), "{broken controller config")
      self.assertEqual(state["last_error"]["type"], "controller_config_invalid")
      self.assertEqual(state["last_error"]["message"], "当前控制器配置文件无效")
      self.assertEqual(state["last_error"]["config_file"], digsight_config_relative_path())
      self.assertEqual(state["last_error"]["resettable_files"], [digsight_config_relative_path()])
      self.assertIn("手工修复", state["last_error"]["manual_action"])
      self.assertIn("点击重置", state["last_error"]["manual_action"])

  def test_save_keeps_malformed_controller_config_until_explicit_reset(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      config_path = config_dir / digsight_config_file_name()
      config_path.write_text("not json", encoding="utf-8")
      store = AppStateStore(path)

      state = store.load()
      state["controller"]["track_mode"] = "ho"
      store.save(state)

      self.assertEqual(config_path.read_text(encoding="utf-8"), "not json")

  def test_reset_controller_config_rewrites_only_selected_controller_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      selected_config = config_dir / digsight_config_file_name()
      other_config = config_dir / "future_controller.json"
      selected_config.write_text("not json", encoding="utf-8")
      other_config.write_text('{"ip":"198.51.100.10"}', encoding="utf-8")
      store = AppStateStore(path)

      result = store.reset_controller_config("digsight_controller")

      self.assertEqual(result["reset_files"], [digsight_config_relative_path()])
      self.assertEqual(other_config.read_text(encoding="utf-8"), '{"ip":"198.51.100.10"}')
      payload = json.loads(selected_config.read_text(encoding="utf-8"))
      self.assertEqual(payload["ip"], models.CONTROLLER_DEFAULT_IP)
      self.assertEqual(payload["display_name"], "动芯 拾Pro")
      self.assertEqual(payload["protocol"], "DXDCNet")
      self.assertEqual(payload["transport"]["udp_port"], 12000)
      self.assertEqual(payload["transport"]["local_udp_port"], 6667)
      self.assertEqual(payload["transport"]["udp_checksum_algorithm"], "xor")

  def test_global_state_corruption_adds_app_state_to_reset_file_list(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      path.parent.mkdir(parents=True)
      path.write_text("{broken app state", encoding="utf-8")
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / digsight_config_file_name()).write_text("not json", encoding="utf-8")

      state = AppStateStore(path).load()

      self.assertEqual(state["last_error"]["type"], "controller_config_invalid")
      self.assertEqual(state["last_error"]["global_config_error"]["type"], "app_state_corrupt_recovered")
      self.assertEqual(
        state["last_error"]["resettable_files"],
        [digsight_config_relative_path(), "data/app-state.json"],
      )

  def test_controller_config_error_is_cleared_when_controller_kind_changes(self):
    state = {
      "last_error": {
        "type": "controller_config_invalid",
        "controller_kind": "digsight_controller",
        "config_file": digsight_config_relative_path(),
      },
    }

    AppStateStore.clear_controller_config_error_for_kind_change(
      state,
      "digsight_controller",
      "custom_defaults_controller",
    )

    self.assertIsNone(state["last_error"])

  def test_controller_config_error_clear_preserves_global_state_error(self):
    state = {
      "last_error": {
        "type": "controller_config_invalid",
        "controller_kind": "digsight_controller",
        "config_file": digsight_config_relative_path(),
        "global_config_error": {
          "type": "app_state_corrupt_recovered",
          "message": "全局状态文件已恢复为默认状态",
        },
      },
    }

    AppStateStore.clear_controller_config_error_for_kind_change(
      state,
      "digsight_controller",
      "custom_defaults_controller",
    )

    self.assertEqual(state["last_error"]["type"], "app_state_corrupt_recovered")

  def test_controller_config_file_overrides_app_state_controller_fields(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      path.parent.mkdir()
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      path.write_text(json.dumps({
        "controller": {
          "kind": "digsight_controller",
          "ip": "192.0.2.47",
          "transport": {
            "kind": "udp",
            "udp_port": 21105,
          },
        }
      }), encoding="utf-8")
      (config_dir / digsight_config_file_name()).write_text(json.dumps({
        "ip": "192.0.2.48",
        "transport": {
          "kind": "udp",
          "udp_port": 12000,
          "local_udp_port": 6667,
          "udp_checksum_algorithm": "xor",
        },
      }), encoding="utf-8")

      state = AppStateStore(path).load()

      self.assertEqual(state["controller"]["ip"], "192.0.2.48")
      self.assertEqual(state["controller"]["udp_port"], 12000)

  def test_app_state_controller_config_fields_are_ignored_without_config_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      path.parent.mkdir()
      path.write_text(json.dumps({
        "controller": {
          "kind": "digsight_controller",
          "ip": "192.0.2.49",
          "transport": {
            "kind": "udp",
            "udp_port": 21105,
            "local_udp_port": 7777,
            "udp_checksum_algorithm": "none",
          },
          "settings": {"screen_brightness": 2},
        }
      }), encoding="utf-8")

      state = AppStateStore(path).load()

      self.assertEqual(state["controller"]["ip"], models.CONTROLLER_DEFAULT_IP)
      self.assertEqual(state["controller"]["udp_port"], 12000)
      self.assertEqual(state["controller"]["local_udp_port"], 6667)
      self.assertEqual(state["controller"]["udp_checksum_algorithm"], "xor")
      self.assertEqual(state["controller"]["settings"], {})

  def test_saves_and_loads_vehicle(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      state = store.load()
      state["vehicles"].append({"id": "v1", "name": "测试车", "address": 3})
      store.save(state)
      loaded = json.loads(path.read_text(encoding="utf-8"))
      self.assertEqual(loaded["vehicles"][0]["address"], 3)

  def test_default_state_uses_safe_track_values(self):
    state = default_state()
    self.assertEqual(state["controller"]["track_mode"], "n")
    self.assertEqual(state["controller"]["dcc_mode_bit"], 0)
    self.assertEqual(state["controller"]["n_output_value"], 0x78)
    self.assertEqual(state["controller"]["ho_output_value"], 0xA0)
    self.assertEqual(state["controller"]["g_output_value"], 0xB4)
    self.assertEqual(state["controller"]["current_step_ma"], 40)
    self.assertIn("g", state["controller"]["track_profiles"])
    self.assertIn("dc", state["controller"]["track_profiles"])

  def test_default_state_uses_programming_track_target(self):
    state = default_state()
    self.assertEqual(state["controller"]["programming_target"], "programming_track")
    self.assertEqual(state["controller"]["runtime_revision"], 0)

  def test_save_after_hardware_rejects_stale_controller_revision(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      state = store.load()
      snapshot = store.load_snapshot()
      state["controller"]["runtime_revision"] = 1
      store.save(state)
      snapshot["controller"]["last_probe_ok"] = True

      with self.assertRaisesRegex(ValueError, "controller runtime changed"):
        store.save_after_hardware(snapshot, expected_controller_revision=0)

      loaded = store.load()
      self.assertEqual(loaded["controller"]["runtime_revision"], 1)
      self.assertFalse(loaded["controller"]["last_probe_ok"])

  def test_save_after_hardware_accepts_matching_controller_revision(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      snapshot = store.load_snapshot()
      snapshot["controller"]["last_probe_ok"] = True

      store.save_after_hardware(snapshot, expected_controller_revision=0)

      loaded = store.load()
      self.assertTrue(loaded["controller"]["last_probe_ok"])

  def test_load_ignores_app_state_track_profile_config_fields(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      path.write_text(json.dumps({
        "controller": {
          "track_profiles": {
            "n": {"output_value": 0xE8, "target_current_limit_ma": 1000},
            "ho": {"output_value": 0xF3, "target_current_limit_ma": 2000},
          }
        }
      }), encoding="utf-8")
      state = AppStateStore(path).load()
      self.assertEqual(state["controller"]["track_profiles"]["n"]["output_value"], 0x78)
      self.assertEqual(state["controller"]["track_profiles"]["ho"]["output_value"], 0xA0)
      self.assertIsNone(state["controller"]["track_profiles"]["n"]["target_current_limit_ma"])

  def test_load_fills_default_udp_settings(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      path.write_text(json.dumps({
        "controller": {
          "transport": {
            "kind": "udp",
            "udp_port": 0,
            "local_udp_port": 0,
            "udp_checksum_algorithm": "unconfirmed",
          },
        }
      }), encoding="utf-8")
      state = AppStateStore(path).load()
      self.assertEqual(state["controller"]["udp_port"], 12000)
      self.assertEqual(state["controller"]["local_udp_port"], 6667)
      self.assertEqual(state["controller"]["udp_checksum_algorithm"], "xor")

  def test_load_preserves_zero_local_udp_port_for_non_digsight_controller(self):
    registry = ControllerRegistry()
    registry.register(CustomDefaultsControllerAdapter(), default=True)
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      path.write_text(json.dumps({
        "controller": {
          "kind": "custom_defaults_controller",
          "transport": {
            "kind": "udp",
            "udp_port": 0,
            "local_udp_port": 0,
            "udp_checksum_algorithm": "unconfirmed",
          },
        }
      }), encoding="utf-8")
      state = AppStateStore(path, controller_registry=registry).load()
      self.assertEqual(state["controller"]["udp_port"], 21105)
      self.assertEqual(state["controller"]["local_udp_port"], 0)
      self.assertEqual(state["controller"]["udp_checksum_algorithm"], "none")

  def test_missing_state_file_uses_injected_registry_defaults(self):
    registry = ControllerRegistry(default_kind="custom_defaults_controller")
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      state = AppStateStore(path, controller_registry=registry).load()

      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertEqual(state["controller"]["ip"], "192.0.2.44")
      self.assertEqual(state["controller"]["udp_port"], 21105)
      self.assertEqual(state["controller"]["local_udp_port"], 0)
      self.assertEqual(state["controller"]["udp_checksum_algorithm"], "none")

  def test_with_defaults_recovers_invalid_controller_settings_to_safe_defaults(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      state = store._with_defaults({
        "controller": {
          "kind": "invalid-kind",
          "settings": "not-a-dict",
          "track_mode": "invalid_scale",
          "programming_target": "main_line",
          "transport": {
            "kind": "udp",
            "udp_port": "invalid",
            "local_udp_port": None,
          },
          "track_profiles": {
            "ho": {"output_value": 0xFF, "target_current_limit_ma": 1800},
            "xx": {"output_value": 0xFF, "target_current_limit_ma": 1800},
          },
        }
      })
      controller = state["controller"]
      self.assertEqual(controller["kind"], "digsight_controller")
      self.assertEqual(controller["settings"], {})
      self.assertEqual(controller["track_mode"], "n")
      self.assertEqual(controller["programming_target"], "programming_track")
      self.assertEqual(controller["udp_port"], 12000)
      self.assertEqual(controller["local_udp_port"], 6667)
      self.assertEqual(controller["track_profiles"]["ho"]["output_value"], 0xA0)
      self.assertIsNone(controller["track_profiles"]["ho"]["target_current_limit_ma"])
      self.assertNotIn("xx", controller["track_profiles"])
      self.assertEqual(state["last_error"]["type"], "controller_runtime_invalid")
      self.assertEqual(state["last_error"]["invalid_fields"], ["track_mode", "programming_target"])

  def test_invalid_runtime_controller_mode_invalidates_stale_safety_state(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      path.write_text(json.dumps({
        "controller": {
          "track_mode": "bogus",
          "programming_target": "bad_target",
          "last_probe_ok": True,
          "controller_reachable": True,
          "controller_unreachable_reason": "",
          "booster_status": {
            "source": "dxdcnet_status_0x23",
            "power_on": True,
            "dcc_mode": True,
          },
          "programming_track_status": {
            "source": "dxdcnet_status_0x23",
            "programming_track_busy": False,
          },
          "safety_snapshot": {
            "controller_endpoint_version": 4,
            "last_read_info_at": "2026-06-22T00:00:00+08:00",
            "booster_status_fresh": True,
            "programming_track_status_fresh": True,
          },
        }
      }), encoding="utf-8")

      state = AppStateStore(path).load()

      controller = state["controller"]
      self.assertEqual(controller["track_mode"], "n")
      self.assertEqual(controller["programming_target"], "programming_track")
      self.assertFalse(controller["last_probe_ok"])
      self.assertFalse(controller["controller_reachable"])
      self.assertEqual(controller["controller_unreachable_reason"], "invalid_runtime_controller_settings")
      self.assertNotIn("booster_status", controller)
      self.assertNotIn("programming_track_status", controller)
      self.assertEqual(controller["safety_snapshot"]["controller_endpoint_version"], 5)
      self.assertFalse(controller["safety_snapshot"]["booster_status_fresh"])
      self.assertFalse(controller["safety_snapshot"]["programming_track_status_fresh"])
      self.assertEqual(state["last_error"]["type"], "controller_runtime_invalid")
      self.assertEqual(state["last_error"]["invalid_fields"], ["track_mode", "programming_target"])

  def test_default_normalization_uses_shared_helpers(self):
    app_state_source = inspect.getsource(AppStateStore)
    defaults_source = inspect.getsource(AppStateStore._with_defaults)
    transport_source = inspect.getsource(AppStateStore._normalize_controller_transport)
    config_transport_source = inspect.getsource(AppStateStore._normalize_controller_config_transport)
    self.assertTrue(hasattr(AppStateStore, "_validated_or_default_with_error"))
    self.assertTrue(hasattr(AppStateStore, "_controller_with_config"))
    self.assertTrue(hasattr(AppStateStore, "_merge_runtime_controller_sections"))
    self.assertTrue(hasattr(AppStateStore, "_normalized_track_profiles"))
    self.assertNotIn("CONTROLLER_KIND_DIGSIGHT", app_state_source)
    self.assertNotIn("digsight_controller", app_state_source)
    self.assertIn("_controller_with_config(", defaults_source)
    self.assertIn("_normalize_controller_transport(", defaults_source)
    self.assertIn("_normalize_controller_config_transport(", transport_source)
    self.assertIn("apply_controller_transport_runtime(adapter, controller)", transport_source)
    self.assertNotIn('controller["udp_port"] =', transport_source)
    self.assertNotIn('controller["local_udp_port"] =', transport_source)
    self.assertIn("normalize_controller_transport_config(", config_transport_source)
    self.assertNotIn("normalize_transport_config(", config_transport_source)

  def test_transport_normalizer_supports_permissive_and_strict_modes(self):
    descriptor = default_controller_registry().get("digsight_controller").transport_descriptor

    permissive = normalize_transport_config(
      {"kind": "udp", "udp_port": 0, "local_udp_port": 0, "udp_checksum_algorithm": "unknown"},
      descriptor,
      strict=False,
    )
    self.assertEqual(permissive["udp_port"], 12000)
    self.assertEqual(permissive["local_udp_port"], 6667)
    self.assertEqual(permissive["udp_checksum_algorithm"], "xor")

    with self.assertRaises(ValueError):
      normalize_transport_config({"udp_port": 0}, descriptor, strict=True)

  def test_with_defaults_replaces_unregistered_controller_kind_with_registry_default(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      state = store._with_defaults({
        "controller": {
          "kind": "future_controller",
        }
      })
      self.assertEqual(state["controller"]["kind"], "digsight_controller")

  def test_with_defaults_replaces_non_object_controller_with_defaults(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      state = AppStateStore(path)._with_defaults({"controller": "not-a-dict"})
      self.assertEqual(state["controller"]["kind"], "digsight_controller")
      self.assertEqual(state["controller"]["track_mode"], "n")
      self.assertEqual(state["controller"]["udp_port"], 12000)

  def test_load_corrupt_state_keeps_backup_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      valid_state = {
        "controller": {"track_mode": "ho"},
        "vehicles": [{"id": "v1", "name": "测试车", "address": 3}],
      }
      path.write_text(f"{json.dumps(valid_state)}\n\"tail fragment\"\n", encoding="utf-8")
      state = AppStateStore(path).load()
      backups = list(path.parent.glob("app-state.json.corrupt-*"))
      self.assertEqual(len(backups), 1)
      self.assertIn("tail fragment", backups[0].read_text(encoding="utf-8"))
      self.assertEqual(state["controller"]["track_mode"], "n")
      recovered = json.loads(path.read_text(encoding="utf-8"))
      self.assertEqual(recovered["controller"]["track_mode"], "n")

  def test_concurrent_saves_do_not_share_temp_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      errors = []
      barrier = threading.Barrier(8)

      def save_state(index):
        try:
          barrier.wait()
          for sequence in range(20):
            state = default_state()
            state["last_error"] = {"worker": index, "sequence": sequence}
            store.save(state)
        except Exception as error:
          errors.append(error)

      threads = [threading.Thread(target=save_state, args=(index,)) for index in range(8)]
      for thread in threads:
        thread.start()
      for thread in threads:
        thread.join()

      self.assertEqual(errors, [])
      json.loads(path.read_text(encoding="utf-8"))

  def test_update_callback_is_atomic_for_read_modify_write(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      store = AppStateStore(path)
      store.save(default_state())
      errors = []
      barrier = threading.Barrier(8)

      def update_state(index):
        try:
          barrier.wait()

          def mutator(state):
            state.setdefault("imports", []).append({"worker": index})

          store.update(mutator)
        except Exception as error:
          errors.append(error)

      threads = [threading.Thread(target=update_state, args=(index,)) for index in range(8)]
      for thread in threads:
        thread.start()
      for thread in threads:
        thread.join()

      self.assertEqual(errors, [])
      loaded = store.load()
      self.assertEqual(len(loaded["imports"]), 8)
      self.assertEqual(sorted(item["worker"] for item in loaded["imports"]), list(range(8)))

  def test_load_normalizes_cached_screen_direction_label(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      path.write_text(json.dumps({
        "controller": {
          "device_info": {
            "screen_direction_raw": 2,
            "screen_direction_label": "右（实测）",
          }
        }
      }), encoding="utf-8")
      state = AppStateStore(path).load()
      self.assertEqual(state["controller"]["device_info"]["screen_direction_label"], "右")


if __name__ == "__main__":
  unittest.main()

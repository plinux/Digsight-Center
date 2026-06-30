import json
import inspect
import threading
import tempfile
import unittest
from pathlib import Path

from server import models
from server.app_state import AppStateStore, default_state
from server.controllers.base import ControllerCapabilities, ControllerTransportDefaults
from server.controllers.registry import ControllerRegistry


class CustomDefaultsControllerAdapter:
  kind = "custom_defaults_controller"
  label = "Custom Defaults Controller"
  default_ip = "192.0.2.44"
  config_file_name = "custom-controller-settings.json"
  capabilities = ControllerCapabilities(
    track_power=False,
    read_info=False,
    cv_programming=False,
    loco_control=False,
    controller_settings=False,
  )
  transport_defaults = ControllerTransportDefaults(
    udp_port=21105,
    local_udp_port=0,
    checksum_algorithm="none",
  )


class AppStateStoreTest(unittest.TestCase):
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

  def test_controller_config_is_saved_in_per_controller_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      store = AppStateStore(path)
      state = store.load()
      state["controller"]["ip"] = "192.0.2.44"
      state["controller"]["udp_port"] = 21105
      state["controller"]["local_udp_port"] = 6668
      state["controller"]["udp_checksum_algorithm"] = "xor"
      state["controller"]["settings"] = {"screen_brightness": 8}

      store.save(state)

      controller_config = json.loads((root / "config" / "controllers" / models.CONTROLLER_CONFIG_FILES["digsight_controller"]).read_text(encoding="utf-8"))
      self.assertEqual(controller_config["ip"], "192.0.2.44")
      self.assertEqual(controller_config["udp_port"], 21105)
      self.assertEqual(controller_config["local_udp_port"], 6668)
      self.assertEqual(controller_config["udp_checksum_algorithm"], "xor")
      self.assertEqual(controller_config["settings"], {"screen_brightness": 8})

      app_state = json.loads(path.read_text(encoding="utf-8"))
      self.assertNotIn("ip", app_state["controller"])
      self.assertNotIn("udp_port", app_state["controller"])
      self.assertNotIn("local_udp_port", app_state["controller"])
      self.assertNotIn("udp_checksum_algorithm", app_state["controller"])
      self.assertNotIn("settings", app_state["controller"])
      self.assertNotIn("track_profiles", app_state["controller"])

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
        "udp_port": 21105,
        "local_udp_port": 0,
        "udp_checksum_algorithm": "none",
      }), encoding="utf-8")

      state = AppStateStore(path, controller_registry=registry).load()

      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertEqual(state["controller"]["ip"], "192.0.2.45")
      self.assertEqual(state["controller"]["settings"], {"vendor": "custom"})
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
      state["controller"]["udp_port"] = 21106
      state["controller"]["local_udp_port"] = 0
      state["controller"]["udp_checksum_algorithm"] = "none"

      store.save(state)

      custom_path = root / "config" / "controllers" / "custom-controller-settings.json"
      fallback_path = root / "config" / "controllers" / "custom_defaults_controller.json"
      controller_config = json.loads(custom_path.read_text(encoding="utf-8"))
      self.assertFalse(fallback_path.exists())
      self.assertEqual(controller_config["ip"], "192.0.2.55")
      self.assertEqual(controller_config["udp_port"], 21106)
      self.assertEqual(controller_config["local_udp_port"], 0)

  def test_missing_app_state_does_not_overwrite_existing_controller_config(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      path = root / "data" / "app-state.json"
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / models.CONTROLLER_CONFIG_FILES["digsight_controller"]).write_text(json.dumps({
        "ip": "192.0.2.46",
        "udp_port": 12000,
        "local_udp_port": 6667,
        "udp_checksum_algorithm": "xor",
        "settings": {"screen_brightness": 6},
      }), encoding="utf-8")

      state = AppStateStore(path).load()

      self.assertEqual(state["controller"]["ip"], "192.0.2.46")
      self.assertEqual(state["controller"]["settings"], {"screen_brightness": 6})
      controller_config = json.loads((config_dir / models.CONTROLLER_CONFIG_FILES["digsight_controller"]).read_text(encoding="utf-8"))
      self.assertEqual(controller_config["ip"], "192.0.2.46")

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
          "udp_port": 21105,
        }
      }), encoding="utf-8")
      (config_dir / models.CONTROLLER_CONFIG_FILES["digsight_controller"]).write_text(json.dumps({
        "ip": "192.0.2.48",
        "udp_port": 12000,
        "local_udp_port": 6667,
        "udp_checksum_algorithm": "xor",
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
          "udp_port": 21105,
          "local_udp_port": 7777,
          "udp_checksum_algorithm": "none",
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
            "n": {"output_value": 0xE8, "current_limit_ma": 1000},
            "ho": {"output_value": 0xF3, "current_limit_ma": 2000},
          }
        }
      }), encoding="utf-8")
      state = AppStateStore(path).load()
      self.assertEqual(state["controller"]["track_profiles"]["n"]["output_value"], 0x78)
      self.assertEqual(state["controller"]["track_profiles"]["ho"]["output_value"], 0xA0)
      self.assertIsNone(state["controller"]["track_profiles"]["n"]["current_limit_ma"])

  def test_load_fills_default_udp_settings(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      path = Path(temp_dir) / "app-state.json"
      path.write_text(json.dumps({
        "controller": {
          "udp_port": 0,
          "local_udp_port": 0,
          "udp_checksum_algorithm": "unconfirmed",
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
          "udp_port": 0,
          "local_udp_port": 0,
          "udp_checksum_algorithm": "unconfirmed",
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
          "udp_port": "invalid",
          "local_udp_port": None,
          "track_profiles": {
            "ho": {"output_value": 0xFF, "current_limit_ma": 1800},
            "xx": {"output_value": 0xFF, "current_limit_ma": 1800},
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
      self.assertIsNone(controller["track_profiles"]["ho"]["current_limit_ma"])
      self.assertNotIn("xx", controller["track_profiles"])

  def test_default_normalization_uses_shared_helpers(self):
    source = inspect.getsource(AppStateStore._with_defaults)
    self.assertTrue(hasattr(AppStateStore, "_validated_or_default"))
    self.assertTrue(hasattr(AppStateStore, "_positive_int_or_default"))
    self.assertNotIn("CONTROLLER_KIND_DIGSIGHT", inspect.getsource(AppStateStore))
    self.assertNotIn("digsight_controller", inspect.getsource(AppStateStore))
    self.assertGreaterEqual(source.count("_validated_or_default("), 2)
    self.assertIn("_positive_int_or_default(", source)

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

  def test_load_migrates_cached_screen_direction_label(self):
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

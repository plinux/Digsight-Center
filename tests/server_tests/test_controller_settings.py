import json
import inspect
import re
from pathlib import Path
import tempfile
import unittest

from server import models
from server.api import ApiRouter
from server.api_support.controller import ControllerApiSupport
from server.app_state import AppStateStore, default_state
from server.controllers.base import ControllerCapabilities
from server.controllers.example import ExampleControllerAdapter
from server.controllers.registry import ControllerRegistry, default_controller_registry
from digsight_dxdcnet.constants import (
  CMD_DEVICE_STATUS,
  CMD_MAC_ADDRESS,
  CMD_PARAMETER_VALUE,
  CMD_VERSION_DATA,
  DEVICE_TYPE_BOOSTER,
  DEVICE_TYPE_COMMAND_STATION,
  DEVICE_TYPE_SPECIAL,
)
from digsight_dxdcnet.frames import build_udp_frame
from tests.server_tests.controller_test_env import CustomDefaultsControllerAdapter, controller_ip_payload, controller_test_ip
from tests.server_tests.fake_udp import FakeRequestMappedUdpTransport
from z21_lan import (
  LAN_GET_COMMON_SETTINGS,
  LAN_GET_MMDCC_SETTINGS,
  LAN_SET_COMMON_SETTINGS,
  LAN_SET_MMDCC_SETTINGS,
  build_get_common_settings,
  build_set_common_settings,
  encode_dataset,
  parse_common_settings,
)


class SettingsReadyExampleControllerAdapter(ExampleControllerAdapter):
  capabilities = ControllerCapabilities(
    track_power=False,
    dc_control=False,
    read_info=False,
    cv_programming=False,
    loco_control=False,
    controller_settings=True,
  )


class RailComStateOnlyZ21Adapter(ExampleControllerAdapter):
  kind = "railcom_state_only_z21_controller"
  label = "RailCom 状态测试控制器"
  default_display_name = "RailCom 状态测试控制器"
  protocol = models.CONTROLLER_PROTOCOL_Z21_LAN
  config_file_name = "railcom_state_only_z21.json"
  capabilities = ControllerCapabilities(
    track_power=False,
    dc_control=False,
    read_info=False,
    cv_programming=False,
    loco_control=False,
    controller_settings=True,
    railcom_settings=False,
  )


class FakeECoSTimeoutTransport:
  def exchange(self, host, port, commands, *, timeout_seconds=None, expected_replies=1, expected_events=0):
    raise TimeoutError("ECoS TCP exchange timed out")


class FakeECoSMissingInfoTransport:
  def exchange(self, host, port, commands, *, timeout_seconds=None, expected_replies=1, expected_events=0):
    return "<REPLY request(1, view)>\n1 status[GO]\n<END 0 (OK)>\n"


class FakeECoSSettingsTransport:
  def __init__(self):
    self.requests = []
    self.railcom_enabled = False
    self.railcomplus_enabled = False

  def exchange(self, host, port, commands, *, timeout_seconds=None, expected_replies=1, expected_events=0):
    command_list = list(commands if isinstance(commands, (list, tuple)) else [commands])
    self.requests.append({
      "host": host,
      "port": port,
      "commands": command_list,
      "timeout_seconds": timeout_seconds,
      "expected_replies": expected_replies,
      "expected_events": expected_events,
    })
    if command_list[0] == "request(65000, control)":
      return "\n".join([
        "<REPLY request(65000, control)>",
        "<END 0 (OK)>",
        f"<REPLY {command_list[1]}>",
        "<END 0 (OK)>",
        "<REPLY get(65000, limit)>",
        "65000 limit[3500]",
        "<END 0 (OK)>",
        "<REPLY release(65000, control)>",
        "<END 0 (OK)>",
      ])
    if command_list[0].startswith("set(1, railcom"):
      replies = []
      for command in command_list:
        if command == "set(1, railcom[0])":
          self.railcom_enabled = False
          self.railcomplus_enabled = False
        elif command == "set(1, railcom[1])":
          self.railcom_enabled = True
        elif command == "set(1, railcomplus[0])":
          self.railcomplus_enabled = False
        elif command == "set(1, railcomplus[1])":
          self.railcomplus_enabled = True
        replies.extend([
          f"<REPLY {command}>",
          "<END 0 (OK)>",
        ])
      replies.extend([
        "<REPLY get(1, railcom, railcomplus)>",
        f"1 railcom[{1 if self.railcom_enabled else 0}] railcomplus[{1 if self.railcomplus_enabled else 0}]",
        "<END 0 (OK)>",
      ])
      return "\n".join(replies)
    raise AssertionError(f"unexpected ECoS settings command batch: {command_list!r}")


class FakeZ21SettingsTransport:
  def __init__(self):
    self.requests = []
    self.mmdcc_settings_payload = bytes.fromhex("19 06 07 01 05 14 88 13 10 27 32 80 80 3e 80 3e")
    self.common_settings_payload = bytes.fromhex("01 00 00 03 01 00 03 00 00 00")

  def exchange(self, host, port, payload, *, local_port=0, max_packets=8, stop_when=None, timeout_seconds=None):
    self.requests.append({
      "host": host,
      "port": port,
      "payload": payload,
      "local_port": local_port,
      "max_packets": max_packets,
      "timeout_seconds": timeout_seconds,
    })
    if payload == bytes.fromhex("04 00 16 00"):
      return [encode_dataset(LAN_GET_MMDCC_SETTINGS, self.mmdcc_settings_payload)]
    if payload == build_get_common_settings():
      return [encode_dataset(LAN_GET_COMMON_SETTINGS, self.common_settings_payload)]
    if len(payload) == 20 and payload[:4] == bytes.fromhex("14 00 17 00"):
      self.mmdcc_settings_payload = payload[4:]
      return [encode_dataset(LAN_SET_MMDCC_SETTINGS)]
    if len(payload) == 14 and payload[:4] == bytes.fromhex("0e 00 13 00"):
      self.common_settings_payload = payload[4:]
      return [encode_dataset(LAN_SET_COMMON_SETTINGS)]
    return []


class ControllerSettingsTest(unittest.TestCase):
  def test_controller_settings_workflow_is_split_into_helpers(self):
    router_source = inspect.getsource(ApiRouter)
    controller_source = inspect.getsource(ControllerApiSupport)

    self.assertNotIn("def _parse_controller_settings_request", router_source)
    self.assertIn("def _parse_controller_settings_request", controller_source)
    self.assertIn("def _next_controller_kind_and_adapter", controller_source)
    self.assertIn("def _parse_transport_settings", controller_source)
    self.assertIn("def _parse_controller_mode_settings", controller_source)
    self.assertIn("def _parse_track_profile_settings", controller_source)
    self.assertIn("def _parse_controller_private_settings", controller_source)
    self.assertIn("def _build_controller_settings_candidate", controller_source)
    self.assertIn("def _apply_controller_settings_to_device", controller_source)
    self.assertIn("def _apply_controller_private_settings_if_requested", controller_source)
    self.assertIn("def _controller_settings_response_payload", controller_source)

  def test_custom_defaults_controller_adapter_fixture_is_shared(self):
    helper_source = Path("tests/server_tests/controller_test_env.py").read_text(encoding="utf-8")
    app_state_source = Path("tests/server_tests/test_app_state.py").read_text(encoding="utf-8")
    settings_source = Path("tests/server_tests/test_controller_settings.py").read_text(encoding="utf-8")
    fixture_pattern = re.compile(r"^class CustomDefaultsControllerAdapter", re.MULTILINE)

    self.assertRegex(helper_source, fixture_pattern)
    self.assertNotRegex(app_state_source, fixture_pattern)
    self.assertNotRegex(settings_source, fixture_pattern)

  def test_controller_info_param_spec_appends_warning_on_param_mismatch(self):
    from server.controllers.dxdcnet_info_helpers import apply_parameter_spec

    warnings = []
    controller = {"device_info": {}}
    parsed = {"param_address": 0x01, "value": 8}
    applied = apply_parameter_spec(
      controller,
      parsed,
      expected_param=0x7E,
      warning_prefix="screen_brightness",
      fields=lambda value: {"screen_brightness": value["value"]},
      warnings=warnings,
    )
    self.assertFalse(applied)
    self.assertEqual(warnings, ["screen_brightness_param_mismatch"])
    self.assertEqual(controller["device_info"], {})

  def test_screen_direction_labels_follow_clockwise_app_sequence(self):
    self.assertEqual(models.SCREEN_DIRECTION_LABELS, {
      0x00: "左",
      0x01: "上",
      0x02: "右",
      0x03: "下",
    })

  def test_controller_info_returns_cached_safe_defaults(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["ip"], models.CONTROLLER_DEFAULT_IP)
    self.assertEqual(payload["data"]["connection"]["reachable"], False)
    self.assertEqual(payload["data"]["connection"]["controller_reachable"], False)
    self.assertEqual(payload["data"]["connection"]["gateway_ready"], False)
    self.assertEqual(payload["data"]["controller_kind"], "digsight_controller")
    self.assertEqual(payload["data"]["controller_label"], "动芯 拾Pro")
    self.assertEqual(payload["data"]["controller_protocol"], "DXDCNet")
    self.assertIn("default_track_output_settings", payload["data"])
    self.assertIn("track_profiles", payload["data"]["default_track_output_settings"])
    self.assertEqual(
      payload["data"]["default_track_output_settings"]["track_profiles"]["n"]["target_voltage_v"],
      models.default_track_profiles()["n"]["target_voltage_v"],
    )
    self.assertEqual(payload["data"]["default_track_output_settings"]["settings"], {})
    self.assertTrue(payload["data"]["controller_capabilities"]["track_power"])
    self.assertTrue(payload["data"]["controller_capabilities"]["dc_control"])
    self.assertTrue(payload["data"]["controller_capabilities"]["read_info"])
    self.assertTrue(payload["data"]["controller_capabilities"]["railcom_settings"])
    self.assertEqual(payload["data"]["railcom_setting"], {
      "available": True,
      "writable": True,
      "enabled": None,
      "source": "",
      "message": "",
    })
    self.assertGreaterEqual(len(payload["data"]["info_sections"]), 2)
    self.assertEqual(payload["data"]["info_sections"][0]["title"], "设备信息")
    self.assertEqual(payload["data"]["info_sections"][1]["title"], "工作状态")
    self.assertEqual(payload["data"]["info_sections"][0]["rows"][0]["path"], "device_info.device_name")
    self.assertIn("n", payload["data"]["track_profiles"])
    self.assertIn("ho", payload["data"]["track_profiles"])
    self.assertIn("g", payload["data"]["track_profiles"])
    self.assertIn("dc", payload["data"]["track_profiles"])
    self.assertFalse(payload["data"]["safe_for_cv"])
    self.assertEqual(payload["data"]["cv_safety_warnings"], ["programming_track_status_unconfirmed"])
    self.assertEqual(payload["data"]["read_capability"]["ready"], False)
    self.assertEqual(payload["data"]["read_capability"]["warnings"], ["controller_ip_unconfigured"])

  def test_controller_info_exposes_z21_railcom_as_writable(self):
    state = default_state()
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_Z21_STD,
      "protocol": models.CONTROLLER_PROTOCOL_Z21_LAN,
      "device_info": {},
    })

    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["controller_protocol"], models.CONTROLLER_PROTOCOL_Z21_LAN)
    self.assertEqual(payload["data"]["railcom_setting"], {
      "available": True,
      "writable": True,
      "enabled": None,
      "source": "",
      "message": "",
    })

  def test_controller_info_reports_unwritable_z21_railcom_message(self):
    registry = ControllerRegistry()
    registry.register(RailComStateOnlyZ21Adapter(), default=True)
    state = default_state()
    state["controller"].update({
      "kind": RailComStateOnlyZ21Adapter.kind,
      "protocol": models.CONTROLLER_PROTOCOL_Z21_LAN,
      "device_info": {"railcom_enabled": True},
    })

    body, status = ApiRouter(None, controller_registry=registry).handle_json(
      "GET",
      "/api/controller/info",
      b"",
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["railcom_setting"], {
      "available": True,
      "writable": False,
      "enabled": True,
      "source": "device_info",
      "message": "当前 Z21 控制器配置未开放 RailCom 写入。",
    })

  def test_registered_controller_info_sections_use_standard_titles(self):
    registry = default_controller_registry()

    for adapter in registry.adapters():
      with self.subTest(controller=adapter.kind):
        titles = [section["title"] for section in adapter.info_sections[:2]]
        self.assertEqual(titles, ["设备信息", "工作状态"])

  def test_controller_info_exposes_ecos_railcom_and_railcomplus_state_as_writable(self):
    state = default_state()
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_ECOS_50200,
      "protocol": models.CONTROLLER_PROTOCOL_ECOS,
      "device_info": {"railcom": "enabled", "railcomplus": "0"},
    })

    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["controller_protocol"], models.CONTROLLER_PROTOCOL_ECOS)
    self.assertEqual(payload["data"]["railcom_setting"], {
      "available": True,
      "writable": True,
      "enabled": True,
      "source": "device_info",
      "message": "",
      "railcomplus": {
        "available": True,
        "writable": True,
        "enabled": False,
        "source": "device_info",
        "message": "",
      },
    })

  def test_controller_info_prefers_ecos_railcom_protocol_field_when_legacy_enabled_is_null(self):
    state = default_state()
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_ECOS_50200,
      "protocol": models.CONTROLLER_PROTOCOL_ECOS,
      "device_info": {
        "railcom_enabled": None,
        "railcom": "1",
        "railcomplus_enabled": None,
        "railcomplus": "1",
      },
    })

    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["railcom_setting"]["enabled"], True)
    self.assertEqual(payload["data"]["railcom_setting"]["source"], "device_info")
    self.assertEqual(payload["data"]["railcom_setting"]["railcomplus"]["enabled"], True)

  def test_controller_info_hides_railcomplus_for_non_ecos_controller_even_if_old_setting_exists(self):
    state = default_state()
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_Z21_STD,
      "protocol": models.CONTROLLER_PROTOCOL_Z21_LAN,
      "device_info": {"railcom_enabled": True},
      "settings": {"railcomplus_enabled": True},
    })

    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertNotIn("railcomplus", payload["data"]["railcom_setting"])

  def test_default_state_tracks_controller_safety_snapshot(self):
    state = default_state()
    snapshot = state["controller"]["safety_snapshot"]
    self.assertFalse(snapshot["booster_status_fresh"])
    self.assertFalse(snapshot["programming_track_status_fresh"])
    self.assertEqual(snapshot["controller_endpoint_version"], 0)

  def test_controller_safety_helper_invalidates_runtime_status(self):
    from server.controller_safety import invalidate_controller_safety

    controller = {
      "last_probe_ok": True,
      "controller_reachable": True,
      "booster_status": {"source": "dxdcnet_status_0x23"},
      "programming_track_status": {"source": "dxdcnet_status_0x23"},
      "safety_snapshot": {
        "controller_endpoint_version": 3,
        "last_read_info_at": "2026-06-25T00:00:00+08:00",
        "booster_status_fresh": True,
        "programming_track_status_fresh": True,
      },
    }
    invalidate_controller_safety(controller, reason="controller_endpoint_changed")
    self.assertFalse(controller["last_probe_ok"])
    self.assertFalse(controller["controller_reachable"])
    self.assertEqual(controller["controller_unreachable_reason"], "controller_endpoint_changed")
    self.assertNotIn("booster_status", controller)
    self.assertNotIn("programming_track_status", controller)
    self.assertEqual(controller["safety_snapshot"]["controller_endpoint_version"], 4)
    self.assertFalse(controller["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(controller["safety_snapshot"]["programming_track_status_fresh"])

  def test_controller_safety_helper_marks_fresh_status(self):
    from server.controller_safety import mark_controller_safety_fresh

    controller = {"safety_snapshot": {"controller_endpoint_version": 2}}
    mark_controller_safety_fresh(controller, booster_status_fresh=True, programming_track_status_fresh=False)
    snapshot = controller["safety_snapshot"]
    self.assertEqual(snapshot["controller_endpoint_version"], 2)
    self.assertTrue(snapshot["booster_status_fresh"])
    self.assertFalse(snapshot["programming_track_status_fresh"])
    self.assertTrue(snapshot["last_read_info_at"])

  def test_controller_info_exposes_cached_cv_safety(self):
    state = default_state()
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
      "programming_track_busy": False,
      "programming_track_current_ma": 0,
      "programming_track_current_raw": 0,
      "output_value": 0x78,
      "current_limit_ma": 400,
      "current_param": 0x81,
    }
    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["safe_for_cv"])
    self.assertIn("programming_track_safety_failed", payload["data"]["cv_safety_warnings"])
    self.assertEqual(payload["data"]["programming_track_status"]["source"], "dxdcnet_status_0x23")

  def test_controller_info_exposes_cached_booster_status_for_header_lamp(self):
    state = default_state()
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {
      "source": "dxdcnet_status_0x23",
      "power_on": False,
      "short_circuit": False,
      "current_alarm": False,
    }
    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["connection"]["controller_reachable"], True)
    self.assertEqual(payload["data"]["connection"]["track_powered"], False)
    self.assertEqual(payload["data"]["connection"]["short_circuit"], False)
    self.assertEqual(payload["data"]["booster_status"]["power_on"], False)

  def test_controller_info_requires_checksum_before_readiness(self):
    state = default_state()
    state["controller"]["ip"] = "192.0.2.10"
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["read_capability"]["ready"], False)
    self.assertIn("udp_checksum_algorithm_unconfirmed", payload["data"]["read_capability"]["warnings"])

  def test_controller_settings_saves_local_safe_profile(self):
    state = default_state()
    request = {
      "track_profiles": {
        "n": {"target_voltage_v": 11.5, "target_current_limit_ma": 200},
        "ho": {"target_voltage_v": 15.0, "target_current_limit_ma": 240},
      }
    }
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["applied_to_device"])
    self.assertEqual(state["controller"]["track_profiles"]["n"]["target_current_limit_ma"], 200)

  def test_z21_controller_settings_keep_voltage_profile_without_current_limit(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_Z21_STD)
    state["controller"]["kind"] = models.CONTROLLER_KIND_Z21_STD

    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"track_profiles":{"ho":{"target_voltage_v":17.0}},"settings":{"programming_track_voltage_v":15.5}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_profiles"]["ho"]["target_voltage_v"], 17.0)
    self.assertEqual(payload["data"]["settings"]["programming_track_voltage_v"], 15.5)
    self.assertNotIn("target_current_limit_ma", payload["data"]["track_profiles"]["ho"])
    self.assertNotIn("max_target_current_limit_ma", state["controller"]["track_profiles"]["ho"])
    self.assertEqual(state["controller"]["settings"]["programming_track_voltage_v"], 15.5)

  def test_z21_controller_settings_apply_voltage_to_device_and_verify_readback(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_Z21_STD)
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_Z21_STD,
      "ip": "192.0.2.21",
      "udp_port": 21105,
      "local_udp_port": 0,
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    })
    transport = FakeZ21SettingsTransport()

    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":true,"track_profiles":{"ho":{"target_voltage_v":17.0}}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["device_results"][0]["setting"], "z21_mmdcc_voltage")
    self.assertEqual(payload["data"]["device_results"][0]["output_voltage_mv"], 17000)
    self.assertEqual(payload["data"]["device_results"][0]["programming_voltage_mv"], 16000)
    self.assertEqual(state["controller"]["track_profiles"]["ho"]["target_voltage_v"], 17.0)
    self.assertEqual(state["controller"]["booster_status"]["output_voltage_v"], 17.0)
    self.assertEqual([entry["payload"] for entry in transport.requests], [
      bytes.fromhex("04 00 16 00"),
      bytes.fromhex("14 00 17 00 19 06 07 01 05 14 88 13 10 27 32 80 68 42 80 3e"),
      bytes.fromhex("04 00 16 00"),
    ])

  def test_z21_track_mode_switch_applies_selected_profile_voltage(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_Z21_STD)
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_Z21_STD,
      "ip": "192.0.2.21",
      "udp_port": 21105,
      "local_udp_port": 0,
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "track_mode": models.TRACK_MODE_N,
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    })
    state["controller"]["track_profiles"]["ho"]["target_voltage_v"] = 17.5
    transport = FakeZ21SettingsTransport()

    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/track-mode",
      b'{"track_mode":"ho"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "ho")
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["device_results"][0]["setting"], "z21_mmdcc_voltage")
    self.assertEqual(payload["data"]["device_results"][0]["output_voltage_mv"], 17500)
    self.assertEqual(payload["data"]["device_results"][0]["programming_voltage_mv"], 16000)
    self.assertEqual(state["controller"]["track_mode"], "ho")
    self.assertEqual(state["controller"]["booster_status"]["output_voltage_v"], 17.5)
    self.assertEqual([entry["payload"] for entry in transport.requests], [
      bytes.fromhex("04 00 16 00"),
      bytes.fromhex("14 00 17 00 19 06 07 01 05 14 88 13 10 27 32 80 5c 44 80 3e"),
      bytes.fromhex("04 00 16 00"),
    ])

  def test_ecos_controller_settings_keep_current_limit_profile_without_voltage(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_ECOS_50200)
    state["controller"]["kind"] = models.CONTROLLER_KIND_ECOS_50200

    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"track_profiles":{"n":{"target_current_limit_ma":3500}},"settings":{"short_circuit_detection_delay_ms":1500}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["applied_to_device"])
    self.assertNotIn("target_voltage_v", payload["data"]["track_profiles"]["n"])
    self.assertEqual(payload["data"]["track_profiles"]["n"]["target_current_limit_ma"], 3500)
    self.assertEqual(payload["data"]["settings"]["short_circuit_detection_delay_ms"], 1500)
    self.assertEqual(state["controller"]["track_profiles"]["n"]["target_current_limit_ma"], 3500)
    self.assertEqual(state["controller"]["settings"]["short_circuit_detection_delay_ms"], 1500)

  def test_controller_info_exposes_database_default_track_output_settings(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      state_store = AppStateStore(root / "data" / "app-state.json")
      state = state_store.load()
      state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_Z21_STD)
      state["controller"]["kind"] = models.CONTROLLER_KIND_Z21_STD
      state["controller"]["track_profiles"]["ho"]["target_voltage_v"] = 17.5
      router = ApiRouter(state_store)

      body, status = router.handle_json("GET", "/api/controller/info", b"", state)
      payload = json.loads(body.decode("utf-8"))

      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["track_profiles"]["ho"]["target_voltage_v"], 17.5)
      self.assertEqual(payload["data"]["default_track_output_settings"]["track_profiles"]["ho"]["target_voltage_v"], 16.0)
      self.assertEqual(payload["data"]["settings"]["programming_track_voltage_v"], 16.0)
      self.assertEqual(payload["data"]["default_track_output_settings"]["settings"], {"programming_track_voltage_v": 16.0})
      self.assertIn("programming_track_voltage_v", [
        spec["key"] for spec in payload["data"]["track_output_setting_specs"]
      ])

  def test_ecos_controller_settings_apply_current_limit_to_booster(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_ECOS_50200)
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_ECOS_50200,
      "ip": "192.0.2.97",
      "tcp_port": 15471,
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    })
    transport = FakeECoSSettingsTransport()

    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":true,"track_profiles":{"ho":{"target_current_limit_ma":3500}},"settings":{"short_circuit_detection_delay_ms":2000}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["device_results"][0]["setting"], "ecos_booster_current_limit")
    self.assertEqual(payload["data"]["device_results"][0]["target_current_limit_ma"], 3500)
    self.assertEqual(payload["data"]["device_results"][0]["readback_current_limit_ma"], 3500)
    self.assertEqual(state["controller"]["track_profiles"]["ho"]["target_current_limit_ma"], 3500)
    self.assertEqual(state["controller"]["settings"]["short_circuit_detection_delay_ms"], 2000)
    self.assertEqual(state["controller"]["booster_status"]["limit_ma"], 3500)
    self.assertEqual([entry["commands"] for entry in transport.requests], [[
      "request(65000, control)",
      "set(65000, limit[3500])",
      "get(65000, limit)",
      "release(65000, control)",
    ]])

  def test_controller_settings_normalizes_existing_transport_config(self):
    state = default_state()
    state["controller"]["transport"].update({
      "udp_port": 12001,
      "local_udp_port": 0,
      "udp_checksum_algorithm": "xor",
    })
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"track_mode":"ho"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["transport"]["udp_port"], 12001)
    self.assertEqual(payload["data"]["transport"]["local_udp_port"], 6667)
    self.assertEqual(payload["data"]["transport"]["udp_checksum_algorithm"], "xor")
    self.assertEqual(state["controller"]["udp_port"], 12001)
    self.assertEqual(state["controller"]["local_udp_port"], 6667)
    self.assertEqual(state["controller"]["udp_checksum_algorithm"], "xor")

  def test_controller_settings_applies_current_limit_to_controller_and_verifies_readback(self):
    state = self._state_with_confirmed_udp()
    requests = {
      bytes.fromhex("ff ff 18 01 40 00 00 82 64 bf"): [],
      bytes.fromhex("ff ff 17 01 41 00 00 82 d5"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x82, 0x64]),
        )
      ],
    }
    request = {
      "apply_to_device": True,
      "track_profiles": {
        "ho": {"target_voltage_v": 15.2, "target_current_limit_ma": 4000},
      },
    }
    transport = FakeRequestMappedUdpTransport(requests)
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["device_results"][0]["mode"], "ho")
    self.assertEqual(payload["data"]["device_results"][0]["param_address"], 0x82)
    self.assertEqual(payload["data"]["device_results"][0]["raw_value"], 0x64)
    self.assertEqual(payload["data"]["device_results"][0]["target_current_limit_ma"], 4000)
    self.assertEqual(state["controller"]["track_profiles"]["ho"]["target_current_limit_ma"], 4000)
    self.assertEqual([entry["payload"] for entry in transport.requests], [
      bytes.fromhex("ff ff 18 01 40 00 00 82 64 bf"),
      bytes.fromhex("ff ff 17 01 41 00 00 82 d5"),
    ])

  def test_controller_settings_applies_digsight_railcom_setting_and_verifies_readback(self):
    state = self._state_with_confirmed_udp()
    requests = {
      bytes.fromhex("ff ff 18 01 40 00 00 03 80 da"): [],
      bytes.fromhex("ff ff 17 01 41 00 00 03 54"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x03, 0x80]),
        )
      ],
    }
    request = {
      "apply_to_device": True,
      "settings": {
        "railcom_enabled": True,
      },
    }
    transport = FakeRequestMappedUdpTransport(requests)
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["settings"]["railcom_enabled"], True)
    self.assertEqual(payload["data"]["device_results"], [{
      "setting": "railcom_enabled",
      "param_address": 0x03,
      "raw_value": 0x80,
      "enabled": True,
      "write_request_hex": "ff ff 18 01 40 00 00 03 80 da",
      "read_request_hex": "ff ff 17 01 41 00 00 03 54",
    }])
    self.assertEqual(state["controller"]["settings"]["railcom_enabled"], True)
    self.assertEqual(state["controller"]["device_info"]["railcom_enabled"], True)
    self.assertEqual([entry["payload"] for entry in transport.requests], [
      bytes.fromhex("ff ff 18 01 40 00 00 03 80 da"),
      bytes.fromhex("ff ff 17 01 41 00 00 03 54"),
    ])

  def test_controller_settings_applies_z21_railcom_setting_and_verifies_readback(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_Z21_STD)
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_Z21_STD,
      "ip": "192.0.2.21",
      "udp_port": 21105,
      "local_udp_port": 0,
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    })
    transport = FakeZ21SettingsTransport()
    before_settings = parse_common_settings(transport.common_settings_payload)
    write_request = build_set_common_settings(before_settings.with_railcom(False))

    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":true,"settings":{"railcom_enabled":false}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["device_results"][0]["setting"], "railcom_enabled")
    self.assertFalse(payload["data"]["device_results"][0]["enabled"])
    self.assertFalse(state["controller"]["settings"]["railcom_enabled"])
    self.assertFalse(state["controller"]["device_info"]["railcom_enabled"])
    self.assertEqual([entry["payload"] for entry in transport.requests], [
      build_get_common_settings(),
      write_request,
      build_get_common_settings(),
    ])

  def test_controller_settings_drops_ecos_private_settings_when_switching_to_z21(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_ECOS_50200)
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_ECOS_50200,
      "ip": "192.0.2.97",
      "tcp_port": 15471,
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "settings": {"railcom_enabled": True, "railcomplus_enabled": True},
      "device_info": {"railcom": "1", "railcomplus": "1"},
    })

    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"kind":"z21_std_controller","ip":"192.0.2.21"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["kind"], models.CONTROLLER_KIND_Z21_STD)
    expected_settings = {
      "programming_track_voltage_v": 16.0,
      "railcom_enabled": True,
    }
    self.assertEqual(payload["data"]["settings"], expected_settings)
    self.assertEqual(state["controller"]["settings"], expected_settings)

  def test_controller_settings_applies_ecos_railcomplus_with_linked_railcom(self):
    state = default_state()
    state["controller"] = AppStateStore.default_controller_config(default_controller_registry(), models.CONTROLLER_KIND_ECOS_50200)
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_ECOS_50200,
      "ip": "192.0.2.97",
      "tcp_port": 15471,
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "telemetry": {},
      "device_info": {"railcom": "0", "railcomplus": "0"},
      "safety_snapshot": {},
    })
    transport = FakeECoSSettingsTransport()

    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":true,"settings":{"railcomplus_enabled":true}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["applied_to_device"])
    self.assertEqual(payload["data"]["settings"]["railcom_enabled"], True)
    self.assertEqual(payload["data"]["settings"]["railcomplus_enabled"], True)
    self.assertEqual(payload["data"]["device_results"], [{
      "setting": "ecos_railcom",
      "railcom_enabled": True,
      "railcomplus_enabled": True,
      "write_request_hex": "\n".join([
        "73 65 74 28 31 2c 20 72 61 69 6c 63 6f 6d 5b 31 5d 29",
        "73 65 74 28 31 2c 20 72 61 69 6c 63 6f 6d 70 6c 75 73 5b 31 5d 29",
        "67 65 74 28 31 2c 20 72 61 69 6c 63 6f 6d 2c 20 72 61 69 6c 63 6f 6d 70 6c 75 73 29",
      ]),
    }])
    self.assertEqual([entry["commands"] for entry in transport.requests], [[
      "set(1, railcom[1])",
      "set(1, railcomplus[1])",
      "get(1, railcom, railcomplus)",
    ]])

  def test_controller_settings_rejects_non_boolean_railcom_setting(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"settings":{"railcom_enabled":"true"}}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_settings")
    self.assertIn("settings.railcom_enabled", payload["error"]["detail"])

  def test_controller_settings_rejects_non_boolean_apply_to_device(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":"true"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_settings")
    self.assertIn("apply_to_device", payload["error"]["detail"])

  def test_controller_settings_rejects_controller_write_when_readback_mismatches(self):
    state = self._state_with_confirmed_udp()
    state["controller"]["track_mode"] = "n"
    requests = {
      bytes.fromhex("ff ff 18 01 40 00 00 82 64 bf"): [],
      bytes.fromhex("ff ff 17 01 41 00 00 82 d5"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x82, 0x63]),
        )
      ],
    }
    request = {
      "apply_to_device": True,
      "track_mode": "ho",
      "track_profiles": {
        "ho": {"target_voltage_v": 15.2, "target_current_limit_ma": 4000},
      },
    }
    body, status = ApiRouter(None, controller_transport=FakeRequestMappedUdpTransport(requests)).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "controller_parameter_write_failed")
    self.assertNotEqual(state["controller"]["track_profiles"]["ho"]["target_current_limit_ma"], 4000)
    self.assertEqual(state["controller"]["track_mode"], "n")

  def test_controller_settings_saves_operation_mode_and_clears_safety_cache(self):
    state = default_state()
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
    }
    request = {"track_mode": "g"}
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "g")
    self.assertEqual(state["controller"]["track_mode"], "g")
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])
    self.assertNotIn("operation_mode_not_safe_for_current_decoder", payload["data"]["warnings"])

  def test_track_power_status_missing_clears_cached_safety_state(self):
    state = default_state()
    state["controller"]["ip"] = "192.0.2.10"
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {
      "source": "dxdcnet_status_0x23",
      "power_on": True,
      "dcc_mode": True,
    }
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
      "programming_track_busy": False,
      "programming_track_current_ma": 0,
      "output_value": 0x78,
      "current_limit_ma": 0,
      "current_limit_confirmed": False,
    }
    state["controller"]["safety_snapshot"] = {
      "controller_endpoint_version": 1,
      "last_read_info_at": "2026-06-22T00:00:00+08:00",
      "booster_status_fresh": True,
      "programming_track_status_fresh": True,
    }
    body, status = ApiRouter(None, controller_transport=FakeRequestMappedUdpTransport({})).handle_json(
      "POST",
      "/api/track-power",
      b'{"powered":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 504)
    self.assertEqual(payload["error"]["type"], "track_power_status_missing")
    self.assertNotIn("booster_status", state["controller"])
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])

  def test_controller_settings_saves_programming_target(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"programming_target":"main_track"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["programming_target"], "main_track")
    self.assertEqual(state["controller"]["programming_target"], "main_track")

  def test_controller_settings_accepts_controller_kind_and_invalidates_runtime(self):
    state = default_state()
    state["controller"]["controller_reachable"] = True
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      controller_ip_payload(kind="digsight_controller"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["data"]["ip"], controller_test_ip())
    self.assertEqual(state["controller"]["kind"], "digsight_controller")

  def test_controller_settings_rejects_unknown_controller_kind(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"kind":"unknown_controller"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_kind")

  def test_controller_settings_accepts_kind_registered_in_router_registry(self):
    registry = ControllerRegistry()
    registry.register(ExampleControllerAdapter())
    state = default_state()
    body, status = ApiRouter(None, controller_registry=registry).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"kind":"example_controller"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["kind"], "example_controller")
    self.assertEqual(state["controller"]["kind"], "example_controller")

  def test_controller_settings_uses_adapter_transport_descriptor_when_kind_changes(self):
    registry = ControllerRegistry()
    registry.register(CustomDefaultsControllerAdapter())
    state = default_state()
    body, status = ApiRouter(None, controller_registry=registry).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"kind":"custom_defaults_controller"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["transport"]["udp_port"], 21105)
    self.assertEqual(payload["data"]["transport"]["local_udp_port"], 0)
    self.assertEqual(payload["data"]["transport"]["udp_checksum_algorithm"], "none")

  def test_controller_settings_rebuilds_config_identity_from_target_kind_defaults(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      state["controller"]["display_name"] = "旧控制器显示名"
      state["controller"]["protocol"] = "OldProtocol"
      store.save(state)

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      custom_config = json.loads(
        (root / "config" / "controllers" / "custom-controller-settings.json").read_text(encoding="utf-8")
      )
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(payload["data"]["kind"], "custom_defaults_controller")
      self.assertEqual(state["controller"]["display_name"], "Custom Defaults Controller")
      self.assertEqual(state["controller"]["protocol"], "CustomProtocol")
      self.assertEqual(custom_config["display_name"], "Custom Defaults Controller")
      self.assertEqual(custom_config["protocol"], "CustomProtocol")

  def test_controller_settings_rejects_invalid_ip_from_target_kind_config(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / "custom-controller-settings.json").write_text(json.dumps({
        "display_name": "Custom Defaults Controller",
        "protocol": "CustomProtocol",
        "ip": "not-an-ip",
        "transport": {
          "kind": "udp",
          "udp_port": 21105,
          "local_udp_port": 0,
          "udp_checksum_algorithm": "none",
        },
      }), encoding="utf-8")
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_controller_settings")
      self.assertEqual(state["controller"]["kind"], "digsight_controller")

  def test_controller_settings_uses_existing_ip_when_target_kind_config_ip_is_empty(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / "custom-controller-settings.json").write_text(json.dumps({
        "display_name": "Custom Defaults Controller",
        "protocol": "CustomProtocol",
        "ip": "",
        "transport": {
          "kind": "udp",
          "udp_port": 21105,
          "local_udp_port": 0,
          "udp_checksum_algorithm": "none",
        },
      }), encoding="utf-8")
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      state["controller"]["ip"] = "192.0.2.77"

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["ip"], "192.0.2.77")
      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertEqual(state["controller"]["ip"], "192.0.2.77")

  def test_controller_settings_normalizes_target_kind_config_ports_above_udp_range(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / "custom-controller-settings.json").write_text(json.dumps({
        "display_name": "Custom Defaults Controller",
        "protocol": "CustomProtocol",
        "ip": "192.0.2.10",
        "transport": {
          "kind": "udp",
          "udp_port": 99999,
          "local_udp_port": 99999,
          "udp_checksum_algorithm": "none",
        },
      }), encoding="utf-8")
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["transport"]["udp_port"], 21105)
      self.assertEqual(payload["data"]["transport"]["local_udp_port"], 0)
      self.assertEqual(state["controller"]["udp_port"], 21105)
      self.assertEqual(state["controller"]["local_udp_port"], 0)

  def test_controller_settings_reports_malformed_target_kind_config_without_rewrite(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      custom_config_path = config_dir / "custom-controller-settings.json"
      malformed_config = "{not json"
      custom_config_path.write_text(malformed_config, encoding="utf-8")
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      self.assertEqual(state["controller"]["kind"], "digsight_controller")
      self.assertIsNone(state.get("last_error"))

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 409)
      self.assertFalse(payload["ok"])
      self.assertEqual(payload["error"]["type"], "controller_config_invalid")
      self.assertEqual(payload["debug"]["controller_kind"], "custom_defaults_controller")
      self.assertEqual(payload["debug"]["resettable_files"], ["config/controllers/custom-controller-settings.json"])
      self.assertEqual(state["controller"]["kind"], "digsight_controller")
      self.assertEqual(state["last_error"]["type"], "controller_config_invalid")
      self.assertEqual(state["last_error"]["controller_kind"], "custom_defaults_controller")
      self.assertEqual(custom_config_path.read_text(encoding="utf-8"), malformed_config)
      reloaded = store.load()
      self.assertEqual(reloaded["last_error"]["type"], "controller_config_invalid")
      self.assertEqual(reloaded["last_error"]["controller_kind"], "custom_defaults_controller")
      self.assertEqual(custom_config_path.read_text(encoding="utf-8"), malformed_config)

  def test_controller_settings_clears_stale_config_error_when_kind_changes_without_requested_ip(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / registry.config_file_name("digsight_controller")).write_text("not json", encoding="utf-8")
      custom_config_path = config_dir / "custom-controller-settings.json"
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      self.assertEqual(state["last_error"]["type"], "controller_config_invalid")

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertNotEqual((state.get("last_error") or {}).get("type"), "controller_config_invalid")
      self.assertTrue(custom_config_path.exists())
      custom_config = json.loads(custom_config_path.read_text(encoding="utf-8"))
      self.assertEqual(custom_config["display_name"], "Custom Defaults Controller")
      self.assertEqual(custom_config["protocol"], "CustomProtocol")

  def test_controller_settings_uses_adapter_transport_descriptor(self):
    registry = ControllerRegistry()
    registry.register(CustomDefaultsControllerAdapter())
    state = default_state()
    request = {
      "kind": "custom_defaults_controller",
      "ip": "192.0.2.10",
    }
    body, status = ApiRouter(None, controller_registry=registry).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["transport"]["udp_port"], 21105)
    self.assertEqual(payload["data"]["transport"]["local_udp_port"], 0)
    self.assertEqual(payload["data"]["transport"]["udp_checksum_algorithm"], "none")
    self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")

  def test_controller_settings_rebuilds_config_identity_and_keeps_requested_ip_when_kind_changes(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      state["controller"]["display_name"] = "旧控制器显示名"
      state["controller"]["protocol"] = "OldProtocol"
      store.save(state)

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        json.dumps({"kind": "custom_defaults_controller", "ip": "192.0.2.10"}).encode("utf-8"),
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      custom_config = json.loads(
        (root / "config" / "controllers" / "custom-controller-settings.json").read_text(encoding="utf-8")
      )
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertEqual(state["controller"]["display_name"], "Custom Defaults Controller")
      self.assertEqual(state["controller"]["protocol"], "CustomProtocol")
      self.assertEqual(custom_config["display_name"], "Custom Defaults Controller")
      self.assertEqual(custom_config["protocol"], "CustomProtocol")

  def test_controller_settings_clears_stale_config_error_when_kind_changes_with_requested_ip(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      (config_dir / registry.config_file_name("digsight_controller")).write_text("not json", encoding="utf-8")
      custom_config_path = config_dir / "custom-controller-settings.json"
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      self.assertEqual(state["last_error"]["type"], "controller_config_invalid")

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "PATCH",
        "/api/controller/settings",
        json.dumps({"kind": "custom_defaults_controller", "ip": "192.0.2.10"}).encode("utf-8"),
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(state["controller"]["kind"], "custom_defaults_controller")
      self.assertNotEqual((state.get("last_error") or {}).get("type"), "controller_config_invalid")
      self.assertTrue(custom_config_path.exists())
      custom_config = json.loads(custom_config_path.read_text(encoding="utf-8"))
      self.assertEqual(custom_config["display_name"], "Custom Defaults Controller")
      self.assertEqual(custom_config["protocol"], "CustomProtocol")

  def test_controller_reset_config_rejects_non_current_kind(self):
    registry = default_controller_registry()
    registry.register(CustomDefaultsControllerAdapter())
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      custom_config_path = root / "config" / "controllers" / "custom-controller-settings.json"
      store = AppStateStore(root / "data" / "app-state.json", controller_registry=registry)
      state = store.load()
      self.assertEqual(state["controller"]["kind"], "digsight_controller")

      body, status = ApiRouter(store, controller_registry=registry).handle_json(
        "POST",
        "/api/controller/reset-config",
        b'{"kind":"custom_defaults_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 409)
      self.assertEqual(payload["error"]["type"], "controller_config_reset_kind_mismatch")
      self.assertFalse(custom_config_path.exists())

  def test_controller_settings_rejects_kind_missing_from_router_registry(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"kind":"example_controller"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_kind")

  def test_controller_settings_apply_to_device_requires_adapter_support(self):
    registry = ControllerRegistry()
    registry.register(ExampleControllerAdapter())
    state = default_state()
    state["controller"]["kind"] = "example_controller"
    state["controller"]["protocol"] = "ExampleProtocol"
    state["controller"]["transport"] = ExampleControllerAdapter.transport_descriptor.default_config()
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    request = {
      "apply_to_device": True,
      "track_profiles": {
        "ho": {"target_voltage_v": 15.2, "target_current_limit_ma": 4000},
      },
    }
    body, status = ApiRouter(
      None,
      controller_registry=registry,
      controller_transport=FakeRequestMappedUdpTransport({}),
    ).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "controller_operation_not_supported")
    self.assertEqual(payload["error"]["message"], "当前控制器不支持该操作")
    self.assertEqual(payload["error"]["detail"], "example_controller does not support controller_settings")

  def test_controller_settings_apply_to_device_uses_adapter_readiness_detail(self):
    registry = ControllerRegistry()
    registry.register(SettingsReadyExampleControllerAdapter(), default=True)
    state = default_state(registry)
    request = {
      "apply_to_device": True,
      "track_profiles": {
        "ho": {"target_voltage_v": 15.2, "target_current_limit_ma": 4000},
      },
    }

    body, status = ApiRouter(
      None,
      controller_registry=registry,
      controller_transport=FakeRequestMappedUdpTransport({}),
    ).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )

    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["error"]["detail"], "样例控制器未实现通信运行时")
    self.assertNotIn("通信端口", payload["error"]["detail"])
    self.assertNotIn("校验算法", payload["error"]["detail"])

  def test_controller_settings_rejects_unknown_operation_mode(self):
    state = default_state()
    request = {"track_mode": "z"}
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_settings")

  def test_controller_settings_rejects_unsafe_n_voltage(self):
    state = default_state()
    request = {"track_profiles": {"n": {"target_voltage_v": 13.0, "target_current_limit_ma": 200}}}
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_settings")

  def test_controller_settings_accepts_dc_voltage_profile_without_real_dc_output(self):
    state = default_state()
    request = {"track_profiles": {"dc": {"target_voltage_v": 13.0, "target_current_limit_ma": 2000}}}
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_profiles"]["dc"]["target_voltage_v"], 13.0)
    self.assertEqual(state["controller"]["track_profiles"]["dc"]["target_voltage_v"], 13.0)

  def test_controller_read_info_requires_confirmed_udp_and_checksum(self):
    state = default_state()
    state["controller"]["ip"] = "192.0.2.10"
    state["controller"]["udp_port"] = 0
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("POST", "/api/controller/read-info", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertIn("udp_port_unconfirmed", payload["debug"]["warnings"])
    self.assertIn("udp_checksum_algorithm_unconfirmed", payload["debug"]["warnings"])

  def test_controller_read_info_requires_confirmed_checksum_when_port_is_set(self):
    state = default_state()
    state["controller"]["ip"] = "192.0.2.10"
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("POST", "/api/controller/read-info", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["error"]["detail"], "控制器 UDP 校验算法未确认")
    self.assertEqual(payload["debug"]["warnings"], ["udp_checksum_algorithm_unconfirmed"])

  def _ecos_read_info_state(self):
    state = default_state()
    state["controller"].update({
      "kind": models.CONTROLLER_KIND_ECOS_50200,
      "protocol": models.CONTROLLER_PROTOCOL_ECOS,
      "ip": "192.0.2.50",
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "tcp_port": 15471,
      "booster_status": {"source": "ecos_object_1", "power_on": True},
      "programming_track_status": {"source": "old_status"},
      "safety_snapshot": {
        "controller_endpoint_version": 1,
        "last_read_info_at": "2026-07-01T00:00:00+08:00",
        "booster_status_fresh": True,
        "programming_track_status_fresh": True,
      },
    })
    return state

  def test_ecos_read_info_timeout_returns_structured_error_and_invalidates_safety(self):
    state = self._ecos_read_info_state()

    body, status = ApiRouter(None, controller_transport=FakeECoSTimeoutTransport()).handle_json(
      "POST",
      "/api/controller/read-info",
      b"{}",
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 504)
    self.assertEqual(payload["error"]["type"], "controller_read_info_failed")
    self.assertEqual(payload["error"]["message"], "读取控制器信息失败")
    self.assertEqual(payload["debug"]["exception_type"], "TimeoutError")
    self.assertFalse(state["controller"]["controller_reachable"])
    self.assertEqual(state["controller"]["controller_unreachable_reason"], "controller_read_info_failed")
    self.assertNotIn("booster_status", state["controller"])
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])

  def test_ecos_read_info_missing_basic_info_returns_structured_error(self):
    state = self._ecos_read_info_state()

    body, status = ApiRouter(None, controller_transport=FakeECoSMissingInfoTransport()).handle_json(
      "POST",
      "/api/controller/read-info",
      b"{}",
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "controller_read_info_failed")
    self.assertIn("basic information", payload["error"]["detail"])
    self.assertEqual(payload["debug"]["exception_type"], "ValueError")

  def _controller_read_info_success_requests(self):
    return {
      bytes.fromhex("ff ff 16 01 22 00 00 35"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
        )
      ],
      bytes.fromhex("ff ff 16 01 22 07 01 33"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x78, 0x78, 0x01, 0x22, 0x00, 0x00, 0x90]),
        )
      ],
      bytes.fromhex("ff ff 16 01 84 00 00 93"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_VERSION_DATA,
          payload=bytes([0x1E, 0x16]),
        )
      ],
      bytes.fromhex("ff ff 16 01 84 0f 0f 93"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_SPECIAL,
          source_id=15,
          command=CMD_VERSION_DATA,
          payload=bytes([0x1E, 0x13]),
        )
      ],
      bytes.fromhex("ff ff 16 01 84 07 01 95"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_VERSION_DATA,
          payload=bytes([0x1E, 0x16]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 03 54"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x03, 0x80]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 7e 29"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x7E, 0x80]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 80 d7"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x80, 0x02]),
        )
      ],
      bytes.fromhex("ff ff 16 01 0b 00 01 1d"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_MAC_ADDRESS,
          payload=bytes([0x00, 0x34, 0x35, 0x38, 0x31, 0x1B, 0x6B]),
        ),
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_MAC_ADDRESS,
          payload=bytes([0x01, 0x33, 0x37, 0x39, 0x4A, 0x0D, 0x32]),
        ),
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 81 d6"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x81, 0x0A]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 82 d5"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x82, 0x64]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 83 d4"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x83, 0xAF]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 84 d3"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x84, 0x32]),
        )
      ],
    }

  def _state_with_confirmed_udp(self):
    state = default_state()
    state["controller"]["ip"] = "192.0.2.10"
    state["controller"]["udp_port"] = 12000
    state["controller"]["local_udp_port"] = 6667
    state["controller"]["udp_checksum_algorithm"] = "xor"
    return state

  def test_controller_read_info_reads_version_status_and_current_limit(self):
    state = self._state_with_confirmed_udp()
    requests = self._controller_read_info_success_requests()
    transport = FakeRequestMappedUdpTransport(requests)
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "POST",
      "/api/controller/read-info",
      b"{}",
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["safe_for_cv"])
    self.assertIn("programming_track_current_limit_unconfirmed", payload["data"]["warnings"])
    self.assertNotIn("main_track_current_limit_not_used_for_programming_track", payload["data"]["warnings"])
    self.assertNotIn("main_track_output_value_not_used_for_programming_track", payload["data"]["warnings"])
    self.assertNotIn("Programming track current limit exceeds 250 mA", "\n".join(payload["data"]["warnings"]))
    self.assertNotIn("编程轨限流超过 250 mA", "\n".join(payload["data"]["warnings"]))
    self.assertEqual(state["controller"]["device_info"]["hardware_version"], "30")
    self.assertEqual(state["controller"]["device_info"]["core_version"], "3.0.1.9")
    self.assertEqual(state["controller"]["device_info"]["wireless_version"], "3.0.2.2")
    self.assertTrue(state["controller"]["device_info"]["railcom_enabled"])
    self.assertEqual(state["controller"]["device_info"]["factory_number"], "6B1B31383534320D4A393733")
    self.assertEqual(state["controller"]["telemetry"]["temperature_c"], 34)
    self.assertEqual(state["controller"]["telemetry"]["track_voltage_v"], 12.0)
    self.assertEqual(state["controller"]["telemetry"]["track_current_a"], 0.1)
    self.assertEqual(state["controller"]["device_info"]["screen_brightness"], 128)
    self.assertEqual(state["controller"]["device_info"]["screen_direction_raw"], 2)
    self.assertEqual(state["controller"]["device_info"]["screen_direction_label"], "右")
    self.assertEqual(state["controller"]["track_profiles"]["n"]["target_current_limit_ma"], 400)
    self.assertEqual(state["controller"]["track_profiles"]["ho"]["target_current_limit_ma"], 4000)
    self.assertEqual(state["controller"]["track_profiles"]["g"]["target_current_limit_ma"], 7000)
    self.assertEqual(state["controller"]["track_profiles"]["dc"]["target_current_limit_ma"], 2000)
    self.assertEqual(state["controller"]["programming_track_status"]["source"], "dxdcnet_status_0x23")
    self.assertEqual(state["controller"]["programming_track_status"]["output_value"], 0x78)
    self.assertFalse(state["controller"]["programming_track_status"]["current_limit_confirmed"])
    self.assertEqual(state["controller"]["programming_track_status"]["current_limit_ma"], 0)
    self.assertNotIn("main_track_current_limit_ma", state["controller"]["programming_track_status"])
    self.assertEqual(len(transport.requests), 13)
    self.assertEqual(transport.requests[0]["local_port"], 6667)
    self.assertEqual(transport.requests[0]["max_packets"], 8)
    timeouts = {request["name"]: request["timeout_seconds"] for request in payload["debug"]["requests"]}
    self.assertLessEqual(timeouts["command_station_status"], 0.4)
    self.assertLessEqual(timeouts["booster_status"], 0.4)
    self.assertLessEqual(timeouts["version"], 0.25)
    self.assertLessEqual(timeouts["mac"], 0.25)
    self.assertLessEqual(timeouts["current_limit_dc"], 0.25)

  def test_controller_read_info_blocks_cv_safety_when_booster_reports_dc(self):
    state = self._state_with_confirmed_udp()
    requests = {
      bytes.fromhex("ff ff 16 01 22 00 00 35"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
        )
      ],
      bytes.fromhex("ff ff 16 01 22 07 01 33"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x00, 0x0B, 0x00, 0x22, 0x00, 0x00, 0xF0]),
        )
      ],
      bytes.fromhex("ff ff 16 01 84 00 00 93"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_VERSION_DATA,
          payload=bytes([0x1E, 0x16]),
        )
      ],
      bytes.fromhex("ff ff 17 01 41 00 00 81 d6"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_PARAMETER_VALUE,
          payload=bytes([0x81, 0x0A]),
        )
      ],
    }
    body, status = ApiRouter(None, controller_transport=FakeRequestMappedUdpTransport(requests)).handle_json(
      "POST",
      "/api/controller/read-info",
      b"{}",
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["safe_for_cv"])
    self.assertEqual(state["controller"]["programming_track_status"]["source"], "dxdcnet_status_0x23_unsafe")
    self.assertIn("booster_dc_mode_reported", payload["data"]["warnings"])

  def test_controller_read_info_missing_booster_clears_cached_track_status(self):
    state = self._state_with_confirmed_udp()
    state["controller"]["booster_status"] = {
      "source": "dxdcnet_status_0x23",
      "power_on": True,
      "dcc_mode": True,
    }
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
    }
    state["controller"]["safety_snapshot"] = {
      "controller_endpoint_version": 1,
      "last_read_info_at": "2026-06-22T00:00:00+08:00",
      "booster_status_fresh": True,
      "programming_track_status_fresh": True,
    }
    requests = {
      bytes.fromhex("ff ff 16 01 22 00 00 35"): [
        build_udp_frame(
          device_type=DEVICE_TYPE_COMMAND_STATION,
          source_id=0,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
        )
      ],
    }
    body, status = ApiRouter(None, controller_transport=FakeRequestMappedUdpTransport(requests)).handle_json(
      "POST",
      "/api/controller/read-info",
      b"{}",
      state,
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["safe_for_cv"])
    self.assertIn("booster_status_missing", payload["data"]["warnings"])
    self.assertNotIn("booster_status", state["controller"])
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])
    self.assertEqual(state["controller"]["controller_unreachable_reason"], "booster_status_missing")


if __name__ == "__main__":
  unittest.main()

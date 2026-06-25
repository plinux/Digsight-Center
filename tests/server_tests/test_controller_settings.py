import json
import unittest

from server import models
from server.api import ApiRouter, SCREEN_DIRECTION_LABELS
from server.app_state import default_state
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
from tests.server_tests.controller_test_env import controller_ip_payload, controller_test_ip


class FakeRequestMappedUdpTransport:
  def __init__(self, responses_by_request):
    self.responses_by_request = responses_by_request
    self.requests = []

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None):
    self.requests.append({
      "host": host,
      "port": port,
      "payload": payload,
      "local_port": local_port,
      "max_packets": max_packets,
      "stop_when": bool(stop_when),
    })
    responses = []
    for response in self.responses_by_request.get(payload, [])[:max_packets]:
      responses.append(response)
      if stop_when and stop_when(response):
        break
    return responses


class ControllerSettingsTest(unittest.TestCase):
  def test_screen_direction_labels_follow_clockwise_app_sequence(self):
    self.assertEqual(SCREEN_DIRECTION_LABELS, {
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
    self.assertEqual(payload["data"]["connection"]["reachable"], True)
    self.assertEqual(payload["data"]["connection"]["controller_reachable"], False)
    self.assertEqual(payload["data"]["connection"]["gateway_ready"], True)
    self.assertEqual(payload["data"]["controller_kind"], "digsight_controller")
    self.assertEqual(payload["data"]["controller_label"], "动芯 DXDCNet")
    self.assertTrue(payload["data"]["controller_capabilities"]["track_power"])
    self.assertTrue(payload["data"]["controller_capabilities"]["read_info"])
    self.assertIn("n", payload["data"]["track_profiles"])
    self.assertIn("ho", payload["data"]["track_profiles"])
    self.assertIn("g", payload["data"]["track_profiles"])
    self.assertIn("dc", payload["data"]["track_profiles"])
    self.assertFalse(payload["data"]["safe_for_cv"])
    self.assertEqual(payload["data"]["cv_safety_warnings"], ["programming_track_status_unconfirmed"])

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

  def test_controller_info_requires_checksum_before_udp_ready(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("GET", "/api/controller/info", b"", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["read_capability"]["dxdcnet_udp_ready"], False)
    self.assertIn("udp_checksum_algorithm_unconfirmed", payload["data"]["read_capability"]["warnings"])

  def test_controller_settings_saves_local_safe_profile(self):
    state = default_state()
    request = {
      "track_profiles": {
        "n": {"voltage_v": 11.5, "current_limit_ma": 200},
        "ho": {"voltage_v": 15.0, "current_limit_ma": 240},
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
    self.assertEqual(state["controller"]["track_profiles"]["n"]["current_limit_ma"], 200)

  def test_controller_settings_preserves_existing_transport_config(self):
    state = default_state()
    state["controller"]["udp_port"] = 12001
    state["controller"]["local_udp_port"] = 0
    state["controller"]["udp_checksum_algorithm"] = "xor"
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"track_mode":"ho"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["udp_port"], 12001)
    self.assertEqual(payload["data"]["local_udp_port"], 0)
    self.assertEqual(payload["data"]["udp_checksum_algorithm"], "xor")
    self.assertEqual(state["controller"]["udp_port"], 12001)
    self.assertEqual(state["controller"]["local_udp_port"], 0)
    self.assertEqual(state["controller"]["udp_checksum_algorithm"], "xor")

  def test_controller_settings_applies_current_limit_to_controller_and_verifies_readback(self):
    state = default_state()
    state["controller"]["udp_port"] = 12000
    state["controller"]["local_udp_port"] = 6667
    state["controller"]["udp_checksum_algorithm"] = "xor"
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
        "ho": {"voltage_v": 15.2, "current_limit_ma": 4000},
      },
    }
    transport = FakeRequestMappedUdpTransport(requests)
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
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
    self.assertEqual(state["controller"]["track_profiles"]["ho"]["current_limit_ma"], 4000)
    self.assertEqual([entry["payload"] for entry in transport.requests], [
      bytes.fromhex("ff ff 18 01 40 00 00 82 64 bf"),
      bytes.fromhex("ff ff 17 01 41 00 00 82 d5"),
    ])

  def test_controller_settings_rejects_controller_write_when_readback_mismatches(self):
    state = default_state()
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
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
        "ho": {"voltage_v": 15.2, "current_limit_ma": 4000},
      },
    }
    body, status = ApiRouter(None, udp_transport=FakeRequestMappedUdpTransport(requests)).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "controller_parameter_write_failed")
    self.assertNotEqual(state["controller"]["track_profiles"]["ho"]["current_limit_ma"], 4000)
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
    body, status = ApiRouter(None, udp_transport=FakeRequestMappedUdpTransport({})).handle_json(
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
      b'{"kind":"z21_controller"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_kind")

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
    request = {"track_profiles": {"n": {"voltage_v": 13.0, "current_limit_ma": 200}}}
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
    request = {"track_profiles": {"dc": {"voltage_v": 13.0, "current_limit_ma": 2000}}}
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      json.dumps(request).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_profiles"]["dc"]["voltage_v"], 13.0)
    self.assertEqual(state["controller"]["track_profiles"]["dc"]["voltage_v"], 13.0)

  def test_controller_read_info_requires_confirmed_udp_and_checksum(self):
    state = default_state()
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
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("POST", "/api/controller/read-info", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["error"]["detail"], "UDP checksum algorithm is unconfirmed")
    self.assertEqual(payload["debug"]["warnings"], ["udp_checksum_algorithm_unconfirmed"])

  def test_controller_read_info_reads_version_status_and_current_limit(self):
    state = default_state()
    state["controller"]["udp_port"] = 12000
    state["controller"]["local_udp_port"] = 6667
    state["controller"]["udp_checksum_algorithm"] = "xor"
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
    transport = FakeRequestMappedUdpTransport(requests)
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
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
    self.assertEqual(state["controller"]["track_profiles"]["n"]["current_limit_ma"], 400)
    self.assertEqual(state["controller"]["track_profiles"]["ho"]["current_limit_ma"], 4000)
    self.assertEqual(state["controller"]["track_profiles"]["g"]["current_limit_ma"], 7000)
    self.assertEqual(state["controller"]["track_profiles"]["dc"]["current_limit_ma"], 2000)
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
    state = default_state()
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
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
    body, status = ApiRouter(None, udp_transport=FakeRequestMappedUdpTransport(requests)).handle_json(
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


if __name__ == "__main__":
  unittest.main()

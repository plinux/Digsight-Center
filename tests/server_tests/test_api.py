import json
import unittest
from pathlib import Path

from server import models
from server.api import ApiRouter
from server.app_state import default_state
from digsight_dxdcnet.constants import (
  CMD_DEVICE_STATUS,
  CMD_LOCO_CONTROL_ACK,
  CMD_LOCO_FUNCTION,
  CMD_LOCO_SPEED,
  DEVICE_TYPE_BOOSTER,
  DEVICE_TYPE_THROTTLE,
  SPEED_MODE_128,
)
from digsight_dxdcnet.frames import build_udp_frame
from digsight_dxdcnet.loco_control import build_loco_control_request_frame, build_loco_function_frame, build_loco_speed_frame
from tests.server_tests.controller_test_env import controller_ip_payload, controller_test_ip
from tests.server_tests.fake_udp import FakeRequestMappedUdpTransport


class ApiRouterTest(unittest.TestCase):
  def test_api_router_dispatches_by_http_method_helpers(self):
    source = Path("server/api.py").read_text(encoding="utf-8")
    self.assertIn("def _handle_get_route(", source)
    self.assertIn("def _handle_post_route(", source)
    self.assertIn("def _handle_patch_route(", source)
    self.assertIn("def _handle_delete_route(", source)

  def test_shared_fake_udp_transport_module_exports_request_mapped_fake(self):
    try:
      module = __import__("tests.server_tests.fake_udp", fromlist=["FakeRequestMappedUdpTransport"])
    except ModuleNotFoundError as exc:
      self.fail(f"missing shared fake UDP transport module: {exc}")
    self.assertTrue(hasattr(module, "FakeRequestMappedUdpTransport"))

  def test_unknown_api_route_returns_structured_not_found(self):
    body, status = ApiRouter(None).handle_json("GET", "/api/missing", b"", default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 404)
    self.assertEqual(payload["error"]["type"], "not_found")
    self.assertEqual(payload["error"]["detail"], "/api/missing")

  def test_category_write_requires_vehicle_store(self):
    body, status = ApiRouter(None).handle_json(
      "POST",
      "/api/categories",
      json.dumps({"name": "未启用"}).encode("utf-8"),
      default_state(),
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "vehicle_store_not_ready")

  def _ready_loco_state(self):
    state = default_state()
    state["controller"].update({
      "track_mode": "ho",
      "udp_port": 12000,
      "local_udp_port": 6667,
      "udp_checksum_algorithm": "xor",
      "last_probe_ok": True,
      "controller_reachable": True,
      "booster_status": {
        "source": "dxdcnet_status_0x23",
        "power_on": True,
        "dcc_mode": True,
      },
      "safety_snapshot": {
        "controller_endpoint_version": 1,
        "last_read_info_at": "2026-06-22T00:00:00+08:00",
        "booster_status_fresh": True,
        "programming_track_status_fresh": True,
      },
    })
    return state

  def _loco_speed_feedback(self, address: int, speed: int, direction: str):
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_SPEED + 0x08,
      payload=bytes([
        address & 0xFF,
        (address >> 8) & 0xFF,
        (0x80 if direction == "forward" else 0x00) | speed,
        SPEED_MODE_128,
      ]),
    )

  def _loco_control_ack(self, address: int):
    high = ((address >> 8) & 0x3F) | (0x80 if address > 0x7F else 0)
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_CONTROL_ACK,
      payload=bytes([address & 0xFF, high, DEVICE_TYPE_THROTTLE, 1]),
    )

  def _loco_function_feedback(self, address: int, f0_enabled: bool):
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_FUNCTION + 0x08,
      payload=bytes([
        address & 0xFF,
        (address >> 8) & 0xFF,
        0x10 if f0_enabled else 0x00,
        0x00,
      ]),
    )

  def test_state_returns_default_controller_ip(self):
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("GET", "/api/state", b"", default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["data"]["controller"]["ip"], models.CONTROLLER_DEFAULT_IP)
    self.assertEqual(payload["data"]["controller"]["udp_port"], 12000)

  def test_state_response_does_not_expose_operation_token_fields(self):
    state = default_state()
    state["controller"]["operation_token"] = "secret-token"
    body, status = ApiRouter(state_store=None).handle_json("GET", "/api/state", b"", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    controller = payload["data"]["controller"]
    self.assertNotIn("operation_token", controller)
    self.assertNotIn("operation_token_configured", controller)

  def test_cv_read_requires_protocol_ready(self):
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("POST", "/api/cv/read", b'{"vehicle_id":"v1","cv":1}', default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")

  def test_connect_rejects_invalid_controller_ip(self):
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("POST", "/api/controller/connect", b'{"ip":"not-an-ip"}', default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_ip")

  def test_connect_defaults_to_confirmed_dxdcnet_udp_settings(self):
    state = default_state()
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("POST", "/api/controller/connect", controller_ip_payload(), state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["udp_port"], 12000)
    self.assertEqual(payload["data"]["local_udp_port"], 6667)
    self.assertEqual(payload["data"]["udp_checksum_algorithm"], "xor")
    self.assertTrue(payload["data"]["connected"])
    self.assertEqual(state["controller"]["udp_port"], 12000)

  def test_connect_clears_safety_cache_when_transport_identity_changes(self):
    state = self._ready_loco_state()
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "ho",
      "dcc_mode": True,
      "programming_track_busy": False,
      "programming_track_current_ma": 0,
      "output_value": 0xA0,
      "current_limit_ma": 0,
      "current_limit_confirmed": False,
    }
    body, status = ApiRouter(state_store=None).handle_json(
      "POST",
      "/api/controller/connect",
      controller_ip_payload(udp_port=12001, local_udp_port=6667, udp_checksum_algorithm="xor"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["udp_port"], 12001)
    self.assertNotIn("booster_status", state["controller"])
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])

  def test_track_power_turns_on_n_mode(self):
    state = default_state()
    request = bytes.fromhex("ff ff 17 01 20 01 90 78 df")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x78, 0x78, 0x01, 0x22, 0x00, 0x00, 0x90]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["powered"])
    self.assertEqual(payload["data"]["track_mode"], "n")
    self.assertEqual(payload["data"]["output_value"], 0x78)
    self.assertEqual(transport.requests[0]["payload"], request)
    self.assertEqual(state["controller"]["telemetry"]["track_voltage_v"], 12.0)
    self.assertEqual(state["controller"]["controller_reachable"], True)

  def test_track_power_allows_user_click_without_operation_token(self):
    state = default_state()
    request = bytes.fromhex("ff ff 17 01 20 01 90 78 df")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x78, 0x78, 0x01, 0x22, 0x00, 0x00, 0x90]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/track-power",
      b'{"powered":true}',
      state,
      request_meta={"headers": {}, "client_ip": "127.0.0.1"},
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["powered"])
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_controller_settings_allows_user_click_without_operation_token(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      controller_ip_payload(),
      state,
      request_meta={"headers": {}, "client_ip": "127.0.0.1"},
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["ip"], controller_test_ip())

  def test_track_mode_switch_does_not_require_operation_token_when_request_has_http_meta(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/track-mode",
      b'{"track_mode":"ho"}',
      state,
      request_meta={"headers": {}, "client_ip": "127.0.0.1"},
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "ho")
    self.assertEqual(state["controller"]["track_mode"], "ho")

  def test_track_power_status_missing_marks_controller_unreachable(self):
    state = default_state()
    request = bytes.fromhex("ff ff 17 01 20 01 90 78 df")
    transport = FakeRequestMappedUdpTransport({request: []})
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 504)
    self.assertEqual(payload["error"]["type"], "track_power_status_missing")
    self.assertEqual(state["controller"]["controller_reachable"], False)
    self.assertEqual(state["controller"]["controller_unreachable_reason"], "track_power_status_missing")

  def test_track_power_allows_g_mode_on(self):
    state = default_state()
    state["controller"]["track_mode"] = "g"
    request = bytes.fromhex("ff ff 17 01 20 01 90 b4 13")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0xB4, 0xB4, 0x00, 0x22, 0x00, 0x00, 0x90]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "g")
    self.assertEqual(payload["data"]["output_value"], 0xB4)
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_track_power_allows_dc_mode_on_with_default_positive_direction(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    request = bytes.fromhex("ff ff 17 01 20 01 f0 78 bf")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x78, 0x78, 0x00, 0x22, 0x00, 0x00, 0xF0]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "dc")
    self.assertFalse(payload["data"]["dcc_mode"])
    self.assertEqual(payload["data"]["direction"], "forward")
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_dc_control_sets_reverse_voltage_without_real_hardware(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    request = bytes.fromhex("ff ff 17 01 20 01 d0 4e a9")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x4E, 0x4E, 0x00, 0x22, 0x00, 0x00, 0xD0]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/dc-control",
      b'{"voltage_v":7.8,"direction":"reverse"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "dc")
    self.assertEqual(payload["data"]["voltage_v"], 7.8)
    self.assertEqual(payload["data"]["direction"], "reverse")
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_dc_control_emergency_stop_sends_dc_power_off_without_real_hardware(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    request = bytes.fromhex("ff ff 17 01 20 01 70 00 47")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x00, 0x00, 0x00, 0x22, 0x00, 0x00, 0x70]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/dc-control",
      b'{"voltage_v":0,"direction":"forward"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["powered"])
    self.assertEqual(payload["data"]["voltage_v"], 0)
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_track_power_off_allows_mode_bit_reset(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    request = bytes.fromhex("ff ff 17 01 20 01 70 00 47")
    transport = FakeRequestMappedUdpTransport({
      request: [
        build_udp_frame(
          device_type=DEVICE_TYPE_BOOSTER,
          source_id=1,
          command=CMD_DEVICE_STATUS,
          payload=bytes([0x00, 0x0D, 0x00, 0x21, 0x00, 0x00, 0x30]),
        )
      ]
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":false}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertFalse(payload["data"]["powered"])
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_track_power_rejects_invalid_payload(self):
    body, status = ApiRouter(None).handle_json("POST", "/api/track-power", b'{"powered":"true"}', default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_track_power")

  def test_cv_read_rejects_dc_track_mode(self):
    state = default_state()
    state["controller"]["udp_port"] = 12345
    state["controller"]["track_mode"] = "dc"
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("POST", "/api/cv/read", b'{"vehicle_id":"v1","cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_track_mode")

if __name__ == "__main__":
  unittest.main()

import json
import tempfile
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
from server.vehicle_store import VehicleStore
from tests.server_tests.controller_test_env import controller_ip_payload, controller_test_ip
from tests.server_tests.fake_udp import FakeRequestMappedUdpTransport, FakeUdpTransport


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

  def _fresh_track_power_state(self, track_mode="n"):
    state = default_state()
    state["controller"].update({
      "track_mode": track_mode,
      "last_probe_ok": True,
      "controller_reachable": True,
      "booster_status": {
        "source": "dxdcnet_status_0x23",
        "power_on": False,
        "dcc_mode": track_mode != "dc",
      },
      "safety_snapshot": {
        "controller_endpoint_version": 1,
        "last_read_info_at": "2026-06-22T00:00:00+08:00",
        "booster_status_fresh": True,
        "programming_track_status_fresh": False,
      },
    })
    return state

  def _safe_programming_track_state(self):
    state = default_state()
    state["controller"].update({
      "udp_port": 21105,
      "udp_checksum_algorithm": "xor",
      "programming_track_status": {
        "source": "dxdcnet_status_0x23",
        "track_mode": "n",
        "dcc_mode": True,
        "programming_track_busy": False,
        "programming_track_current_ma": 60,
        "output_value": 0x78,
        "current_limit_ma": 200,
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

  def test_error_response_keeps_message_detail_and_debug_shape(self):
    router = ApiRouter(state_store=None, udp_transport=FakeUdpTransport([]))
    body, status = router.handle_json("POST", "/api/cv/read", b'{"cv":7}', self._safe_programming_track_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["data"], None)
    self.assertEqual(payload["error"]["type"], "cv_read_no_value")
    self.assertEqual(payload["error"]["message"], "控制器未返回匹配的 CV 值")
    self.assertIn("detail", payload["error"])
    self.assertEqual(payload["debug"]["cv"], 7)
    self.assertEqual(payload["debug"]["client_id"], 1)
    self.assertIn("request_hex", payload["debug"])
    self.assertEqual(payload["debug"]["responses"], [])

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
    state = self._fresh_track_power_state("n")
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

  def test_track_power_on_requires_fresh_controller_status(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["error"]["message"], "请先连接控制器并读取最新状态")
    self.assertIn("controller_not_confirmed", payload["debug"]["warnings"])
    self.assertIn("booster_status_stale", payload["debug"]["warnings"])
    self.assertIn("booster_status_unconfirmed", payload["debug"]["warnings"])

  def test_track_power_allows_user_click_without_operation_token(self):
    state = self._fresh_track_power_state("n")
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

  def test_persistent_write_routes_do_not_fail_with_operation_token_error(self):
    state = default_state()
    router = ApiRouter(None)
    request_meta = {"headers": {}, "client_ip": "127.0.0.1"}
    route_cases = [
      ("POST", "/api/vehicles", b"{}"),
      ("PATCH", "/api/vehicles/order", b"{}"),
      ("POST", "/api/vehicle-images", b"{}"),
      ("POST", "/api/categories", b"{}"),
      ("POST", "/api/consists", b"{}"),
      ("PATCH", "/api/vehicles/local-vehicle-1", b"{}"),
      ("PATCH", "/api/categories/local-category-1", b"{}"),
      ("PATCH", "/api/consists/local-consist-1", b"{}"),
      ("DELETE", "/api/vehicles/local-vehicle-1", b""),
      ("DELETE", "/api/categories/local-category-1", b""),
      ("DELETE", "/api/consists/local-consist-1", b""),
    ]
    for method, route, request_body in route_cases:
      with self.subTest(method=method, route=route):
        body, status = router.handle_json(method, route, request_body, state, request_meta=request_meta)
        payload = json.loads(body.decode("utf-8"))
        self.assertNotEqual(status, 403)
        if not payload["ok"]:
          self.assertNotEqual(payload["error"]["type"], "operation_not_authorized")

    for route, call in [
      ("/api/import/config", lambda: router.import_config_bytes(
        "z21_layout_config",
        "HO.z21",
        b"not a zip",
        state,
        request_meta=request_meta,
      )),
      ("/api/import/z21", lambda: router.import_z21_bytes(
        "HO.z21",
        b"not a zip",
        state,
        request_meta=request_meta,
      )),
    ]:
      with self.subTest(route=route):
        body, status = call()
        payload = json.loads(body.decode("utf-8"))
        self.assertNotEqual(status, 403)
        if not payload["ok"]:
          self.assertNotEqual(payload["error"]["type"], "operation_not_authorized")

  def test_loco_control_uses_shared_target_executor_helpers(self):
    source = Path("server/api.py").read_text(encoding="utf-8")
    self.assertIn("def _validated_control_request(", source)
    self.assertIn("def _execute_loco_targets(", source)
    self.assertNotIn("def _execute_loco_speed_targets(", source)

  def test_loco_speed_rejects_stale_booster_status_after_ip_change(self):
    state = self._ready_loco_state()
    state["vehicles"].append({"id": "v1", "name": "Test", "address": 3, "track_mode": "ho"})
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"ip":"10.10.200.99"}',
      state,
    )
    self.assertEqual(status, 200)
    control_request = build_loco_control_request_frame(address=3, client_id=1)
    speed_request = build_loco_speed_frame(address=3, speed=10, direction="forward", client_id=1)
    transport = FakeRequestMappedUdpTransport({
      control_request: [self._loco_control_ack(3)],
      speed_request: [self._loco_speed_feedback(3, 10, "forward")],
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/loco/speed",
      b'{"vehicle_id":"v1","speed":10,"direction":"forward"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertIn("booster_status_stale", payload["debug"]["warnings"])
    self.assertEqual(transport.requests, [])

  def test_loco_speed_continues_when_control_ack_is_missing(self):
    state = self._ready_loco_state()
    state["vehicles"].append({"id": "v1", "name": "Test", "address": 3, "track_mode": "ho"})
    control_request = build_loco_control_request_frame(address=3, client_id=1)
    speed_request = build_loco_speed_frame(address=3, speed=10, direction="forward", client_id=1)
    transport = FakeRequestMappedUdpTransport({
      control_request: [],
      speed_request: [self._loco_speed_feedback(3, 10, "forward")],
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/loco/speed",
      b'{"vehicle_id":"v1","speed":10,"direction":"forward"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["targets"][0]["control_feedback"], None)
    self.assertEqual(payload["data"]["speed"], 10)
    self.assertEqual([request["payload"] for request in transport.requests], [control_request, speed_request])

  def test_track_power_status_missing_marks_controller_unreachable(self):
    state = self._fresh_track_power_state("n")
    request = bytes.fromhex("ff ff 17 01 20 01 90 78 df")
    transport = FakeRequestMappedUdpTransport({request: []})
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 504)
    self.assertEqual(payload["error"]["type"], "track_power_status_missing")
    self.assertEqual(state["controller"]["controller_reachable"], False)
    self.assertEqual(state["controller"]["controller_unreachable_reason"], "track_power_status_missing")

  def test_track_power_allows_g_mode_on(self):
    state = self._fresh_track_power_state("g")
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
    state = self._fresh_track_power_state("dc")
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

  def test_type3_vehicle_speed_control_fans_out_to_consist_members(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      control = store.create_vehicle({"id": "mu", "name": "重联", "address": 3, "type": 3})
      first = store.create_vehicle({"id": "loco-a", "name": "A", "address": 11})
      second = store.create_vehicle({"id": "loco-b", "name": "B", "address": 22})
      store.create_consist({
        "name": "重联",
        "control_vehicle_id": control["id"],
        "members": [
          {"vehicle_id": first["id"], "address": 11, "direction": "forward", "order": 1},
          {"vehicle_id": second["id"], "address": 22, "direction": "forward", "order": 2},
        ],
      })
      control_a = build_loco_control_request_frame(address=11, client_id=1)
      control_b = build_loco_control_request_frame(address=22, client_id=1)
      request_a = build_loco_speed_frame(address=11, speed=42, direction="forward", client_id=1)
      request_b = build_loco_speed_frame(address=22, speed=42, direction="forward", client_id=1)
      transport = FakeRequestMappedUdpTransport({
        control_a: [self._loco_control_ack(11)],
        request_a: [self._loco_speed_feedback(11, 42, "forward")],
        control_b: [self._loco_control_ack(22)],
        request_b: [self._loco_speed_feedback(22, 42, "forward")],
      })
      body, status = ApiRouter(None, udp_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/loco/speed",
        b'{"vehicle_id":"mu","speed":42,"direction":"forward"}',
        self._ready_loco_state(),
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
      self.assertEqual([target["address"] for target in payload["data"]["targets"]], [11, 22])
      self.assertEqual(payload["data"]["control_mode"], "consist_vehicle")

  def test_type3_vehicle_speed_control_reverses_reversed_consist_member(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      control = store.create_vehicle({"id": "mu", "name": "重联", "address": 3, "type": 3})
      first = store.create_vehicle({"id": "loco-a", "name": "A", "address": 11})
      second = store.create_vehicle({"id": "loco-b", "name": "B", "address": 22})
      store.create_consist({
        "name": "重联",
        "control_vehicle_id": control["id"],
        "members": [
          {"vehicle_id": first["id"], "address": 11, "direction": "forward", "order": 1},
          {"vehicle_id": second["id"], "address": 22, "direction": "reverse", "order": 2},
        ],
      })
      control_a = build_loco_control_request_frame(address=11, client_id=1)
      control_b = build_loco_control_request_frame(address=22, client_id=1)
      request_a = build_loco_speed_frame(address=11, speed=42, direction="forward", client_id=1)
      request_b = build_loco_speed_frame(address=22, speed=42, direction="reverse", client_id=1)
      transport = FakeRequestMappedUdpTransport({
        control_a: [self._loco_control_ack(11)],
        request_a: [self._loco_speed_feedback(11, 42, "forward")],
        control_b: [self._loco_control_ack(22)],
        request_b: [self._loco_speed_feedback(22, 42, "reverse")],
      })
      body, status = ApiRouter(None, udp_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/loco/speed",
        b'{"vehicle_id":"mu","speed":42,"direction":"forward"}',
        self._ready_loco_state(),
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
      self.assertEqual([target["direction"] for target in payload["data"]["targets"]], ["forward", "reverse"])

  def test_sync_function_control_fans_out_member_function_to_all_consist_members(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      control = store.create_vehicle({
        "id": "mu",
        "name": "重联",
        "address": 3,
        "type": 3,
        "sync_function_control": True,
      })
      first = store.create_vehicle({"id": "loco-a", "name": "A", "address": 11})
      second = store.create_vehicle({"id": "loco-b", "name": "B", "address": 22})
      store.create_consist({
        "name": "重联",
        "control_vehicle_id": control["id"],
        "members": [
          {"vehicle_id": first["id"], "address": 11, "direction": "forward", "order": 1},
          {"vehicle_id": second["id"], "address": 22, "direction": "forward", "order": 2},
        ],
      })
      control_a = build_loco_control_request_frame(address=11, client_id=1)
      control_b = build_loco_control_request_frame(address=22, client_id=1)
      request_a = build_loco_function_frame(address=11, function_states={"0": True}, client_id=1)
      request_b = build_loco_function_frame(address=22, function_states={"0": True}, client_id=1)
      transport = FakeRequestMappedUdpTransport({
        control_a: [self._loco_control_ack(11)],
        request_a: [self._loco_function_feedback(11, True)],
        control_b: [self._loco_control_ack(22)],
        request_b: [self._loco_function_feedback(22, True)],
      })
      body, status = ApiRouter(None, udp_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/loco/function",
        b'{"vehicle_id":"loco-a","function_number":0,"enabled":true,"function_states":{"0":true}}',
        self._ready_loco_state(),
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
      self.assertEqual([target["vehicle_id"] for target in payload["data"]["targets"]], ["loco-a", "loco-b"])
      self.assertEqual(payload["data"]["control_mode"], "synced_consist_function")


if __name__ == "__main__":
  unittest.main()

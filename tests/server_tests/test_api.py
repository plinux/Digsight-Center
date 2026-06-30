import json
import tempfile
import unittest
from pathlib import Path

from server import models
from server.api import ApiRouter
from server.app_state import AppStateStore, default_state
from server.api_support.controller import controller_settings_apply_to_device
from server.api_support.routes import LOCK_MODE_HARDWARE, handler_for, mutation_route_spec
from server.controllers.digsight import DigsightDXDCNetControllerAdapter
from server.controllers.example import ExampleControllerAdapter
from server.controllers.registry import ControllerRegistry
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
from tests.server_tests.controller_test_env import (
  controller_ip_payload,
  controller_test_ip,
  ready_loco_control_state,
  temporary_vehicle_router,
)
from tests.server_tests.fake_udp import FakeRequestMappedUdpTransport, FakeUdpTransport


class ApiRouterTest(unittest.TestCase):
  def test_api_router_dispatches_by_http_method_helpers(self):
    source = Path("server/api.py").read_text(encoding="utf-8")
    self.assertIn("handler_for(method, route)", source)
    self.assertIn("self._handlers", source)
    self.assertIn("def _build_handlers(", source)
    self.assertNotIn("_GET_ROUTES", source)

  def test_api_router_delegates_vehicle_and_consist_domains(self):
    source = Path("server/api.py").read_text(encoding="utf-8")
    self.assertIn("self.vehicle_api", source)
    self.assertIn("VehicleLibraryApiSupport", source)
    self.assertIn("self.loco_control_api", source)
    self.assertLess(source.count("def _handle_"), 57)

  def test_shared_fake_controller_transport_module_exports_request_mapped_fake(self):
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

  def test_dynamic_api_routes_reject_extra_path_segments(self):
    invalid_routes = [
      ("PATCH", "/api/vehicles/foo/bar"),
      ("PATCH", "/api/vehicles/"),
      ("PATCH", "/api//vehicles/foo"),
      ("PATCH", "/api/vehicles//foo"),
      ("PATCH", "/api/vehicles/foo/"),
      ("DELETE", "/api/vehicles/"),
      ("DELETE", "/api/categories/foo/bar"),
      ("DELETE", "/api/categories/"),
      ("DELETE", "/api/categories//foo"),
      ("PATCH", "/api/consists/foo/bar"),
      ("PATCH", "/api/consists/"),
      ("DELETE", "/api/consists/"),
      ("POST", "/api/consists/a/b/speed"),
      ("POST", "/api/consists/a/b/stop"),
      ("POST", "/api//consists/c1/speed"),
      ("POST", "/api/consists//c1/stop"),
      ("POST", "/api/consists/c1//speed"),
      ("POST", "/api/consists/c1/speed/"),
    ]
    for method, route in invalid_routes:
      with self.subTest(method=method, route=route):
        self.assertIsNone(handler_for(method, route))

  def test_consist_operation_route_hardware_lock_requires_exact_shape(self):
    self.assertEqual(handler_for("POST", "/api/consists/c1/speed"), "consists.operation")
    self.assertEqual(handler_for("POST", "/api/consists/c1/stop"), "consists.operation")

    valid_speed_spec = mutation_route_spec("POST", "/api/consists/c1/speed")
    valid_stop_spec = mutation_route_spec("POST", "/api/consists/c1/stop")
    invalid_speed_spec = mutation_route_spec("POST", "/api/consists/c1/extra/speed")
    empty_prefix_spec = mutation_route_spec("POST", "/api//consists/c1/speed")
    empty_id_spec = mutation_route_spec("POST", "/api/consists//c1/stop")

    self.assertEqual(valid_speed_spec["lock_mode"], LOCK_MODE_HARDWARE)
    self.assertEqual(valid_stop_spec["lock_mode"], LOCK_MODE_HARDWARE)
    self.assertNotEqual(invalid_speed_spec["lock_mode"], LOCK_MODE_HARDWARE)
    self.assertNotEqual(empty_prefix_spec["lock_mode"], LOCK_MODE_HARDWARE)
    self.assertNotEqual(empty_id_spec["lock_mode"], LOCK_MODE_HARDWARE)

  def test_controller_settings_apply_to_device_lock_policy_lives_in_controller_support(self):
    route_spec = mutation_route_spec("PATCH", "/api/controller/settings")
    routes_source = Path("server/api_support/routes.py").read_text(encoding="utf-8")
    main_source = Path("server/main.py").read_text(encoding="utf-8")

    self.assertNotEqual(route_spec["lock_mode"], LOCK_MODE_HARDWARE)
    self.assertTrue(controller_settings_apply_to_device(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":true}',
    ))
    self.assertFalse(controller_settings_apply_to_device(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":false}',
    ))
    self.assertFalse(controller_settings_apply_to_device(
      "PATCH",
      "/api/controller/settings",
      b'{"apply_to_device":"true"}',
    ))
    self.assertFalse(controller_settings_apply_to_device("PATCH", "/api/controller/settings", b"{"))
    self.assertFalse(controller_settings_apply_to_device(
      "POST",
      "/api/controller/settings",
      b'{"apply_to_device":true}',
    ))
    self.assertNotIn("json.loads", routes_source)
    self.assertIn("controller_settings_apply_to_device", main_source)

  def test_get_vehicle_and_category_routes_use_vehicle_store(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      vehicle_store.create_vehicle({"id": "v1", "name": "测试车", "address": 3, "track_mode": "ho"})
      vehicle_store.create_category({"id": "c1", "name": "测试分类"})
      state["vehicles"] = [{"id": "runtime-json-vehicle", "name": "运行态 JSON 车辆"}]
      state["categories"] = [{"id": "runtime-json-category", "name": "运行态 JSON 分类"}]

      vehicle_body, vehicle_status = router.handle_json("GET", "/api/vehicles", b"", state)
      category_body, category_status = router.handle_json("GET", "/api/categories", b"", state)

      self.assertEqual(vehicle_status, 200)
      self.assertEqual(category_status, 200)
      self.assertEqual(json.loads(vehicle_body.decode("utf-8"))["data"][0]["id"], "v1")
      self.assertEqual(json.loads(category_body.decode("utf-8"))["data"][0]["id"], "c1")

  def test_old_controller_connect_disconnect_routes_are_not_available(self):
    router = ApiRouter(None)
    for path in ["/api/controller/connect", "/api/controller/disconnect"]:
      with self.subTest(path=path):
        body, status = router.handle_json("POST", path, b"{}", default_state())
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 404)
        self.assertEqual(payload["error"]["type"], "not_found")

  def test_controller_reset_config_route_rewrites_current_controller_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      state_store = AppStateStore(root / "data" / "app-state.json")
      config_dir = root / "config" / "controllers"
      config_dir.mkdir(parents=True)
      config_path = config_dir / "Digsight_D9000.json"
      config_path.write_text("not json", encoding="utf-8")
      state = state_store.load()
      router = ApiRouter(state_store)

      body, status = router.handle_json(
        "POST",
        "/api/controller/reset-config",
        b'{"kind":"digsight_controller"}',
        state,
      )

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(payload["data"]["controller_kind"], "digsight_controller")
      self.assertEqual(payload["data"]["reset_files"], ["config/controllers/Digsight_D9000.json"])
      self.assertEqual(json.loads(config_path.read_text(encoding="utf-8"))["ip"], models.CONTROLLER_DEFAULT_IP)
      self.assertIsNone(state_store.load()["last_error"])

  def _fresh_track_power_state(self, track_mode="n"):
    state = default_state()
    state["controller"].update({
      "ip": "192.0.2.10",
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
      "ip": "192.0.2.10",
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
    with temporary_vehicle_router() as (router, _store, state):
      body, status = router.handle_json("GET", "/api/state", b"", state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["ok"])
      self.assertEqual(payload["data"]["controller"]["ip"], models.CONTROLLER_DEFAULT_IP)
      self.assertEqual(payload["data"]["controller"]["udp_port"], 12000)

  def test_cv_read_requires_protocol_ready(self):
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("POST", "/api/cv/read", b'{"vehicle_id":"v1","cv":1}', default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")

  def test_error_response_keeps_message_detail_and_debug_shape(self):
    router = ApiRouter(state_store=None, controller_transport=FakeUdpTransport([]))
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

  def test_loco_speed_rejects_invalid_controller_client_id(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      vehicle_store.create_vehicle({"id": "v1", "name": "测试车", "address": 3, "track_mode": "ho"})
      state.update(ready_loco_control_state())
      state["controller"]["client_id"] = 128
      body, status = router.handle_json(
        "POST",
        "/api/loco/speed",
        b'{"vehicle_id":"v1","speed":10,"direction":"forward"}',
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 409)
      self.assertEqual(payload["error"]["type"], "invalid_controller_settings")

  def test_settings_rejects_invalid_controller_ip(self):
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("PATCH", "/api/controller/settings", b'{"ip":"not-an-ip"}', default_state())
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_settings")

  def test_settings_defaults_to_confirmed_dxdcnet_udp_settings(self):
    state = default_state()
    router = ApiRouter(state_store=None)
    body, status = router.handle_json("PATCH", "/api/controller/settings", controller_ip_payload(), state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["transport"]["udp_port"], 12000)
    self.assertEqual(payload["data"]["transport"]["local_udp_port"], 6667)
    self.assertEqual(payload["data"]["transport"]["udp_checksum_algorithm"], "xor")
    self.assertEqual(state["controller"]["udp_port"], 12000)

  def test_settings_normalizes_zero_local_udp_port_when_adapter_disallows_it(self):
    state = default_state()
    router = ApiRouter(state_store=None)
    body, status = router.handle_json(
      "PATCH",
      "/api/controller/settings",
      controller_ip_payload(local_udp_port=0),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["transport"]["local_udp_port"], 6667)
    self.assertEqual(state["controller"]["local_udp_port"], 6667)

  def test_settings_clears_safety_cache_when_transport_identity_changes(self):
    state = ready_loco_control_state()
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
      "PATCH",
      "/api/controller/settings",
      controller_ip_payload(udp_port=12001, local_udp_port=6667, udp_checksum_algorithm="xor"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["transport"]["udp_port"], 12001)
    self.assertNotIn("booster_status", state["controller"])
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])

  def test_controller_kind_change_does_not_copy_previous_runtime_sections(self):
    registry = ControllerRegistry()
    registry.register(DigsightDXDCNetControllerAdapter(), default=True)
    registry.register(ExampleControllerAdapter())
    state = ready_loco_control_state()
    state["controller"]["telemetry"] = {"track_voltage_v": 99}
    state["controller"]["device_info"] = {"device_name": "旧控制器", "source": "dxdcnet"}
    state["controller"]["programming_track_status"] = {"source": "dxdcnet_status_0x23"}
    state["controller"]["dc_control"] = {"voltage_v": 9.9, "direction": "reverse"}

    body, status = ApiRouter(None, controller_registry=registry).handle_json(
      "PATCH",
      "/api/controller/settings",
      b'{"kind":"example_controller","ip":"0.0.0.0"}',
      state,
    )

    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["kind"], "example_controller")
    self.assertNotIn("booster_status", state["controller"])
    self.assertNotIn("programming_track_status", state["controller"])
    self.assertNotIn("dc_control", state["controller"])
    self.assertEqual(state["controller"]["telemetry"]["track_voltage_v"], None)
    self.assertEqual(state["controller"]["device_info"]["device_name"], "")
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "POST",
      "/api/track-power",
      b'{"powered":true}',
      state,
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
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["ip"], controller_test_ip())

  def test_track_mode_switch_does_not_require_operation_token(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    body, status = ApiRouter(None).handle_json(
      "PATCH",
      "/api/controller/track-mode",
      b'{"track_mode":"ho"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "ho")
    self.assertEqual(state["controller"]["track_mode"], "ho")

  def test_persistent_write_routes_do_not_fail_with_operation_token_error(self):
    with temporary_vehicle_router() as (router, _store, state):
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
          body, status = router.handle_json(method, route, request_body, state)
          payload = json.loads(body.decode("utf-8"))
          self.assertNotEqual(status, 403)
          if not payload["ok"]:
            self.assertNotEqual(payload["error"]["type"], "operation_not_authorized")

      body, status = router.import_config_bytes(
        "z21_layout_config",
        "HO.z21",
        b"not a zip",
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertNotEqual(status, 403)
      if not payload["ok"]:
        self.assertNotEqual(payload["error"]["type"], "operation_not_authorized")

  def test_loco_control_uses_shared_target_executor_helpers(self):
    router_source = Path("server/api.py").read_text(encoding="utf-8")
    service_source = Path("server/controller_services/loco_control.py").read_text(encoding="utf-8")
    self.assertNotIn("def _validated_control_request(", router_source)
    self.assertNotIn("def _validated_control_request(", service_source)
    self.assertIn("def _loco_control_denied_response(", service_source)
    self.assertIn("request_loco_control_grant", service_source)
    self.assertIn("def execute_loco_targets(", service_source)
    self.assertNotIn("def _execute_loco_speed_targets(", router_source)

  def test_loco_speed_rejects_stale_booster_status_after_ip_change(self):
    state = ready_loco_control_state()
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
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

  def test_failed_probe_reports_result_without_invalidating_safety_when_ip_is_unchanged(self):
    state = ready_loco_control_state()
    state["vehicles"].append({"id": "v1", "name": "Test", "address": 3, "track_mode": "ho"})

    def failing_probe(command):
      self.assertEqual(command[-1], state["controller"]["ip"])
      return 1, "", "simulated failure"

    body, status = ApiRouter(None, probe_runner=failing_probe).handle_json(
      "POST",
      "/api/controller/probe",
      json.dumps({"ip": state["controller"]["ip"]}).encode("utf-8"),
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertFalse(payload["data"]["reachable"])
    self.assertTrue(state["controller"]["last_probe_ok"])
    self.assertTrue(state["controller"]["controller_reachable"])
    self.assertIn("booster_status", state["controller"])
    self.assertTrue(state["controller"]["safety_snapshot"]["booster_status_fresh"])

    control_request = build_loco_control_request_frame(address=3, client_id=1)
    speed_request = build_loco_speed_frame(address=3, speed=10, direction="forward", client_id=1)
    transport = FakeRequestMappedUdpTransport({
      control_request: [self._loco_control_ack(3)],
      speed_request: [self._loco_speed_feedback(3, 10, "forward")],
    })
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "POST",
      "/api/loco/speed",
      b'{"vehicle_id":"v1","speed":10,"direction":"forward"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual([entry["payload"] for entry in transport.requests], [control_request, speed_request])

  def test_loco_speed_continues_when_control_ack_is_missing(self):
    state = ready_loco_control_state()
    state["vehicles"].append({"id": "v1", "name": "Test", "address": 3, "track_mode": "ho"})
    control_request = build_loco_control_request_frame(address=3, client_id=1)
    speed_request = build_loco_speed_frame(address=3, speed=10, direction="forward", client_id=1)
    transport = FakeRequestMappedUdpTransport({
      control_request: [],
      speed_request: [self._loco_speed_feedback(3, 10, "forward")],
    })
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "g")
    self.assertEqual(payload["data"]["output_value"], 0xB4)
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_track_power_rejects_dc_mode_on(self):
    state = self._fresh_track_power_state("dc")
    transport = FakeRequestMappedUdpTransport({})
    body, status = ApiRouter(None, controller_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_track_mode")
    self.assertEqual(payload["error"]["message"], "DC 模式通电必须使用 DC 控制")
    self.assertEqual(transport.requests, [])

  def test_track_power_allows_dc_mode_off(self):
    state = self._fresh_track_power_state("dc")
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":false}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["track_mode"], "dc")
    self.assertFalse(payload["data"]["dcc_mode"])
    self.assertEqual(payload["data"]["direction"], "forward")
    self.assertEqual(transport.requests[0]["payload"], request)

  def test_dc_control_sets_reverse_voltage_without_real_hardware(self):
    state = self._fresh_track_power_state("dc")
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
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

  def test_dc_control_voltage_requires_fresh_controller_status(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    body, status = ApiRouter(None).handle_json(
      "POST",
      "/api/dc-control",
      b'{"voltage_v":7.8,"direction":"reverse"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["error"]["message"], "请先连接控制器并读取最新状态")
    self.assertIn("booster_status_stale", payload["debug"]["warnings"])
    self.assertIn("booster_status_unconfirmed", payload["debug"]["warnings"])

  def test_dc_control_emergency_stop_sends_dc_power_off_without_real_hardware(self):
    state = default_state()
    state["controller"]["ip"] = "192.0.2.10"
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
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
    state["controller"]["ip"] = "192.0.2.10"
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json("POST", "/api/track-power", b'{"powered":false}', state)
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

  def test_import_config_bytes_updates_state(self):
    sample = Path("tests/fixtures/z21/N.z21")
    self.assertTrue(sample.exists(), f"fixture is missing: {sample}")
    with tempfile.TemporaryDirectory() as temp_dir:
      state_store = AppStateStore(Path(temp_dir) / "app-state.json")
      with temporary_vehicle_router(
        state_store=state_store,
        image_dir=Path(temp_dir) / "vehicle-images",
      ) as (router, vehicle_store, state):
        body, status = router.import_config_bytes("z21_layout_config", "N.z21", sample.read_bytes(), state)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 200)
        self.assertEqual(payload["data"]["summary"]["vehicles_imported"], 71)
        self.assertEqual(len(vehicle_store.list_vehicles()), 71)
        self.assertEqual(state_store.load()["vehicles"], [])

  def test_persistent_state_filters_sqlite_vehicle_data(self):
    with temporary_vehicle_router() as (router, _store, state):
      state["vehicles"] = [{"id": "runtime-only"}]
      state["functions"] = [{"vehicle_id": "runtime-only"}]
      state["categories"] = [{"id": "runtime-category"}]
      state["consists"] = [{"id": "runtime-consist"}]
      state["_request_runtime_marker"] = "not persisted"
      persistent_state = router.persistent_state(state)
      self.assertEqual(persistent_state["vehicles"], [])
      self.assertEqual(persistent_state["functions"], [])
      self.assertEqual(persistent_state["categories"], [])
      self.assertEqual(persistent_state["consists"], [])
      self.assertNotIn("_request_runtime_marker", persistent_state)

  def test_type3_vehicle_speed_control_fans_out_to_consist_members(self):
    with temporary_vehicle_router() as (_router, store, _state):
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
      body, status = ApiRouter(None, controller_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/loco/speed",
        b'{"vehicle_id":"mu","speed":42,"direction":"forward"}',
        ready_loco_control_state(),
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
      self.assertEqual([target["address"] for target in payload["data"]["targets"]], [11, 22])
      self.assertEqual(payload["data"]["control_mode"], "consist_vehicle")

  def test_type3_vehicle_speed_control_reverses_reversed_consist_member(self):
    with temporary_vehicle_router() as (_router, store, _state):
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
      body, status = ApiRouter(None, controller_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/loco/speed",
        b'{"vehicle_id":"mu","speed":42,"direction":"forward"}',
        ready_loco_control_state(),
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
      self.assertEqual([target["direction"] for target in payload["data"]["targets"]], ["forward", "reverse"])

  def test_sync_function_control_fans_out_member_function_to_all_consist_members(self):
    with temporary_vehicle_router() as (_router, store, _state):
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
      body, status = ApiRouter(None, controller_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/loco/function",
        b'{"vehicle_id":"loco-a","function_number":0,"enabled":true,"function_states":{"0":true}}',
        ready_loco_control_state(),
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
      self.assertEqual([target["vehicle_id"] for target in payload["data"]["targets"]], ["loco-a", "loco-b"])
      self.assertEqual(payload["data"]["control_mode"], "synced_consist_function")


if __name__ == "__main__":
  unittest.main()

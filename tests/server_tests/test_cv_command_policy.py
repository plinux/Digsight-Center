import json
import inspect
import tempfile
import unittest
from pathlib import Path

from server.api import ApiRouter
from server.app_state import default_state
from digsight_dxdcnet.constants import (
  CMD_PROGRAM_TRACK_ACK,
  CMD_PROGRAM_TRACK_VALUE,
  PROGRAMMER_ACK_ACK,
  PROGRAMMER_ACK_BUSY,
  PROGRAMMER_ACK_NOACK,
  PROGRAMMER_OP_MAIN_LOCO_POM,
  WARNING_CHECKSUM_INVALID,
)
from train_dcc.cv import validate_cv_number
from digsight_dxdcnet.frames import build_udp_frame
from digsight_dxdcnet.programmer import build_cv_read_frame, build_cv_write_frame
from server.api_support.cv_read_all import CvReadAllApiSupport
from server.cv_read_session import CVReadSessionRegistry
from server.vehicle_store import VehicleStore
from tests.server_tests.fake_udp import FakeUdpTransport, SequencedUdpTransport


class CancellingUdpTransport(FakeUdpTransport):
  def __init__(self, responses, sessions, session_id):
    super().__init__(responses)
    self.sessions = sessions
    self.session_id = session_id

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None):
    responses = super().exchange(host, port, payload, local_port, max_packets, stop_when)
    if len(self.requests) == 1:
      self.sessions.cancel(self.session_id)
    return responses


class RaisingUdpTransport:
  def __init__(self, exc):
    self.exc = exc
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
    raise self.exc


class CvCommandPolicyTest(unittest.TestCase):
  def test_cv_read_all_workflow_is_split_into_helpers(self):
    router_source = inspect.getsource(ApiRouter)
    support_source = inspect.getsource(CvReadAllApiSupport)

    self.assertIn("self.cv_read_all_api", router_source)
    self.assertNotIn("def _read_cv8_for_read_all", router_source)
    self.assertIn("def _resolve_cv_read_all_numbers", support_source)
    self.assertIn("def _read_cv8_for_read_all", support_source)
    self.assertIn("def _read_cv_list_rows", support_source)
    self.assertIn("def _build_cv_read_all_response", support_source)

  def test_cv_operation_runner_keeps_debug_context(self):
    from server.api_support.cv_operations import CvOperationContext

    context = CvOperationContext(cv_number=7, client_id=1, request_frame=b"\xff\xff")
    self.assertEqual(context.cv_number, 7)
    self.assertEqual(context.client_id, 1)
    self.assertEqual(context.request_hex, "ff ff")

  def test_shared_fake_udp_transport_module_exports_cv_fakes(self):
    try:
      module = __import__("tests.server_tests.fake_udp", fromlist=["FakeUdpTransport", "SequencedUdpTransport"])
    except ModuleNotFoundError as exc:
      self.fail(f"missing shared fake UDP transport module: {exc}")
    self.assertTrue(hasattr(module, "FakeUdpTransport"))
    self.assertTrue(hasattr(module, "SequencedUdpTransport"))

  def _state_with_safe_programming_track(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
      "programming_track_busy": False,
      "programming_track_current_ma": 60,
      "output_value": 0x78,
      "current_limit_ma": 200,
    }
    return state

  def _state_with_main_track_ready(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["programming_target"] = "main_track"
    state["controller"]["safety_snapshot"]["booster_status_fresh"] = True
    state["controller"]["booster_status"] = {
      "source": "dxdcnet_status_0x23",
      "power_on": True,
      "dcc_mode": True,
    }
    state["vehicles"].append({"id": "v1", "name": "车", "address": 12})
    return state

  def test_cv_read_blocks_when_port_unknown(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")

  def test_cv_read_timeout_marks_controller_unreachable(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["safety_snapshot"]["booster_status_fresh"] = True
    state["controller"]["safety_snapshot"]["programming_track_status_fresh"] = True
    transport = RaisingUdpTransport(TimeoutError("simulated timeout"))
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":1}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 504)
    self.assertEqual(payload["error"]["type"], "cv_read_timeout")
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])

  def test_cv_write_transport_error_marks_controller_unreachable(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["safety_snapshot"]["booster_status_fresh"] = True
    state["controller"]["safety_snapshot"]["programming_track_status_fresh"] = True
    transport = RaisingUdpTransport(OSError("simulated network error"))
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":3,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_write_transport_error")
    self.assertFalse(state["controller"]["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(state["controller"]["safety_snapshot"]["programming_track_status_fresh"])

  def test_cv_programming_routes_reject_invalid_controller_client_id(self):
    routes_and_bodies = [
      ("/api/cv/read", b'{"cv":1}'),
      ("/api/cv/read-all", b'{"read_mode":"known"}'),
      ("/api/chip-info/read", b"{}"),
      ("/api/address/read", b"{}"),
      ("/api/cv/write", b'{"cv":1,"value":3,"confirmed":true}'),
      ("/api/address/write", b'{"address":12,"confirmed":true}'),
    ]
    for route, body_bytes in routes_and_bodies:
      with self.subTest(route=route):
        state = self._state_with_safe_programming_track()
        state["controller"]["client_id"] = 128
        body, status = ApiRouter(None).handle_json("POST", route, body_bytes, state)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 409)
        self.assertEqual(payload["error"]["type"], "invalid_controller_settings")
        self.assertIn("client id", payload["error"]["detail"])

  def test_cv_read_rejects_non_numeric_controller_client_id(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["client_id"] = "bad-client"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "invalid_controller_settings")

  def test_cv_write_requires_confirmed_true(self):
    state = default_state()
    state["controller"]["udp_port"] = 12345
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/write", b'{"cv":1,"value":3}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "operation_requires_confirmation")
    self.assertNotIn("目标车辆", payload["error"]["detail"])
    self.assertIn("CV、新值", payload["error"]["detail"])

  def test_address_read_requires_protocol_ready(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/address/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")

  def test_address_read_rejects_dc_operation_mode(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "xor"
    body, status = ApiRouter(None).handle_json("POST", "/api/address/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_track_mode")

  def test_address_write_rejects_out_of_user_range(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/address/write", b'{"address":10000,"confirmed":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_address")

  def test_g_mode_is_supported_by_static_address_mode_gate(self):
    source = Path("server/models.py").read_text(encoding="utf-8")
    self.assertIn("DCC_TRACK_MODES = {TRACK_MODE_N, TRACK_MODE_HO, TRACK_MODE_G}", source)
    self.assertIn("track mode must be N, HO or G for DCC digital operation", source)

  def test_address_read_uses_cv29_and_cv1_for_short_address(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      vehicle_store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle_store.create_vehicle({"id": "v1", "name": "车", "address": 3, "track_mode": "ho"})
      state = self._state_with_safe_programming_track()
      transport = FakeUdpTransport([
        build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x1C, 0x06, 0x01, 0x01])),
        build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x0C, 0x01, 0x01])),
      ])
      body, status = ApiRouter(None, udp_transport=transport, vehicle_store=vehicle_store).handle_json("POST", "/api/address/read", b'{"vehicle_id":"v1"}', state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["address"], 12)
      self.assertEqual(payload["data"]["address_type"], "short")
      self.assertEqual(vehicle_store.get_vehicle("v1")["address"], 12)
      self.assertEqual([request["payload"] for request in transport.requests], [
        build_cv_read_frame(29, client_id=1),
        build_cv_read_frame(1, client_id=1),
      ])

  def test_address_read_uses_cv17_and_cv18_for_long_address(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x1C, 0x26, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x10, 0xC3, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x11, 0xE8, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/address/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["address"], 1000)
    self.assertEqual(payload["data"]["address_type"], "long")
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_read_frame(29, client_id=1),
      build_cv_read_frame(17, client_id=1),
      build_cv_read_frame(18, client_id=1),
    ])

  def test_address_write_short_address_uses_cv1_and_clears_cv29_bit5(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      vehicle_store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle_store.create_vehicle({"id": "v1", "name": "车", "address": 1000, "track_mode": "ho"})
      state = self._state_with_safe_programming_track()
      transport = FakeUdpTransport([
        build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x1C, 0x26, 0x01, 0x01])),
        build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01])),
      ])
      body, status = ApiRouter(None, udp_transport=transport, vehicle_store=vehicle_store).handle_json(
        "POST",
        "/api/address/write",
        b'{"vehicle_id":"v1","address":12,"confirmed":true}',
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["address"], 12)
      self.assertEqual(payload["data"]["address_type"], "short")
      self.assertEqual(vehicle_store.get_vehicle("v1")["address"], 12)
      self.assertEqual([request["payload"] for request in transport.requests], [
        build_cv_read_frame(29, client_id=1),
        build_cv_write_frame(1, 12, client_id=1),
        build_cv_write_frame(29, 0x06, client_id=1),
      ])

  def test_address_write_retries_busy_ack_for_cv29_write(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["cv_write_busy_retry_delay_seconds"] = 0
    transport = SequencedUdpTransport([
      [build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x1C, 0x20, 0x01, 0x01]))],
      [build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]))],
      [build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_BUSY, 0x01, 0x01]))],
      [build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]))],
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/address/write",
      b'{"address":12,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["address"], 12)
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_read_frame(29, client_id=1),
      build_cv_write_frame(1, 12, client_id=1),
      build_cv_write_frame(29, 0x00, client_id=1),
      build_cv_write_frame(29, 0x00, client_id=1),
    ])

  def test_address_write_long_address_uses_cv17_cv18_and_sets_cv29_bit5(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x1C, 0x06, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/address/write",
      b'{"address":1000,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["address"], 1000)
    self.assertEqual(payload["data"]["address_type"], "long")
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_read_frame(29, client_id=1),
      build_cv_write_frame(17, 0xC3, client_id=1),
      build_cv_write_frame(18, 0xE8, client_id=1),
      build_cv_write_frame(29, 0x26, client_id=1),
    ])

  def test_cv_read_requires_safe_dcc_mode(self):
    state = default_state()
    state["controller"]["udp_port"] = 12345
    state["controller"]["track_mode"] = "dc"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_track_mode")

  def test_g_mode_is_supported_by_static_programming_track_gate(self):
    source = Path("packages/digsight-dxdcnet/src/digsight_dxdcnet/programming_track.py").read_text(encoding="utf-8")
    self.assertIn('{"n", "ho", "g"}', source)
    self.assertIn("编程轨必须使用 N、HO 或 G 的 DCC 数码模式", source)

  def test_cv_read_rejects_stale_programming_status_after_mode_change(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["track_mode"] = "ho"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["debug"]["warnings"], ["programming_track_status_stale"])

  def test_cv_read_requires_confirmed_checksum_when_port_is_set(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["debug"]["warnings"], ["udp_checksum_algorithm_unconfirmed"])

  def test_cv_read_requires_parsed_programming_track_status(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "xor"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["debug"]["warnings"], ["programming_track_status_unconfirmed"])

  def test_cv_read_rejects_unsafe_programming_track_status(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
      "programming_track_busy": False,
      "programming_track_current_ma": 260,
      "output_value": 0x78,
      "current_limit_ma": 260,
    }
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":1}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_programming_track")

  def test_cv_read_rejects_invalid_cv_number(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/read", b'{"cv":0}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_cv")

  def test_main_track_cv_read_requires_vehicle(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["programming_target"] = "main_track"
    transport = FakeUdpTransport([])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":1,"programming_target":"main_track"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "vehicle_required_for_main_track_programming")
    self.assertEqual(transport.requests, [])

  def test_main_track_cv_read_rejects_stale_booster_status(self):
    state = self._state_with_main_track_ready()
    state["controller"]["safety_snapshot"]["booster_status_fresh"] = False
    transport = FakeUdpTransport([])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":1,"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["debug"]["warnings"], ["booster_status_stale"])
    self.assertEqual(transport.requests, [])

  def test_main_track_cv_read_uses_selected_vehicle_pom_address(self):
    state = self._state_with_main_track_ready()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x03, 0x01, 0x01, 0x0C, 0x00])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":1,"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["value"], 3)
    self.assertEqual(payload["data"]["programming_target"], "main_track")
    self.assertEqual(payload["data"]["vehicle_address"], 12)
    self.assertEqual(
      transport.requests[0]["payload"],
      build_cv_read_frame(1, client_id=1, op=PROGRAMMER_OP_MAIN_LOCO_POM, pom_address=12),
    )

  def test_main_track_cv_read_uses_type3_consist_vehicle_address_without_member_fanout(self):
    state = self._state_with_main_track_ready()
    state["vehicles"] = [
      {"id": "member-a", "name": "成员 A", "address": 12, "type": 0},
      {"id": "member-b", "name": "成员 B", "address": 13, "type": 0},
      {"id": "mu", "name": "重联控制车", "address": 77, "type": 3},
    ]
    state["consists"] = [{
      "id": "consist-1",
      "control_vehicle_id": "mu",
      "members": [
        {"vehicle_id": "member-a", "address": 12, "direction": "forward", "order": 1},
        {"vehicle_id": "member-b", "address": 13, "direction": "forward", "order": 2},
      ],
    }]
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x09, 0x01, 0x01, 0x4D, 0x00])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":1,"programming_target":"main_track","vehicle_id":"mu"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["value"], 9)
    self.assertEqual(payload["data"]["vehicle_id"], "mu")
    self.assertEqual(payload["data"]["vehicle_address"], 77)
    self.assertEqual(len(transport.requests), 1)
    self.assertEqual(
      transport.requests[0]["payload"],
      build_cv_read_frame(1, client_id=1, op=PROGRAMMER_OP_MAIN_LOCO_POM, pom_address=77),
    )

  def test_main_track_cv_read_uses_vehicle_store_lookup_when_state_vehicle_list_is_empty(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      store.create_vehicle({"id": "v1", "name": "车", "address": 12, "track_mode": "ho"})
      state = self._state_with_safe_programming_track()
      state["vehicles"] = []
      state["controller"]["programming_target"] = "main_track"
      state["controller"]["safety_snapshot"]["booster_status_fresh"] = True
      state["controller"]["booster_status"] = {
        "source": "dxdcnet_status_0x23",
        "power_on": True,
        "dcc_mode": True,
      }
      transport = FakeUdpTransport([
        build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x07, 0x01, 0x01, 0x0C, 0x00])),
      ])
      body, status = ApiRouter(None, udp_transport=transport, vehicle_store=store).handle_json(
        "POST",
        "/api/cv/read",
        b'{"cv":1,"programming_target":"main_track","vehicle_id":"v1"}',
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["value"], 7)
      self.assertEqual(payload["data"]["vehicle_address"], 12)
      self.assertEqual(
        transport.requests[0]["payload"],
        build_cv_read_frame(1, client_id=1, op=PROGRAMMER_OP_MAIN_LOCO_POM, pom_address=12),
      )

  def test_main_track_cv_read_requires_track_power(self):
    state = self._state_with_main_track_ready()
    state["controller"]["booster_status"]["power_on"] = False
    transport = FakeUdpTransport([])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":1,"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "main_track_power_required")
    self.assertEqual(transport.requests, [])

  def test_cv_read_uses_official_programmer_command_after_safety_passes(self):
    state = self._state_with_safe_programming_track()
    value_response = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=bytes([0x80, 0x07, 0x91, 0x01, 0x01]),
    )
    transport = FakeUdpTransport([value_response])
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/cv/read", b'{"cv":8}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["value"], 0x91)
    self.assertEqual(transport.requests[0]["payload"], bytes.fromhex("ff ff 17 01 14 80 07 00 85"))
    self.assertTrue(transport.requests[0]["stop_when"])

  def test_cv_read_debug_preserves_checksum_invalid_response(self):
    state = self._state_with_safe_programming_track()
    valid_value_response = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=bytes([0x80, 0x07, 0x56, 0x01, 0x01]),
    )
    checksum_invalid_response = valid_value_response[:-1] + bytes([valid_value_response[-1] ^ 0x01])
    transport = FakeUdpTransport([checksum_invalid_response])

    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/cv/read", b'{"cv":8}', state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_read_no_value")
    self.assertEqual(len(payload["debug"]["responses"]), 1)
    response_debug = payload["debug"]["responses"][0]
    self.assertFalse(response_debug["checksum_valid"])
    self.assertIn(WARNING_CHECKSUM_INVALID, response_debug["warnings"])

  def test_cv_read_all_uses_cv8_manufacturer_for_meanings(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x97, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x03, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x3E, 0x5A, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read-all",
      b'{"cv_numbers":[8,1,63]}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["manufacturer_id"], 151)
    self.assertEqual(payload["data"]["manufacturer_name"], "ESU")
    self.assertEqual(
      [(row["cv"], row["meaning"], row["value"], row["ok"]) for row in payload["data"]["rows"]],
      [
        (8, "生产厂家/复位（写入8恢复出厂）", 151, True),
        (1, "短地址", 3, True),
        (63, "总音量", 90, True),
      ],
    )
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_read_frame(8, client_id=1),
      build_cv_read_frame(1, client_id=1),
      build_cv_read_frame(63, client_id=1),
    ])

  def test_cv_read_all_known_mode_does_not_scan_full_range(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x56, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x03, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x06, 0x01, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read-all",
      b'{"read_mode":"known"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["read_mode"], "known")
    self.assertLess(payload["data"]["read_count"], 1024)
    self.assertEqual(transport.requests[0]["payload"], build_cv_read_frame(8, client_id=1))

  def test_cv_read_all_full_mode_scans_full_range(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x56, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/read-all",
      b'{"read_mode":"full"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["read_mode"], "full")
    self.assertEqual(payload["data"]["read_count"], 1024)

  def test_cv_read_cancel_endpoint_marks_session_cancelled(self):
    sessions = CVReadSessionRegistry()
    router = ApiRouter(None, cv_read_sessions=sessions)
    body, status = router.handle_json(
      "POST",
      "/api/cv/read-all/cancel",
      b'{"session_id":"session-1"}',
      default_state(),
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["cancelled"])
    self.assertEqual(payload["data"]["session_id"], "session-1")
    self.assertTrue(sessions.is_cancelled("session-1"))

  def test_cv_read_all_can_be_cancelled_by_session(self):
    state = self._state_with_safe_programming_track()
    sessions = CVReadSessionRegistry()
    transport = CancellingUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x56, 0x01, 0x01])),
    ], sessions, "session-1")
    body, status = ApiRouter(None, udp_transport=transport, cv_read_sessions=sessions).handle_json(
      "POST",
      "/api/cv/read-all",
      b'{"read_mode":"full","session_id":"session-1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["cancelled"])
    self.assertEqual(payload["data"]["session_id"], "session-1")
    self.assertEqual(payload["data"]["read_count"], 1)
    self.assertEqual(len(transport.requests), 1)
    self.assertFalse(sessions.is_cancelled("session-1"))

  def test_chip_info_read_reads_standard_cv8_and_cv7(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x55, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x06, 0x01, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/chip-info/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["manufacturer_id"], 85)
    self.assertEqual(payload["data"]["manufacturer_name"], "Uhlenbrock GmbH")
    self.assertEqual(payload["data"]["software_version"], 1)
    self.assertIsNone(payload["data"]["model"])
    self.assertIsNone(payload["data"]["hardware_version"])
    self.assertNotIn("extended_manufacturer_id", payload["data"])
    self.assertEqual([request["payload"] for request in transport.requests], [
      bytes.fromhex("ff ff 17 01 14 80 07 00 85"),
      bytes.fromhex("ff ff 17 01 14 80 06 00 84"),
    ])

  def test_chip_info_read_parses_digsight_model_and_hardware(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x1E, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x06, 0x22, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x7E, 0xA1, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x7F, 0x34, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/chip-info/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["manufacturer_id"], 30)
    self.assertEqual(payload["data"]["manufacturer_name"], "Digsight")
    self.assertEqual(payload["data"]["software_version"], 0x22)
    self.assertEqual(payload["data"]["hardware_version"], 5)
    self.assertEqual(payload["data"]["model"], 308)
    self.assertEqual(payload["data"]["cvs"]["127"]["value"], 0xA1)
    self.assertEqual(payload["data"]["cvs"]["128"]["value"], 0x34)
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_read_frame(8, client_id=1),
      build_cv_read_frame(7, client_id=1),
      build_cv_read_frame(127, client_id=1),
      build_cv_read_frame(128, client_id=1),
    ])

  def test_chip_info_read_does_not_read_extended_manufacturer_bytes(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0xEE, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x06, 0x02, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/chip-info/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["manufacturer_id"], 238)
    self.assertNotIn("extended_manufacturer_id", payload["data"])
    self.assertNotIn("107", payload["data"]["cvs"])
    self.assertNotIn("108", payload["data"]["cvs"])
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_read_frame(8, client_id=1),
      build_cv_read_frame(7, client_id=1),
    ])

  def test_chip_info_read_rejects_dc_operation_mode(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["track_mode"] = "dc"
    body, status = ApiRouter(None).handle_json("POST", "/api/chip-info/read", b"{}", state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_track_mode")

  def test_main_track_chip_info_read_surfaces_decoder_noack(self):
    state = self._state_with_main_track_ready()
    state["vehicles"][0]["address"] = 3
    noack_response = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_NOACK, 0x01, 0x01]),
    )
    body, status = ApiRouter(None, udp_transport=FakeUdpTransport([noack_response])).handle_json(
      "POST",
      "/api/chip-info/read",
      b'{"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "main_track_cv_read_no_ack")
    self.assertIn("主轨 CV 读取未收到车辆确认", payload["error"]["message"])
    self.assertIn("车辆地址 3", payload["error"]["detail"])
    self.assertEqual(payload["debug"]["ack"], "noack")
    self.assertEqual(payload["debug"]["pom_address"], 3)

  def test_cv_read_reports_ack_without_value(self):
    state = self._state_with_safe_programming_track()
    ack_response = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_NOACK, 0x01, 0x01]),
    )
    body, status = ApiRouter(None, udp_transport=FakeUdpTransport([ack_response])).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":8}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_read_ack_without_value")
    self.assertEqual(payload["debug"]["ack"], "noack")

  def test_cv_read_reports_malformed_programmer_response(self):
    state = self._state_with_safe_programming_track()
    malformed_value = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=b"\x00",
    )
    body, status = ApiRouter(None, udp_transport=FakeUdpTransport([malformed_value])).handle_json(
      "POST",
      "/api/cv/read",
      b'{"cv":8}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_programmer_response_parse_error")
    self.assertEqual(payload["debug"]["parse_warnings"][0]["type"], "programmer_value_parse_error")

  def test_cv_write_rejects_invalid_cv_number_after_confirmation(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/write", b'{"cv":0,"value":3,"confirmed":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_cv")

  def test_cv_write_rejects_invalid_cv_value_after_confirmation(self):
    state = default_state()
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/write", b'{"cv":1,"value":256,"confirmed":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_cv_value")

  def test_cv_write_requires_confirmed_checksum_when_port_is_set(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "unconfirmed"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/write", b'{"cv":1,"value":3,"confirmed":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["debug"]["warnings"], ["udp_checksum_algorithm_unconfirmed"])

  def test_cv_write_requires_parsed_programming_track_status(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "xor"
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/write", b'{"cv":1,"value":3,"confirmed":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")
    self.assertEqual(payload["debug"]["warnings"], ["programming_track_status_unconfirmed"])

  def test_cv_write_rejects_unsafe_programming_track_status(self):
    state = default_state()
    state["controller"]["udp_port"] = 21105
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["programming_track_status"] = {
      "source": "dxdcnet_status_0x23",
      "track_mode": "n",
      "dcc_mode": True,
      "programming_track_busy": False,
      "programming_track_current_ma": 260,
      "output_value": 0x78,
      "current_limit_ma": 260,
    }
    body, status = ApiRouter(None).handle_json("POST", "/api/cv/write", b'{"cv":1,"value":3,"confirmed":true}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_programming_track")

  def test_cv_write_uses_official_programmer_command_after_safety_passes(self):
    state = self._state_with_safe_programming_track()
    ack_response = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]),
    )
    transport = FakeUdpTransport([ack_response])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":3,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["value"], 3)
    self.assertEqual(transport.requests[0]["payload"], bytes.fromhex("ff ff 17 01 14 e0 00 03 e1"))
    self.assertTrue(transport.requests[0]["stop_when"])

  def test_cv_write_reports_no_ack_after_safety_passes(self):
    state = self._state_with_safe_programming_track()
    transport = FakeUdpTransport([])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":3,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_write_no_ack")
    self.assertEqual(transport.requests[0]["payload"], build_cv_write_frame(1, 3, client_id=1))
    self.assertEqual(payload["debug"]["request_hex"], build_cv_write_frame(1, 3, client_id=1).hex(" "))

  def test_cv_write_reports_malformed_programmer_ack(self):
    state = self._state_with_safe_programming_track()
    malformed_ack = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=b"\x00",
    )
    body, status = ApiRouter(None, udp_transport=FakeUdpTransport([malformed_ack])).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":3,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_programmer_response_parse_error")
    self.assertEqual(payload["debug"]["parse_warnings"][0]["type"], "programmer_ack_parse_error")

  def test_cv_write_retries_busy_ack_before_accepting(self):
    state = self._state_with_safe_programming_track()
    state["controller"]["cv_write_busy_retry_delay_seconds"] = 0
    transport = SequencedUdpTransport([
      [build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_BUSY, 0x01, 0x01]))],
      [build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]))],
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":3,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["value"], 3)
    self.assertEqual([request["payload"] for request in transport.requests], [
      build_cv_write_frame(1, 3, client_id=1),
      build_cv_write_frame(1, 3, client_id=1),
    ])
    self.assertEqual(payload["data"]["busy_retries"], 1)

  def test_main_track_cv_write_reads_back_after_ack(self):
    state = self._state_with_main_track_ready()
    state["controller"]["main_track_pom_verify_delay_seconds"] = 0
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x05, 0x01, 0x01, 0x0C, 0x00])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":5,"confirmed":true,"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["value"], 5)
    self.assertEqual(payload["data"]["readback"]["value"], 5)
    self.assertEqual(
      [request["payload"] for request in transport.requests],
      [
        build_cv_write_frame(1, 5, client_id=1, op=PROGRAMMER_OP_MAIN_LOCO_POM, pom_address=12),
        build_cv_read_frame(1, client_id=1, op=PROGRAMMER_OP_MAIN_LOCO_POM, pom_address=12),
      ],
    )

  def test_main_track_cv_write_reports_readback_failure(self):
    state = self._state_with_main_track_ready()
    state["controller"]["main_track_pom_verify_delay_seconds"] = 0
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":5,"confirmed":true,"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_write_readback_failed")
    self.assertIn("readback_request_hex", payload["debug"])

  def test_main_track_cv_write_reports_readback_mismatch(self):
    state = self._state_with_main_track_ready()
    state["controller"]["main_track_pom_verify_delay_seconds"] = 0
    transport = FakeUdpTransport([
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01])),
      build_udp_frame(0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x00, 0x04, 0x01, 0x01, 0x0C, 0x00])),
    ])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":1,"value":5,"confirmed":true,"programming_target":"main_track","vehicle_id":"v1"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 502)
    self.assertEqual(payload["error"]["type"], "cv_write_readback_mismatch")
    self.assertEqual(payload["debug"]["readback"]["value"], 4)

  def test_decoder_reset_uses_cv8_value8_programming_track_write(self):
    state = self._state_with_safe_programming_track()
    ack_response = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_ACK, 0x08, 0x01]),
    )
    transport = FakeUdpTransport([ack_response])
    body, status = ApiRouter(None, udp_transport=transport).handle_json(
      "POST",
      "/api/cv/write",
      b'{"cv":8,"value":8,"confirmed":true}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["cv"], 8)
    self.assertEqual(payload["data"]["value"], 8)
    self.assertEqual(transport.requests[0]["payload"], build_cv_write_frame(8, 8, client_id=1))

  def test_validate_cv_number_accepts_dcc_cv_range(self):
    self.assertEqual(validate_cv_number(1), 1)
    self.assertEqual(validate_cv_number(1024), 1024)

  def test_validate_cv_number_rejects_out_of_range_values(self):
    for cv_number in [0, 1025]:
      with self.assertRaises(ValueError):
        validate_cv_number(cv_number)


if __name__ == "__main__":
  unittest.main()

import json
import tempfile
import unittest
from pathlib import Path

from server.api import ApiRouter
from server.app_state import AppStateStore, default_state
from digsight_dxdcnet.constants import CMD_LOCO_CONTROL_ACK, CMD_LOCO_SPEED, DEVICE_TYPE_THROTTLE, SPEED_MODE_128
from digsight_dxdcnet.frames import build_udp_frame
from digsight_dxdcnet.loco_control import build_loco_control_request_frame, build_loco_speed_frame
from server.vehicle_store import VehicleStore
from tests.server_tests.controller_test_env import ready_loco_control_state, temporary_vehicle_router
from tests.server_tests.fake_udp import FakeRequestMappedUdpTransport


class ConsistApiTest(unittest.TestCase):
  def _loco_control_ack(self, address: int):
    high = ((address >> 8) & 0x3F) | (0x80 if address > 0x7F else 0)
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_CONTROL_ACK,
      payload=bytes([address & 0xFF, high, DEVICE_TYPE_THROTTLE, 1]),
    )

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

  def _members(self, count: int) -> list[dict]:
    return [
      {"vehicle_id": f"v{index}", "address": index + 1, "direction": "forward", "order": index + 1}
      for index in range(count)
    ]

  def _seed_member_vehicles(self, vehicle_store, count: int) -> None:
    for index in range(count):
      vehicle_store.create_vehicle({
        "id": f"v{index}",
        "name": f"测试车 {index}",
        "address": index + 1,
        "track_mode": "ho",
      })

  def test_create_consist_requires_members(self):
    with temporary_vehicle_router() as (router, _vehicle_store, state):
      request = json.dumps({"name": "空编组", "members": []}).encode("utf-8")
      body, status = router.handle_json("POST", "/api/consists", request, state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_consist")

  def test_create_consist_saves_members(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      self._seed_member_vehicles(vehicle_store, 2)
      request = {
        "name": "测试编组",
        "members": [{"vehicle_id": "v1", "address": 3, "direction": "forward", "order": 1}]
      }
      body, status = router.handle_json("POST", "/api/consists", json.dumps(request).encode("utf-8"), state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["members"][0]["address"], 3)
      self.assertEqual(vehicle_store.list_consists()[0]["name"], "测试编组")

  def test_create_consist_allows_up_to_eight_members(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      self._seed_member_vehicles(vehicle_store, 8)
      request = {"name": "八车编组", "members": self._members(8)}
      body, status = router.handle_json("POST", "/api/consists", json.dumps(request).encode("utf-8"), state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(len(payload["data"]["members"]), 8)

  def test_create_consist_rejects_more_than_eight_members(self):
    with temporary_vehicle_router() as (router, _vehicle_store, state):
      request = {"name": "九车编组", "members": self._members(9)}
      body, status = router.handle_json("POST", "/api/consists", json.dumps(request).encode("utf-8"), state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_consist")
      self.assertIn("最多 8 辆", payload["error"]["message"])

  def test_consist_speed_requires_protocol_ready(self):
    state = default_state()
    state["consists"].append({
      "id": "local-consist-1",
      "name": "测试编组",
      "members": [{"vehicle_id": "v1", "address": 3, "direction": "forward", "order": 1}],
    })
    body, status = ApiRouter(None).handle_json("POST", "/api/consists/local-consist-1/speed", b'{"speed":10}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")

  def test_consist_speed_fans_out_to_all_members_with_loco_safety_gate(self):
    state = ready_loco_control_state()
    state["vehicles"] = [
      {"id": "v1", "name": "A", "address": 11},
      {"id": "v2", "name": "B", "address": 22},
    ]
    state["consists"].append({
      "id": "local-consist-1",
      "name": "测试编组",
      "members": [
        {"vehicle_id": "v1", "address": 11, "direction": "forward", "order": 1},
        {"vehicle_id": "v2", "address": 22, "direction": "forward", "order": 2},
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
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "POST",
      "/api/consists/local-consist-1/speed",
      b'{"speed":42,"direction":"forward"}',
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])
    self.assertEqual([target["address"] for target in payload["data"]["targets"]], [11, 22])
    self.assertEqual(payload["data"]["control_mode"], "consist")

  def test_consist_stop_sets_speed_zero_for_all_members(self):
    state = ready_loco_control_state()
    state["vehicles"] = [
      {"id": "v1", "name": "A", "address": 11},
      {"id": "v2", "name": "B", "address": 22},
    ]
    state["consists"].append({
      "id": "local-consist-1",
      "name": "测试编组",
      "members": [
        {"vehicle_id": "v1", "address": 11, "direction": "forward", "order": 1},
        {"vehicle_id": "v2", "address": 22, "direction": "forward", "order": 2},
      ],
    })
    control_a = build_loco_control_request_frame(address=11, client_id=1)
    control_b = build_loco_control_request_frame(address=22, client_id=1)
    request_a = build_loco_speed_frame(address=11, speed=0, direction="forward", client_id=1)
    request_b = build_loco_speed_frame(address=22, speed=0, direction="forward", client_id=1)
    transport = FakeRequestMappedUdpTransport({
      control_a: [self._loco_control_ack(11)],
      request_a: [self._loco_speed_feedback(11, 0, "forward")],
      control_b: [self._loco_control_ack(22)],
      request_b: [self._loco_speed_feedback(22, 0, "forward")],
    })
    body, status = ApiRouter(None, controller_transport=transport).handle_json(
      "POST",
      "/api/consists/local-consist-1/stop",
      b"{}",
      state,
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["speed"], 0)
    self.assertEqual([request["payload"] for request in transport.requests], [control_a, request_a, control_b, request_b])

  def test_g_operation_mode_uses_primary_dcc_mode_gate_without_fixture_whitelist(self):
    models_source = Path("server/models.py").read_text(encoding="utf-8")
    api_source = Path("server/api.py").read_text(encoding="utf-8")
    app_source = Path("assets/js/app.js").read_text(encoding="utf-8")
    self.assertIn("DCC_TRACK_MODES = {TRACK_MODE_N, TRACK_MODE_HO, TRACK_MODE_G}", models_source)
    self.assertNotIn("CURRENT_FIXTURE_TESTED_DCC_TRACK_MODES", models_source)
    self.assertNotIn("CURRENT_FIXTURE_TESTED_DCC_TRACK_MODES", api_source)
    self.assertNotIn("operation_mode_not_safe_for_current_decoder", api_source)
    self.assertNotIn("operation_mode_not_safe_for_current_decoder", app_source)

  def test_patch_consist_updates_name_and_members(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      self._seed_member_vehicles(vehicle_store, 3)
      vehicle_store.create_consist({
        "id": "local-consist-1",
        "name": "旧编组",
        "members": [{"vehicle_id": "v1", "address": 3, "direction": "forward", "order": 1}],
      })
      request = {
        "name": "新编组",
        "members": [{"vehicle_id": "v2", "address": 4, "direction": "reverse", "order": 1}],
      }
      body, status = router.handle_json(
        "PATCH",
        "/api/consists/local-consist-1",
        json.dumps(request).encode("utf-8"),
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["name"], "新编组")
      self.assertEqual(payload["data"]["members"][0]["address"], 4)

  def test_patch_consist_rejects_more_than_eight_members(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      self._seed_member_vehicles(vehicle_store, 1)
      vehicle_store.create_consist({
        "id": "local-consist-1",
        "name": "旧编组",
        "members": [{"vehicle_id": "v0", "address": 1, "direction": "forward", "order": 1}],
      })
      request = {"members": self._members(9)}
      body, status = router.handle_json(
        "PATCH",
        "/api/consists/local-consist-1",
        json.dumps(request).encode("utf-8"),
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_consist")
      self.assertIn("最多 8 辆", payload["error"]["message"])

  def test_delete_consist_removes_record(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      self._seed_member_vehicles(vehicle_store, 2)
      vehicle_store.create_consist({
        "id": "local-consist-1",
        "name": "测试编组",
        "members": [{"vehicle_id": "v1", "address": 3, "direction": "forward", "order": 1}],
      })
      body, status = router.handle_json("DELETE", "/api/consists/local-consist-1", b"", state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["data"]["deleted"])
      self.assertEqual(vehicle_store.list_consists(), [])

  def test_sqlite_consist_api_persists_create_patch_delete(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      first = vehicle_store.create_vehicle({"name": "A", "address": 3, "track_mode": "ho"})
      second = vehicle_store.create_vehicle({"name": "B", "address": 4, "track_mode": "ho"})
      state["controller"]["track_mode"] = "ho"
      create_body, create_status = router.handle_json(
        "POST",
        "/api/consists",
        json.dumps({
          "name": "双机重联",
          "note": "测试",
          "members": [
            {"vehicle_id": first["id"], "address": 3, "direction": "forward", "order": 1},
            {"vehicle_id": second["id"], "address": 4, "direction": "reverse", "order": 2},
          ],
        }).encode("utf-8"),
        state,
      )
      created = json.loads(create_body.decode("utf-8"))["data"]
      self.assertEqual(create_status, 200)
      self.assertEqual(vehicle_store.list_consists()[0]["name"], "双机重联")
      self.assertEqual(len(vehicle_store.list_consists()[0]["members"]), 2)

      patch_body, patch_status = router.handle_json(
        "PATCH",
        f"/api/consists/{created['id']}",
        json.dumps({
          "name": "反向重联",
          "members": [
            {"vehicle_id": second["id"], "address": 4, "direction": "forward", "order": 1},
          ],
        }).encode("utf-8"),
        state,
      )
      patched = json.loads(patch_body.decode("utf-8"))["data"]
      self.assertEqual(patch_status, 200)
      self.assertEqual(patched["name"], "反向重联")
      self.assertEqual(vehicle_store.list_consists()[0]["members"][0]["vehicle_id"], second["id"])

      delete_body, delete_status = router.handle_json("DELETE", f"/api/consists/{created['id']}", b"", state)
      deleted = json.loads(delete_body.decode("utf-8"))["data"]
      self.assertEqual(delete_status, 200)
      self.assertTrue(deleted["deleted"])
      self.assertEqual(vehicle_store.list_consists(), [])

  def test_sqlite_consist_data_is_not_mirrored_to_app_state_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      state_store = AppStateStore(Path(temp_dir) / "app-state.json")
      vehicle_store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = vehicle_store.create_vehicle({"name": "A", "address": 3, "track_mode": "ho"})
      state = state_store.load()
      router = ApiRouter(state_store, vehicle_store=vehicle_store)
      body, status = router.handle_json(
        "POST",
        "/api/consists",
        json.dumps({
          "name": "持久编组",
          "members": [{"vehicle_id": vehicle["id"], "address": 3, "direction": "forward", "order": 1}],
        }).encode("utf-8"),
        state,
      )
      self.assertEqual(status, 200)
      self.assertEqual(json.loads(body.decode("utf-8"))["data"]["name"], "持久编组")
      saved_state = state_store.load()
      self.assertEqual(saved_state["consists"], [])
      self.assertEqual(vehicle_store.list_consists()[0]["name"], "持久编组")

  def test_sqlite_consist_list_does_not_fallback_to_app_state(self):
    with temporary_vehicle_router() as (router, _vehicle_store, state):
      state = default_state()
      state["consists"].append({
        "id": "runtime-json-consist",
        "name": "旧 JSON 编组",
        "members": [{"vehicle_id": "v1", "address": 3, "direction": "forward", "order": 1}],
      })
      body, status = router.handle_json("GET", "/api/consists", b"", state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"], [])


if __name__ == "__main__":
  unittest.main()

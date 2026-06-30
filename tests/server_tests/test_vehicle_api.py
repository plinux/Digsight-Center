import base64
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import zipfile

from server.api import ApiRouter
from server.app_state import AppStateStore, default_state
from digsight_dxdcnet.constants import CMD_LOCO_CONTROL_ACK, CMD_LOCO_FUNCTION, CMD_LOCO_SPEED, DEVICE_TYPE_THROTTLE
from digsight_dxdcnet.frames import build_udp_frame
from digsight_dxdcnet.loco_control import (
  build_loco_control_request_frame,
  build_loco_function_frame,
  build_loco_speed_frame,
)
from server.vehicle_store import VehicleStore
from tests.server_tests.controller_test_env import temporary_vehicle_router
from tests.server_tests.fake_udp import FakeRequestMappedUdpTransport


class VehicleApiTest(unittest.TestCase):
  def _mark_booster_status_fresh(self, state):
    state["controller"]["safety_snapshot"]["booster_status_fresh"] = True

  def _loco_control_ack(self, address: int, granted_id: int = 1):
    high = ((address >> 8) & 0x3F) | (0x80 if address > 0x7F else 0)
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_CONTROL_ACK,
      payload=bytes([address & 0xFF, high, DEVICE_TYPE_THROTTLE, granted_id]),
    )

  def _loco_speed_feedback(self, address: int, speed: int = 10):
    high = ((address >> 8) & 0x3F) | (0x80 if address > 0x7F else 0)
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_SPEED + 0x08,
      payload=bytes([address & 0xFF, high, 0x80 | speed, 0x02]),
    )

  def _loco_function_feedback(self, address: int):
    high = ((address >> 8) & 0x3F) | (0x80 if address > 0x7F else 0)
    return build_udp_frame(
      device_type=DEVICE_TYPE_THROTTLE,
      source_id=1,
      command=CMD_LOCO_FUNCTION + 0x08,
      payload=bytes([address & 0xFF, high, 0x1A, 0x01]),
    )

  def _create_minimal_z21_bytes(self, temp_dir: Path) -> bytes:
    sqlite_path = temp_dir / "Loco.sqlite"
    con = sqlite3.connect(sqlite_path)
    try:
      con.execute(
        "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT)"
      )
      con.execute(
        "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
      )
      con.execute("CREATE TABLE train_list (train_id TEXT, vehicle_id INTEGER, position INTEGER)")
      con.execute(
        "INSERT INTO vehicles (id, position, name, address, type, image_name) VALUES (1, 0, '测试车', 3, 0, '')"
      )
      con.execute(
        "INSERT INTO functions (id, vehicle_id, function, shortcut, image_name, button_type, time, position, show_function_number, is_configured) VALUES (1, 1, 0, '灯', 'main_beam', 0, '', 0, 1, 1)"
      )
      con.commit()
    finally:
      con.close()
    archive_path = temp_dir / "HO.z21"
    with zipfile.ZipFile(archive_path, "w") as archive:
      archive.write(sqlite_path, "export/test/Loco.sqlite")
    return archive_path.read_bytes()

  def test_sqlite_vehicle_api_creates_categories_and_vehicle(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      state["controller"]["track_mode"] = "ho"
      category_body, category_status = router.handle_json(
        "POST",
        "/api/categories",
        json.dumps({"name": "内燃机车", "description": "自定义"}).encode("utf-8"),
        state,
      )
      category_payload = json.loads(category_body.decode("utf-8"))
      self.assertEqual(category_status, 200)
      vehicle_body, vehicle_status = router.handle_json(
        "POST",
        "/api/vehicles",
        json.dumps({
          "name": "DF11",
          "address": 1160,
          "railway": "CR",
          "category_ids": [category_payload["data"]["id"]],
          "functions": [{"function_number": 0, "label": "行车灯", "icon_name": "main_beam"}],
        }).encode("utf-8"),
        state,
      )
      vehicle_payload = json.loads(vehicle_body.decode("utf-8"))
      self.assertEqual(vehicle_status, 200)
      self.assertEqual(vehicle_payload["data"]["name"], "DF11")
      self.assertEqual(vehicle_payload["data"]["track_mode"], "ho")
      self.assertEqual(vehicle_payload["data"]["categories"][0]["name"], "内燃机车")
      self.assertEqual(vehicle_payload["data"]["functions"][0]["label"], "行车灯")

  def test_sqlite_vehicle_api_preserves_function_trigger_mode(self):
    with temporary_vehicle_router() as (router, _vehicle_store, _state):
      request = json.dumps({
        "name": "BR 218",
        "address": 218,
        "functions": [
          {"function_number": 3, "label": "喇叭", "trigger_mode": "momentary", "duration_ms": 0}
        ],
      }).encode("utf-8")
      body, status = router.handle_json("POST", "/api/vehicles", request, {"controller": {"track_mode": "ho"}})
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["functions"][0]["trigger_mode"], "momentary")

  def test_sqlite_vehicle_list_returns_batched_details(self):
    with temporary_vehicle_router() as (router, vehicle_store, _state):
      category = vehicle_store.create_category({"name": "电力机车"})
      vehicle_store.create_vehicle_with_functions(
        {
          "name": "HXD1",
          "address": 1937,
          "track_mode": "ho",
          "category_ids": [category["id"]],
        },
        [{"function_number": 4, "label": "机舱灯"}],
      )

      body, status = router.handle_json("GET", "/api/vehicles", b"", default_state())
      payload = json.loads(body.decode("utf-8"))

      self.assertEqual(status, 200)
      self.assertEqual(payload["data"][0]["categories"][0]["name"], "电力机车")
      self.assertEqual(payload["data"][0]["functions"][0]["label"], "机舱灯")

  def test_sqlite_vehicle_patch_replaces_categories_functions_and_address_together(self):
    with temporary_vehicle_router() as (router, vehicle_store, _state):
      old_category = vehicle_store.create_category({"name": "旧分类"})
      new_category = vehicle_store.create_category({"name": "新分类"})
      vehicle = vehicle_store.create_vehicle_with_functions(
        {
          "name": "DF7",
          "address": 7140,
          "track_mode": "ho",
          "category_ids": [old_category["id"]],
        },
        [{"function_number": 0, "label": "旧灯"}],
      )
      request = json.dumps({
        "address": 7141,
        "category_ids": [new_category["id"]],
        "functions": [
          {"function_number": 0, "label": "行车灯"},
          {"function_number": 5, "label": "缓解", "trigger_mode": "momentary"},
        ],
      }).encode("utf-8")

      body, status = router.handle_json("PATCH", f"/api/vehicles/{vehicle['id']}", request, default_state())
      payload = json.loads(body.decode("utf-8"))

      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["address"], 7141)
      self.assertEqual(payload["data"]["category_ids"], [new_category["id"]])
      self.assertEqual([function["label"] for function in payload["data"]["functions"]], ["行车灯", "缓解"])
      stored = vehicle_store.get_vehicle(vehicle["id"])
      self.assertEqual(stored["category_ids"], [new_category["id"]])
      stored_functions = vehicle_store.list_functions(vehicle["id"])
      self.assertEqual([function["function_number"] for function in stored_functions], [0, 5])

  def test_sqlite_state_includes_vehicle_categories(self):
    with temporary_vehicle_router() as (router, vehicle_store, _state):
      category = vehicle_store.create_category({"name": "客运"})
      state = default_state()
      body, status = router.handle_json("GET", "/api/state", b"", state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["categories"][0]["id"], category["id"])

  def test_sqlite_vehicle_api_reorders_custom_vehicle_order(self):
    with temporary_vehicle_router() as (router, vehicle_store, _state):
      first = vehicle_store.create_vehicle({"name": "B", "address": 2, "track_mode": "ho"})
      second = vehicle_store.create_vehicle({"name": "A", "address": 1, "track_mode": "ho"})
      request = json.dumps({"vehicle_ids": [second["id"], first["id"]]}).encode("utf-8")
      body, status = router.handle_json("PATCH", "/api/vehicles/order", request, {"controller": {}})
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([vehicle["id"] for vehicle in payload["data"]["vehicles"][:2]], [second["id"], first["id"]])

  def test_sqlite_category_api_updates_and_deletes_category(self):
    with temporary_vehicle_router() as (router, vehicle_store, _state):
      category = vehicle_store.create_category({"name": "旧分类", "description": "旧说明", "sort_order": 3})

      update_body, update_status = router.handle_json(
        "PATCH",
        f"/api/categories/{category['id']}",
        json.dumps({"name": "新分类", "description": "新说明", "sort_order": 1}).encode("utf-8"),
        default_state(),
      )
      update_payload = json.loads(update_body.decode("utf-8"))
      self.assertEqual(update_status, 200)
      self.assertEqual(update_payload["data"]["name"], "新分类")
      self.assertEqual(update_payload["data"]["description"], "新说明")
      self.assertEqual(update_payload["data"]["sort_order"], 1)
      self.assertEqual(vehicle_store.get_category(category["id"])["name"], "新分类")

      delete_body, delete_status = router.handle_json("DELETE", f"/api/categories/{category['id']}", b"", default_state())
      delete_payload = json.loads(delete_body.decode("utf-8"))
      self.assertEqual(delete_status, 200)
      self.assertEqual(delete_payload["data"], {"id": category["id"], "deleted": True})
      self.assertIsNone(vehicle_store.get_category(category["id"]))

  def test_sqlite_category_api_reports_missing_category(self):
    with temporary_vehicle_router() as (router, _vehicle_store, _state):
      update_body, update_status = router.handle_json(
        "PATCH",
        "/api/categories/missing",
        json.dumps({"name": "不存在"}).encode("utf-8"),
        default_state(),
      )
      update_payload = json.loads(update_body.decode("utf-8"))
      self.assertEqual(update_status, 404)
      self.assertEqual(update_payload["error"]["type"], "category_not_found")

      delete_body, delete_status = router.handle_json("DELETE", "/api/categories/missing", b"", default_state())
      delete_payload = json.loads(delete_body.decode("utf-8"))
      self.assertEqual(delete_status, 404)
      self.assertEqual(delete_payload["error"]["type"], "category_not_found")

  def test_create_vehicle_with_invalid_function_rolls_back_vehicle_insert(self):
    with temporary_vehicle_router() as (router, vehicle_store, _state):
      request = json.dumps({
        "name": "DF11",
        "address": 1160,
        "track_mode": "ho",
        "functions": [{"function_number": 69, "label": "非法"}],
      }).encode("utf-8")
      body, status = router.handle_json("POST", "/api/vehicles", request, default_state())
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_vehicle")
      self.assertEqual(vehicle_store.list_vehicles(), [])

  def test_create_vehicle_rejects_missing_category_with_structured_error(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      request = json.dumps({
        "name": "DF11",
        "address": 1160,
        "track_mode": "ho",
        "category_ids": ["missing-category"],
      }).encode("utf-8")

      try:
        body, status = router.handle_json("POST", "/api/vehicles", request, state)
      except Exception as exc:  # pragma: no cover - exercised only before the regression fix
        self.fail(f"expected structured invalid_vehicle response, got {type(exc).__name__}: {exc}")

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_vehicle")
      self.assertEqual(vehicle_store.list_vehicles(), [])

  def test_patch_vehicle_rejects_duplicate_function_ids_with_structured_error(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      vehicle_store.create_vehicle({"id": "v1", "name": "车", "address": 3, "track_mode": "ho"})
      vehicle_store.replace_vehicle_functions("v1", [{"function_number": 0, "label": "灯"}])
      request = json.dumps({
        "functions": [
          {"id": "same-function", "function_number": 0, "label": "前灯"},
          {"id": "same-function", "function_number": 1, "label": "喇叭"},
        ]
      }).encode("utf-8")

      try:
        body, status = router.handle_json("PATCH", "/api/vehicles/v1", request, state)
      except Exception as exc:  # pragma: no cover - exercised only before the regression fix
        self.fail(f"expected structured invalid_vehicle response, got {type(exc).__name__}: {exc}")

      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_vehicle")
      self.assertEqual([function["label"] for function in vehicle_store.list_functions("v1")], ["灯"])

  def test_sqlite_vehicle_data_is_not_mirrored_to_app_state_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      state_store = AppStateStore(Path(temp_dir) / "app-state.json")
      vehicle_store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      first = vehicle_store.create_vehicle({"name": "B", "address": 2, "track_mode": "ho"})
      second = vehicle_store.create_vehicle({"name": "A", "address": 1, "track_mode": "ho"})
      router = ApiRouter(state_store, vehicle_store=vehicle_store)
      state = state_store.load()
      request = json.dumps({"vehicle_ids": [second["id"], first["id"]]}).encode("utf-8")
      body, status = router.handle_json("PATCH", "/api/vehicles/order", request, state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual([vehicle["id"] for vehicle in payload["data"]["vehicles"][:2]], [second["id"], first["id"]])
      saved_state = state_store.load()
      self.assertEqual(saved_state["vehicles"], [])
      self.assertEqual(saved_state["functions"], [])
      self.assertEqual(saved_state["categories"], [])

  def test_sqlite_z21_import_summary_is_not_mirrored_to_app_state_file(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      state_store = AppStateStore(temp_dir / "app-state.json")
      vehicle_store = VehicleStore(temp_dir / "vehicles.sqlite3")
      router = ApiRouter(state_store, image_dir=temp_dir / "vehicle-images", vehicle_store=vehicle_store)
      state = state_store.load()
      body, status = router.import_config_bytes("z21_layout_config", "HO.z21", self._create_minimal_z21_bytes(temp_dir), state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["summary"]["track_mode"], "ho")
      self.assertEqual(payload["data"]["summary"]["vehicles_imported"], 1)
      self.assertEqual(vehicle_store.list_vehicles()[0]["track_mode"], "ho")
      saved_state = state_store.load()
      self.assertEqual(saved_state["imports"], [])
      with vehicle_store._connect() as con:
        import_count = con.execute("SELECT COUNT(*) FROM vehicle_imports").fetchone()[0]
      self.assertEqual(import_count, 1)

  def test_vehicle_image_upload_stores_safe_local_image(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      router = ApiRouter(None, image_dir=temp_dir / "vehicle-images")
      png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgwJ/l92hlAAAAABJRU5ErkJggg=="
      )
      request = json.dumps({
        "file_name": "../test.png",
        "content_base64": base64.b64encode(png_1x1).decode("ascii"),
      }).encode("utf-8")
      body, status = router.handle_json("POST", "/api/vehicle-images", request, default_state())
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["data"]["image_path"].startswith("/data/vehicle-images/"))
      self.assertNotIn("..", payload["data"]["image_path"])
      stored = temp_dir / "vehicle-images" / Path(payload["data"]["image_path"]).name
      self.assertEqual(stored.read_bytes(), png_1x1)

  def test_vehicle_image_upload_rejects_decoded_content_above_json_budget(self):
    router = ApiRouter(None)
    oversized = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"0" * (1536 * 1024)).decode("ascii")
    body, status = router.handle_json(
      "POST",
      "/api/vehicle-images",
      json.dumps({"file_name": "large.png", "content_base64": oversized}).encode("utf-8"),
      default_state(),
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_vehicle_image")
    self.assertIn("1.5MB", payload["error"]["detail"])

  def test_sqlite_vehicle_api_delete_cleans_functions_and_consists(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      vehicle_store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = vehicle_store.create_vehicle({"name": "ICE", "address": 403})
      vehicle_store.replace_vehicle_functions(vehicle["id"], [{"function_number": 0, "label": "灯"}])
      vehicle_store.create_consist({
        "name": "编组",
        "members": [{"vehicle_id": vehicle["id"], "address": 403, "direction": "forward", "order": 1}],
      })
      state = default_state()
      body, status = ApiRouter(None, vehicle_store=vehicle_store).handle_json(
        "DELETE",
        f"/api/vehicles/{vehicle['id']}",
        b"",
        state,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["data"]["deleted"])
      self.assertIsNone(vehicle_store.get_vehicle(vehicle["id"]))
      self.assertEqual(vehicle_store.list_functions(vehicle["id"]), [])
      self.assertEqual(vehicle_store.list_consists()[0]["members"], [])

  def test_patch_vehicle_updates_address_and_consist_member(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      vehicle_store.create_vehicle({"id": "v1", "name": "旧名称", "address": 3, "description": "", "track_mode": "ho"})
      vehicle_store.create_consist({
        "id": "c1",
        "name": "编组",
        "members": [{"vehicle_id": "v1", "address": 3, "direction": "forward", "order": 1}],
      })
      request = json.dumps({"name": "新名称", "address": 12, "description": "已更新"}).encode("utf-8")
      body, status = router.handle_json("PATCH", "/api/vehicles/v1", request, state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["name"], "新名称")
      self.assertEqual(vehicle_store.get_vehicle("v1")["address"], 12)
      self.assertEqual(vehicle_store.list_consists()[0]["members"][0]["address"], 12)

  def test_patch_vehicle_rejects_invalid_address(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      vehicle_store.create_vehicle({"id": "v1", "name": "车", "address": 3, "track_mode": "ho"})
      for address in [0, 10000]:
        request = json.dumps({"address": address}).encode("utf-8")
        body, status = router.handle_json("PATCH", "/api/vehicles/v1", request, state)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["type"], "invalid_vehicle")

  def test_patch_vehicle_updates_function_table(self):
    with temporary_vehicle_router() as (router, vehicle_store, state):
      vehicle_store.create_vehicle({"id": "v1", "name": "车", "address": 3, "track_mode": "ho"})
      vehicle_store.replace_vehicle_functions("v1", [{"function_number": 0, "label": "灯"}])
      request = json.dumps({
        "functions": [
          {"function_number": 0, "label": "前灯", "icon_name": "light", "button_type": 1, "position": 0, "show_function_number": True, "is_configured": True},
          {"function_number": 1, "label": "喇叭", "icon_name": "horn", "button_type": 2, "position": 1, "show_function_number": True, "is_configured": True},
        ]
      }).encode("utf-8")
      body, status = router.handle_json("PATCH", "/api/vehicles/v1", request, state)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(len(payload["data"]["functions"]), 2)
      self.assertEqual(vehicle_store.list_functions("v1")[0]["label"], "前灯")

  def test_loco_speed_requires_protocol_ready(self):
    state = default_state()
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({"vehicle_id": "v1", "speed": 10, "direction": "forward"}).encode("utf-8")
    body, status = ApiRouter(None).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "protocol_not_ready")

  def test_loco_speed_rejects_dc_operation_mode(self):
    state = default_state()
    state["controller"]["track_mode"] = "dc"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    request = json.dumps({"vehicle_id": "v1", "speed": 10, "direction": "forward"}).encode("utf-8")
    body, status = ApiRouter(None).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "unsafe_track_mode")

  def test_loco_speed_requires_track_power(self):
    state = default_state()
    state["controller"]["track_mode"] = "n"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": False, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({"vehicle_id": "v1", "speed": 10, "direction": "forward"}).encode("utf-8")
    body, status = ApiRouter(None, udp_transport=FakeRequestMappedUdpTransport({})).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "track_power_required")

  def test_loco_speed_sends_dxdcnet_speed_command_after_protocol_ready(self):
    state = default_state()
    state["controller"]["track_mode"] = "n"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({"vehicle_id": "v1", "speed": 10, "direction": "forward"}).encode("utf-8")
    expected_control = build_loco_control_request_frame(3)
    expected_frame = build_loco_speed_frame(3, 10, "forward")
    transport = FakeRequestMappedUdpTransport({
      expected_control: [self._loco_control_ack(3)],
      expected_frame: [],
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual([item["payload"] for item in transport.requests], [expected_control, expected_frame])
    self.assertEqual(payload["data"]["request_hex"], expected_frame.hex(" "))

  def test_loco_speed_feedback_ignores_wrong_address_before_target_feedback(self):
    state = default_state()
    state["controller"]["track_mode"] = "n"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({"vehicle_id": "v1", "speed": 10, "direction": "forward"}).encode("utf-8")
    expected_control = build_loco_control_request_frame(3)
    expected_frame = build_loco_speed_frame(3, 10, "forward")
    transport = FakeRequestMappedUdpTransport({
      expected_control: [self._loco_control_ack(3)],
      expected_frame: [self._loco_speed_feedback(4, 20), self._loco_speed_feedback(3, 10)],
    })

    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["feedback"]["address"], 3)
    self.assertEqual(payload["data"]["feedback"]["speed"], 10)

  def test_loco_speed_requests_control_for_long_dcc_address(self):
    state = default_state()
    state["controller"]["track_mode"] = "ho"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v4945", "name": "车", "address": 4945})
    request = json.dumps({"vehicle_id": "v4945", "speed": 10, "direction": "forward"}).encode("utf-8")
    expected_control = build_loco_control_request_frame(4945)
    expected_frame = build_loco_speed_frame(4945, 10, "forward")
    transport = FakeRequestMappedUdpTransport({
      expected_control: [self._loco_control_ack(4945)],
      expected_frame: [],
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual([item["payload"] for item in transport.requests], [expected_control, expected_frame])
    self.assertEqual(payload["data"]["request_hex"], "ff ff 18 01 10 51 93 8a 02 43")

  def test_loco_function_sends_dxdcnet_function_command_after_protocol_ready(self):
    state = default_state()
    state["controller"]["track_mode"] = "ho"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({
      "vehicle_id": "v1",
      "function_number": 5,
      "enabled": True,
      "function_states": {"0": True, "2": True, "4": True, "5": True},
    }).encode("utf-8")
    expected_control = build_loco_control_request_frame(3)
    expected_frame = build_loco_function_frame(3, {0: True, 2: True, 4: True, 5: True})
    transport = FakeRequestMappedUdpTransport({
      expected_control: [self._loco_control_ack(3)],
      expected_frame: [],
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/function", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual([item["payload"] for item in transport.requests], [expected_control, expected_frame])
    self.assertEqual(payload["data"]["function_number"], 5)

  def test_loco_function_rejects_non_boolean_enabled_and_function_states(self):
    state = self._state_with_ready_loco_control()
    requests = (
      {"vehicle_id": "v1", "function_number": 5, "enabled": "false", "function_states": {"5": False}},
      {"vehicle_id": "v1", "function_number": 5, "enabled": False, "function_states": {"5": "false"}},
    )
    for request in requests:
      with self.subTest(request=request):
        body, status = ApiRouter(None).handle_json(
          "POST",
          "/api/loco/function",
          json.dumps(request).encode("utf-8"),
          state,
        )
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["type"], "invalid_loco_control")

  def test_loco_function_feedback_ignores_wrong_address_before_target_feedback(self):
    state = default_state()
    state["controller"]["track_mode"] = "ho"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({
      "vehicle_id": "v1",
      "function_number": 5,
      "enabled": True,
      "function_states": {"0": True, "2": True, "4": True, "5": True},
    }).encode("utf-8")
    expected_control = build_loco_control_request_frame(3)
    expected_frame = build_loco_function_frame(3, {0: True, 2: True, 4: True, 5: True})
    transport = FakeRequestMappedUdpTransport({
      expected_control: [self._loco_control_ack(3)],
      expected_frame: [self._loco_function_feedback(4), self._loco_function_feedback(3)],
    })

    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/function", request, state)
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertEqual(payload["data"]["feedback"]["address"], 3)
    self.assertTrue(payload["data"]["feedback"]["function_states"]["5"])

  def test_loco_function_sends_f13_group_after_protocol_ready(self):
    state = default_state()
    state["controller"]["track_mode"] = "ho"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v4945", "name": "车", "address": 4945})
    request = json.dumps({
      "vehicle_id": "v4945",
      "function_number": 13,
      "enabled": True,
      "function_states": {"0": True, "13": True},
    }).encode("utf-8")
    expected_control = build_loco_control_request_frame(4945)
    expected_frame = build_loco_function_frame(4945, {0: True, 13: True}, function_number=13)
    transport = FakeRequestMappedUdpTransport({
      expected_control: [self._loco_control_ack(4945)],
      expected_frame: [],
    })
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/function", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertEqual([item["payload"] for item in transport.requests], [expected_control, expected_frame])
    self.assertEqual(payload["data"]["request_hex"], "ff ff 18 01 11 51 93 40 01 8b")
    self.assertEqual(payload["data"]["function_number"], 13)

  def test_loco_control_denial_stops_before_speed_command(self):
    state = default_state()
    state["controller"]["track_mode"] = "ho"
    state["controller"]["udp_port"] = 12000
    state["controller"]["udp_checksum_algorithm"] = "xor"
    state["controller"]["last_probe_ok"] = True
    state["controller"]["controller_reachable"] = True
    state["controller"]["booster_status"] = {"source": "dxdcnet_status_0x23", "power_on": True, "dcc_mode": True}
    self._mark_booster_status_fresh(state)
    state["vehicles"].append({"id": "v1", "name": "车", "address": 3})
    request = json.dumps({"vehicle_id": "v1", "speed": 10, "direction": "forward"}).encode("utf-8")
    expected_control = build_loco_control_request_frame(3)
    transport = FakeRequestMappedUdpTransport({expected_control: [self._loco_control_ack(3, granted_id=0)]})
    body, status = ApiRouter(None, udp_transport=transport).handle_json("POST", "/api/loco/speed", request, state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 409)
    self.assertEqual(payload["error"]["type"], "loco_control_denied")
    self.assertEqual([item["payload"] for item in transport.requests], [expected_control])


if __name__ == "__main__":
  unittest.main()

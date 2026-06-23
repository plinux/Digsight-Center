import tempfile
import unittest
from pathlib import Path
import sqlite3

from server.vehicle_store import VehicleStore


class VehicleStoreCoreTest(unittest.TestCase):
  def test_initial_test_vehicle_seed_creates_n_ho_g_single_and_consist_fixtures(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      self.assertEqual(store.list_vehicles(), [])

      store.ensure_initial_test_vehicles()
      store.ensure_initial_test_vehicles()

      vehicles = store.list_vehicles()
      self.assertEqual(len(vehicles), 9)
      vehicles_by_mode = {
        mode: [vehicle for vehicle in vehicles if vehicle["track_mode"] == mode]
        for mode in ("n", "ho", "g")
      }
      for mode in ("n", "ho", "g"):
        self.assertEqual([vehicle["address"] for vehicle in vehicles_by_mode[mode]], [3, 4, 3])
        self.assertEqual([vehicle["type"] for vehicle in vehicles_by_mode[mode]], [0, 0, 3])
        self.assertTrue(all(vehicle["source"] == "seed" for vehicle in vehicles_by_mode[mode]))
        self.assertEqual([vehicle["image_path"] for vehicle in vehicles_by_mode[mode]], [
          "/assets/icons/vehicle-types/energy-electric.svg",
          "/assets/icons/vehicle-types/energy-electric.svg",
          "/assets/icons/vehicle-types/consist-multiple-unit.svg",
        ])
        self.assertEqual(vehicles_by_mode[mode][0]["id"], f"seed-test-vehicle-{mode}-3")
        self.assertEqual(vehicles_by_mode[mode][1]["id"], f"seed-test-vehicle-{mode}-4")
        self.assertEqual(vehicles_by_mode[mode][2]["id"], f"seed-test-vehicle-{mode}-3-4-consist")
        self.assertEqual(vehicles_by_mode[mode][2]["consist_kind"], "consist")
        self.assertTrue(vehicles_by_mode[mode][2]["sync_function_control"])
      self.assertEqual(store.list_categories(), [])
      consists = store.list_consists()
      self.assertEqual(len(consists), 3)
      for consist in consists:
        mode = consist["track_mode"]
        self.assertIn(mode, {"n", "ho", "g"})
        self.assertEqual(consist["id"], f"seed-test-consist-{mode}-3-4")
        self.assertEqual(consist["control_vehicle_id"], f"seed-test-vehicle-{mode}-3-4-consist")
        self.assertEqual(consist["consist_kind"], "consist")
        self.assertEqual([member["vehicle_id"] for member in consist["members"]], [
          f"seed-test-vehicle-{mode}-3",
          f"seed-test-vehicle-{mode}-4",
        ])
        self.assertEqual([member["address"] for member in consist["members"]], [3, 4])

      for vehicle in vehicles:
        functions = store.list_functions(vehicle["id"])
        self.assertEqual([function["function_number"] for function in functions], list(range(32)))
        self.assertTrue(all(function["label"] == "" for function in functions))
        self.assertTrue(all(function["icon_name"] == "function-generic" for function in functions))
        self.assertTrue(all(function["trigger_mode"] == "toggle" for function in functions))
        self.assertTrue(all(function["show_function_number"] for function in functions))
        self.assertTrue(all(function["is_configured"] for function in functions))

  def test_initial_test_vehicle_seed_backfills_missing_fixtures_for_seed_only_library(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      store.create_vehicle({"id": "seed-test-vehicle-n-3", "name": "N 测试车", "address": 3, "track_mode": "n", "source": "seed"})
      store.create_vehicle({"id": "seed-test-vehicle-ho-3", "name": "HO 测试车", "address": 3, "track_mode": "ho", "source": "seed"})

      store.ensure_initial_test_vehicles()

      vehicles = store.list_vehicles()
      self.assertEqual(len(vehicles), 9)
      by_id = {vehicle["id"]: vehicle for vehicle in vehicles}
      for mode in ("n", "ho", "g"):
        self.assertEqual(by_id[f"seed-test-vehicle-{mode}-3"]["address"], 3)
        self.assertEqual(by_id[f"seed-test-vehicle-{mode}-4"]["address"], 4)
        self.assertEqual(by_id[f"seed-test-vehicle-{mode}-3-4-consist"]["type"], 3)
        self.assertEqual(by_id[f"seed-test-vehicle-{mode}-3"]["image_path"], "/assets/icons/vehicle-types/energy-electric.svg")
        self.assertEqual(by_id[f"seed-test-vehicle-{mode}-4"]["image_path"], "/assets/icons/vehicle-types/energy-electric.svg")
        self.assertEqual(by_id[f"seed-test-vehicle-{mode}-3-4-consist"]["image_path"], "/assets/icons/vehicle-types/consist-multiple-unit.svg")
      self.assertEqual(sorted(consist["id"] for consist in store.list_consists()), [
        "seed-test-consist-g-3-4",
        "seed-test-consist-ho-3-4",
        "seed-test-consist-n-3-4",
      ])
      self.assertEqual([function["function_number"] for function in store.list_functions("seed-test-vehicle-g-3")], list(range(32)))

  def test_initial_test_vehicle_seed_does_not_modify_non_empty_library(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      existing = store.create_vehicle({"name": "用户车辆", "address": 9, "track_mode": "ho"})

      store.ensure_initial_test_vehicles()

      vehicles = store.list_vehicles()
      self.assertEqual(len(vehicles), 1)
      self.assertEqual(vehicles[0]["id"], existing["id"])
      self.assertEqual(vehicles[0]["name"], "用户车辆")

  def test_vehicle_store_adds_renamed_buffer_columns_to_existing_database(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      db_path = Path(temp_dir) / "vehicles.sqlite3"
      old_buffer_column = "buffer_leng" "ht"
      old_model_buffer_column = "model_buffer_leng" "ht"
      con = sqlite3.connect(db_path)
      con.executescript(
        f"""
        CREATE TABLE vehicles (
          id TEXT PRIMARY KEY,
          source TEXT NOT NULL DEFAULT 'manual',
          source_vehicle_id TEXT,
          track_mode TEXT DEFAULT '',
          z21_position INTEGER,
          custom_sort_order INTEGER DEFAULT 0,
          name TEXT NOT NULL,
          address INTEGER NOT NULL,
          image_name TEXT,
          image_path TEXT,
          type INTEGER DEFAULT 0,
          sync_function_control INTEGER DEFAULT 0,
          energy_type TEXT DEFAULT '',
          car_subtype TEXT DEFAULT '',
          consist_kind TEXT DEFAULT '',
          max_speed INTEGER,
          brand TEXT,
          full_name TEXT,
          railway TEXT,
          article_number TEXT,
          decoder_type TEXT,
          {old_buffer_column} TEXT,
          {old_model_buffer_column} TEXT,
          service_weight TEXT,
          model_weight TEXT,
          rmin TEXT,
          description TEXT,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        """
      )
      con.close()

      store = VehicleStore(db_path)
      vehicle = store.create_vehicle({
        "name": "迁移测试车",
        "address": 3,
        "track_mode": "ho",
        "buffer_length": "120",
        "model_buffer_length": "10400",
      })

      self.assertEqual(vehicle["buffer_length"], "120")
      self.assertEqual(vehicle["model_buffer_length"], "10400")

  def test_vehicle_functions_preserve_explicit_empty_label(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle({"name": "空功能名测试车", "address": 3, "track_mode": "ho"})

      functions = store.replace_vehicle_functions(vehicle["id"], [
        {"function_number": 0, "label": "", "icon_name": "function-generic"},
      ])

      self.assertEqual(functions[0]["label"], "")

  def test_vehicle_store_uses_shared_update_and_function_row_helpers(self):
    source = Path("server/vehicle_store.py").read_text(encoding="utf-8")
    self.assertIn("VEHICLE_UPDATE_COLUMNS", source)
    self.assertIn("def _vehicle_update_assignments(", source)
    self.assertIn("def _normalized_function_row(", source)

  def test_schema_preserves_z21_vehicle_fields_and_categories(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      category = store.create_category({"name": "电力机车", "description": "自定义分类"})
      vehicle = store.create_vehicle({
        "name": "BR 103",
        "address": 103,
        "source": "manual",
        "source_vehicle_id": None,
        "z21_position": 7,
        "image_name": "image-uuid",
        "image_path": "/data/vehicle-images/br103.png",
        "type": 0,
        "full_name": "DB BR 103",
        "railway": "DB",
        "article_number": "39150",
        "decoder_type": "DCC 128",
        "buffer_length": "192",
        "model_buffer_length": "1200",
        "service_weight": "114",
        "model_weight": "0.45",
        "rmin": "360",
        "description": "测试车辆",
        "track_mode": "ho",
        "category_ids": [category["id"]],
      })
      stored = store.get_vehicle(vehicle["id"])
      self.assertEqual(stored["name"], "BR 103")
      self.assertEqual(stored["address"], 103)
      self.assertEqual(stored["article_number"], "39150")
      self.assertEqual(stored["buffer_length"], "192")
      self.assertEqual(stored["track_mode"], "ho")
      self.assertEqual(stored["categories"][0]["name"], "电力机车")

  def test_update_and_delete_vehicle_cleans_related_rows(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      category = store.create_category({"name": "客运"})
      vehicle = store.create_vehicle({"name": "ICE", "address": 401, "category_ids": [category["id"]]})
      store.replace_vehicle_functions(vehicle["id"], [
        {
          "function_number": 0,
          "label": "灯",
          "icon_name": "light",
          "button_type": 0,
          "time": "",
          "position": 0,
          "show_function_number": True,
          "is_configured": True,
        }
      ])
      updated = store.update_vehicle(vehicle["id"], {"name": "ICE 3", "category_ids": []})
      self.assertEqual(updated["name"], "ICE 3")
      self.assertEqual(updated["categories"], [])
      store.delete_vehicle(vehicle["id"])
      self.assertIsNone(store.get_vehicle(vehicle["id"]))
      self.assertEqual(store.list_functions(vehicle["id"]), [])

  def test_update_vehicle_with_functions_keeps_created_at_and_updates_functions_atomically(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle_with_functions(
        {
          "name": "原始车辆",
          "address": 3,
          "track_mode": "ho",
          "functions": [{"function_number": 0, "label": "旧灯"}],
        },
        [{"function_number": 0, "label": "旧灯"}],
      )
      created_at = vehicle["created_at"]

      updated = store.update_vehicle_with_functions(
        vehicle["id"],
        {"name": "更新车辆", "address": 33},
        [
          {"function_number": 0, "label": "前灯"},
          {"function_number": 1, "label": "鸣笛", "trigger_mode": "momentary"},
          {"function_number": 2, "label": "广播", "trigger_mode": "timed", "duration_ms": 1500},
        ],
      )

      self.assertEqual(updated["name"], "更新车辆")
      self.assertEqual(updated["address"], 33)
      self.assertEqual(updated["created_at"], created_at)
      functions = store.list_functions(vehicle["id"])
      self.assertEqual([function["function_number"] for function in functions], [0, 1, 2])
      self.assertEqual([function["label"] for function in functions], ["前灯", "鸣笛", "广播"])
      self.assertEqual(functions[2]["duration_ms"], 1500)

  def test_vehicle_functions_preserve_trigger_mode_and_duration(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle({"name": "ICE", "address": 401})
      functions = store.replace_vehicle_functions(vehicle["id"], [
        {"function_number": 0, "label": "灯", "trigger_mode": "toggle", "duration_ms": 0},
        {"function_number": 1, "label": "鸣笛", "trigger_mode": "momentary", "duration_ms": 0},
        {"function_number": 2, "label": "广播", "trigger_mode": "timed", "duration_ms": 3000},
      ])
      self.assertEqual(functions[0]["trigger_mode"], "toggle")
      self.assertEqual(functions[1]["trigger_mode"], "momentary")
      self.assertEqual(functions[2]["trigger_mode"], "timed")
      self.assertEqual(functions[2]["duration_ms"], 3000)

  def test_vehicle_functions_sync_button_type_from_trigger_mode(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle({"name": "ICE", "address": 401})
      functions = store.replace_vehicle_functions(vehicle["id"], [
        {"function_number": 0, "label": "灯", "trigger_mode": "toggle"},
        {"function_number": 1, "label": "鸣笛", "trigger_mode": "momentary"},
        {"function_number": 2, "label": "广播", "trigger_mode": "timed", "duration_ms": 3000},
      ])
      self.assertEqual([function["button_type"] for function in functions], [0, 1, 2])

  def test_vehicle_preserves_max_speed(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle({
        "name": "速度测试车",
        "address": 88,
        "track_mode": "ho",
        "max_speed": 140,
        "functions": [{"function_number": 0, "label": "灯"}],
      })
      self.assertEqual(vehicle["max_speed"], 140)

      updated = store.update_vehicle(vehicle["id"], {"max_speed": 160})
      self.assertEqual(updated["max_speed"], 160)

  def test_vehicle_preserves_model_brand(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle({
        "name": "ROCO BR218",
        "address": 218,
        "track_mode": "ho",
        "brand": "ROCO",
      })
      self.assertEqual(vehicle["brand"], "ROCO")

      updated = store.update_vehicle(vehicle["id"], {"brand": "PIKO"})
      self.assertEqual(updated["brand"], "PIKO")

  def test_vehicle_type_and_sync_function_control_are_persisted(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicle = store.create_vehicle({
        "name": "重联测试车",
        "address": 3,
        "type": 3,
        "sync_function_control": True,
      })
      self.assertEqual(vehicle["type"], 3)
      self.assertTrue(vehicle["sync_function_control"])

      updated = store.update_vehicle(vehicle["id"], {
        "type": 1,
        "sync_function_control": False,
      })
      self.assertEqual(updated["type"], 1)
      self.assertFalse(updated["sync_function_control"])

  def test_vehicle_kind_fields_have_type_specific_defaults(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      locomotive = store.create_vehicle({"name": "默认电力机车", "address": 10, "type": 0})
      coach = store.create_vehicle({"name": "默认客车", "address": 11, "type": 1})
      consist = store.create_vehicle({"name": "默认编组", "address": 3, "type": 3})

      self.assertEqual(locomotive["energy_type"], "electric")
      self.assertEqual(locomotive["car_subtype"], "")
      self.assertEqual(coach["energy_type"], "")
      self.assertEqual(coach["car_subtype"], "passenger")
      self.assertEqual(consist["consist_kind"], "multiple_unit")

  def test_vehicle_store_validation_keeps_existing_defaults_and_errors(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      with self.assertRaisesRegex(ValueError, "energy type must be diesel, electric, steam or hybrid"):
        store.create_vehicle({"name": "bad", "address": 3, "type": 0, "energy_type": "solar"})
      vehicle = store.create_vehicle({"name": "default energy", "address": 4, "type": 0})
      self.assertEqual(vehicle["energy_type"], "electric")
      car = store.create_vehicle({"name": "car", "address": 5, "type": 1})
      self.assertEqual(car["car_subtype"], "passenger")

  def test_sync_function_control_only_persists_for_consist_control_vehicle(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      locomotive = store.create_vehicle({
        "name": "普通机车",
        "address": 12,
        "type": 0,
        "sync_function_control": True,
      })
      consist = store.create_vehicle({
        "name": "同步重联",
        "address": 3,
        "type": 3,
        "consist_kind": "multiple_unit",
        "sync_function_control": True,
      })

      self.assertFalse(locomotive["sync_function_control"])
      self.assertTrue(consist["sync_function_control"])
      self.assertEqual(consist["consist_kind"], "multiple_unit")

  def test_new_consist_kind_values_persist_for_control_vehicle_and_consist(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      locomotive = store.create_vehicle({"name": "动力车", "address": 21, "type": 0})
      coach = store.create_vehicle({"name": "控制车", "address": 22, "type": 1})
      control = store.create_vehicle({
        "name": "动集列车",
        "address": 3,
        "type": 3,
        "consist_kind": "powered_set",
      })

      consist = store.create_consist({
        "name": "旅客列车编组",
        "control_vehicle_id": control["id"],
        "consist_kind": "train_set",
        "members": [
          {"vehicle_id": locomotive["id"], "address": locomotive["address"], "direction": "forward"},
          {"vehicle_id": coach["id"], "address": coach["address"], "direction": "reverse"},
        ],
      })

      self.assertEqual(control["consist_kind"], "powered_set")
      self.assertEqual(consist["consist_kind"], "train_set")

  def test_update_vehicle_custom_order_persists_sequence(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      first = store.create_vehicle({"name": "B", "address": 2, "track_mode": "ho"})
      second = store.create_vehicle({"name": "A", "address": 1, "track_mode": "ho"})
      store.update_vehicle_custom_order([second["id"], first["id"]])
      vehicles = store.list_vehicles()
      self.assertEqual([vehicle["id"] for vehicle in vehicles[:2]], [second["id"], first["id"]])
      self.assertEqual(vehicles[0]["custom_sort_order"], 0)
      self.assertEqual(vehicles[1]["custom_sort_order"], 1)

  def test_create_consist_rejects_more_than_eight_members(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      vehicles = [
        store.create_vehicle({"name": f"车{index}", "address": index + 1, "track_mode": "ho"})
        for index in range(9)
      ]
      members = [
        {"vehicle_id": vehicle["id"], "address": vehicle["address"], "direction": "forward", "order": index + 1}
        for index, vehicle in enumerate(vehicles)
      ]
      with self.assertRaisesRegex(ValueError, "最多 8 辆"):
        store.create_consist({"name": "九车编组", "members": members})

  def test_consist_control_vehicle_id_is_persisted(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store = VehicleStore(Path(temp_dir) / "vehicles.sqlite3")
      control = store.create_vehicle({"id": "mu", "name": "重联", "address": 3, "type": 3})
      first = store.create_vehicle({"id": "loco-a", "name": "A", "address": 11})
      second = store.create_vehicle({"id": "loco-b", "name": "B", "address": 22})
      consist = store.create_consist({
        "name": "重联",
        "control_vehicle_id": control["id"],
        "members": [
          {"vehicle_id": first["id"], "address": first["address"], "direction": "forward", "order": 1},
          {"vehicle_id": second["id"], "address": second["address"], "direction": "forward", "order": 2},
        ],
      })
      self.assertEqual(consist["control_vehicle_id"], control["id"])
      self.assertEqual([member["address"] for member in consist["members"]], [11, 22])



if __name__ == "__main__":
  unittest.main()

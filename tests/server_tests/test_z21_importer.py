import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
import zipfile

import server.importers.z21_parser as z21_module
from server.importers.z21_parser import Z21Importer


FIXTURE_DIR = Path("tests/fixtures")


class Z21ImporterTest(unittest.TestCase):
  def _create_minimal_z21(self, temp_dir: Path, function_rows: list[tuple]) -> Path:
    sqlite_path = temp_dir / "Loco.sqlite"
    con = sqlite3.connect(sqlite_path)
    try:
      con.execute(
        "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT, max_speed INTEGER)"
      )
      con.execute(
        "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
      )
      con.execute("CREATE TABLE train_list (train_id TEXT, vehicle_id INTEGER, position INTEGER)")
      con.execute(
        "INSERT INTO vehicles (id, position, name, address, type, image_name, max_speed) VALUES (1, 0, '测试车', 3, 0, '', 100)"
      )
      for row in function_rows:
        con.execute(
          "INSERT INTO functions (id, vehicle_id, function, shortcut, image_name, button_type, time, position, show_function_number, is_configured) VALUES (?, 1, ?, ?, ?, ?, ?, ?, 1, 0)",
          row,
        )
      con.commit()
    finally:
      con.close()
    archive_path = temp_dir / "HO.z21"
    with zipfile.ZipFile(archive_path, "w") as archive:
      archive.write(sqlite_path, "export/test/Loco.sqlite")
    return archive_path

  def test_imports_known_samples(self):
    baselines = json.loads(Path("tests/fixtures/z21_baselines.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as temp_dir:
      importer = Z21Importer(Path(temp_dir) / "vehicle-images")
      for file_name, expected in baselines.items():
        path = FIXTURE_DIR / expected["fixture"]
        self.assertTrue(path.exists(), f"fixture is missing: {path}")
        result = importer.import_file(path)
        self.assertEqual(result.summary["vehicles_imported"], expected["vehicles"], file_name)
        self.assertEqual(result.summary["functions_imported"], expected["functions"], file_name)
        self.assertEqual(result.summary["consists_imported"], expected["train_list"], file_name)
        self.assertEqual(result.summary["layout_controls_seen"], expected["control_station_controls"], file_name)
        self.assertEqual(result.summary["layout_routes_seen"], expected["control_station_routes"], file_name)

  def test_import_preserves_z21_vehicle_fields_and_categories(self):
    sample = FIXTURE_DIR / "z21" / "HO.z21"
    self.assertTrue(sample.exists(), f"fixture is missing: {sample}")
    with tempfile.TemporaryDirectory() as temp_dir:
      result = Z21Importer(Path(temp_dir) / "vehicle-images").import_file(sample)
      self.assertEqual(result.summary["track_mode"], "ho")
      first_vehicle = result.vehicles[0]
      self.assertEqual(first_vehicle["track_mode"], "ho")
      self.assertTrue(first_vehicle["id"].startswith("z21-ho-vehicle-"))
      self.assertIn("article_number", first_vehicle)
      self.assertIn("buffer_length", first_vehicle)
      self.assertIn("model_buffer_length", first_vehicle)
      self.assertIn("service_weight", first_vehicle)
      self.assertIn("model_weight", first_vehicle)
      self.assertIn("rmin", first_vehicle)
      self.assertIn("max_speed", first_vehicle)
      self.assertEqual(first_vehicle["max_speed"], 100)
      self.assertIn("category_ids", first_vehicle)
      self.assertGreater(len(result.categories), 0)
      self.assertTrue(any(vehicle["category_ids"] for vehicle in result.vehicles))

  def test_import_infers_n_track_mode_from_file_name(self):
    sample = FIXTURE_DIR / "z21" / "N.z21"
    self.assertTrue(sample.exists(), f"fixture is missing: {sample}")
    with tempfile.TemporaryDirectory() as temp_dir:
      result = Z21Importer(Path(temp_dir) / "vehicle-images").import_file(sample)
      self.assertEqual(result.summary["track_mode"], "n")
      self.assertTrue(all(vehicle["track_mode"] == "n" for vehicle in result.vehicles))

  def test_import_uses_file_name_scope_when_track_mode_is_not_in_name(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      archive_path = self._create_minimal_z21(Path(temp_dir), [])
      scoped_path = archive_path.with_name("Depot Layout 2026.z21")
      archive_path.rename(scoped_path)
      result = Z21Importer(Path(temp_dir) / "vehicle-images").import_file(scoped_path)
      self.assertEqual(result.summary["track_mode"], "")
      self.assertTrue(result.vehicles[0]["id"].startswith("z21-depot-layout-2026-vehicle-"))

  def test_rejects_archive_without_loco_sqlite(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      archive_path = Path(temp_dir) / "empty.z21"
      import zipfile
      with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("note.txt", "not a z21 export")
      importer = Z21Importer(Path(temp_dir) / "vehicle-images")
      with self.assertRaises(ValueError):
        importer.import_file(archive_path)

  def test_rejects_loco_sqlite_member_over_size_budget(self):
    with tempfile.TemporaryDirectory() as temp_dir_name:
      temp_dir = Path(temp_dir_name)
      archive_path = temp_dir / "oversized.z21"
      with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("export/test/Loco.sqlite", b"0123456789")
      previous_limit = z21_module.MAX_Z21_SQLITE_BYTES
      z21_module.MAX_Z21_SQLITE_BYTES = 8
      try:
        with self.assertRaisesRegex(ValueError, "超过导入大小限制"):
          Z21Importer(temp_dir / "vehicle-images").import_file(archive_path)
      finally:
        z21_module.MAX_Z21_SQLITE_BYTES = previous_limit

  def test_maps_z21_button_type_to_trigger_mode_and_local_icons(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      archive_path = self._create_minimal_z21(temp_dir, [
        (1, 0, "灯", "main_beam", 0, "", 0),
        (2, 1, "鸣笛", "horn_high", 1, "", 1),
        (3, 2, "未映射", "unknown_z21_icon", 2, "2500", 2),
      ])
      result = Z21Importer(temp_dir / "vehicle-images").import_file(archive_path)
      by_number = {item["function_number"]: item for item in result.functions}
      self.assertEqual(by_number[0]["trigger_mode"], "toggle")
      self.assertEqual(by_number[1]["trigger_mode"], "momentary")
      self.assertEqual(by_number[2]["trigger_mode"], "timed")
      self.assertTrue(by_number[0]["is_configured"])
      self.assertTrue(by_number[1]["is_configured"])
      self.assertTrue(by_number[2]["is_configured"])
      self.assertEqual(by_number[0]["icon_name"], "light-front")
      self.assertEqual(by_number[1]["icon_name"], "horn-high")
      self.assertEqual(by_number[2]["icon_name"], "function-generic")
      self.assertEqual(by_number[2]["z21_icon_name"], "unknown_z21_icon")

  def test_type3_vehicle_is_linked_to_train_list_consist_members(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      sqlite_path = temp_dir / "Loco.sqlite"
      con = sqlite3.connect(sqlite_path)
      try:
        con.execute(
          "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT, max_speed INTEGER)"
        )
        con.execute(
          "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
        )
        con.execute("CREATE TABLE train_list (train_id TEXT, vehicle_id INTEGER, position INTEGER)")
        con.execute("INSERT INTO vehicles VALUES (1, 0, 'A车', 11, 0, '', 100)")
        con.execute("INSERT INTO vehicles VALUES (2, 1, 'B车', 22, 0, '', 100)")
        con.execute("INSERT INTO vehicles VALUES (100, 2, 'AB重联', 3, 3, '', 100)")
        con.execute("INSERT INTO train_list VALUES ('100', 1, 0)")
        con.execute("INSERT INTO train_list VALUES ('100', 2, 1)")
        con.commit()
      finally:
        con.close()

      archive_path = temp_dir / "HO.z21"
      with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(sqlite_path, "export/test/Loco.sqlite")

      result = Z21Importer(temp_dir / "vehicle-images").import_file(archive_path)
      consist = result.consists[0]
      first_vehicle = next(vehicle for vehicle in result.vehicles if vehicle["id"] == "z21-ho-vehicle-1")
      self.assertEqual(first_vehicle["brand"], "A车")
      self.assertEqual(consist["control_vehicle_id"], "z21-ho-vehicle-100")
      self.assertEqual(consist["name"], "AB重联")
      self.assertEqual([member["vehicle_id"] for member in consist["members"]], [
        "z21-ho-vehicle-1",
        "z21-ho-vehicle-2",
      ])
      self.assertEqual([vehicle["type"] for vehicle in result.vehicles if vehicle["id"] == "z21-ho-vehicle-100"], [3])
      self.assertEqual([vehicle["consist_kind"] for vehicle in result.vehicles if vehicle["id"] == "z21-ho-vehicle-100"], ["multiple_unit"])
      self.assertEqual(consist["consist_kind"], "multiple_unit")

  def test_type3_vehicle_with_non_locomotive_member_is_imported_as_train_set(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      sqlite_path = temp_dir / "Loco.sqlite"
      con = sqlite3.connect(sqlite_path)
      try:
        con.execute(
          "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT, max_speed INTEGER)"
        )
        con.execute(
          "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
        )
        con.execute("CREATE TABLE train_list (train_id TEXT, vehicle_id INTEGER, position INTEGER)")
        con.execute("INSERT INTO vehicles VALUES (1, 0, '机车', 11, 0, '', 100)")
        con.execute("INSERT INTO vehicles VALUES (2, 1, '工程车', 22, 1, '', 100)")
        con.execute("INSERT INTO vehicles VALUES (100, 2, '施工编组', 3, 3, '', 100)")
        con.execute("INSERT INTO train_list VALUES ('100', 1, 0)")
        con.execute("INSERT INTO train_list VALUES ('100', 2, 1)")
        con.commit()
      finally:
        con.close()

      archive_path = temp_dir / "HO.z21"
      with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(sqlite_path, "export/test/Loco.sqlite")

      result = Z21Importer(temp_dir / "vehicle-images").import_file(archive_path)
      control = next(vehicle for vehicle in result.vehicles if vehicle["id"] == "z21-ho-vehicle-100")
      self.assertEqual(control["consist_kind"], "train_set")
      self.assertEqual(result.consists[0]["consist_kind"], "train_set")

  def test_import_prefills_brand_from_first_vehicle_name_token(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      sqlite_path = temp_dir / "Loco.sqlite"
      con = sqlite3.connect(sqlite_path)
      try:
        con.execute(
          "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT, max_speed INTEGER)"
        )
        con.execute(
          "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
        )
        con.execute("INSERT INTO vehicles VALUES (1, 0, 'ROCO EK750 0604 (HO)', 604, 1, '', 6)")
        con.execute("INSERT INTO vehicles VALUES (2, 1, '   ', 605, 1, '', 100)")
        con.commit()
      finally:
        con.close()

      archive_path = temp_dir / "HO.z21"
      with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(sqlite_path, "export/test/Loco.sqlite")

      result = Z21Importer(temp_dir / "vehicle-images").import_file(archive_path)
      first = next(vehicle for vehicle in result.vehicles if vehicle["id"] == "z21-ho-vehicle-1")
      second = next(vehicle for vehicle in result.vehicles if vehicle["id"] == "z21-ho-vehicle-2")
      self.assertEqual(first["brand"], "ROCO")
      self.assertEqual(second["brand"], "")

  def test_import_prefills_vehicle_kind_from_z21_categories(self):
    with tempfile.TemporaryDirectory() as temp_name:
      temp_dir = Path(temp_name)
      sqlite_path = temp_dir / "Loco.sqlite"
      con = sqlite3.connect(sqlite_path)
      try:
        con.execute(
          "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT, max_speed INTEGER)"
        )
        con.execute(
          "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
        )
        con.execute("CREATE TABLE categories (id INTEGER PRIMARY KEY, name TEXT)")
        con.execute("CREATE TABLE vehicles_to_categories (vehicle_id INTEGER, category_id INTEGER)")
        con.execute("CREATE TABLE train_list (train_id TEXT, vehicle_id INTEGER, position INTEGER)")
        con.executemany(
          "INSERT INTO vehicles VALUES (?, ?, ?, ?, ?, '', 100)",
          [
            (1, 0, "内燃测试车", 11, 0),
            (2, 1, "电力测试车", 22, 0),
            (3, 2, "混动测试车", 33, 0),
            (4, 3, "蒸汽测试车", 44, 0),
            (100, 4, "重连测试车", 3, 3),
          ],
        )
        con.executemany(
          "INSERT INTO categories VALUES (?, ?)",
          [
            (1, "内燃机车"),
            (2, "电力机车"),
            (3, "混动机车"),
            (4, "蒸汽机车"),
            (5, "重连机车"),
          ],
        )
        con.executemany(
          "INSERT INTO vehicles_to_categories VALUES (?, ?)",
          [(1, 1), (2, 2), (3, 3), (4, 4), (100, 5)],
        )
        con.execute("INSERT INTO train_list VALUES ('100', 1, 0)")
        con.execute("INSERT INTO train_list VALUES ('100', 2, 1)")
        con.commit()
      finally:
        con.close()

      archive_path = temp_dir / "HO.z21"
      with zipfile.ZipFile(archive_path, "w") as archive:
        archive.write(sqlite_path, "export/test/Loco.sqlite")

      result = Z21Importer(temp_dir / "vehicle-images").import_file(archive_path)
      vehicles = {vehicle["source_vehicle_id"]: vehicle for vehicle in result.vehicles}
      self.assertEqual(vehicles["1"]["energy_type"], "diesel")
      self.assertEqual(vehicles["2"]["energy_type"], "electric")
      self.assertEqual(vehicles["3"]["energy_type"], "hybrid")
      self.assertEqual(vehicles["4"]["energy_type"], "steam")
      self.assertEqual(vehicles["100"]["consist_kind"], "multiple_unit")
      self.assertEqual(result.consists[0]["consist_kind"], "multiple_unit")


if __name__ == "__main__":
  unittest.main()

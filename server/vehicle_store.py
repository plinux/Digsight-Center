"""SQLite backed vehicle library."""

from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sqlite3
import uuid

from server import models


VEHICLE_FIELDS = (
  "source",
  "source_vehicle_id",
  "track_mode",
  "z21_position",
  "custom_sort_order",
  "name",
  "address",
  "image_name",
  "image_path",
  "type",
  "sync_function_control",
  "energy_type",
  "car_subtype",
  "consist_kind",
  "max_speed",
  "brand",
  "full_name",
  "railway",
  "article_number",
  "decoder_type",
  "buffer_length",
  "model_buffer_length",
  "service_weight",
  "model_weight",
  "rmin",
  "description",
)

VEHICLE_UPDATE_COLUMNS = (
  *VEHICLE_FIELDS,
  "created_at",
  "updated_at",
)

FUNCTION_FIELDS = (
  "source_function_id",
  "function_number",
  "label",
  "icon_name",
  "button_type",
  "time",
  "trigger_mode",
  "duration_ms",
  "position",
  "show_function_number",
  "is_configured",
)

REPLACEABLE_SEED_IMAGE_PATHS = {
  "",
  None,
  "/assets/icons/vehicle-types/consist-group.svg",
}

TRIGGER_MODE_TO_BUTTON_TYPE = {
  "toggle": 0,
  "momentary": 1,
  "timed": 2,
}

BUTTON_TYPE_TO_TRIGGER_MODE = {
  0: "toggle",
  1: "momentary",
  2: "timed",
}

INITIAL_TEST_TRACK_MODES = (
  (models.TRACK_MODE_N, "N", 0),
  (models.TRACK_MODE_HO, "HO", 10),
  (models.TRACK_MODE_G, "G", 20),
)

INITIAL_TEST_VEHICLES = tuple(
  vehicle
  for mode, label, sort_offset in INITIAL_TEST_TRACK_MODES
  for vehicle in (
    {
      "id": f"seed-test-vehicle-{mode}-3",
      "source": "seed",
      "track_mode": mode,
      "custom_sort_order": sort_offset + 1,
      "name": f"{label} 测试车",
      "address": 3,
      "image_path": "/assets/icons/vehicle-types/energy-electric.svg",
      "type": 0,
    },
    {
      "id": f"seed-test-vehicle-{mode}-4",
      "source": "seed",
      "track_mode": mode,
      "custom_sort_order": sort_offset + 2,
      "name": f"{label} 测试车 4",
      "address": 4,
      "image_path": "/assets/icons/vehicle-types/energy-electric.svg",
      "type": 0,
    },
    {
      "id": f"seed-test-vehicle-{mode}-3-4-consist",
      "source": "seed",
      "track_mode": mode,
      "custom_sort_order": sort_offset + 3,
      "name": f"{label} 3+4 重联",
      "address": 3,
      "image_path": "/assets/icons/vehicle-types/consist-multiple-unit.svg",
      "type": 3,
      "sync_function_control": True,
      "consist_kind": "consist",
    },
  )
)

INITIAL_TEST_CONSISTS = tuple(
  {
    "id": f"seed-test-consist-{mode}-3-4",
    "source": "seed",
    "track_mode": mode,
    "control_vehicle_id": f"seed-test-vehicle-{mode}-3-4-consist",
    "consist_kind": "consist",
    "name": f"{label} 3+4 重联",
    "members": [
      {
        "vehicle_id": f"seed-test-vehicle-{mode}-3",
        "address": 3,
        "direction": "forward",
        "order": 1,
      },
      {
        "vehicle_id": f"seed-test-vehicle-{mode}-4",
        "address": 4,
        "direction": "forward",
        "order": 2,
      },
    ],
  }
  for mode, label, _sort_offset in INITIAL_TEST_TRACK_MODES
)


class VehicleStore:
  def __init__(self, path: Path):
    self.path = Path(path)
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self._initialize()

  def _initialize(self) -> None:
    with self._connect() as con:
      schema = Path(__file__).with_name("vehicle_schema.sql").read_text(encoding="utf-8")
      con.executescript(schema)
      self._ensure_column(con, "vehicles", "track_mode", "TEXT DEFAULT ''")
      self._ensure_column(con, "vehicles", "custom_sort_order", "INTEGER DEFAULT 0")
      self._ensure_column(con, "vehicles", "max_speed", "INTEGER")
      self._ensure_column(con, "vehicles", "sync_function_control", "INTEGER DEFAULT 0")
      self._ensure_column(con, "vehicles", "energy_type", "TEXT DEFAULT ''")
      self._ensure_column(con, "vehicles", "car_subtype", "TEXT DEFAULT ''")
      self._ensure_column(con, "vehicles", "consist_kind", "TEXT DEFAULT ''")
      self._ensure_column(con, "vehicles", "brand", "TEXT DEFAULT ''")
      self._ensure_column(con, "vehicles", "buffer_length", "TEXT")
      self._ensure_column(con, "vehicles", "model_buffer_length", "TEXT")
      self._ensure_column(con, "categories", "track_mode", "TEXT DEFAULT ''")
      self._ensure_column(con, "consists", "track_mode", "TEXT DEFAULT ''")
      self._ensure_column(con, "consists", "control_vehicle_id", "TEXT")
      self._ensure_column(con, "consists", "consist_kind", "TEXT DEFAULT ''")
      self._ensure_column(con, "vehicle_functions", "trigger_mode", "TEXT DEFAULT 'toggle'")
      self._ensure_column(con, "vehicle_functions", "duration_ms", "INTEGER DEFAULT 0")
      self._merge_shared_z21_categories(con)

  def ensure_initial_test_vehicles(self) -> None:
    """Seed the runtime vehicle library with the minimal N/HO/G test fixtures."""
    with self._connect() as con:
      rows = con.execute("SELECT id, source, image_path FROM vehicles").fetchall()
      consist_rows = con.execute("SELECT id, source FROM consists").fetchall()
      expected_seed_ids = {vehicle["id"] for vehicle in INITIAL_TEST_VEHICLES}
      expected_consist_ids = {consist["id"] for consist in INITIAL_TEST_CONSISTS}
      existing_ids = {row["id"] for row in rows}
      existing_by_id = {row["id"]: row for row in rows}
      existing_consist_ids = {row["id"] for row in consist_rows}
      if (rows or consist_rows) and (
        any(row["source"] != "seed" for row in rows)
        or not existing_ids.issubset(expected_seed_ids)
        or any(row["source"] != "seed" for row in consist_rows)
        or not existing_consist_ids.issubset(expected_consist_ids)
      ):
        return
      now = self._now()
      for vehicle in INITIAL_TEST_VEHICLES:
        vehicle_id = vehicle["id"]
        if vehicle_id in existing_ids:
          if vehicle.get("image_path") and existing_by_id[vehicle_id]["image_path"] in REPLACEABLE_SEED_IMAGE_PATHS:
            con.execute(
              "UPDATE vehicles SET image_path = ?, updated_at = ? WHERE id = ?",
              (vehicle["image_path"], now, vehicle_id),
            )
          continue
        self._insert_vehicle(con, vehicle, now)
        self._replace_vehicle_functions(con, vehicle_id, self._initial_test_functions())
      for consist in INITIAL_TEST_CONSISTS:
        if consist["id"] in existing_consist_ids:
          continue
        self._insert_consist(con, consist, now)

  def _initial_test_functions(self) -> list[dict]:
    return [{
      "function_number": function_number,
      "label": "",
      "icon_name": "function-generic",
      "trigger_mode": "toggle",
      "button_type": 0,
      "duration_ms": 0,
      "position": function_number,
      "show_function_number": True,
      "is_configured": True,
    } for function_number in range(32)]

  @contextmanager
  def _connect(self):
    con = sqlite3.connect(self.path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    try:
      yield con
      con.commit()
    finally:
      con.close()

  def list_vehicles(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute("SELECT * FROM vehicles ORDER BY custom_sort_order, z21_position IS NULL, z21_position, name, address").fetchall()
      return [self._vehicle_from_row(con, row) for row in rows]

  def list_all_functions(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute(
        """
        SELECT *
        FROM vehicle_functions
        ORDER BY vehicle_id, position, function_number
        """
      ).fetchall()
      return [self._function_from_row(row) for row in rows]

  def list_consists(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute("SELECT * FROM consists ORDER BY created_at, name").fetchall()
      return [self._consist_from_row(con, row) for row in rows]

  def get_consist(self, consist_id: str) -> dict | None:
    with self._connect() as con:
      row = con.execute("SELECT * FROM consists WHERE id = ?", (consist_id,)).fetchone()
      if row is None:
        return None
      return self._consist_from_row(con, row)

  def get_vehicle(self, vehicle_id: str) -> dict | None:
    with self._connect() as con:
      row = con.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
      if row is None:
        return None
      return self._vehicle_from_row(con, row)

  def create_vehicle(self, data: dict) -> dict:
    return self.create_vehicle_with_functions(data, None)

  def create_vehicle_with_functions(self, data: dict, functions: list[dict] | None) -> dict:
    now = self._now()
    vehicle_id = data.get("id") or f"local-vehicle-{uuid.uuid4().hex}"
    with self._connect() as con:
      self._insert_vehicle(con, {**data, "id": vehicle_id}, now)
      self._replace_vehicle_categories(con, vehicle_id, data.get("category_ids", []))
      self._replace_vehicle_functions(con, vehicle_id, functions or [])
      row = con.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
      return self._vehicle_from_row(con, row)

  def update_vehicle(self, vehicle_id: str, data: dict) -> dict | None:
    return self.update_vehicle_with_functions(vehicle_id, data, None)

  def update_vehicle_with_functions(self, vehicle_id: str, data: dict, functions: list[dict] | None) -> dict | None:
    with self._connect() as con:
      row = con.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
      if row is None:
        return None
      current = self._vehicle_from_row(con, row)
      merged = {**current, **data}
      updated_at = self._now()
      values = self._vehicle_values(merged, current["created_at"], updated_at)
      con.execute(
        f"UPDATE vehicles SET {self._vehicle_update_assignments()} WHERE id = ?",
        (*values, vehicle_id),
      )
      if "category_ids" in data:
        self._replace_vehicle_categories(con, vehicle_id, data.get("category_ids", []))
      if functions is not None:
        self._replace_vehicle_functions(con, vehicle_id, functions)
      row = con.execute("SELECT * FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
      return self._vehicle_from_row(con, row)

  def delete_vehicle(self, vehicle_id: str) -> bool:
    with self._connect() as con:
      result = con.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))
      return result.rowcount > 0

  def create_category(self, data: dict) -> dict:
    now = self._now()
    category_id = data.get("id") or f"local-category-{uuid.uuid4().hex}"
    with self._connect() as con:
      self._insert_category(con, {**data, "id": category_id, "source": data.get("source") or "manual"}, now)
    return self.get_category(category_id)

  def get_category(self, category_id: str) -> dict | None:
    with self._connect() as con:
      row = con.execute("SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
      return self._category_from_row(row) if row else None

  def list_categories(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute("SELECT * FROM categories ORDER BY created_at, sort_order, name").fetchall()
      return [self._category_from_row(row) for row in rows]

  def update_category(self, category_id: str, data: dict) -> dict | None:
    current = self.get_category(category_id)
    if current is None:
      return None
    merged = {**current, **data}
    with self._connect() as con:
      con.execute(
        """
        UPDATE categories
        SET name = ?, description = ?, sort_order = ?, updated_at = ?
        WHERE id = ?
        """,
        (
          self._required_text(merged.get("name"), "category name"),
          merged.get("description", ""),
          int(merged.get("sort_order", 0) or 0),
          self._now(),
          category_id,
        ),
      )
    return self.get_category(category_id)

  def delete_category(self, category_id: str) -> bool:
    with self._connect() as con:
      result = con.execute("DELETE FROM categories WHERE id = ?", (category_id,))
      return result.rowcount > 0

  def list_functions(self, vehicle_id: str) -> list[dict]:
    with self._connect() as con:
      return self._functions_for_vehicle(con, vehicle_id)

  def replace_vehicle_functions(self, vehicle_id: str, functions: list[dict]) -> list[dict]:
    with self._connect() as con:
      self._replace_vehicle_functions(con, vehicle_id, functions)
      return self._functions_for_vehicle(con, vehicle_id)

  def update_vehicle_custom_order(self, vehicle_ids: list[str]) -> list[dict]:
    with self._connect() as con:
      now = self._now()
      for index, vehicle_id in enumerate(vehicle_ids):
        con.execute(
          "UPDATE vehicles SET custom_sort_order = ?, updated_at = ? WHERE id = ?",
          (index, now, vehicle_id),
        )
    return self.list_vehicles()

  def create_consist(self, data: dict) -> dict:
    now = self._now()
    consist_id = data.get("id") or f"local-consist-{uuid.uuid4().hex}"
    with self._connect() as con:
      self._insert_consist(con, {**data, "id": consist_id, "source": data.get("source") or "manual"}, now)
    return self.get_consist(consist_id)

  def update_consist(self, consist_id: str, data: dict) -> dict | None:
    current = self.get_consist(consist_id)
    if current is None:
      return None
    merged = {**current, **data}
    with self._connect() as con:
      con.execute(
        """
        UPDATE consists
        SET name = ?, note = ?, control_vehicle_id = ?, track_mode = ?, consist_kind = ?, updated_at = ?
        WHERE id = ?
        """,
        (
          self._required_text(merged.get("name"), "consist name"),
          merged.get("note", ""),
          self._validate_consist_control_vehicle(con, merged.get("control_vehicle_id")),
          self._validate_track_mode(merged.get("track_mode", "")),
          self._validate_consist_kind(merged.get("consist_kind", "")),
          self._now(),
          consist_id,
        ),
      )
      if "members" in data:
        self._replace_consist_members(con, consist_id, data.get("members", []))
    return self.get_consist(consist_id)

  def delete_consist(self, consist_id: str) -> bool:
    with self._connect() as con:
      result = con.execute("DELETE FROM consists WHERE id = ?", (consist_id,))
      return result.rowcount > 0

  def update_consist_member_address(self, vehicle_id: str, address: int) -> None:
    with self._connect() as con:
      con.execute(
        "UPDATE consist_members SET address = ? WHERE vehicle_id = ?",
        (int(address), vehicle_id),
      )

  def replace_imported_z21_data(
    self,
    summary: dict,
    vehicles: list[dict],
    categories: list[dict],
    functions: list[dict],
    consists: list[dict],
  ) -> dict:
    imported_at = self._now()
    track_mode = self._validate_track_mode(summary.get("track_mode", ""))
    with self._connect() as con:
      if track_mode:
        con.execute("DELETE FROM consists WHERE source = 'z21' AND (track_mode = ? OR track_mode = '')", (track_mode,))
        con.execute("DELETE FROM vehicles WHERE source = 'z21' AND (track_mode = ? OR track_mode = '')", (track_mode,))
      else:
        con.execute("DELETE FROM consists WHERE source = 'z21'")
        con.execute("DELETE FROM vehicles WHERE source = 'z21'")
        con.execute("DELETE FROM categories WHERE source = 'z21'")
      category_id_map = self._upsert_import_categories(con, categories, imported_at)
      for vehicle in vehicles:
        mapped_vehicle = {
          **vehicle,
          "category_ids": [category_id_map.get(category_id, category_id) for category_id in vehicle.get("category_ids", [])],
        }
        self._insert_vehicle(con, mapped_vehicle, imported_at)
        self._replace_vehicle_categories(con, mapped_vehicle["id"], mapped_vehicle.get("category_ids", []))
      functions_by_vehicle = {}
      for function in functions:
        functions_by_vehicle.setdefault(function["vehicle_id"], []).append(function)
      for vehicle_id, vehicle_functions in functions_by_vehicle.items():
        self._replace_vehicle_functions(con, vehicle_id, vehicle_functions)
      for consist in consists:
        self._insert_consist(con, consist, imported_at)
      self._delete_unreferenced_z21_categories(con)
      import_id = f"z21-import-{uuid.uuid4().hex}"
      con.execute(
        "INSERT INTO vehicle_imports (id, file_name, summary_json, imported_at) VALUES (?, ?, ?, ?)",
        (
          import_id,
          summary.get("file_name", "import.z21"),
          json.dumps(summary, ensure_ascii=False, sort_keys=True),
          imported_at,
        ),
      )
    return summary

  def _insert_vehicle(self, con, data: dict, now: str) -> None:
    values = self._vehicle_values(data, now, now)
    con.execute(
      """
      INSERT INTO vehicles (
        id, source, source_vehicle_id, track_mode, z21_position, custom_sort_order, name, address, image_name, image_path,
        type, sync_function_control, energy_type, car_subtype, consist_kind, max_speed, brand, full_name, railway, article_number, decoder_type, buffer_length,
        model_buffer_length, service_weight, model_weight, rmin, description,
        created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (data["id"], *values),
    )

  def _insert_category(self, con, data: dict, now: str) -> None:
    con.execute(
      """
      INSERT INTO categories (
        id, source, source_category_id, track_mode, name, description, sort_order, created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        data["id"],
        data.get("source") or "z21",
        self._text_or_none(data.get("source_category_id")),
        self._validate_track_mode(data.get("track_mode", "")),
        self._required_text(data.get("name"), "category name"),
        data.get("description", ""),
        int(data.get("sort_order", 0) or 0),
        now,
        now,
      ),
    )

  def _upsert_import_categories(self, con, categories: list[dict], now: str) -> dict:
    category_id_map = {}
    for category in categories:
      if (category.get("source") or "z21") == "z21":
        canonical_id = self._shared_z21_category_id(category.get("name"))
        category_id_map[category["id"]] = canonical_id
        self._upsert_shared_z21_category(con, category, canonical_id, now)
      else:
        self._insert_category(con, category, now)
        category_id_map[category["id"]] = category["id"]
    return category_id_map

  def _upsert_shared_z21_category(self, con, data: dict, category_id: str, now: str) -> None:
    name = self._required_text(data.get("name"), "category name")
    con.execute(
      """
      INSERT INTO categories (
        id, source, source_category_id, track_mode, name, description, sort_order, created_at, updated_at
      )
      VALUES (?, 'z21', ?, '', ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        name = excluded.name,
        description = excluded.description,
        sort_order = excluded.sort_order,
        track_mode = '',
        updated_at = excluded.updated_at
      """,
      (
        category_id,
        self._text_or_none(data.get("source_category_id")),
        name,
        data.get("description", ""),
        int(data.get("sort_order", 0) or 0),
        now,
        now,
      ),
    )

  def _merge_shared_z21_categories(self, con) -> None:
    rows = con.execute("SELECT * FROM categories WHERE source = 'z21' ORDER BY name, id").fetchall()
    for row in rows:
      name = self._required_text(row["name"], "category name")
      canonical_id = self._shared_z21_category_id(name)
      self._upsert_shared_z21_category(con, dict(row), canonical_id, row["updated_at"] or self._now())
      if row["id"] == canonical_id:
        continue
      con.execute(
        """
        INSERT OR IGNORE INTO vehicle_categories (vehicle_id, category_id)
        SELECT vehicle_id, ? FROM vehicle_categories WHERE category_id = ?
        """,
        (canonical_id, row["id"]),
      )
      con.execute("DELETE FROM vehicle_categories WHERE category_id = ?", (row["id"],))
      con.execute("DELETE FROM categories WHERE id = ?", (row["id"],))
    self._delete_unreferenced_z21_categories(con)

  def _delete_unreferenced_z21_categories(self, con) -> None:
    con.execute(
      """
      DELETE FROM categories
      WHERE source = 'z21'
        AND id NOT IN (SELECT DISTINCT category_id FROM vehicle_categories)
      """
    )

  def _insert_consist(self, con, data: dict, now: str) -> None:
    members = self._validate_consist_members(data.get("members", []))
    con.execute(
      """
      INSERT INTO consists (id, source, source_train_id, control_vehicle_id, track_mode, consist_kind, name, note, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        data["id"],
        data.get("source") or "z21",
        self._text_or_none(data.get("source_train_id")),
        self._validate_consist_control_vehicle(con, data.get("control_vehicle_id")),
        self._validate_track_mode(data.get("track_mode", "")),
        self._validate_consist_kind(data.get("consist_kind", "")),
        self._required_text(data.get("name"), "consist name"),
        data.get("note", ""),
        now,
        now,
      ),
    )
    self._replace_consist_members(con, data["id"], members)

  def _replace_consist_members(self, con, consist_id: str, members: list[dict]) -> None:
    members = self._validate_consist_members(members)
    con.execute("DELETE FROM consist_members WHERE consist_id = ?", (consist_id,))
    for index, member in enumerate(members):
      vehicle_id = self._required_text(member.get("vehicle_id"), "consist member vehicle_id")
      vehicle_row = con.execute("SELECT address FROM vehicles WHERE id = ?", (vehicle_id,)).fetchone()
      if vehicle_row is None:
        raise ValueError(f"consist member vehicle not found: {vehicle_id}")
      con.execute(
        """
        INSERT INTO consist_members (consist_id, vehicle_id, address, direction, member_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
          consist_id,
          vehicle_id,
          int(member.get("address", vehicle_row["address"])),
          self._validate_consist_direction(member.get("direction", "forward")),
          int(member.get("order", index + 1)),
        ),
      )

  def _replace_vehicle_categories(self, con, vehicle_id: str, category_ids: list) -> None:
    con.execute("DELETE FROM vehicle_categories WHERE vehicle_id = ?", (vehicle_id,))
    for category_id in category_ids or []:
      con.execute(
        "INSERT OR IGNORE INTO vehicle_categories (vehicle_id, category_id) VALUES (?, ?)",
        (vehicle_id, category_id),
      )

  def _replace_vehicle_functions(self, con, vehicle_id: str, functions: list[dict]) -> None:
    con.execute("DELETE FROM vehicle_functions WHERE vehicle_id = ?", (vehicle_id,))
    for index, function in enumerate(functions or []):
      con.execute(
        """
        INSERT INTO vehicle_functions (
          id, vehicle_id, source_function_id, function_number, label, icon_name,
          button_type, time, trigger_mode, duration_ms, position, show_function_number, is_configured
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        self._normalized_function_row(vehicle_id, function, index),
      )

  def _vehicle_from_row(self, con, row) -> dict:
    vehicle = dict(row)
    vehicle["type"] = int(vehicle.get("type") or 0)
    vehicle["sync_function_control"] = bool(vehicle.get("sync_function_control"))
    vehicle["energy_type"] = self._validate_energy_type(vehicle.get("energy_type", ""), vehicle["type"])
    vehicle["car_subtype"] = self._validate_car_subtype(vehicle.get("car_subtype", ""), vehicle["type"])
    vehicle["consist_kind"] = self._validate_vehicle_consist_kind(vehicle.get("consist_kind", ""), vehicle["type"])
    vehicle["categories"] = self._categories_for_vehicle(con, vehicle["id"])
    vehicle["category_ids"] = [category["id"] for category in vehicle["categories"]]
    return vehicle

  def _category_from_row(self, row) -> dict:
    category = dict(row)
    category["sort_order"] = int(category.get("sort_order") or 0)
    return category

  def _categories_for_vehicle(self, con, vehicle_id: str) -> list[dict]:
    rows = con.execute(
      """
      SELECT c.*
      FROM categories c
      JOIN vehicle_categories vc ON vc.category_id = c.id
      WHERE vc.vehicle_id = ?
      ORDER BY c.sort_order, c.name
      """,
      (vehicle_id,),
    ).fetchall()
    return [self._category_from_row(row) for row in rows]

  def _functions_for_vehicle(self, con, vehicle_id: str) -> list[dict]:
    rows = con.execute(
      """
      SELECT *
      FROM vehicle_functions
      WHERE vehicle_id = ?
      ORDER BY position, function_number
      """,
      (vehicle_id,),
    ).fetchall()
    return [self._function_from_row(row) for row in rows]

  def _function_from_row(self, row) -> dict:
    function = dict(row)
    function["show_function_number"] = bool(function.get("show_function_number"))
    function["is_configured"] = bool(function.get("is_configured"))
    function["trigger_mode"] = self._validate_trigger_mode(function.get("trigger_mode", "toggle"))
    function["duration_ms"] = max(0, int(function.get("duration_ms", 0) or 0))
    return function

  def _consist_from_row(self, con, row) -> dict:
    consist = dict(row)
    consist["consist_kind"] = self._validate_consist_kind(consist.get("consist_kind", ""))
    member_rows = con.execute(
      """
      SELECT *
      FROM consist_members
      WHERE consist_id = ?
      ORDER BY member_order
      """,
      (consist["id"],),
    ).fetchall()
    consist["members"] = [{
      "vehicle_id": member["vehicle_id"],
      "address": member["address"],
      "direction": member["direction"],
      "order": member["member_order"],
    } for member in member_rows]
    return consist

  def _vehicle_values(self, data: dict, created_at: str, updated_at: str) -> tuple:
    vehicle_type = self._validate_vehicle_type(data.get("type", 0))
    return (
      data.get("source") or "manual",
      self._text_or_none(data.get("source_vehicle_id")),
      self._validate_track_mode(data.get("track_mode", "")),
      self._int_or_none(data.get("z21_position", data.get("position"))),
      int(data.get("custom_sort_order", data.get("z21_position", data.get("position", 0))) or 0),
      self._required_text(data.get("name"), "vehicle name"),
      self._validate_address(data.get("address")),
      data.get("image_name", ""),
      data.get("image_path", data.get("image", "")),
      vehicle_type,
      1 if vehicle_type == 3 and data.get("sync_function_control") else 0,
      self._validate_energy_type(data.get("energy_type", ""), vehicle_type),
      self._validate_car_subtype(data.get("car_subtype", ""), vehicle_type),
      self._validate_vehicle_consist_kind(data.get("consist_kind", ""), vehicle_type),
      self._int_or_none(data.get("max_speed")),
      data.get("brand", ""),
      data.get("full_name", ""),
      data.get("railway", ""),
      data.get("article_number", ""),
      data.get("decoder_type", ""),
      data.get("buffer_length", ""),
      data.get("model_buffer_length", ""),
      data.get("service_weight", ""),
      data.get("model_weight", ""),
      data.get("rmin", ""),
      data.get("description", ""),
      created_at,
      updated_at,
    )

  def _vehicle_update_assignments(self) -> str:
    return ", ".join(f"{column} = ?" for column in VEHICLE_UPDATE_COLUMNS)

  def _normalized_function_row(self, vehicle_id: str, function: dict, index: int) -> tuple:
    function_number = int(function.get("function_number", function.get("function", index)))
    if function_number < 0 or function_number > 68:
      raise ValueError("function number must be in range F0..F68")
    function_id = function.get("id") or f"local-function-{vehicle_id}-{function_number}-{index}"
    trigger_mode = self._function_trigger_mode(function)
    label = function.get("label") if "label" in function else function.get("shortcut")
    if label is None:
      label = f"F{function_number}"
    return (
      function_id,
      vehicle_id,
      self._text_or_none(function.get("source_function_id")),
      function_number,
      str(label),
      function.get("icon_name") or function.get("image_name") or "",
      TRIGGER_MODE_TO_BUTTON_TYPE[trigger_mode],
      str(function.get("time", "")),
      trigger_mode,
      max(0, self._int_value(function.get("duration_ms", function.get("time", 0)), 0)),
      int(function.get("position", index) or 0),
      1 if function.get("show_function_number", True) else 0,
      1 if function.get("is_configured", True) else 0,
    )

  def _validate_address(self, address) -> int:
    value = int(address)
    if value < 1 or value > 9999:
      raise ValueError("DCC address must be in range 1..9999")
    return value

  def _validate_vehicle_type(self, vehicle_type) -> int:
    value = int(vehicle_type or 0)
    if value not in {0, 1, 2, 3, 4}:
      raise ValueError("vehicle type must be one of 0, 1, 2, 3, 4")
    return value

  def _validate_choice(self, value, *, default: str, allowed: set[str], error_message: str) -> str:
    normalized = str(value or default).strip().lower()
    if normalized not in allowed:
      raise ValueError(error_message)
    return normalized

  def _validate_optional_choice(self, value, *, allowed: set[str], error_message: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized == "":
      return ""
    if normalized not in allowed:
      raise ValueError(error_message)
    return normalized

  def _validate_energy_type(self, energy_type, vehicle_type: int) -> str:
    if vehicle_type != 0:
      return ""
    return self._validate_choice(
      energy_type,
      default="electric",
      allowed={"diesel", "electric", "steam", "hybrid"},
      error_message="energy type must be diesel, electric, steam or hybrid",
    )

  def _validate_car_subtype(self, car_subtype, vehicle_type: int) -> str:
    if vehicle_type != 1:
      return ""
    return self._validate_choice(
      car_subtype,
      default="passenger",
      allowed={"passenger", "engineering", "inspection", "crane"},
      error_message="car subtype must be passenger, engineering, inspection or crane",
    )

  def _validate_vehicle_consist_kind(self, consist_kind, vehicle_type: int) -> str:
    if vehicle_type != 3:
      return ""
    return self._validate_consist_kind(consist_kind or "multiple_unit")

  def _validate_consist_kind(self, consist_kind) -> str:
    return self._validate_optional_choice(
      consist_kind,
      allowed={"multiple_unit", "powered_set", "train_set", "consist"},
      error_message="consist kind must be multiple_unit, powered_set, train_set or consist",
    )

  def _validate_track_mode(self, track_mode) -> str:
    return self._validate_optional_choice(
      track_mode,
      allowed={"n", "ho", "g"},
      error_message="vehicle track mode must be N, HO, G or empty",
    )

  def _validate_trigger_mode(self, value) -> str:
    return self._validate_choice(
      value,
      default="toggle",
      allowed={"toggle", "momentary", "timed"},
      error_message=f"invalid function trigger mode: {value}",
    )

  def _function_trigger_mode(self, function: dict) -> str:
    if function.get("trigger_mode"):
      return self._validate_trigger_mode(function.get("trigger_mode"))
    try:
      button_type = int(function.get("button_type", 0) or 0)
    except (TypeError, ValueError):
      button_type = 0
    return BUTTON_TYPE_TO_TRIGGER_MODE.get(button_type, "toggle")

  def _validate_consist_direction(self, value) -> str:
    return self._validate_choice(
      value,
      default="forward",
      allowed={"forward", "reverse"},
      error_message=f"invalid consist direction: {value}",
    )

  def _validate_consist_control_vehicle(self, con, vehicle_id):
    if vehicle_id is None or vehicle_id == "":
      return None
    text = self._required_text(vehicle_id, "control vehicle_id")
    if con.execute("SELECT 1 FROM vehicles WHERE id = ?", (text,)).fetchone() is None:
      raise ValueError(f"consist control vehicle not found: {text}")
    return text

  def _validate_consist_members(self, members) -> list[dict]:
    if not isinstance(members, list) or not members:
      raise ValueError("consist members cannot be empty")
    if len(members) > models.CONSIST_MAX_MEMBERS:
      raise ValueError(f"编组最多 {models.CONSIST_MAX_MEMBERS} 辆")
    return members

  def _shared_z21_category_id(self, name) -> str:
    normalized_name = self._normalize_category_name(self._required_text(name, "category name"))
    digest = hashlib.sha1(normalized_name.encode("utf-8")).hexdigest()[:12]
    return f"z21-category-shared-{digest}"

  def _normalize_category_name(self, name: str) -> str:
    return " ".join(str(name or "").strip().split()).casefold()

  def _required_text(self, value, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
      raise ValueError(f"{field_name} is required")
    return text

  def _text_or_none(self, value):
    if value is None:
      return None
    return str(value)

  def _int_or_none(self, value):
    if value is None or value == "":
      return None
    return int(value)

  def _int_value(self, value, default: int = 0) -> int:
    if value is None or value == "":
      return default
    try:
      return int(value)
    except (TypeError, ValueError):
      return int(float(value))

  def _now(self) -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

  def _ensure_column(self, con, table_name: str, column_name: str, definition: str) -> None:
    columns = [row["name"] for row in con.execute(f"PRAGMA table_info({table_name})").fetchall()]
    if column_name not in columns:
      con.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

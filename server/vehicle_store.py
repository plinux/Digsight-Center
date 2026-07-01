"""SQLite backed vehicle library."""

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import uuid

from server import models
from server.controller_config_defaults import controller_default_config_rows
from server.controllers.registry import default_controller_registry
from server.importers.category_merge import shared_category_id, should_share_by_name
from server.public_paths import (
  ALLOWED_VEHICLE_IMAGE_PATH_PREFIXES,
  VEHICLE_TYPE_ICON_PUBLIC_PREFIX,
)


VEHICLE_FIELDS = (
  "source",
  "source_format",
  "source_key",
  "source_vehicle_id",
  "track_mode",
  "source_position",
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
VEHICLE_LIST_ORDER_BY = "custom_sort_order, source_position IS NULL, source_position, name, address"

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
  f"{VEHICLE_TYPE_ICON_PUBLIC_PREFIX}consist-group.svg",
}
SEED_ELECTRIC_ICON_PATH = f"{VEHICLE_TYPE_ICON_PUBLIC_PREFIX}energy-electric.svg"
SEED_CONSIST_ICON_PATH = f"{VEHICLE_TYPE_ICON_PUBLIC_PREFIX}consist-multiple-unit.svg"

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
      "image_path": SEED_ELECTRIC_ICON_PATH,
      "type": 0,
    },
    {
      "id": f"seed-test-vehicle-{mode}-4",
      "source": "seed",
      "track_mode": mode,
      "custom_sort_order": sort_offset + 2,
      "name": f"{label} 测试车 4",
      "address": 4,
      "image_path": SEED_ELECTRIC_ICON_PATH,
      "type": 0,
    },
    {
      "id": f"seed-test-vehicle-{mode}-3-4-consist",
      "source": "seed",
      "track_mode": mode,
      "custom_sort_order": sort_offset + 3,
      "name": f"{label} 3+4 重联",
      "address": 3,
      "image_path": SEED_CONSIST_ICON_PATH,
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
  def __init__(self, path: Path, *, controller_registry=None):
    self.path = Path(path)
    self.controller_registry = controller_registry or default_controller_registry()
    self.path.parent.mkdir(parents=True, exist_ok=True)
    self._initialize()

  def _initialize(self) -> None:
    with self._connect() as con:
      schema = Path(__file__).with_name("vehicle_schema.sql").read_text(encoding="utf-8")
      con.executescript(schema)
      self._upsert_controller_default_configs(con)

  def _upsert_controller_default_configs(self, con) -> None:
    now = self._now()
    for row in controller_default_config_rows(self.controller_registry):
      con.execute(
        """
        INSERT INTO controller_default_configs (
          kind,
          config_file_name,
          config_json,
          sort_order,
          created_at,
          updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(kind) DO UPDATE SET
          config_file_name = excluded.config_file_name,
          config_json = excluded.config_json,
          sort_order = excluded.sort_order,
          updated_at = excluded.updated_at
        """,
        (
          row["kind"],
          row["config_file_name"],
          json.dumps(row["config"], ensure_ascii=False, sort_keys=True),
          row["sort_order"],
          now,
          now,
        ),
      )

  def list_controller_default_configs(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute(
        """
        SELECT *
        FROM controller_default_configs
        ORDER BY sort_order, kind
        """
      ).fetchall()
      return [self._controller_default_config_from_row(row) for row in rows]

  def controller_default_config_for_kind(self, controller_kind: str) -> dict | None:
    with self._connect() as con:
      row = con.execute(
        """
        SELECT *
        FROM controller_default_configs
        WHERE kind = ?
        """,
        (controller_kind,),
      ).fetchone()
      if row is None:
        return None
      return self._controller_default_config_from_row(row)["config"]

  @staticmethod
  def _controller_default_config_from_row(row) -> dict:
    return {
      "kind": row["kind"],
      "config_file_name": row["config_file_name"],
      "config": json.loads(row["config_json"]),
      "sort_order": row["sort_order"],
      "created_at": row["created_at"],
      "updated_at": row["updated_at"],
    }

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

  @staticmethod
  def _table_count(con, table: str) -> int:
    return int(con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

  def list_vehicles(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute(f"SELECT * FROM vehicles ORDER BY {VEHICLE_LIST_ORDER_BY}").fetchall()
      return [self._vehicle_from_row(con, row) for row in rows]

  def list_vehicles_with_details(self) -> list[dict]:
    with self._connect() as con:
      rows = con.execute(f"SELECT * FROM vehicles ORDER BY {VEHICLE_LIST_ORDER_BY}").fetchall()
      vehicles = [self._vehicle_from_row_without_categories(row) for row in rows]
      vehicle_ids = [vehicle["id"] for vehicle in vehicles]
      categories_by_vehicle = self._categories_for_vehicles(con, vehicle_ids)
      functions_by_vehicle = self._functions_for_vehicles(con, vehicle_ids)
      for vehicle in vehicles:
        categories = categories_by_vehicle.get(vehicle["id"], [])
        vehicle["categories"] = categories
        vehicle["category_ids"] = [category["id"] for category in categories]
        vehicle["functions"] = functions_by_vehicle.get(vehicle["id"], [])
      return vehicles

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
      consist_ids = [row["id"] for row in rows]
      members_by_consist = self._members_for_consists(con, consist_ids)
      return [self._consist_from_row(row, members_by_consist.get(row["id"], [])) for row in rows]

  def get_consist(self, consist_id: str) -> dict | None:
    with self._connect() as con:
      row = con.execute("SELECT * FROM consists WHERE id = ?", (consist_id,)).fetchone()
      if row is None:
        return None
      return self._consist_from_row(row, self._members_for_consist(con, consist_id))

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

  def clear_vehicle_library(self) -> dict:
    with self._connect() as con:
      image_paths = [
        row["image_path"]
        for row in con.execute(
          "SELECT DISTINCT image_path FROM vehicles WHERE image_path IS NOT NULL AND image_path != ''"
        ).fetchall()
      ]
      counts = {
        "vehicles_deleted": self._table_count(con, "vehicles"),
        "functions_deleted": self._table_count(con, "vehicle_functions"),
        "vehicle_categories_deleted": self._table_count(con, "vehicle_categories"),
        "categories_deleted": self._table_count(con, "categories"),
        "consists_deleted": self._table_count(con, "consists"),
        "consist_members_deleted": self._table_count(con, "consist_members"),
        "imports_deleted": self._table_count(con, "vehicle_imports"),
      }
      for table in (
        "vehicle_functions",
        "vehicle_categories",
        "consist_members",
        "consists",
        "vehicle_imports",
        "categories",
        "vehicles",
      ):
        con.execute(f"DELETE FROM {table}")
      return {**counts, "image_paths": image_paths}

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

  def replace_imported_config_data(self, import_result) -> dict:
    imported_at = self._now()
    with self._connect() as con:
      return self._persist_import_result(con, import_result, imported_at)

  def _persist_import_result(self, con, import_result, imported_at: str) -> dict:
    source_format = self._required_text(import_result.source.format, "import source format")
    source_key = self._required_text(import_result.source.key, "import source key")
    source_keys = self._import_replace_source_keys(import_result, source_key)
    track_modes = self._import_replace_track_modes(import_result)
    self._delete_replaced_import_data(con, source_format, source_keys, track_modes)
    category_id_map = self._upsert_import_categories(con, import_result, source_format, source_key, imported_at)
    self._insert_import_vehicles(con, import_result, source_format, source_key, category_id_map, imported_at)
    self._insert_import_functions(con, import_result)
    self._insert_import_consists(con, import_result, source_format, source_key, imported_at)
    self._delete_unreferenced_import_categories(con, source_format, source_keys)
    self._insert_import_record(con, import_result, source_format, source_key, imported_at)
    return import_result.summary

  def _import_replace_source_keys(self, import_result, default_source_key: str) -> list[str]:
    replace_scope = getattr(import_result, "replace_scope", None) or {}
    raw_source_keys = replace_scope.get("source_keys")
    if raw_source_keys is None:
      return [default_source_key]
    if isinstance(raw_source_keys, str):
      raw_source_keys = [raw_source_keys]
    return [self._required_text(source_key, "replace source key") for source_key in raw_source_keys]

  def _import_replace_track_modes(self, import_result) -> list[str]:
    replace_scope = getattr(import_result, "replace_scope", None) or {}
    raw_track_modes = replace_scope.get("track_modes")
    if raw_track_modes is None:
      return []
    if isinstance(raw_track_modes, str):
      raw_track_modes = [raw_track_modes]
    return [self._validate_track_mode(track_mode) for track_mode in raw_track_modes if str(track_mode or "").strip()]

  @staticmethod
  def _sql_in_filter(column: str, values: list[str]) -> tuple[str, list[str]]:
    if not values:
      return "", []
    placeholders = ", ".join("?" for _value in values)
    return f" AND {column} IN ({placeholders})", list(values)

  def _delete_replaced_import_data(self, con, source_format: str, source_keys: list[str], track_modes: list[str]) -> None:
    source_key_filter, source_key_params = self._sql_in_filter("source_key", source_keys)
    base_where = f"source_format = ?{source_key_filter}"
    base_params = [source_format, *source_key_params]
    if track_modes:
      mode_placeholders = ", ".join("?" for _mode in track_modes)
      mode_filter = f" AND (track_mode IN ({mode_placeholders}) OR track_mode = '')"
      params = [*base_params, *track_modes]
      con.execute(
        f"DELETE FROM consists WHERE {base_where}{mode_filter}",
        params,
      )
      con.execute(
        f"DELETE FROM vehicles WHERE {base_where}{mode_filter}",
        params,
      )
      return
    con.execute(f"DELETE FROM consists WHERE {base_where}", base_params)
    con.execute(f"DELETE FROM vehicles WHERE {base_where}", base_params)
    con.execute(f"DELETE FROM categories WHERE {base_where}", base_params)

  def _upsert_import_categories(self, con, import_result, source_format: str, source_key: str, imported_at: str) -> dict:
    category_id_map = {}
    for category in import_result.categories:
      mapped_category = self._with_import_source(category, source_format, source_key)
      if should_share_by_name(import_result.source):
        canonical_id = shared_category_id(source_key, mapped_category.get("name"))
        category_id_map[category["id"]] = canonical_id
        mapped_category = {**mapped_category, "id": canonical_id, "track_mode": ""}
      else:
        category_id_map[category["id"]] = category["id"]
      self._upsert_import_category(con, mapped_category, imported_at)
    return category_id_map

  def _insert_import_vehicles(self, con, import_result, source_format: str, source_key: str, category_id_map: dict, imported_at: str) -> None:
    for vehicle in import_result.vehicles:
      mapped_vehicle = {
        **self._with_import_source(vehicle, source_format, source_key),
        "category_ids": [category_id_map.get(category_id, category_id) for category_id in vehicle.get("category_ids", [])],
      }
      self._insert_vehicle(con, mapped_vehicle, imported_at)
      self._replace_vehicle_categories(con, mapped_vehicle["id"], mapped_vehicle.get("category_ids", []))

  def _insert_import_functions(self, con, import_result) -> None:
    functions_by_vehicle = {}
    for function in import_result.functions:
      functions_by_vehicle.setdefault(function["vehicle_id"], []).append(function)
    for vehicle_id, vehicle_functions in functions_by_vehicle.items():
      self._replace_vehicle_functions(con, vehicle_id, vehicle_functions)

  def _insert_import_consists(self, con, import_result, source_format: str, source_key: str, imported_at: str) -> None:
    for consist in import_result.consists:
      self._insert_consist(con, self._with_import_source(consist, source_format, source_key), imported_at)

  def _insert_import_record(self, con, import_result, source_format: str, source_key: str, imported_at: str) -> None:
    import_id = f"{source_key}-import-{uuid.uuid4().hex}"
    con.execute(
      """
      INSERT INTO vehicle_imports (id, source_format, source_key, file_name, summary_json, imported_at)
      VALUES (?, ?, ?, ?, ?, ?)
      """,
      (
        import_id,
        source_format,
        source_key,
        import_result.summary.get("file_name", "import.config"),
        json.dumps(import_result.summary, ensure_ascii=False, sort_keys=True),
        imported_at,
      ),
    )

  def _with_import_source(self, row: dict, source_format: str, source_key: str) -> dict:
    return {
      **row,
      "source": row.get("source") or source_key,
      "source_format": source_format,
      "source_key": source_key,
    }

  def _insert_vehicle(self, con, data: dict, now: str) -> None:
    values = self._vehicle_values(data, now, now)
    con.execute(
      """
      INSERT INTO vehicles (
        id, source, source_format, source_key, source_vehicle_id, track_mode, source_position, custom_sort_order, name, address, image_name, image_path,
        type, sync_function_control, energy_type, car_subtype, consist_kind, max_speed, brand, full_name, railway, article_number, decoder_type, buffer_length,
        model_buffer_length, service_weight, model_weight, rmin, description,
        created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (data["id"], *values),
    )

  def _insert_category(self, con, data: dict, now: str) -> None:
    con.execute(
      """
      INSERT INTO categories (
        id, source, source_format, source_key, source_category_id, track_mode, name, description, sort_order, created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      self._category_values(data, now),
    )

  def _upsert_import_category(self, con, data: dict, now: str) -> None:
    con.execute(
      """
      INSERT INTO categories (
        id, source, source_format, source_key, source_category_id, track_mode, name, description, sort_order, created_at, updated_at
      )
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      ON CONFLICT(id) DO UPDATE SET
        source = excluded.source,
        name = excluded.name,
        description = excluded.description,
        sort_order = excluded.sort_order,
        source_category_id = excluded.source_category_id,
        source_format = excluded.source_format,
        source_key = excluded.source_key,
        track_mode = excluded.track_mode,
        updated_at = excluded.updated_at
      """,
      self._category_values(data, now),
    )

  def _delete_unreferenced_import_categories(self, con, source_format: str, source_keys: list[str]) -> None:
    source_key_filter, source_key_params = self._sql_in_filter("source_key", source_keys)
    con.execute(
      f"""
      DELETE FROM categories
      WHERE source_format = ?{source_key_filter}
        AND id NOT IN (SELECT DISTINCT category_id FROM vehicle_categories)
      """,
      (source_format, *source_key_params),
    )

  def _insert_consist(self, con, data: dict, now: str) -> None:
    members = self._validate_consist_members(data.get("members", []))
    con.execute(
      """
      INSERT INTO consists (id, source, source_format, source_key, source_train_id, control_vehicle_id, track_mode, consist_kind, name, note, created_at, updated_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      """,
      (
        data["id"],
        data.get("source") or data.get("source_key") or "",
        data.get("source_format") or "",
        data.get("source_key") or "",
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
    vehicle = self._vehicle_from_row_without_categories(row)
    vehicle["categories"] = self._categories_for_vehicle(con, vehicle["id"])
    vehicle["category_ids"] = [category["id"] for category in vehicle["categories"]]
    return vehicle

  def _vehicle_from_row_without_categories(self, row) -> dict:
    vehicle = dict(row)
    vehicle["type"] = int(vehicle.get("type") or 0)
    vehicle["sync_function_control"] = bool(vehicle.get("sync_function_control"))
    vehicle["energy_type"] = self._validate_energy_type(vehicle.get("energy_type", ""), vehicle["type"])
    vehicle["car_subtype"] = self._validate_car_subtype(vehicle.get("car_subtype", ""), vehicle["type"])
    vehicle["consist_kind"] = self._validate_vehicle_consist_kind(vehicle.get("consist_kind", ""), vehicle["type"])
    return vehicle

  def _category_from_row(self, row) -> dict:
    category = dict(row)
    category["sort_order"] = int(category.get("sort_order") or 0)
    return category

  def _categories_for_vehicle(self, con, vehicle_id: str) -> list[dict]:
    return self._categories_for_vehicles(con, [vehicle_id]).get(vehicle_id, [])

  def _categories_for_vehicles(self, con, vehicle_ids: list[str]) -> dict[str, list[dict]]:
    if not vehicle_ids:
      return {}
    placeholders = ",".join("?" for _vehicle_id in vehicle_ids)
    rows = con.execute(
      f"""
      SELECT vc.vehicle_id AS linked_vehicle_id, c.*
      FROM categories c
      JOIN vehicle_categories vc ON vc.category_id = c.id
      WHERE vc.vehicle_id IN ({placeholders})
      ORDER BY vc.vehicle_id, c.sort_order, c.name
      """,
      tuple(vehicle_ids),
    ).fetchall()
    categories_by_vehicle = {vehicle_id: [] for vehicle_id in vehicle_ids}
    for row in rows:
      category = self._category_from_row(row)
      vehicle_id = category.pop("linked_vehicle_id")
      categories_by_vehicle.setdefault(vehicle_id, []).append(category)
    return categories_by_vehicle

  def _functions_for_vehicle(self, con, vehicle_id: str) -> list[dict]:
    return self._functions_for_vehicles(con, [vehicle_id]).get(vehicle_id, [])

  def _functions_for_vehicles(self, con, vehicle_ids: list[str]) -> dict[str, list[dict]]:
    if not vehicle_ids:
      return {}
    placeholders = ",".join("?" for _vehicle_id in vehicle_ids)
    rows = con.execute(
      f"""
      SELECT *
      FROM vehicle_functions
      WHERE vehicle_id IN ({placeholders})
      ORDER BY vehicle_id, position, function_number
      """,
      tuple(vehicle_ids),
    ).fetchall()
    functions_by_vehicle = {vehicle_id: [] for vehicle_id in vehicle_ids}
    for row in rows:
      function = self._function_from_row(row)
      functions_by_vehicle.setdefault(function["vehicle_id"], []).append(function)
    return functions_by_vehicle

  def _function_from_row(self, row) -> dict:
    function = dict(row)
    function["show_function_number"] = bool(function.get("show_function_number"))
    function["is_configured"] = bool(function.get("is_configured"))
    function["trigger_mode"] = self._validate_trigger_mode(function.get("trigger_mode", "toggle"))
    function["duration_ms"] = max(0, int(function.get("duration_ms", 0) or 0))
    return function

  def _members_for_consist(self, con, consist_id: str) -> list[dict]:
    return self._members_for_consists(con, [consist_id]).get(consist_id, [])

  def _members_for_consists(self, con, consist_ids: list[str]) -> dict[str, list[dict]]:
    if not consist_ids:
      return {}
    placeholders = ",".join("?" for _consist_id in consist_ids)
    rows = con.execute(
      f"""
      SELECT *
      FROM consist_members
      WHERE consist_id IN ({placeholders})
      ORDER BY consist_id, member_order
      """,
      tuple(consist_ids),
    ).fetchall()
    members_by_consist = {consist_id: [] for consist_id in consist_ids}
    for row in rows:
      members_by_consist.setdefault(row["consist_id"], []).append(self._consist_member_from_row(row))
    return members_by_consist

  def _consist_from_row(self, row, members: list[dict]) -> dict:
    consist = dict(row)
    consist["consist_kind"] = self._validate_consist_kind(consist.get("consist_kind", ""))
    consist["members"] = members
    return consist

  def _consist_member_from_row(self, member) -> dict:
    return {
      "vehicle_id": member["vehicle_id"],
      "address": member["address"],
      "direction": member["direction"],
      "order": member["member_order"],
    }

  def _vehicle_values(self, data: dict, created_at: str, updated_at: str) -> tuple:
    vehicle_type = self._validate_vehicle_type(data.get("type", 0))
    return (
      data.get("source") or "manual",
      data.get("source_format") or "",
      data.get("source_key") or "",
      self._text_or_none(data.get("source_vehicle_id")),
      self._validate_track_mode(data.get("track_mode", "")),
      self._int_or_none(data.get("source_position", data.get("position"))),
      int(data.get("custom_sort_order", data.get("source_position", data.get("position", 0))) or 0),
      self._required_text(data.get("name"), "vehicle name"),
      self._validate_address(data.get("address")),
      data.get("image_name", ""),
      self._validate_image_path(data.get("image_path", data.get("image", ""))),
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

  def _category_values(self, data: dict, now: str) -> tuple:
    return (
      data["id"],
      data.get("source") or data.get("source_key") or "",
      data.get("source_format") or "",
      data.get("source_key") or "",
      self._text_or_none(data.get("source_category_id")),
      self._validate_track_mode(data.get("track_mode", "")),
      self._required_text(data.get("name"), "category name"),
      data.get("description", ""),
      int(data.get("sort_order", 0) or 0),
      now,
      now,
    )

  def _validate_image_path(self, value) -> str:
    image_path = str(value or "").strip()
    if not image_path:
      return ""
    if image_path.startswith("//") or "://" in image_path or image_path.startswith("data:"):
      raise ValueError("vehicle image path must be a local public asset path")
    if "?" in image_path or "#" in image_path or "\\" in image_path:
      raise ValueError("vehicle image path must not contain query, fragment, or backslash")
    for prefix in ALLOWED_VEHICLE_IMAGE_PATH_PREFIXES:
      if image_path.startswith(prefix):
        file_name = image_path[len(prefix):]
        if file_name and "/" not in file_name and file_name not in {".", ".."} and ".." not in file_name:
          return image_path
    allowed = " or ".join(ALLOWED_VEHICLE_IMAGE_PATH_PREFIXES)
    raise ValueError(f"vehicle image path must be under {allowed}")

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

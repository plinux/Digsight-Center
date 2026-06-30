"""Z21 .z21 import support."""

from dataclasses import dataclass
import json
from pathlib import Path
import os
import re
import sqlite3
import tempfile
import zipfile


DEFAULT_FUNCTION_ICON = "function-generic"
Z21_BUTTON_TYPE_TO_TRIGGER_MODE = {
  0: "toggle",
  1: "momentary",
  2: "timed",
}
Z21_CATEGORY_ENERGY_TYPES = {
  "内燃机车": "diesel",
  "电力机车": "electric",
  "混动机车": "hybrid",
  "蒸汽机车": "steam",
}
Z21_CATEGORY_CONSIST_KINDS = {
  "重联机车": "multiple_unit",
  "重连机车": "multiple_unit",
}
MAX_Z21_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_Z21_SQLITE_BYTES = 32 * 1024 * 1024
MAX_Z21_IMAGE_BYTES = 8 * 1024 * 1024
MAX_Z21_TOTAL_IMAGE_BYTES = 128 * 1024 * 1024
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def map_z21_button_type_to_trigger_mode(button_type) -> str:
  try:
    numeric_type = int(button_type)
  except (TypeError, ValueError):
    numeric_type = 0
  return Z21_BUTTON_TYPE_TO_TRIGGER_MODE.get(numeric_type, "toggle")


@dataclass
class Z21ImportResult:
  vehicles: list
  functions: list
  categories: list
  consists: list
  summary: dict


class Z21Importer:
  def __init__(
    self,
    image_dir: Path,
    function_icon_catalog_path: Path | None = None,
    function_icon_mapping_path: Path | None = None,
  ):
    self.image_dir = Path(image_dir)
    self.function_icon_catalog = self._load_function_icon_catalog(function_icon_catalog_path)
    self.function_icon_mappings = self._load_function_icon_mapping(function_icon_mapping_path)

  def import_file(self, path: Path) -> Z21ImportResult:
    path = Path(path)
    if path.stat().st_size > MAX_Z21_ARCHIVE_BYTES:
      raise ValueError("Z21 文件超过导入大小限制")
    with zipfile.ZipFile(path) as archive:
      sqlite_names = [name for name in archive.namelist() if name.endswith("Loco.sqlite")]
      if len(sqlite_names) != 1:
        raise ValueError(f"Expected exactly one Loco.sqlite, got {len(sqlite_names)}")
      sqlite_info = archive.getinfo(sqlite_names[0])
      if sqlite_info.file_size > MAX_Z21_SQLITE_BYTES:
        raise ValueError("Loco.sqlite 超过导入大小限制")
      self._validate_image_member_budgets(archive)
      sqlite_bytes = archive.read(sqlite_names[0])
      png_names = {Path(name).name: name for name in archive.namelist() if name.lower().endswith(".png")}

      with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as temp_db:
        temp_db.write(sqlite_bytes)
        temp_db_path = Path(temp_db.name)

      try:
        return self._import_sqlite(path.name, temp_db_path, archive, png_names)
      finally:
        os.remove(temp_db_path)

  def _import_sqlite(self, file_name: str, sqlite_path: Path, archive: zipfile.ZipFile, png_names: dict) -> Z21ImportResult:
    con = sqlite3.connect(sqlite_path)
    con.row_factory = sqlite3.Row
    try:
      track_mode = self._infer_track_mode(file_name)
      import_scope = track_mode or self._import_scope(file_name)
      categories = self._read_categories(con)
      vehicle_categories = self._read_vehicle_categories(con)
      categories = self._scope_categories(categories, import_scope, track_mode)
      vehicle_categories = self._scope_vehicle_categories(vehicle_categories, import_scope)
      category_names_by_id = {category["id"]: category["name"] for category in categories}
      vehicles = self._read_vehicles(file_name, import_scope, track_mode, con, archive, png_names, vehicle_categories, category_names_by_id)
      functions = self._read_functions(con, import_scope)
      consists = self._read_consists(con, vehicles)
      self._apply_consist_kind_to_control_vehicles(vehicles, consists)
      summary = {
        "file_name": file_name,
        "track_mode": track_mode,
        "vehicles_imported": len(vehicles),
        "functions_imported": len(functions),
        "categories_imported": len(categories),
        "consists_imported": self._count_table(con, "train_list"),
        "images_imported": sum(1 for vehicle in vehicles if vehicle.get("image_path")),
        "layout_controls_seen": self._count_table(con, "control_station_controls"),
        "layout_routes_seen": self._count_table(con, "control_station_routes"),
        "warnings": [],
      }
      return Z21ImportResult(vehicles, functions, categories, consists, summary)
    finally:
      con.close()

  def _read_vehicles(self, file_name, import_scope, track_mode, con, archive, png_names, vehicle_categories, category_names_by_id):
    rows = con.execute("SELECT * FROM vehicles ORDER BY position, id").fetchall()
    vehicles = []
    for row in rows:
      row_keys = row.keys()
      vehicle_id = f"z21-{import_scope}-vehicle-{row['id']}"
      image_path = self._extract_vehicle_image(vehicle_id, row["image_name"], archive, png_names)
      vehicle_name = row["name"] or f"车辆 {row['address']}"
      category_ids = vehicle_categories.get(row["id"], [])
      category_names = [category_names_by_id.get(category_id, "") for category_id in category_ids]
      vehicles.append({
        "id": vehicle_id,
        "source": "z21",
        "source_vehicle_id": str(row["id"]),
        "track_mode": track_mode,
        "source_position": row["position"] if "position" in row_keys else None,
        "name": vehicle_name,
        "address": row["address"],
        "type": row["type"],
        "energy_type": self._infer_energy_type(row["type"], category_names),
        "car_subtype": self._default_car_subtype(row["type"]),
        "consist_kind": self._infer_consist_kind_from_categories(row["type"], category_names),
        "max_speed": row["max_speed"] if "max_speed" in row_keys else None,
        "brand": self._infer_brand(row["name"] if "name" in row_keys else ""),
        "image_name": row["image_name"],
        "image_path": image_path,
        "full_name": row["full_name"] if "full_name" in row_keys else "",
        "railway": row["railway"] if "railway" in row_keys else "",
        "article_number": row["article_number"] if "article_number" in row_keys else "",
        "decoder_type": row["decoder_type"] if "decoder_type" in row_keys else "",
        "buffer_length": row["buffer_length"] if "buffer_length" in row_keys else "",
        "model_buffer_length": row["model_buffer_length"] if "model_buffer_length" in row_keys else "",
        "service_weight": row["service_weight"] if "service_weight" in row_keys else "",
        "model_weight": row["model_weight"] if "model_weight" in row_keys else "",
        "rmin": row["rmin"] if "rmin" in row_keys else "",
        "description": row["description"] if "description" in row_keys else "",
        "category_ids": category_ids,
        "import_file": file_name,
      })
    return vehicles

  def _read_categories(self, con):
    if not self._table_exists(con, "categories"):
      return []
    rows = con.execute("SELECT * FROM categories ORDER BY id").fetchall()
    categories = []
    for row in rows:
      categories.append({
        "id": f"z21-category-{row['id']}",
        "source": "z21",
        "source_category_id": str(row["id"]),
        "name": row["name"] or f"Z21 分类 {row['id']}",
        "description": "",
        "sort_order": row["id"],
      })
    return categories

  def _read_vehicle_categories(self, con):
    if not self._table_exists(con, "vehicles_to_categories"):
      return {}
    rows = con.execute("SELECT * FROM vehicles_to_categories ORDER BY vehicle_id, category_id").fetchall()
    vehicle_categories = {}
    for row in rows:
      vehicle_categories.setdefault(row["vehicle_id"], []).append(f"z21-category-{row['category_id']}")
    return vehicle_categories

  def _read_functions(self, con, import_scope):
    rows = con.execute("SELECT * FROM functions ORDER BY vehicle_id, position").fetchall()
    functions = []
    for index, row in enumerate(rows):
      z21_icon_name = row["image_name"] or ""
      functions.append({
        "id": f"z21-{import_scope}-function-{row['vehicle_id']}-{row['function']}-{index}",
        "vehicle_id": f"z21-{import_scope}-vehicle-{row['vehicle_id']}",
        "source_function_id": str(row["id"]),
        "function_number": row["function"],
        "label": row["shortcut"] or f"F{row['function']}",
        "icon_name": self._resolve_function_icon_name(z21_icon_name, row["shortcut"]),
        "z21_icon_name": z21_icon_name,
        "button_type": row["button_type"],
        "trigger_mode": map_z21_button_type_to_trigger_mode(row["button_type"]),
        "time": row["time"],
        "position": row["position"],
        "show_function_number": bool(row["show_function_number"]),
        "is_configured": True,
      })
    return functions

  def _read_consists(self, con, vehicles):
    if not self._table_exists(con, "train_list"):
      return []
    vehicle_by_source_id = {str(vehicle["source_vehicle_id"]): vehicle for vehicle in vehicles}
    control_vehicle_by_train_id = {
      str(vehicle["source_vehicle_id"]): vehicle
      for vehicle in vehicles
      if int(vehicle.get("type", 0) or 0) == 3
    }
    rows = con.execute("SELECT * FROM train_list ORDER BY train_id, position").fetchall()
    grouped = {}
    for row in rows:
      train_id = str(row["train_id"])
      member = vehicle_by_source_id.get(str(row["vehicle_id"]))
      if member is None:
        continue
      control_vehicle = control_vehicle_by_train_id.get(train_id)
      if control_vehicle and member["id"] == control_vehicle["id"]:
        continue
      members = grouped.setdefault(train_id, [])
      members.append({
        "vehicle_id": member["id"],
        "address": member["address"],
        "direction": "forward",
        "order": len(members) + 1,
      })
    consists = []
    default_track_mode = vehicles[0]["track_mode"] if vehicles else ""
    for train_id, members in grouped.items():
      if not members:
        continue
      control_vehicle = control_vehicle_by_train_id.get(train_id)
      track_mode = control_vehicle["track_mode"] if control_vehicle else default_track_mode
      consists.append({
        "id": f"z21-{track_mode or 'unknown'}-consist-{train_id}",
        "source": "z21",
        "source_train_id": train_id,
        "control_vehicle_id": control_vehicle["id"] if control_vehicle else None,
        "track_mode": track_mode,
        "consist_kind": (control_vehicle or {}).get("consist_kind") or self._infer_consist_kind(members, vehicle_by_source_id),
        "name": control_vehicle["name"] if control_vehicle else f"Z21 编组 {train_id}",
        "members": members,
        "note": "由 Z21 train_list 导入；type=3 车辆作为控制入口" if control_vehicle else "由 Z21 train_list 导入",
      })
    return consists

  def _default_energy_type(self, vehicle_type) -> str:
    return "electric" if self._vehicle_type_equals(vehicle_type, 0) else ""

  def _default_car_subtype(self, vehicle_type) -> str:
    return "passenger" if self._vehicle_type_equals(vehicle_type, 1) else ""

  def _infer_energy_type(self, vehicle_type, category_names: list[str]) -> str:
    if not self._vehicle_type_equals(vehicle_type, 0):
      return ""
    energy_type = self._mapped_category_value(category_names, Z21_CATEGORY_ENERGY_TYPES)
    if energy_type:
      return energy_type
    return self._default_energy_type(vehicle_type)

  def _infer_consist_kind_from_categories(self, vehicle_type, category_names: list[str]) -> str:
    if not self._vehicle_type_equals(vehicle_type, 3):
      return ""
    return self._mapped_category_value(category_names, Z21_CATEGORY_CONSIST_KINDS)

  def _vehicle_type_equals(self, vehicle_type, expected_type: int) -> bool:
    try:
      return int(vehicle_type or 0) == expected_type
    except (TypeError, ValueError):
      return False

  def _mapped_category_value(self, category_names: list[str], mapping: dict) -> str:
    for category_name in category_names:
      mapped_value = mapping.get(self._normalize_category_name(category_name))
      if mapped_value:
        return mapped_value
    return ""

  def _normalize_category_name(self, category_name) -> str:
    return re.sub(r"\s+", "", str(category_name or ""))

  def _infer_brand(self, name) -> str:
    words = str(name or "").strip().split()
    return words[0] if words else ""

  def _infer_consist_kind(self, members: list[dict], vehicle_by_source_id: dict) -> str:
    member_types = []
    for member in members:
      vehicle_id = member.get("vehicle_id", "")
      source_id = str(vehicle_id).rsplit("-", 1)[-1]
      vehicle = vehicle_by_source_id.get(source_id)
      if vehicle is None:
        continue
      try:
        member_types.append(int(vehicle.get("type", 0) or 0))
      except (TypeError, ValueError):
        member_types.append(-1)
    return "multiple_unit" if member_types and all(vehicle_type == 0 for vehicle_type in member_types) else "train_set"

  def _apply_consist_kind_to_control_vehicles(self, vehicles: list[dict], consists: list[dict]) -> None:
    by_id = {vehicle["id"]: vehicle for vehicle in vehicles}
    for consist in consists:
      control_vehicle = by_id.get(consist.get("control_vehicle_id"))
      if control_vehicle is not None:
        control_vehicle["consist_kind"] = consist.get("consist_kind") or "multiple_unit"

  def _extract_vehicle_image(self, vehicle_id, image_name, archive, png_names):
    if not image_name:
      return ""
    candidates = [image_name, f"{image_name}.png", Path(image_name).name, f"{Path(image_name).name}.png"]
    archive_name = next((png_names.get(candidate) for candidate in candidates if png_names.get(candidate)), None)
    if not archive_name:
      return ""
    if archive.getinfo(archive_name).file_size > MAX_Z21_IMAGE_BYTES:
      raise ValueError("车辆图片超过导入大小限制")
    self.image_dir.mkdir(parents=True, exist_ok=True)
    target = self.image_dir / f"{vehicle_id}.png"
    target.write_bytes(archive.read(archive_name))
    return f"/data/vehicle-images/{target.name}"

  def _validate_image_member_budgets(self, archive: zipfile.ZipFile) -> None:
    total_image_bytes = 0
    for member in archive.infolist():
      if not member.filename.lower().endswith(".png"):
        continue
      if member.file_size > MAX_Z21_IMAGE_BYTES:
        raise ValueError("车辆图片超过导入大小限制")
      total_image_bytes += member.file_size
      if total_image_bytes > MAX_Z21_TOTAL_IMAGE_BYTES:
        raise ValueError("车辆图片总量超过导入大小限制")

  def _count_table(self, con, table_name):
    try:
      return con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    except sqlite3.Error:
      return 0

  def _table_exists(self, con, table_name):
    return con.execute(
      "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
      (table_name,),
    ).fetchone() is not None

  def _infer_track_mode(self, file_name: str) -> str:
    tokens = [token for token in re.split(r"[^a-z0-9]+", Path(file_name).stem.lower()) if token]
    if "ho" in tokens:
      return "ho"
    if "n" in tokens:
      return "n"
    if "g" in tokens:
      return "g"
    return ""

  def _import_scope(self, file_name: str) -> str:
    scope = re.sub(r"[^a-z0-9]+", "-", Path(file_name).stem.lower()).strip("-")
    return scope or "unknown"

  def _scope_categories(self, categories: list[dict], import_scope: str, track_mode: str) -> list[dict]:
    scoped = []
    for category in categories:
      scoped.append({
        **category,
        "id": f"z21-{import_scope}-category-{category['source_category_id']}",
        "track_mode": track_mode,
      })
    return scoped

  def _scope_vehicle_categories(self, vehicle_categories: dict, import_scope: str) -> dict:
    return {
      vehicle_id: [f"z21-{import_scope}-category-{category_id.rsplit('-', 1)[-1]}" for category_id in category_ids]
      for vehicle_id, category_ids in vehicle_categories.items()
    }

  def _load_function_icon_catalog(self, function_icon_catalog_path: Path | None) -> dict:
    catalog_path = Path(function_icon_catalog_path) if function_icon_catalog_path else PROJECT_ROOT / "config" / "function-icons.json"
    try:
      catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
      return {"default_icon": DEFAULT_FUNCTION_ICON, "icons": {DEFAULT_FUNCTION_ICON: {}}}
    if not isinstance(catalog.get("icons"), dict):
      return {"default_icon": DEFAULT_FUNCTION_ICON, "icons": {DEFAULT_FUNCTION_ICON: {}}}
    return catalog

  def _load_function_icon_mapping(self, function_icon_mapping_path: Path | None = None) -> dict:
    mapping_path = Path(function_icon_mapping_path) if function_icon_mapping_path else PROJECT_ROOT / "config" / "function-icon-mappings" / "z21.json"
    try:
      mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
      return {}
    if mapping.get("source_system") != "z21" or not isinstance(mapping.get("mappings"), dict):
      return {}
    return mapping["mappings"]

  def _resolve_function_icon_name(self, image_name, shortcut) -> str:
    icons = self.function_icon_catalog.get("icons", {})
    default_icon = self.function_icon_catalog.get("default_icon") or DEFAULT_FUNCTION_ICON
    for candidate in (image_name, shortcut):
      text = str(candidate or "").strip()
      if not text:
        continue
      icon_key = self.function_icon_mappings.get(text)
      if icon_key in icons:
        return icon_key
      if text in icons:
        return text
    searchable = " ".join(str(candidate or "") for candidate in (image_name, shortcut)).lower()
    for icon_key, icon in icons.items():
      for keyword in icon.get("keywords", []):
        if str(keyword).lower() in searchable:
          return icon_key
    return default_icon if default_icon in icons else DEFAULT_FUNCTION_ICON

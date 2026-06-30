"""Helpers for building small Z21 layout export fixtures in tests."""

import sqlite3
import zipfile
from pathlib import Path


def write_minimal_z21_archive(
  root: Path,
  *,
  file_name: str = "HO.z21",
  sqlite_member: str = "export/test/Loco.sqlite",
  vehicles: list[dict] | None = None,
  functions: list[dict] | None = None,
  train_list: list[dict] | None = None,
  image_files: dict[str, bytes] | None = None,
) -> Path:
  root.mkdir(parents=True, exist_ok=True)
  sqlite_path = root / "Loco.sqlite"
  _write_minimal_loco_sqlite(
    sqlite_path,
    vehicles=vehicles or [_default_vehicle()],
    functions=functions or [],
    train_list=train_list or [],
  )
  archive_path = root / file_name
  with zipfile.ZipFile(archive_path, "w") as archive:
    archive.write(sqlite_path, sqlite_member)
    for image_name, image_bytes in (image_files or {}).items():
      archive.writestr(image_name, image_bytes)
  return archive_path


def write_custom_z21_archive(
  root: Path,
  configure_database,
  *,
  file_name: str = "HO.z21",
  sqlite_member: str = "export/test/Loco.sqlite",
  image_files: dict[str, bytes] | None = None,
) -> Path:
  root.mkdir(parents=True, exist_ok=True)
  sqlite_path = root / "Loco.sqlite"
  connection = sqlite3.connect(sqlite_path)
  try:
    configure_database(connection)
    connection.commit()
  finally:
    connection.close()
  archive_path = root / file_name
  with zipfile.ZipFile(archive_path, "w") as archive:
    archive.write(sqlite_path, sqlite_member)
    for image_name, image_bytes in (image_files or {}).items():
      archive.writestr(image_name, image_bytes)
  return archive_path


def _default_vehicle() -> dict:
  return {
    "id": 1,
    "position": 0,
    "name": "测试车",
    "address": 3,
    "type": 0,
    "image_name": "",
    "max_speed": 100,
  }


def _write_minimal_loco_sqlite(
  sqlite_path: Path,
  *,
  vehicles: list[dict],
  functions: list[dict],
  train_list: list[dict],
) -> None:
  connection = sqlite3.connect(sqlite_path)
  try:
    connection.execute(
      "CREATE TABLE vehicles (id INTEGER PRIMARY KEY, position INTEGER, name TEXT, address INTEGER, type INTEGER, image_name TEXT, max_speed INTEGER)"
    )
    connection.execute(
      "CREATE TABLE functions (id INTEGER PRIMARY KEY, vehicle_id INTEGER, function INTEGER, shortcut TEXT, image_name TEXT, button_type INTEGER, time TEXT, position INTEGER, show_function_number INTEGER, is_configured INTEGER)"
    )
    connection.execute("CREATE TABLE train_list (train_id TEXT, vehicle_id INTEGER, position INTEGER)")
    for vehicle in vehicles:
      connection.execute(
        """
        INSERT INTO vehicles
          (id, position, name, address, type, image_name, max_speed)
        VALUES
          (:id, :position, :name, :address, :type, :image_name, :max_speed)
        """,
        {
          "id": vehicle.get("id", 1),
          "position": vehicle.get("position", 0),
          "name": vehicle.get("name", "测试车"),
          "address": vehicle.get("address", 3),
          "type": vehicle.get("type", 0),
          "image_name": vehicle.get("image_name", ""),
          "max_speed": vehicle.get("max_speed", 100),
        },
      )
    for function in functions:
      connection.execute(
        """
        INSERT INTO functions
          (id, vehicle_id, function, shortcut, image_name, button_type, time, position, show_function_number, is_configured)
        VALUES
          (:id, :vehicle_id, :function, :shortcut, :image_name, :button_type, :time, :position, :show_function_number, :is_configured)
        """,
        {
          "id": function.get("id", 1),
          "vehicle_id": function.get("vehicle_id", 1),
          "function": function.get("function", 0),
          "shortcut": function.get("shortcut", ""),
          "image_name": function.get("image_name", ""),
          "button_type": function.get("button_type", 0),
          "time": function.get("time", ""),
          "position": function.get("position", 0),
          "show_function_number": function.get("show_function_number", 1),
          "is_configured": function.get("is_configured", 1),
        },
      )
    for train_member in train_list:
      connection.execute(
        "INSERT INTO train_list (train_id, vehicle_id, position) VALUES (:train_id, :vehicle_id, :position)",
        train_member,
      )
    connection.commit()
  finally:
    connection.close()

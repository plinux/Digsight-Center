"""Vehicle, category, and consist API orchestration."""

import sqlite3

from server import models, response
from server.api_support import http_helpers


class VehicleLibraryApiSupport:
  def __init__(self, context):
    self.context = context

  @property
  def vehicle_store(self):
    return self.context.vehicle_store

  def list_vehicles(self, state: dict):
    return http_helpers.success(self.vehicle_store.list_vehicles_with_details())

  def list_categories(self, state: dict):
    return http_helpers.success(self.vehicle_store.list_categories())

  def create_category(self, body: bytes):
    request = http_helpers.json_body(body)
    try:
      category = self.vehicle_store.create_category(request)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_category", "车辆分类无效", str(exc)), 400
    return http_helpers.success(category)

  def patch_category(self, route: str, body: bytes):
    category_id = http_helpers.resource_id(route)
    try:
      category = self.vehicle_store.update_category(category_id, http_helpers.json_body(body))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_category", "车辆分类无效", str(exc)), 400
    if category is None:
      return response.failure("category_not_found", "车辆分类不存在", category_id), 404
    return http_helpers.success(category)

  def delete_category(self, route: str):
    category_id = http_helpers.resource_id(route)
    if not self.vehicle_store.delete_category(category_id):
      return response.failure("category_not_found", "车辆分类不存在", category_id), 404
    return http_helpers.success({"id": category_id, "deleted": True})

  def create_vehicle(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    self.apply_default_track_mode(request, state)
    functions = request.pop("functions", [])
    try:
      vehicle = self.vehicle_store.create_vehicle_with_functions(request, functions)
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
      return response.failure("invalid_vehicle", "车辆数据无效", str(exc)), 400
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success(self.vehicle_with_store_functions(vehicle))

  def patch_vehicle(self, route: str, body: bytes, state: dict):
    vehicle_id = http_helpers.resource_id(route)
    return self._patch_store_vehicle(vehicle_id, body, state)

  def delete_vehicle(self, route: str, state: dict):
    vehicle_id = http_helpers.resource_id(route)
    if not self.vehicle_store.delete_vehicle(vehicle_id):
      return response.failure("vehicle_not_found", "车辆不存在", vehicle_id), 404
    self.remove_consist_members_for_vehicle(state, vehicle_id)
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success({"id": vehicle_id, "deleted": True})

  def reorder_vehicles(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    vehicle_ids = request.get("vehicle_ids") or []
    if not isinstance(vehicle_ids, list) or not all(isinstance(item, str) for item in vehicle_ids):
      return response.failure("invalid_vehicle_order", "车辆排序列表无效", "vehicle_ids"), 400
    vehicles = self.vehicle_store.update_vehicle_custom_order(vehicle_ids)
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success({"vehicles": [self.vehicle_with_store_functions(vehicle) for vehicle in vehicles]})

  def list_consists(self, state: dict):
    return http_helpers.success(self.vehicle_store.list_consists())

  def create_consist(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    members = request.get("members", [])
    member_error = self.validate_consist_members(members)
    if member_error:
      return member_error
    self.apply_default_track_mode(request, state)
    try:
      consist = self.vehicle_store.create_consist(request)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_consist", "编组数据无效", str(exc)), 400
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success(consist)

  def patch_consist(self, route: str, body: bytes, state: dict):
    consist_id = http_helpers.resource_id(route)
    return self._patch_store_consist(consist_id, body, state)

  def delete_consist(self, route: str, state: dict):
    consist_id = http_helpers.resource_id(route)
    if not self.vehicle_store.delete_consist(consist_id):
      return response.failure("consist_not_found", "编组不存在", consist_id), 404
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success({"id": consist_id, "deleted": True})

  def find_by_id(self, items, item_id):
    return next((item for item in items if item.get("id") == item_id), None)

  def validate_vehicle_address(self, address) -> int:
    value = int(address)
    if value < models.DCC_ADDRESS_MIN or value > models.DCC_ADDRESS_MAX:
      raise ValueError(f"DCC address must be in range {models.DCC_ADDRESS_MIN}..{models.DCC_ADDRESS_MAX}")
    return value

  def current_editable_track_mode(self, state: dict) -> str:
    track_mode = str(state.get("controller", {}).get("track_mode", "")).lower()
    if track_mode in {models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G}:
      return track_mode
    return ""

  def apply_default_track_mode(self, request: dict, state: dict) -> None:
    if request.get("track_mode"):
      return
    track_mode = self.current_editable_track_mode(state)
    if track_mode:
      request["track_mode"] = track_mode

  def validate_consist_members(self, members):
    if not isinstance(members, list) or not members:
      return response.failure("invalid_consist", "编组至少需要一辆车", ""), 400
    if len(members) > models.CONSIST_MAX_MEMBERS:
      return response.failure(
        "invalid_consist",
        f"编组最多 {models.CONSIST_MAX_MEMBERS} 辆",
        f"当前请求包含 {len(members)} 辆",
      ), 400
    return None

  def sync_consist_member_addresses(self, state: dict, vehicle_id: str, address: int) -> None:
    self.vehicle_store.update_consist_member_address(vehicle_id, address)
    for consist in state["consists"]:
      for member in consist.get("members", []):
        if member.get("vehicle_id") == vehicle_id:
          member["address"] = address

  def remove_consist_members_for_vehicle(self, state: dict, vehicle_id: str) -> None:
    for consist in state["consists"]:
      consist["members"] = [
        member for member in consist.get("members", [])
        if member.get("vehicle_id") != vehicle_id
      ]

  def sync_vehicle_address_if_present(self, state: dict, vehicle_id, address: int) -> bool:
    if not vehicle_id:
      return False
    vehicle = self.vehicle_store.get_vehicle(vehicle_id)
    if vehicle is None:
      return False
    self.vehicle_store.update_vehicle(vehicle_id, {"address": address})
    self.sync_consist_member_addresses(state, vehicle_id, address)
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return True

  def vehicle_with_store_functions(self, vehicle: dict) -> dict:
    payload = dict(vehicle)
    if "functions" not in payload:
      payload["functions"] = self.vehicle_store.list_functions(vehicle["id"])
    return payload

  def _patch_store_vehicle(self, vehicle_id: str, body: bytes, state: dict):
    vehicle = self.vehicle_store.get_vehicle(vehicle_id)
    if vehicle is None:
      return response.failure("vehicle_not_found", "车辆不存在", vehicle_id), 404
    request = http_helpers.json_body(body)
    functions = request.pop("functions", None)
    try:
      updated = self.vehicle_store.update_vehicle_with_functions(vehicle_id, request, functions)
      if "address" in request:
        self.sync_consist_member_addresses(state, vehicle_id, updated["address"])
    except (TypeError, ValueError, sqlite3.IntegrityError) as exc:
      return response.failure("invalid_vehicle", "车辆地址无效" if "address" in request else "车辆数据无效", str(exc)), 400
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success(self.vehicle_with_store_functions(updated))

  def _patch_store_consist(self, consist_id: str, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    if "members" in request:
      member_error = self.validate_consist_members(request["members"])
      if member_error:
        return member_error
    try:
      consist = self.vehicle_store.update_consist(consist_id, request)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_consist", "编组数据无效", str(exc)), 400
    if consist is None:
      return response.failure("consist_not_found", "编组不存在", consist_id), 404
    self.context.refresh_vehicle_store_data(state)
    self.context.save(state)
    return http_helpers.success(consist)

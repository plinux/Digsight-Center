"""Single-vehicle loco control API orchestration."""

from server import response
from server.api_support import http_helpers


def parse_function_states(value) -> dict:
  if value is None:
    return {}
  if not isinstance(value, dict):
    raise ValueError("function_states must be a JSON object")
  function_states = {}
  for function_number, enabled in value.items():
    function_states[str(function_number)] = http_helpers.require_json_bool(
      enabled,
      f"function_states.{function_number}",
    )
  return function_states


class LocoControlApiSupport:
  def __init__(self, context, controller_service, controller_api, vehicle_library):
    self.context = context
    self.controller_service = controller_service
    self.controller_api = controller_api
    self.vehicle_library = vehicle_library

  def handle(self, route: str, body: bytes, state: dict):
    unsupported = self.controller_api.controller_capability_failure(state["controller"], "loco_control", "loco_control")
    if unsupported:
      return unsupported
    blocked = self._loco_control_preflight(state, "数码车辆控制")
    if blocked:
      return blocked
    request = http_helpers.json_body(body)
    if self.context.vehicle_store:
      self.context.refresh_vehicle_store_data(state)
    vehicle = self.vehicle_library.find_by_id(state["vehicles"], request.get("vehicle_id"))
    if vehicle is None:
      return response.failure("vehicle_not_found", "车辆不存在", str(request.get("vehicle_id", ""))), 404

    if route == "/api/loco/speed":
      return self._handle_speed(request, state, vehicle)
    return self._handle_function(request, state, vehicle)

  def _handle_speed(self, request: dict, state: dict, vehicle: dict):
    try:
      speed = self.controller_service.validate_loco_speed_value(request.get("speed", 0))
      direction = str(request.get("direction", "forward")).lower()
      targets, control_mode = self._loco_speed_targets(state, vehicle)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_loco_control", "车辆控制参数无效", str(exc)), 400

    target_results, error_response = self.controller_service.execute_loco_targets(
      state,
      targets,
      loco_command_kind="speed",
      speed=speed,
      direction=direction,
    )
    if error_response:
      return http_helpers.service_result(error_response)
    return self._loco_control_success_response(
      vehicle.get("id"),
      target_results,
      control_mode,
      speed=speed,
      direction=direction,
    )

  def _handle_function(self, request: dict, state: dict, vehicle: dict):
    try:
      function_number = int(request.get("function_number"))
      if function_number < 0 or function_number > 68:
        raise ValueError("function number must be in F0..F68")
      enabled = http_helpers.require_json_bool(request.get("enabled"), "enabled")
      function_states = parse_function_states(request.get("function_states"))
      function_states[str(function_number)] = enabled
      targets, control_mode = self._loco_function_targets(state, vehicle)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_loco_control", "车辆控制参数无效", str(exc)), 400

    target_results, error_response = self.controller_service.execute_loco_targets(
      state,
      targets,
      loco_command_kind="function",
      function_states=function_states,
      function_number=function_number,
    )
    if error_response:
      return http_helpers.service_result(error_response)
    return self._loco_control_success_response(
      vehicle.get("id"),
      target_results,
      control_mode,
      function_number=function_number,
      enabled=enabled,
    )

  def handle_consist_operation(self, route: str, body: bytes, state: dict):
    unsupported = self.controller_api.controller_capability_failure(state["controller"], "loco_control", "consist_control")
    if unsupported:
      return unsupported
    blocked = self._loco_control_preflight(state, "数码编组控制")
    if blocked:
      return blocked
    if self.context.vehicle_store:
      self.context.refresh_vehicle_store_data(state)
    route_parts = route.split("/")
    consist_id = route_parts[3] if len(route_parts) > 3 else ""
    consist = self.vehicle_library.find_by_id(state.get("consists", []), consist_id)
    if consist is None:
      return response.failure("consist_not_found", "编组不存在", consist_id), 404
    targets = self._consist_member_targets(state, consist)
    if not targets:
      return response.failure("invalid_consist", "编组没有可控成员", "consist has no controllable members"), 400
    try:
      if route.endswith("/stop"):
        speed = 0
        direction = str((http_helpers.json_body(body) if body else {}).get("direction", "forward")).lower()
      else:
        request = http_helpers.json_body(body)
        speed = self.controller_service.validate_loco_speed_value(request.get("speed", 0))
        direction = str(request.get("direction", "forward")).lower()
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_loco_control", "编组控制参数无效", str(exc)), 400
    target_results, error_response = self.controller_service.execute_loco_targets(
      state,
      targets,
      loco_command_kind="speed",
      speed=speed,
      direction=direction,
    )
    if error_response:
      return http_helpers.service_result(error_response)
    return self._loco_control_success_response(
      consist_id,
      target_results,
      "consist",
      speed=speed,
      direction=direction,
    )

  def _loco_control_success_response(self, vehicle_id, target_results, control_mode, **fields):
    first_result = target_results[0]
    payload = {
      "vehicle_id": vehicle_id,
      "address": first_result["address"],
      **fields,
      "request_hex": first_result["request_hex"],
      "feedback": first_result["feedback"],
      "control_mode": control_mode,
      "targets": target_results,
    }
    return response.success(payload), 200

  def _loco_control_preflight(self, state: dict, operation_name: str):
    blocked = self.controller_service.digital_operation_mode_failure(state["controller"], operation_name)
    if blocked:
      return http_helpers.service_result(blocked)
    stale_booster = self.controller_api.fresh_booster_status_failure(state["controller"])
    if stale_booster:
      return stale_booster
    readiness_warnings = self.controller_service.loco_control_readiness_warnings(state["controller"])
    if readiness_warnings:
      adapter = self.controller_api.controller_adapter(state["controller"])
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        f"不能发送真实{operation_name}命令",
        {"warnings": readiness_warnings},
      ), 409
    booster_status = state["controller"].get("booster_status")
    adapter = self.controller_api.controller_adapter(state["controller"])
    if not adapter.is_booster_status_confirmed(state["controller"]):
      return response.failure(
        "protocol_not_ready",
        "轨道状态尚未确认",
        "需要先读取控制器或执行通电操作，得到确认后的轨道状态后再执行车辆控制",
        {"warnings": ["booster_status_unconfirmed"]},
      ), 409
    if not booster_status.get("power_on", False):
      return response.failure(
        "track_power_required",
        "车辆控制需要先给轨道通电",
        "请先点击“通电”并确认状态灯变绿，再发送速度、方向或功能键命令",
        {"warnings": ["track_power_required"]},
      ), 409
    if not booster_status.get("dcc_mode", False):
      return response.failure(
        "unsafe_track_mode",
        "当前轨道不是 DCC 数码输出",
        "车辆控制只允许在 N、HO 或 G 的 DCC 数码模式下执行",
        {"warnings": ["main_track_not_dcc"]},
      ), 409
    return None

  def _loco_speed_targets(self, state: dict, vehicle: dict):
    if int(vehicle.get("type", 0) or 0) == 3:
      consist = self._find_controlled_consist(state, vehicle.get("id"))
      if consist:
        members = self._consist_member_targets(state, consist)
        if members:
          return members, "consist_vehicle"
    return [self._vehicle_loco_target(vehicle)], "single"

  def _loco_function_targets(self, state: dict, vehicle: dict):
    consist = self._find_synced_function_consist(state, vehicle.get("id"))
    if consist:
      members = self._consist_member_targets(state, consist)
      if members:
        return members, "synced_consist_function"
    return [self._vehicle_loco_target(vehicle)], "single"

  def _find_controlled_consist(self, state: dict, vehicle_id):
    if not vehicle_id:
      return None
    return next((consist for consist in state.get("consists", []) if consist.get("control_vehicle_id") == vehicle_id), None)

  def _find_synced_function_consist(self, state: dict, vehicle_id):
    if not vehicle_id:
      return None
    for consist in state.get("consists", []):
      control_vehicle_id = consist.get("control_vehicle_id")
      if not control_vehicle_id:
        continue
      control_vehicle = self.vehicle_library.find_by_id(state.get("vehicles", []), control_vehicle_id)
      if not control_vehicle or not control_vehicle.get("sync_function_control"):
        continue
      if control_vehicle_id == vehicle_id:
        return consist
      if any(member.get("vehicle_id") == vehicle_id for member in consist.get("members", [])):
        return consist
    return None

  def _consist_member_targets(self, state: dict, consist: dict) -> list[dict]:
    targets = []
    for member in sorted(consist.get("members", []), key=lambda item: int(item.get("order", 0) or 0)):
      member_vehicle = self.vehicle_library.find_by_id(state.get("vehicles", []), member.get("vehicle_id"))
      if member_vehicle is None:
        continue
      targets.append({
        "vehicle_id": member_vehicle.get("id"),
        "name": member_vehicle.get("name", ""),
        "address": member.get("address", member_vehicle.get("address")),
        "member_direction": member.get("direction", "forward"),
      })
    return targets

  def _vehicle_loco_target(self, vehicle: dict) -> dict:
    return {
      "vehicle_id": vehicle.get("id"),
      "name": vehicle.get("name", ""),
      "address": vehicle.get("address"),
    }

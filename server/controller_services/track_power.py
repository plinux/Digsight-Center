"""Track output controller operations."""

from datetime import datetime

from server import models
from server.controllers.base import ControllerOperationNotSupported, TrackOutputRequest
from server.controller_services.results import ServiceResult


class TrackPowerService:
  def prepare_track_power_request(self, controller: dict, powered: bool):
    try:
      track_mode = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError) as exc:
      return None, ServiceResult.failure("invalid_controller_settings", "控制器本地参数无效", str(exc), status=409)
    if powered and track_mode == models.TRACK_MODE_DC:
      return None, ServiceResult.failure(
        "unsafe_track_mode",
        "DC 模式通电必须使用 DC 控制",
        "请使用 DC 控制接口设置电压和方向；普通轨道通电仅用于 N/HO/G 数码模式",
        status=409,
        debug={"warnings": ["dc_power_requires_dc_control"]},
      )
    profiles = controller.get("track_profiles", models.default_track_profiles())
    profile = profiles.get(track_mode, models.default_track_profiles().get(track_mode, {}))
    output_value = track_output_value(track_mode, profile, powered)
    direction = "forward"
    if track_mode == models.TRACK_MODE_DC:
      try:
        direction = validate_dc_direction(controller.get("dc_control", {}).get("direction", "forward"))
      except (TypeError, ValueError):
        direction = "forward"
    return {
      "powered": powered,
      "track_mode": track_mode,
      "output_value": output_value,
      "dc_direction_positive": direction != "reverse",
      "dc_direction": direction if track_mode == models.TRACK_MODE_DC else None,
    }, None

  def prepare_dc_control_request(self, controller: dict, request: dict):
    try:
      track_mode = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError) as exc:
      return None, ServiceResult.failure("invalid_controller_settings", "控制器本地参数无效", str(exc), status=409)
    if track_mode != models.TRACK_MODE_DC:
      return None, ServiceResult.failure(
        "unsafe_track_mode",
        "DC 控制只允许在 DC 模式下执行",
        "请先切换到 DC 模式；N/HO/G 使用 DCC 车辆控制",
        status=409,
        debug={"warnings": ["operation_mode_not_dc"]},
      )
    try:
      voltage = validate_dc_voltage(controller, request.get("voltage_v", 0))
      direction = validate_dc_direction(request.get("direction", "forward"))
    except (TypeError, ValueError) as exc:
      return None, ServiceResult.failure("invalid_dc_control", "DC 控制参数无效", str(exc), status=400)
    powered = voltage > 0
    output_value = dc_output_value(voltage)
    return {
      "dc_control": {
        "voltage_v": voltage,
        "direction": direction,
        "powered": powered,
        "output_value": output_value,
      },
      "track_output": {
        "powered": powered,
        "track_mode": models.TRACK_MODE_DC,
        "output_value": output_value,
        "dc_direction_positive": direction != "reverse",
        "dc_direction": direction,
        "voltage_v": voltage,
      },
    }, None

  def send_track_output(
    self,
    state: dict,
    *,
    powered: bool,
    track_mode: str,
    output_value: int,
    dc_direction_positive: bool = True,
    dc_direction: str | None = None,
    voltage_v: float | None = None,
  ):
    support = self.service_support
    controller = state["controller"]
    try:
      self.controller_client_id(controller)
    except (TypeError, ValueError) as exc:
      return ServiceResult.failure(
        "invalid_controller_settings",
        "控制器本地参数无效",
        str(exc),
        status=409,
    )
    dcc_mode = track_mode != models.TRACK_MODE_DC
    try:
      result = self._send_track_output_request(
        controller,
        powered=powered,
        track_mode=track_mode,
        output_value=output_value,
        dc_direction_positive=dc_direction_positive,
      )
    except ControllerOperationNotSupported as exc:
      return self.operation_not_supported_response(exc)
    except TimeoutError as exc:
      support.mark_controller_unreachable(state, "track_power_timeout")
      return ServiceResult.failure(
        "track_power_timeout",
        "轨道输出命令超时",
        str(exc),
        status=504,
        debug={"request_hex": "", "powered": powered},
      )
    except (OSError, ValueError) as exc:
      support.mark_controller_unreachable(state, "track_power_transport_error")
      return ServiceResult.failure(
        "track_power_transport_error",
        "轨道输出通信失败",
        str(exc),
        status=502,
        debug={"request_hex": "", "powered": powered},
      )

    if not result.booster_status:
      support.mark_controller_unreachable(state, "track_power_status_missing")
      return ServiceResult.failure(
        "track_power_status_missing",
        "控制器未返回轨道输出状态",
        "No 0x23 booster status response matched the track power command",
        status=504,
        debug={
          "request_hex": result.request_hex,
          "powered": powered,
          "responses": result.debug.get("responses", []),
        },
      )
    try:
      booster_status = self._store_track_output_booster_status(controller, result.booster_status)
    except (KeyError, TypeError, ValueError) as exc:
      support.mark_controller_unreachable(state, "track_power_status_parse_error")
      return ServiceResult.failure(
        "track_power_status_parse_error",
        "轨道输出状态解析失败",
        str(exc),
        status=502,
        debug={
          "request_hex": result.request_hex,
          "booster_status": result.booster_status,
          "responses": result.debug.get("responses", []),
        },
      )
    support.save(state)
    if bool(booster_status.get("power_on")) != powered:
      return ServiceResult.failure(
        "track_power_state_mismatch",
        "轨道输出状态未达到目标",
        f"目标状态为{'通电' if powered else '断电'}，回包状态为{'通电' if booster_status.get('power_on') else '断电'}",
        status=502,
        debug={
          "request_hex": result.request_hex,
          "responses": result.debug.get("responses", []),
          "booster_status": booster_status,
        },
      )
    response_dcc_mode = bool(booster_status.get("dcc_mode", False))
    if powered and response_dcc_mode != dcc_mode:
      return ServiceResult.failure(
        "unsafe_track_mode",
        "控制器回报的轨道模式与目标模式不一致",
        f"目标模式为{'DCC' if dcc_mode else 'DC'}，回包模式为{'DCC' if response_dcc_mode else 'DC'}",
        status=409,
        debug={
          "request_hex": result.request_hex,
          "responses": result.debug.get("responses", []),
          "booster_status": booster_status,
        },
      )
    return ServiceResult.success(self._track_output_success_payload(
      controller,
      result,
      powered=powered,
      track_mode=track_mode,
      output_value=output_value,
      dcc_mode=dcc_mode,
      dc_direction=dc_direction,
      dc_direction_positive=dc_direction_positive,
      voltage_v=voltage_v,
      booster_status=booster_status,
    ))

  def _send_track_output_request(
    self,
    controller: dict,
    *,
    powered: bool,
    track_mode: str,
    output_value: int,
    dc_direction_positive: bool,
  ):
    adapter = self.ensure_supported(controller, "track_power", "track_power")
    return adapter.send_track_output_request(
      self.controller_session,
      controller,
      TrackOutputRequest(
        powered=powered,
        track_mode=track_mode,
        output_value=output_value,
        dc_direction_positive=dc_direction_positive,
        timeout_seconds=float(controller.get("track_power_timeout_seconds", 1.5)),
      ),
      transport=self.udp_transport,
    )

  def _track_output_success_payload(
    self,
    controller: dict,
    result,
    *,
    powered: bool,
    track_mode: str,
    output_value: int,
    dcc_mode: bool,
    dc_direction: str | None,
    dc_direction_positive: bool,
    voltage_v: float | None,
    booster_status: dict,
  ) -> dict:
    data = {
      "powered": powered,
      "track_mode": track_mode,
      "dcc_mode": dcc_mode,
      "output_value": output_value,
      "request_hex": result.request_hex,
      "booster_status": booster_status,
      "telemetry": controller.get("telemetry", {}),
    }
    if track_mode == models.TRACK_MODE_DC:
      data["direction"] = dc_direction or ("forward" if dc_direction_positive else "reverse")
      data["voltage_v"] = round(output_value / 10, 1) if voltage_v is None else voltage_v
    return data

  def _store_track_output_booster_status(self, controller: dict, booster_status: dict) -> dict:
    stored_status = dict(booster_status)
    controller["booster_status"] = stored_status
    controller["controller_reachable"] = True
    controller["controller_unreachable_reason"] = ""
    controller["last_controller_seen_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    self.service_support.mark_safety_snapshot_fresh(controller, booster_status_fresh=True)
    voltage = stored_status["output_voltage_v"]
    current = stored_status["output_current_a"]
    controller["telemetry"] = {
      **controller.get("telemetry", {}),
      "temperature_c": stored_status["temperature_c"],
      "track_voltage_v": voltage,
      "track_current_a": current,
      "track_power_w": round(voltage * current, 3),
    }
    return stored_status


def validate_dc_direction(value) -> str:
  direction = str(value or "forward").strip().lower()
  if direction not in {"forward", "reverse"}:
    raise ValueError("DC direction must be forward or reverse")
  return direction


def validate_dc_voltage(controller: dict, value) -> float:
  profiles = controller.get("track_profiles", models.default_track_profiles())
  profile = profiles.get(models.TRACK_MODE_DC, models.default_track_profiles()[models.TRACK_MODE_DC])
  max_voltage = float(profile.get("max_voltage_v") or models.default_track_profiles()[models.TRACK_MODE_DC]["max_voltage_v"])
  voltage = float(value)
  if voltage < 0 or voltage > max_voltage:
    raise ValueError(f"DC voltage must be 0..{max_voltage} V")
  return round(voltage, 1)


def dc_output_value(voltage: float) -> int:
  return max(0, min(255, int(round(voltage * 10))))


def track_output_value(track_mode: str, profile: dict, powered: bool) -> int:
  if not powered:
    return 0
  if track_mode == models.TRACK_MODE_DC:
    voltage = float(profile.get("voltage_v") or models.default_track_profiles()[models.TRACK_MODE_DC]["voltage_v"])
    return dc_output_value(voltage)
  return max(0, min(255, int(profile.get("output_value", 0))))

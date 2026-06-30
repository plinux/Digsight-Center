"""Loco command controller operations."""

from server.controllers.base import (
  ControllerOperationNotSupported,
  LocoControlGrantRequest,
  LocoFunctionRequest,
  LocoSpeedRequest,
)
from server.controller_services.results import ServiceResult
from train_dcc.address import validate_loco_address, validate_loco_speed_128


class LocoCommandService:
  def validate_loco_speed_value(self, value) -> int:
    return validate_loco_speed_128(value)

  def execute_loco_targets(
    self,
    state: dict,
    targets: list[dict],
    *,
    loco_command_kind: str,
    speed: int | None = None,
    direction: str | None = None,
    function_states: dict | None = None,
    function_number: int | None = None,
  ):
    support = self.service_support
    if loco_command_kind not in {"speed", "function"}:
      return None, ServiceResult.failure(
        "invalid_loco_control",
        "车辆控制参数无效",
        "loco_command_kind must be 'speed' or 'function'",
        status=400,
      )
    controller = state["controller"]
    try:
      client_id = self.controller_client_id(controller)
    except (TypeError, ValueError) as exc:
      return None, ServiceResult.failure("invalid_controller_settings", "控制器本地参数无效", str(exc), status=409)
    try:
      adapter = self.ensure_supported(controller, "loco_control", "loco_control")
    except ControllerOperationNotSupported as exc:
      return None, self.operation_not_supported_response(exc)
    target_results = []
    for target in targets:
      try:
        address = validate_loco_address(target["address"])
        command_request = self._build_loco_command_request(
          target,
          address,
          client_id,
          loco_command_kind=loco_command_kind,
          speed=speed,
          direction=direction,
          function_states=function_states,
          function_number=function_number,
        )
      except (TypeError, ValueError) as exc:
        return None, ServiceResult.failure("invalid_loco_control", "车辆控制参数无效", str(exc), status=400)
      try:
        target_result, denied = self._execute_loco_target(
          adapter,
          controller,
          target,
          address,
          command_request,
          loco_command_kind,
        )
      except TimeoutError as exc:
        support.mark_controller_unreachable(state, "loco_control_timeout")
        return None, ServiceResult.failure(
          "loco_control_timeout",
          "车辆控制命令超时",
          str(exc),
          status=504,
          debug={"request_hex": "", "vehicle_id": target.get("vehicle_id")},
        )
      except (OSError, ValueError) as exc:
        support.mark_controller_unreachable(state, "loco_control_transport_error")
        return None, ServiceResult.failure(
          "loco_control_transport_error",
          "车辆控制通信失败",
          str(exc),
          status=502,
          debug={"request_hex": "", "vehicle_id": target.get("vehicle_id")},
        )
      if denied:
        return None, denied
      target_results.append(target_result)

    if not target_results:
      return None, ServiceResult.failure("invalid_consist", "编组没有可控成员", "consist has no controllable members", status=400)
    state["controller"]["controller_reachable"] = True
    state["controller"]["controller_unreachable_reason"] = ""
    support.save(state)
    return target_results, None

  def _execute_loco_target(
    self,
    adapter,
    controller: dict,
    target: dict,
    address: int,
    command_request,
    loco_command_kind: str,
  ):
    control_grant = adapter.request_loco_control_grant(
      self.controller_session,
      controller,
      LocoControlGrantRequest(address=address, client_id=command_request.client_id),
      transport=self.udp_transport,
    )
    denied = self._loco_control_denied_response(control_grant, target)
    if denied:
      return None, denied
    command_result = self._send_loco_command(adapter, controller, command_request, loco_command_kind)
    return {
      **target,
      "address": address,
      "control_request_hex": control_grant.request_hex,
      "control_feedback": control_grant.feedback,
      **command_result.extra,
      "request_hex": command_result.request_hex,
      "request_hexes": command_result.request_hexes,
      "feedback": command_result.feedback,
    }, None

  def _build_loco_command_request(
    self,
    target: dict,
    address: int,
    client_id: int,
    *,
    loco_command_kind: str,
    speed: int | None,
    direction: str | None,
    function_states: dict | None,
    function_number: int | None,
  ):
    if loco_command_kind == "speed":
      return LocoSpeedRequest(
        address=address,
        speed=self.validate_loco_speed_value(speed),
        direction=self._consist_target_direction(direction, target),
        client_id=client_id,
      )
    return LocoFunctionRequest(
      address=address,
      function_states=dict(function_states or {}),
      client_id=client_id,
      function_number=int(function_number),
    )

  def _send_loco_command(self, adapter, controller: dict, command_request, loco_command_kind: str):
    if loco_command_kind == "speed":
      return adapter.send_loco_speed_request(
        self.controller_session,
        controller,
        command_request,
        transport=self.udp_transport,
      )
    return adapter.send_loco_function_request(
      self.controller_session,
      controller,
      command_request,
      transport=self.udp_transport,
    )

  def _loco_control_denied_response(self, control_grant, target: dict):
    control_feedback = control_grant.feedback
    if not control_feedback or control_feedback.get("granted_to_client"):
      return None
    return ServiceResult.failure(
      "loco_control_denied",
      "车辆控制权请求被拒绝",
      f"车辆地址 {control_grant.address} 当前不能由本手柄控制",
      status=409,
      debug={
        "vehicle_id": target.get("vehicle_id"),
        "address": control_grant.address,
        "control_request_hex": control_grant.request_hex,
        "control_feedback": control_feedback,
      },
    )

  def _consist_target_direction(self, command_direction: str | None, target: dict) -> str:
    target_direction = str(command_direction or "forward").lower()
    if target_direction not in {"forward", "reverse"}:
      raise ValueError("direction must be forward or reverse")
    if str(target.get("member_direction", "forward")).lower() != "reverse":
      return target_direction
    return "reverse" if target_direction == "forward" else "forward"

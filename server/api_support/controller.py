"""Controller API orchestration outside the HTTP router."""

import copy
from datetime import datetime
import ipaddress

from server import models, response
from server.api_support import http_helpers
from server.controller_probe import probe_ip, probe_ip_with_runner
from server.controllers.base import (
  ControllerInfoReadRequest,
  ControllerOperationNotSupported,
  ControllerParameterWriteError,
)


class ControllerApiSupport:
  def __init__(self, context, controller_service, *, probe_runner=None):
    self.context = context
    self.controller_service = controller_service
    self.probe_runner = probe_runner

  def controller_adapter(self, controller: dict):
    return self.context.controller_registry.get(controller.get("kind") or self.context.controller_registry.default_kind)

  def controller_not_supported_response(self, exc: ControllerOperationNotSupported):
    return http_helpers.service_result(self.controller_service.operation_not_supported_response(exc))

  def controller_capability_failure(self, controller: dict, capability_name: str, operation_name: str):
    try:
      self.controller_service.ensure_supported(controller, capability_name, operation_name)
    except ControllerOperationNotSupported as exc:
      return self.controller_not_supported_response(exc)
    return None

  def connect(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    controller = state["controller"]
    try:
      kind = models.validate_controller_kind(request.get("kind", controller.get("kind") or self.context.controller_registry.default_kind))
      adapter = self.context.controller_registry.get(kind)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_kind", "控制器类型无效", str(exc)), 400
    transport_defaults = adapter.transport_defaults
    try:
      ip = validate_controller_ip(request.get("ip", controller.get("ip") or adapter.default_ip))
    except ValueError as exc:
      return response.failure("invalid_controller_ip", "控制器 IP 格式无效", str(exc)), 400
    try:
      udp_port = validate_udp_port(request.get("udp_port", transport_defaults.udp_port))
      local_udp_port = normalize_local_udp_port(
        request.get("local_udp_port", transport_defaults.local_udp_port),
        transport_defaults,
      )
      checksum_algorithm = validate_checksum_algorithm(
        request.get("udp_checksum_algorithm", transport_defaults.checksum_algorithm),
        transport_defaults.checksum_algorithms,
      )
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_connection", "控制器连接参数无效", str(exc)), 400
    previous_identity = controller_transport_identity(controller)
    next_identity = controller_transport_identity(
      controller,
      kind=kind,
      ip=ip,
      udp_port=udp_port,
      local_udp_port=local_udp_port,
      checksum_algorithm=checksum_algorithm,
    )
    if next_identity != previous_identity:
      self.context.invalidate_controller_runtime_safety(controller, reason="controller_transport_changed")
    controller["kind"] = kind
    controller["ip"] = ip
    controller["udp_port"] = udp_port
    controller["local_udp_port"] = local_udp_port
    controller["udp_checksum_algorithm"] = checksum_algorithm
    self.context.save(state)
    return response.success({
      "ip": ip,
      "udp_port": udp_port,
      "local_udp_port": local_udp_port,
      "udp_checksum_algorithm": checksum_algorithm,
      "connected": udp_port > 0,
    }), 200

  def probe(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    try:
      ip = validate_controller_ip(request.get("ip") or state["controller"].get("ip") or models.CONTROLLER_DEFAULT_IP)
    except ValueError as exc:
      return response.failure("invalid_controller_ip", "控制器 IP 格式无效", str(exc)), 400
    result = probe_ip_with_runner(ip, self.probe_runner) if self.probe_runner else probe_ip(ip)
    endpoint_changed = ip != state["controller"].get("ip")
    if endpoint_changed:
      self.context.invalidate_controller_runtime_safety(state["controller"], reason="controller_endpoint_changed")
    elif not result.ok:
      self.context.invalidate_controller_runtime_safety(state["controller"], reason="controller_probe_failed")
    state["controller"]["ip"] = ip
    state["controller"]["last_probe_ok"] = result.ok
    state["controller"]["last_probe_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    self.context.save(state)
    status = 200 if result.ok else 502
    return response.success({
      "ip": ip,
      "reachable": result.ok,
      "detail": result.detail,
    }), status

  def disconnect(self, state: dict):
    self.context.invalidate_controller_runtime_safety(state["controller"], reason="controller_disconnected")
    self.context.save(state)
    return response.success({"connected": False}), 200

  def controller_info(self, state: dict) -> dict:
    controller = state["controller"]
    adapter = self.controller_adapter(controller)
    readiness_warnings = self.controller_service.controller_readiness_warnings(controller)
    booster_status = controller.get("booster_status", {})
    if not isinstance(booster_status, dict):
      booster_status = {}
    cv_safety = self.cached_cv_safety(controller)
    controller_reachable = bool(controller.get("controller_reachable", False))
    short_circuit = bool(booster_status.get("short_circuit") or booster_status.get("current_alarm"))
    return {
      "ip": controller.get("ip"),
      "controller_kind": adapter.kind,
      "controller_label": adapter.label,
      "controller_capabilities": adapter.capabilities.to_dict(),
      "connection": {
        "reachable": not readiness_warnings,
        "controller_reachable": controller_reachable,
        "controller_unreachable_reason": controller.get("controller_unreachable_reason", ""),
        "last_probe_ok": bool(controller.get("last_probe_ok")),
        "last_probe_at": controller.get("last_probe_at", ""),
        "last_controller_seen_at": controller.get("last_controller_seen_at", ""),
        "udp_port": int(controller.get("udp_port", 0)),
        "local_udp_port": int(controller.get("local_udp_port", 0)),
        "udp_checksum_algorithm": controller.get("udp_checksum_algorithm", ""),
        "gateway_ready": not readiness_warnings,
        "track_powered": bool(booster_status.get("power_on", False)) if controller_reachable else False,
        "short_circuit": short_circuit if controller_reachable else False,
      },
      "booster_status": booster_status,
      "safety_snapshot": controller.get("safety_snapshot", {}),
      "telemetry": controller.get("telemetry", {}),
      "device_info": controller.get("device_info", {}),
      "track_profiles": controller.get("track_profiles", models.default_track_profiles()),
      "safe_for_cv": cv_safety["safe_for_cv"],
      "programming_track_status": cv_safety["programming_track_status"],
      "cv_safety_warnings": cv_safety["warnings"],
      "read_capability": {
        "dxdcnet_udp_ready": not readiness_warnings,
        "warnings": readiness_warnings,
      },
    }

  def cached_cv_safety(self, controller: dict) -> dict:
    warnings = []
    try:
      track_mode = models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      return {
        "safe_for_cv": False,
        "programming_track_status": controller.get("programming_track_status", {}),
        "warnings": ["unsafe_track_mode"],
      }
    programming_status = self.controller_adapter(controller).programming_track_status(controller)
    if programming_status is None:
      return {
        "safe_for_cv": False,
        "programming_track_status": controller.get("programming_track_status", {}),
        "warnings": ["programming_track_status_unconfirmed"],
      }
    if programming_status.track_mode != track_mode:
      warnings.append("programming_track_status_stale")
    try:
      self.controller_adapter(controller).validate_programming_track_safety(programming_status)
    except ValueError:
      warnings.append("programming_track_safety_failed")
    return {
      "safe_for_cv": not warnings,
      "programming_track_status": controller.get("programming_track_status", {}),
      "warnings": warnings,
    }

  def settings(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    parsed, error_response = self._parse_controller_settings_request(request, state["controller"])
    if error_response:
      return error_response
    candidate_controller = self._build_controller_settings_candidate(state["controller"], parsed)
    device_results = []
    if parsed["apply_to_device"] and parsed["requested_profile_modes"]:
      device_results, error_response = self._apply_controller_settings_to_device(
        candidate_controller,
        parsed["next_profiles"],
        parsed["requested_profile_modes"],
      )
      if error_response:
        return error_response
    candidate_controller["track_profiles"] = parsed["next_profiles"]
    state["controller"] = candidate_controller
    self.context.save(state)
    return response.success(self._controller_settings_response_payload(candidate_controller, parsed, device_results)), 200

  def track_mode(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    try:
      next_track_mode = models.validate_profile_mode(request.get("track_mode"))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_track_mode", "轨道模式无效", str(exc)), 400
    candidate_controller = copy.deepcopy(state["controller"])
    previous_track_mode = candidate_controller.get("track_mode", models.TRACK_MODE_N)
    if next_track_mode != previous_track_mode:
      self.context.invalidate_controller_runtime_safety(candidate_controller, reason="track_mode_changed")
    candidate_controller["track_mode"] = next_track_mode
    state["controller"] = candidate_controller
    self.context.save(state)
    return response.success({
      "track_mode": next_track_mode,
      "warnings": ["saved_locally_only"],
    }), 200

  def track_power(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    if not isinstance(request.get("powered"), bool):
      return response.failure("invalid_track_power", "轨道输出参数无效", "powered must be true or false"), 400
    powered = bool(request["powered"])
    controller = state["controller"]
    unsupported = self.controller_capability_failure(controller, "track_power", "track_power")
    if unsupported:
      return unsupported
    prepared_request, error_response = self.controller_service.prepare_track_power_request(controller, powered)
    if error_response:
      return http_helpers.service_result(error_response)
    if powered:
      preflight_failure = self.track_power_on_preflight_failure(controller)
      if preflight_failure is not None:
        return preflight_failure
    readiness_warnings = self.controller_service.controller_readiness_warnings(controller)
    if readiness_warnings:
      adapter = self.controller_adapter(controller)
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        "不能发送真实轨道通电或断电命令",
        {"warnings": readiness_warnings},
      ), 409
    try:
      self.controller_service.controller_client_id(controller)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_settings", "控制器本地参数无效", str(exc)), 409

    return http_helpers.service_result(self.controller_service.send_track_output(state, **prepared_request))

  def dc_control(self, body: bytes, state: dict):
    controller = state["controller"]
    request = http_helpers.json_body(body)
    prepared_request, error_response = self.controller_service.prepare_dc_control_request(controller, request)
    if error_response:
      return http_helpers.service_result(error_response)
    unsupported = self.controller_capability_failure(controller, "track_power", "dc_control")
    if unsupported:
      return unsupported
    readiness_warnings = self.controller_service.controller_readiness_warnings(controller)
    if readiness_warnings:
      adapter = self.controller_adapter(controller)
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        "不能发送真实 DC 控制命令",
        {"warnings": readiness_warnings},
      ), 409
    controller["dc_control"] = prepared_request["dc_control"]
    return http_helpers.service_result(self.controller_service.send_track_output(state, **prepared_request["track_output"]))

  def read_info(self, state: dict):
    controller = state["controller"]
    unsupported = self.controller_capability_failure(controller, "read_info", "read_info")
    if unsupported:
      return unsupported
    warnings = self.controller_service.controller_readiness_warnings(controller)
    if warnings:
      adapter = self.controller_adapter(controller)
      detail = "UDP port and checksum algorithm are unconfirmed"
      if warnings == ["udp_checksum_algorithm_unconfirmed"]:
        detail = "UDP checksum algorithm is unconfirmed"
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        detail,
        {"warnings": warnings},
      ), 409
    try:
      self.controller_service.controller_client_id(controller)
      track_mode = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_settings", "控制器本地参数无效", str(exc)), 400

    profiles = controller.get("track_profiles", models.default_track_profiles())
    profile = profiles.get(track_mode, models.default_track_profiles()[track_mode])
    current_param = int(profile.get("current_param", models.default_track_profiles()[track_mode]["current_param"]))
    adapter = self.controller_adapter(controller)
    read_request = ControllerInfoReadRequest(track_mode=track_mode, current_param=current_param)
    read_info_result = adapter.read_controller_info(
      self.context.controller_session,
      controller,
      read_request,
      transport=self.context.udp_transport,
    )
    parsed = adapter.parse_controller_info(controller, read_request, read_info_result)
    controller["last_read_info_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    self.context.save(state)
    return response.success(
      {
        "controller": self.controller_info(state),
        "safe_for_cv": parsed["safe_for_cv"],
        "warnings": parsed["warnings"],
      },
      {
        "warnings": parsed["warnings"],
        "requests": read_info_result.requests,
      },
    ), 200

  def fresh_booster_status_failure(self, controller: dict):
    if self.context.default_safety_snapshot(controller)["booster_status_fresh"]:
      return None
    return response.failure(
      "protocol_not_ready",
      "轨道状态尚未重新确认",
      "控制器端点或模式已变化，需要重新读取控制器状态",
      {"warnings": ["booster_status_stale"]},
    ), 409

  def track_power_on_preflight_failure(self, controller: dict):
    warnings = self.controller_service.loco_control_readiness_warnings(controller)
    if not self.context.default_safety_snapshot(controller)["booster_status_fresh"]:
      warnings.append("booster_status_stale")
    adapter = self.controller_adapter(controller)
    if not adapter.is_booster_status_confirmed(controller):
      warnings.append("booster_status_unconfirmed")
    if not warnings:
      return None
    return response.failure(
      "protocol_not_ready",
      "请先连接控制器并读取最新状态",
      "Power-on requires fresh controller status from the current session",
      {"warnings": warnings},
    ), 409

  def _parse_controller_settings_request(self, request: dict, controller: dict):
    previous_kind = models.validate_controller_kind(
      controller.get("kind") or self.context.controller_registry.default_kind
    )
    next_kind = previous_kind
    next_adapter = None
    if "kind" in request:
      try:
        next_kind = models.validate_controller_kind(request.get("kind"))
        next_adapter = self.context.controller_registry.get(next_kind)
      except (TypeError, ValueError) as exc:
        return None, (response.failure("invalid_controller_kind", "控制器类型无效", str(exc)), 400)
    if next_adapter is None:
      try:
        next_adapter = self.context.controller_registry.get(next_kind)
      except ValueError as exc:
        return None, (response.failure("invalid_controller_kind", "控制器类型无效", str(exc)), 400)
    try:
      previous_ip = controller.get("ip", models.CONTROLLER_DEFAULT_IP)
      next_ip = validate_controller_ip(request.get("ip")) if "ip" in request else previous_ip
      previous_track_mode = controller.get("track_mode", models.TRACK_MODE_N)
      next_track_mode = models.validate_profile_mode(request.get("track_mode")) if "track_mode" in request else previous_track_mode
      previous_programming_target = controller.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK)
      next_programming_target = (
        models.validate_programming_target(request.get("programming_target"))
        if "programming_target" in request
        else previous_programming_target
      )
      requested_profile_modes = set()
      current_profiles = controller.get("track_profiles", models.default_track_profiles())
      next_profiles = {mode: dict(profile) for mode, profile in current_profiles.items()}
      for mode, profile in request.get("track_profiles", {}).items():
        normalized_mode = models.validate_profile_mode(mode)
        requested_profile_modes.add(normalized_mode)
        next_profiles[normalized_mode] = models.validate_track_profile(normalized_mode, profile)
    except (TypeError, ValueError) as exc:
      return None, (response.failure("invalid_controller_settings", "控制器参数无效", str(exc)), 400)
    return {
      "previous_kind": previous_kind,
      "next_kind": next_kind,
      "next_adapter": next_adapter,
      "previous_ip": previous_ip,
      "next_ip": next_ip,
      "previous_track_mode": previous_track_mode,
      "next_track_mode": next_track_mode,
      "previous_programming_target": previous_programming_target,
      "next_programming_target": next_programming_target,
      "apply_to_device": bool(request.get("apply_to_device", False)),
      "requested_profile_modes": requested_profile_modes,
      "next_profiles": next_profiles,
    }, None

  def _build_controller_settings_candidate(self, controller: dict, parsed: dict) -> dict:
    candidate_controller = copy.deepcopy(controller)
    if parsed["next_kind"] != parsed["previous_kind"]:
      self.context.invalidate_controller_runtime_safety(candidate_controller, reason="controller_kind_changed")
    elif parsed["next_ip"] != parsed["previous_ip"]:
      self.context.invalidate_controller_runtime_safety(candidate_controller, reason="controller_endpoint_changed")
    elif parsed["next_track_mode"] != parsed["previous_track_mode"]:
      self.context.invalidate_controller_runtime_safety(candidate_controller, reason="track_mode_changed")
    elif parsed["next_programming_target"] != parsed["previous_programming_target"]:
      self.context.invalidate_controller_runtime_safety(candidate_controller, reason="programming_target_changed")
    candidate_controller["kind"] = parsed["next_kind"]
    candidate_controller["ip"] = parsed["next_ip"]
    transport_defaults = parsed["next_adapter"].transport_defaults
    if parsed["next_kind"] != parsed["previous_kind"]:
      candidate_controller["udp_port"] = transport_defaults.udp_port
      candidate_controller["local_udp_port"] = transport_defaults.local_udp_port
      candidate_controller["udp_checksum_algorithm"] = transport_defaults.checksum_algorithm
    else:
      candidate_controller.setdefault("udp_port", transport_defaults.udp_port)
      candidate_controller["local_udp_port"] = normalize_local_udp_port(
        candidate_controller.get("local_udp_port", transport_defaults.local_udp_port),
        transport_defaults,
      )
      candidate_controller.setdefault("udp_checksum_algorithm", transport_defaults.checksum_algorithm)
    candidate_controller["track_mode"] = parsed["next_track_mode"]
    candidate_controller["programming_target"] = parsed["next_programming_target"]
    return candidate_controller

  def _apply_controller_settings_to_device(self, candidate_controller: dict, next_profiles: dict, requested_profile_modes: set):
    unsupported = self.controller_capability_failure(candidate_controller, "controller_settings", "controller_settings")
    if unsupported:
      return [], unsupported
    readiness_warnings = self.controller_service.controller_readiness_warnings(candidate_controller)
    if readiness_warnings:
      adapter = self.controller_adapter(candidate_controller)
      return [], (response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        "控制器轨道输出参数需要先确认通信端口和校验算法",
        {"warnings": readiness_warnings},
      ), 409)
    try:
      return self._apply_track_profile_parameters_to_controller(
        candidate_controller,
        next_profiles,
        sorted(requested_profile_modes),
      ), None
    except ControllerOperationNotSupported as exc:
      return [], (response.failure(
        "controller_settings_not_supported",
        "控制器不支持写入这些设置",
        str(exc),
        {"kind": candidate_controller.get("kind")},
      ), 409)
    except ControllerParameterWriteError as exc:
      return [], (response.failure(
        "controller_parameter_write_failed",
        "控制器轨道输出参数写入失败",
        str(exc),
        exc.debug,
      ), 502)

  def _controller_settings_response_payload(self, candidate_controller: dict, parsed: dict, device_results: list) -> dict:
    warnings = [] if device_results else ["saved_locally_only"]
    return {
      "applied_to_device": bool(device_results),
      "device_results": device_results,
      "kind": parsed["next_kind"],
      "ip": parsed["next_ip"],
      "udp_port": candidate_controller["udp_port"],
      "local_udp_port": candidate_controller["local_udp_port"],
      "udp_checksum_algorithm": candidate_controller["udp_checksum_algorithm"],
      "track_mode": parsed["next_track_mode"],
      "programming_target": parsed["next_programming_target"],
      "track_profiles": parsed["next_profiles"],
      "warnings": warnings,
    }

  def _apply_track_profile_parameters_to_controller(self, controller: dict, profiles: dict, modes: list[str]) -> list[dict]:
    adapter = self.controller_adapter(controller)
    return adapter.apply_track_profile_parameters(
      self.context.controller_session,
      controller,
      profiles,
      modes,
      transport=self.context.udp_transport,
    )


def transport_port_value(value) -> int:
  try:
    return int(value)
  except (TypeError, ValueError):
    return 0


def controller_transport_identity(
  controller: dict,
  *,
  kind=None,
  ip=None,
  udp_port=None,
  local_udp_port=None,
  checksum_algorithm=None,
) -> tuple:
  return (
    controller.get("kind", "") if kind is None else kind,
    controller.get("ip") if ip is None else ip,
    transport_port_value(controller.get("udp_port", 0) if udp_port is None else udp_port),
    transport_port_value(controller.get("local_udp_port", 0) if local_udp_port is None else local_udp_port),
    controller.get("udp_checksum_algorithm") if checksum_algorithm is None else checksum_algorithm,
  )


def validate_controller_ip(ip_value) -> str:
  ip_text = str(ip_value or "").strip()
  address = ipaddress.ip_address(ip_text)
  if address.version != 4:
    raise ValueError("controller IP must be IPv4")
  return str(address)


def validate_udp_port(port_value) -> int:
  port = int(port_value)
  if port < 1 or port > 65535:
    raise ValueError("UDP port must be in range 1..65535")
  return port


def validate_local_udp_port(port_value) -> int:
  port = int(port_value)
  if port < 0 or port > 65535:
    raise ValueError("local UDP port must be in range 0..65535")
  return port


def normalize_local_udp_port(port_value, transport_defaults) -> int:
  local_port = validate_local_udp_port(port_value)
  if local_port == 0 and not transport_defaults.allow_zero_local_udp_port:
    return int(transport_defaults.local_udp_port)
  return local_port


def validate_checksum_algorithm(checksum_algorithm, allowed_algorithms=("xor",)) -> str:
  normalized = str(checksum_algorithm or "").strip().lower()
  allowed = tuple(algorithm for algorithm in allowed_algorithms if algorithm)
  if normalized not in allowed:
    allowed_text = ", ".join(allowed) if allowed else "<none>"
    raise ValueError(f"checksum algorithm must be one of: {allowed_text}")
  return normalized


def validate_cv_value(value) -> int:
  cv_value = int(value)
  if cv_value < 0 or cv_value > 255:
    raise ValueError("CV value must be in range 0..255")
  return cv_value

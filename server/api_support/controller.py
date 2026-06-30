"""Controller API orchestration outside the HTTP router."""

import copy
from datetime import datetime
import ipaddress
import json

from server import models, response
from server.app_state import AppStateStore, default_state
from server.api_support import http_helpers
from server.controller_probe import probe_ip, probe_ip_with_runner
from server.controllers.base import (
  ControllerInfoReadRequest,
  ControllerOperationNotSupported,
  ControllerParameterWriteError,
  ControllerProtocolNotSupported,
  apply_controller_transport_runtime,
  controller_display_name,
  controller_protocol,
  controller_readiness_detail,
  normalize_controller_transport_config,
)
from server.controllers.registry import ControllerRegistry


class ControllerConfigInvalid(Exception):
  def __init__(self, error_payload: dict):
    super().__init__(error_payload.get("detail", "controller config is invalid"))
    self.error_payload = error_payload


def controller_settings_apply_to_device(method: str, route: str, body: bytes) -> bool:
  if method != "PATCH" or route != "/api/controller/settings":
    return False
  try:
    payload = json.loads(body.decode("utf-8") or "{}")
  except (UnicodeDecodeError, json.JSONDecodeError):
    return False
  return isinstance(payload, dict) and payload.get("apply_to_device") is True


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

  def probe(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    try:
      ip = validate_controller_ip(request.get("ip") or state["controller"].get("ip") or models.CONTROLLER_DEFAULT_IP)
    except ValueError as exc:
      return response.failure("invalid_controller_ip", "控制器 IP 格式无效", str(exc)), 400
    result = probe_ip_with_runner(ip, self.probe_runner) if self.probe_runner else probe_ip(ip)
    status = 200 if result.ok else 502
    return response.success({
      "ip": ip,
      "reachable": result.ok,
      "detail": result.detail,
    }), status

  def reset_config(self, body: bytes, state: dict):
    if not self.context.state_store:
      return response.failure(
        "controller_config_reset_unavailable",
        "控制器配置重置不可用",
        "No persistent app state store is configured",
      ), 409
    request = http_helpers.json_body(body)
    controller = state.get("controller", {})
    try:
      kind = models.validate_controller_kind(controller.get("kind") or self.context.controller_registry.default_kind)
      requested_kind = models.validate_controller_kind(request.get("kind", kind))
      self.context.controller_registry.get(kind)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_kind", "控制器类型无效", str(exc)), 400
    if requested_kind != kind:
      return response.failure(
        "controller_config_reset_kind_mismatch",
        "只能重置当前选择的控制器配置",
        "Reset request kind must match current controller kind",
        {
          "current_kind": kind,
          "requested_kind": requested_kind,
        },
      ), 409
    reset_global_state = self._should_reset_global_state(state)
    reset_result = self.context.state_store.reset_controller_config(kind)
    reset_files = list(reset_result["reset_files"])
    if reset_global_state:
      reset_files.append(self.context.state_store.app_state_relative_path())
      next_state = default_state(self.context.controller_registry)
      state.clear()
      state.update(next_state)
    next_controller = copy.deepcopy(state.get("controller", {}))
    next_controller.update(reset_result["controller"])
    next_controller["kind"] = kind
    state["controller"] = next_controller
    state["last_error"] = None
    self.context.invalidate_controller_runtime_safety(state["controller"], reason="controller_config_reset")
    self.context.save(state)
    return response.success({
      "controller_kind": kind,
      "controller_label": reset_result["controller_label"],
      "config_file": reset_result["config_file"],
      "reset_files": reset_files,
      "reset_global_state": reset_global_state,
      "controller": {
        "kind": kind,
        "ip": state["controller"].get("ip"),
        "transport": copy.deepcopy(state["controller"].get("transport", {})),
      },
    }), 200

  @staticmethod
  def _should_reset_global_state(state: dict) -> bool:
    last_error = state.get("last_error")
    if AppStateStore.is_app_state_corrupt_recovered_error(last_error):
      return True
    if not isinstance(last_error, dict):
      return False
    global_config_error = last_error.get("global_config_error")
    return AppStateStore.is_app_state_corrupt_recovered_error(global_config_error)

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
      "controller_label": controller_display_name(adapter, controller),
      "controller_protocol": controller_protocol(adapter, controller),
      "controller_capabilities": adapter.capabilities.to_dict(),
      "connection": {
        "reachable": not readiness_warnings,
        "controller_reachable": controller_reachable,
        "controller_unreachable_reason": controller.get("controller_unreachable_reason", ""),
        "last_probe_ok": bool(controller.get("last_probe_ok")),
        "last_probe_at": controller.get("last_probe_at", ""),
        "last_controller_seen_at": controller.get("last_controller_seen_at", ""),
        "transport": copy.deepcopy(controller.get("transport", {})),
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
        "ready": not readiness_warnings,
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
    try:
      candidate_controller = self._build_controller_settings_candidate(state["controller"], parsed)
    except ControllerConfigInvalid as exc:
      state["last_error"] = exc.error_payload
      self.context.save(state)
      return response.failure(
        exc.error_payload.get("type", "controller_config_invalid"),
        exc.error_payload.get("message", "当前控制器配置文件无效"),
        exc.error_payload.get("detail", ""),
        {
          "controller_kind": exc.error_payload.get("controller_kind"),
          "config_file": exc.error_payload.get("config_file"),
          "resettable_files": exc.error_payload.get("resettable_files", []),
        },
      ), 409
    except ValueError as exc:
      return response.failure("invalid_controller_settings", "控制器参数无效", str(exc)), 400
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
    if parsed["next_kind"] != parsed["previous_kind"]:
      AppStateStore.clear_controller_config_error_for_kind_change(state, parsed["previous_kind"], parsed["next_kind"])
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
    return self._send_prepared_track_output(
      state,
      prepared_request,
      "不能发送真实轨道通电或断电命令",
      preflight_failure_fn=self.track_power_on_preflight_failure,
      require_controller_client_id=True,
    )

  def dc_control(self, body: bytes, state: dict):
    controller = state["controller"]
    request = http_helpers.json_body(body)
    unsupported = self.controller_capability_failure(controller, "dc_control", "dc_control")
    if unsupported:
      return unsupported
    prepared_request, error_response = self.controller_service.prepare_dc_control_request(controller, request)
    if error_response:
      return http_helpers.service_result(error_response)
    return self._send_prepared_track_output(
      state,
      prepared_request["track_output"],
      "不能发送真实 DC 控制命令",
      preflight_failure_fn=self.dc_power_on_preflight_failure,
      controller_updates={"dc_control": prepared_request["dc_control"]},
    )

  def _send_prepared_track_output(
    self,
    state: dict,
    track_output_request: dict,
    not_ready_detail: str,
    *,
    preflight_failure_fn=None,
    controller_updates: dict | None = None,
    require_controller_client_id: bool = False,
  ):
    controller = state["controller"]
    if track_output_request.get("powered") and preflight_failure_fn:
      preflight_failure = preflight_failure_fn(controller)
      if preflight_failure is not None:
        return preflight_failure
    readiness_warnings = self.controller_service.controller_readiness_warnings(controller)
    if readiness_warnings:
      adapter = self.controller_adapter(controller)
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        not_ready_detail,
        {"warnings": readiness_warnings},
      ), 409
    if require_controller_client_id:
      try:
        self.controller_service.controller_client_id(controller)
      except (TypeError, ValueError) as exc:
        return response.failure("invalid_controller_settings", "控制器本地参数无效", str(exc)), 409
    for key, value in (controller_updates or {}).items():
      controller[key] = value
    return http_helpers.service_result(self.controller_service.send_track_output(state, **track_output_request))

  def read_info(self, state: dict):
    controller = state["controller"]
    unsupported = self.controller_capability_failure(controller, "read_info", "read_info")
    if unsupported:
      return unsupported
    warnings = self.controller_service.controller_readiness_warnings(controller)
    if warnings:
      adapter = self.controller_adapter(controller)
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        controller_readiness_detail(adapter, warnings),
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
    try:
      read_info_result = adapter.read_controller_info(
        self.controller_service.controller_session_for_adapter(adapter, controller),
        controller,
        read_request,
        transport=self.context.controller_transport,
      )
    except ControllerProtocolNotSupported as exc:
      return http_helpers.service_result(self.controller_service.protocol_not_supported_response(exc))
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
    return self._power_on_preflight_failure(
      controller,
      self.controller_service.loco_control_readiness_warnings(controller),
      "Power-on requires fresh controller status from the current session",
    )

  def dc_power_on_preflight_failure(self, controller: dict):
    return self._power_on_preflight_failure(
      controller,
      self.controller_service.controller_readiness_warnings(controller),
      "DC voltage output requires fresh controller status from the current session",
    )

  def _power_on_preflight_failure(self, controller: dict, warnings: list[str], detail: str):
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
      detail,
      {"warnings": warnings},
    ), 409

  def _parse_controller_settings_request(self, request: dict, controller: dict):
    previous_kind = models.validate_controller_kind(
      controller.get("kind") or self.context.controller_registry.default_kind
    )
    try:
      next_kind, next_adapter = self._next_controller_kind_and_adapter(request, previous_kind)
    except (TypeError, ValueError) as exc:
      return None, (response.failure("invalid_controller_kind", "控制器类型无效", str(exc)), 400)
    try:
      kind_changed = next_kind != previous_kind
      transport_settings = self._parse_transport_settings(request, controller, next_adapter, kind_changed)
      mode_settings = self._parse_controller_mode_settings(request, controller)
      profile_settings = self._parse_track_profile_settings(request, controller)
      apply_to_device = http_helpers.optional_json_bool(request, "apply_to_device")
    except (TypeError, ValueError) as exc:
      return None, (response.failure("invalid_controller_settings", "控制器参数无效", str(exc)), 400)
    return {
      "previous_kind": previous_kind,
      "next_kind": next_kind,
      "next_adapter": next_adapter,
      "apply_to_device": apply_to_device,
      **transport_settings,
      **mode_settings,
      **profile_settings,
    }, None

  def _next_controller_kind_and_adapter(self, request: dict, previous_kind: str):
    next_kind = (
      models.validate_controller_kind(request.get("kind"))
      if "kind" in request
      else previous_kind
    )
    return next_kind, self.context.controller_registry.get(next_kind)

  def _parse_transport_settings(self, request: dict, controller: dict, next_adapter, kind_changed: bool) -> dict:
    previous_ip = controller.get("ip", models.CONTROLLER_DEFAULT_IP)
    next_ip = validate_controller_ip(request.get("ip")) if "ip" in request else previous_ip
    transport_requested = "transport" in request
    ip_requested = "ip" in request
    transport_request = request.get("transport") if isinstance(request.get("transport"), dict) else {}
    current_transport = controller.get("transport") if isinstance(controller.get("transport"), dict) else {}
    base_transport = next_adapter.transport_descriptor.default_config() if kind_changed else current_transport
    requested_transport = {
      **base_transport,
      **transport_request,
      "kind": str(transport_request.get("kind") or base_transport.get("kind") or next_adapter.transport_descriptor.kind),
    }
    next_transport = normalize_controller_transport_config(next_adapter, requested_transport, strict=True)
    return self._transport_settings_result(previous_ip, next_ip, next_transport, transport_requested, ip_requested)

  @staticmethod
  def _transport_settings_result(previous_ip, next_ip, next_transport, transport_requested, ip_requested):
    return {
      "previous_ip": previous_ip,
      "next_ip": next_ip,
      "next_transport": next_transport,
      "transport_requested": transport_requested,
      "ip_requested": ip_requested,
    }

  @staticmethod
  def _parse_controller_mode_settings(request: dict, controller: dict) -> dict:
    previous_track_mode = controller.get("track_mode", models.TRACK_MODE_N)
    previous_programming_target = controller.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK)
    return {
      "previous_track_mode": previous_track_mode,
      "next_track_mode": (
        models.validate_profile_mode(request.get("track_mode"))
        if "track_mode" in request
        else previous_track_mode
      ),
      "previous_programming_target": previous_programming_target,
      "next_programming_target": (
        models.validate_programming_target(request.get("programming_target"))
        if "programming_target" in request
        else previous_programming_target
      ),
    }

  @staticmethod
  def _parse_track_profile_settings(request: dict, controller: dict) -> dict:
    requested_profile_modes = set()
    current_profiles = controller.get("track_profiles", models.default_track_profiles())
    next_profiles = {mode: dict(profile) for mode, profile in current_profiles.items()}
    for mode, profile in request.get("track_profiles", {}).items():
      normalized_mode = models.validate_profile_mode(mode)
      requested_profile_modes.add(normalized_mode)
      next_profiles[normalized_mode] = models.validate_track_profile(normalized_mode, profile)
    return {
      "requested_profile_modes": requested_profile_modes,
      "next_profiles": next_profiles,
    }

  def _build_controller_settings_candidate(self, controller: dict, parsed: dict) -> dict:
    kind_changed = parsed["next_kind"] != parsed["previous_kind"]
    candidate_controller = self._controller_for_kind(controller, parsed["next_kind"]) if kind_changed else copy.deepcopy(controller)
    if kind_changed:
      self.context.invalidate_controller_runtime_safety(candidate_controller, reason="controller_kind_changed")
    candidate_controller["kind"] = parsed["next_kind"]
    if kind_changed and not parsed["ip_requested"]:
      try:
        parsed["next_ip"] = validate_controller_ip(
          candidate_controller.get("ip") or parsed["next_ip"] or parsed["next_adapter"].default_ip
        )
      except ValueError as exc:
        raise ValueError(f"target controller IP is invalid: {exc}") from exc
    candidate_controller["ip"] = parsed["next_ip"]
    candidate_transport = copy.deepcopy(parsed["next_transport"])
    candidate_controller["transport"] = candidate_transport
    apply_controller_transport_runtime(parsed["next_adapter"], candidate_controller)
    candidate_controller["track_mode"] = parsed["next_track_mode"]
    candidate_controller["programming_target"] = parsed["next_programming_target"]
    if not kind_changed:
      if controller_transport_identity(candidate_controller) != controller_transport_identity(controller):
        self.context.invalidate_controller_runtime_safety(candidate_controller, reason="controller_transport_changed")
      elif parsed["next_track_mode"] != parsed["previous_track_mode"]:
        self.context.invalidate_controller_runtime_safety(candidate_controller, reason="track_mode_changed")
      elif parsed["next_programming_target"] != parsed["previous_programming_target"]:
        self.context.invalidate_controller_runtime_safety(candidate_controller, reason="programming_target_changed")
    if kind_changed:
      next_profiles = {
        mode: dict(profile)
        for mode, profile in candidate_controller.get("track_profiles", models.default_track_profiles()).items()
      }
      for mode in parsed["requested_profile_modes"]:
        next_profiles[mode] = parsed["next_profiles"][mode]
      parsed["next_profiles"] = next_profiles
    return candidate_controller

  def _controller_for_kind(self, controller: dict, kind: str) -> dict:
    if self.context.state_store and hasattr(self.context.state_store, "controller_config_for_kind"):
      if hasattr(self.context.state_store, "controller_config_for_kind_with_error"):
        target_config, target_config_error = self.context.state_store.controller_config_for_kind_with_error(kind)
        if target_config_error:
          raise ControllerConfigInvalid(target_config_error)
      else:
        target_config = self.context.state_store.controller_config_for_kind(kind)
    else:
      target_config = AppStateStore.default_controller_config(self.context.controller_registry, kind)
    target_registry = ControllerRegistry(default_kind=kind)
    target_registry.register(self.context.controller_registry.get(kind), default=True)
    candidate_controller = copy.deepcopy(default_state(target_registry)["controller"])
    candidate_controller.update(copy.deepcopy(target_config))
    candidate_controller["kind"] = kind
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
        controller_readiness_detail(adapter, readiness_warnings),
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
    except ControllerProtocolNotSupported as exc:
      return [], http_helpers.service_result(self.controller_service.protocol_not_supported_response(exc))
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
      "transport": copy.deepcopy(candidate_controller["transport"]),
      "track_mode": parsed["next_track_mode"],
      "programming_target": parsed["next_programming_target"],
      "track_profiles": parsed["next_profiles"],
      "warnings": warnings,
    }

  def _apply_track_profile_parameters_to_controller(self, controller: dict, profiles: dict, modes: list[str]) -> list[dict]:
    adapter = self.controller_adapter(controller)
    return adapter.apply_track_profile_parameters(
      self.controller_service.controller_session_for_adapter(adapter, controller),
      controller,
      profiles,
      modes,
      transport=self.context.controller_transport,
    )


def controller_transport_identity(
  controller: dict,
) -> tuple:
  transport = controller.get("transport") if isinstance(controller.get("transport"), dict) else {}
  return (
    controller.get("kind", ""),
    controller.get("ip"),
    json.dumps(transport, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
  )


def validate_controller_ip(ip_value) -> str:
  ip_text = str(ip_value or "").strip()
  address = ipaddress.ip_address(ip_text)
  if address.version != 4:
    raise ValueError("controller IP must be IPv4")
  return str(address)

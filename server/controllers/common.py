"""Shared helpers for controller adapters."""

from copy import deepcopy

from server import models


INFO_SECTION_DEVICE = "设备信息"
INFO_SECTION_WORK = "工作状态"


def validate_transport_port(value, label: str, *, allow_zero: bool = False) -> int:
  """Validate a controller transport port field."""
  port = int(value)
  minimum = 0 if allow_zero else 1
  if port < minimum or port > 65535:
    raise ValueError(f"{label} must be in {minimum}..65535")
  return port


def controller_info_sections(*sections: dict) -> list[dict]:
  """Return a deep-copyable info section descriptor list."""
  return [deepcopy(section) for section in sections]


def read_only_session_identity(controller: dict) -> tuple:
  """Return the session identity for stateless read-only controller adapters."""
  return ()


def read_only_controller_client_id(controller: dict) -> int:
  """Return a neutral client id for controller adapters that do not use one."""
  return 0


def read_only_programming_track_status(controller: dict):
  """Return no programming-track status for read-only adapters."""
  return None


def update_cv_safety_from_programming_status(
  controller: dict,
  adapter,
  warnings: list,
  *,
  source: str,
) -> bool:
  """Update cached CV safety from an adapter-owned programming track status."""
  programming_status = adapter.programming_track_status(controller)
  if programming_status is None:
    controller.pop("programming_track_status", None)
    warnings.append("programming_track_status_unconfirmed")
    return False
  controller["programming_track_status"] = {
    "source": source,
    "track_mode": getattr(programming_status, "track_mode", ""),
    "dcc_mode": bool(getattr(programming_status, "dcc_mode", False)),
    "programming_track_busy": bool(getattr(programming_status, "programming_track_busy", True)),
    "programming_track_current_ma": int(getattr(programming_status, "programming_track_current_ma", 0) or 0),
    "output_value": int(getattr(programming_status, "output_value", 0) or 0),
    "current_limit_ma": int(getattr(programming_status, "current_limit_ma", 0) or 0),
    "current_limit_confirmed": bool(getattr(programming_status, "current_limit_confirmed", False)),
  }
  try:
    adapter.validate_programming_track_safety(programming_status)
  except ValueError as exc:
    warnings.append(f"programming_track_safety_failed:{exc}")
    return False
  return True


def controller_not_ready_message() -> str:
  """Return the shared not-ready message for unconfigured controller endpoints."""
  return "控制器通信参数尚未确认"


def endpoint_readiness_warnings(controller: dict, *, port_field: str, port_warning: str) -> list[str]:
  """Build common IP/port readiness warnings for controller endpoints."""
  warnings = []
  if str(controller.get("ip") or "").strip() in ("", models.CONTROLLER_DEFAULT_IP):
    warnings.append("controller_ip_unconfigured")
  if int(controller.get(port_field, 0) or 0) <= 0:
    warnings.append(port_warning)
  return warnings


def endpoint_readiness_detail(warnings: list[str], *, port_warning: str, port_detail: str) -> str:
  """Return a localized endpoint readiness detail."""
  warning_set = set(warnings)
  if warning_set == {"controller_ip_unconfigured"}:
    return "控制器 IP 尚未配置"
  if port_warning in warning_set:
    return port_detail
  return "控制器通信端点尚未确认"


def track_profiles_with_limits(
  *,
  current_limit_ma: int | None = None,
  min_current_limit_ma: int | None = None,
  max_current_limit_ma: int | None = None,
  current_step_ma: int | None = None,
  enabled_modes: set[str] | None = None,
  target_voltage_v: float | None = None,
  min_target_voltage_v: float | None = None,
  max_target_voltage_v: float | None = None,
  voltage_fields: bool = True,
  controller_output_fields: bool = True,
  current_limit_fields: bool = True,
) -> dict:
  """Build default track profiles with controller-specific capability hints."""
  profiles = models.default_track_profiles()
  for mode, profile in profiles.items():
    if not controller_output_fields:
      profile.pop("output_value", None)
      profile.pop("current_param", None)
    if not voltage_fields:
      profile.pop("target_voltage_v", None)
      profile.pop("min_target_voltage_v", None)
      profile.pop("max_target_voltage_v", None)
    if not current_limit_fields:
      profile.pop("min_target_current_limit_ma", None)
      profile.pop("target_current_limit_ma", None)
      profile.pop("max_target_current_limit_ma", None)
      profile.pop("current_step_ma", None)
    elif current_limit_ma is not None:
      profile["target_current_limit_ma"] = current_limit_ma
      profile["max_target_current_limit_ma"] = max_current_limit_ma if max_current_limit_ma is not None else current_limit_ma
    if current_limit_fields:
      if min_current_limit_ma is not None:
        profile["min_target_current_limit_ma"] = min_current_limit_ma
      if max_current_limit_ma is not None:
        profile["max_target_current_limit_ma"] = max_current_limit_ma
      if current_step_ma is not None:
        profile["current_step_ma"] = current_step_ma
    if target_voltage_v is not None:
      profile["target_voltage_v"] = float(target_voltage_v)
    if min_target_voltage_v is not None:
      profile["min_target_voltage_v"] = float(min_target_voltage_v)
    if max_target_voltage_v is not None:
      profile["max_target_voltage_v"] = float(max_target_voltage_v)
    if enabled_modes is not None:
      profile["enabled"] = mode in enabled_modes
  return profiles

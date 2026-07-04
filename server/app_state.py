"""Persistent application state for Digsight-Center."""

from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict

from server import models
from server.controller_config_defaults import (
  CONTROLLER_CONFIG_FIELDS,
  controller_default_config,
  controller_field_descriptions,
)
from server.controller_safety import invalidate_controller_safety
from server.controllers.base import (
  apply_controller_transport_runtime,
  controller_display_name,
  controller_protocol,
  normalize_controller_transport_config,
)
from server.controllers.registry import default_controller_registry


APP_STATE_CORRUPT_RECOVERED_ERROR = "app_state_corrupt_recovered"
CONTROLLER_CONFIG_INVALID_ERROR = "controller_config_invalid"
CONTROLLER_RUNTIME_INVALID_ERROR = "controller_runtime_invalid"

def _write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with tempfile.NamedTemporaryFile(
    "w",
    encoding="utf-8",
    dir=path.parent,
    prefix=f"{path.name}.",
    suffix=".tmp",
    delete=False,
  ) as handle:
    temp_path = Path(handle.name)
    json.dump(payload, handle, ensure_ascii=False, indent=2)
    handle.write("\n")
  try:
    temp_path.replace(path)
  except Exception:
    temp_path.unlink(missing_ok=True)
    raise


def _default_controller_descriptor(controller_registry=None):
  registry = controller_registry or default_controller_registry()
  adapter = registry.get(registry.default_kind)
  return adapter


def default_state(controller_registry=None) -> Dict[str, Any]:
  default_adapter = _default_controller_descriptor(controller_registry)
  transport_descriptor = default_adapter.transport_descriptor
  controller = {
    "kind": default_adapter.kind,
    "ip": default_adapter.default_ip,
    "settings": {},
    "transport": transport_descriptor.default_config(),
    "safety_snapshot": {
      "controller_endpoint_version": 0,
      "last_read_info_at": "",
      "booster_status_fresh": False,
      "programming_track_status_fresh": False,
    },
    "runtime_revision": 0,
    "last_probe_at": "",
    "last_probe_ok": False,
    "controller_reachable": False,
    "controller_unreachable_reason": "not_read",
    "display_name": controller_display_name(default_adapter),
    "field_descriptions": controller_field_descriptions(default_adapter),
    "protocol": controller_protocol(default_adapter),
    "last_controller_seen_at": "",
    "controller_info_status_timeout_seconds": models.CONTROLLER_INFO_STATUS_TIMEOUT_SECONDS,
    "controller_info_poll_timeout_seconds": models.CONTROLLER_INFO_POLL_TIMEOUT_SECONDS,
    "track_mode": models.TRACK_MODE_N,
    "programming_target": models.PROGRAMMING_TARGET_PROGRAMMING_TRACK,
    "dcc_mode_bit": models.DCC_MODE_BIT,
    "n_output_value": models.N_OUTPUT_VALUE,
    "ho_output_value": models.HO_OUTPUT_VALUE,
    "g_output_value": models.G_OUTPUT_VALUE,
    "n_current_param": models.N_CURRENT_PARAM,
    "ho_current_param": models.HO_CURRENT_PARAM,
    "g_current_param": models.G_CURRENT_PARAM,
    "dc_current_param": models.DC_CURRENT_PARAM,
    "current_step_ma": models.CURRENT_STEP_MA,
    "service_mode_limit_ma": models.SERVICE_MODE_LIMIT_MA,
    "telemetry": {
      "temperature_c": None,
      "track_voltage_v": None,
      "track_current_a": None,
      "track_power_w": None,
    },
    "device_info": {
      "device_name": "",
      "factory_number": "",
      "mac_address": "",
      "model": "",
      "hardware_version": "",
      "software_version": "",
      "firmware_version": "",
      "core_version": "",
      "wireless_version": "",
      "railcom_enabled": None,
      "screen_brightness": None,
      "screen_brightness_raw": None,
      "screen_direction_raw": None,
      "screen_direction_label": "",
      "source": "not_read",
    },
    "track_profiles": models.default_track_profiles(),
  }
  apply_controller_transport_runtime(default_adapter, controller)
  return {
    "schema_version": 1,
    "controller": controller,
    "vehicles": [],
    "functions": [],
    "consists": [],
    "imports": [],
    "last_error": None,
  }


class AppStateStore:
  def __init__(
    self,
    path: Path,
    *,
    controller_registry=None,
    controller_config_dir: Path | None = None,
    vehicle_store=None,
  ):
    self.path = Path(path)
    project_root = self.path.parent.parent if self.path.parent.name == "data" else self.path.parent
    self.project_root = project_root
    self.controller_config_dir = Path(controller_config_dir) if controller_config_dir else project_root / "config" / "controllers"
    self.controller_registry = controller_registry or default_controller_registry()
    self.vehicle_store = vehicle_store
    self._save_lock = threading.RLock()

  def load(self) -> Dict[str, Any]:
    with self._save_lock:
      return self._load_unlocked()

  def load_snapshot(self) -> Dict[str, Any]:
    return self.load()

  def save_after_hardware(self, state: Dict[str, Any], *, expected_controller_revision: int | None = None) -> Dict[str, Any]:
    with self._save_lock:
      current = self._load_unlocked()
      if expected_controller_revision is not None:
        current_revision = int(current.get("controller", {}).get("runtime_revision", 0) or 0)
        if current_revision != expected_controller_revision:
          raise ValueError("controller runtime changed during hardware operation")
      self._save_unlocked(state)
      return self._with_defaults(state)

  def _load_unlocked(self) -> Dict[str, Any]:
    if not self.path.exists():
      state = self._app_state_for_disk(default_state(self.controller_registry))
      self._save_unlocked(state)
      return self._with_defaults(state)
    text = self.path.read_text(encoding="utf-8")
    try:
      state = json.loads(text)
    except json.JSONDecodeError as error:
      state = self._recover_first_json_object(text, error)
    return self._with_defaults(state)

  def save(self, state: Dict[str, Any]) -> None:
    with self._save_lock:
      self._save_unlocked(state)

  def _save_unlocked(self, state: Dict[str, Any]) -> None:
    normalized_state = self._with_defaults(state, allow_state_controller_config=True)
    if not self._has_active_controller_config_error(normalized_state):
      self._save_controller_config_unlocked(normalized_state["controller"])
    disk_state = self._app_state_for_disk(normalized_state)
    _write_json_atomic(self.path, disk_state)

  def update(self, mutator, persist=None):
    with self._save_lock:
      state = self._load_unlocked()
      result = mutator(state)
      self._save_unlocked(persist(state) if persist else state)
      return state if result is None else result

  def _recover_first_json_object(self, text: str, original_error: json.JSONDecodeError) -> Dict[str, Any]:
    timestamp = datetime.now().astimezone().strftime("%Y%m%d%H%M%S%f")
    backup_path = self.path.with_name(f"{self.path.name}.corrupt-{timestamp}")
    self.path.replace(backup_path)
    state = default_state(self.controller_registry)
    state["last_error"] = {
      "type": APP_STATE_CORRUPT_RECOVERED_ERROR,
      "detail": str(original_error),
      "backup_file": backup_path.name,
    }
    self._save_unlocked(state)
    return state

  @staticmethod
  def _validated_or_default_with_error(value, default, validator):
    try:
      return validator(value), False
    except (TypeError, ValueError):
      return default, True

  def _registered_controller_kind_or_default(self, value) -> str:
    try:
      controller_kind = models.validate_controller_kind(value)
      self.controller_registry.get(controller_kind)
      return controller_kind
    except (TypeError, ValueError):
      return self.controller_registry.default_kind

  def _controller_default_config(self, controller_kind: str) -> Dict[str, Any]:
    if self.vehicle_store is not None:
      config = self.vehicle_store.controller_default_config_for_kind(controller_kind)
      if config is not None:
        return config
    return self.default_controller_config(self.controller_registry, controller_kind)

  @staticmethod
  def default_controller_config(controller_registry, controller_kind: str) -> Dict[str, Any]:
    return controller_default_config(controller_registry, controller_kind)

  def _controller_config_path(self, controller_kind: str) -> Path:
    return self.controller_config_dir / self.controller_registry.config_file_name(controller_kind)

  def _relative_path(self, path: Path) -> str:
    try:
      return path.relative_to(self.project_root).as_posix()
    except ValueError:
      return path.as_posix()

  def app_state_relative_path(self) -> str:
    return self._relative_path(self.path)

  def controller_config_relative_path(self, controller_kind: str) -> str:
    return self._relative_path(self._controller_config_path(controller_kind))

  @staticmethod
  def is_app_state_corrupt_recovered_error(error: dict | None) -> bool:
    return isinstance(error, dict) and error.get("type") == APP_STATE_CORRUPT_RECOVERED_ERROR

  def _controller_config_error(self, controller_kind: str, error: Exception, global_config_error: dict | None = None) -> Dict[str, Any]:
    config_file = self.controller_config_relative_path(controller_kind)
    payload = {
      "type": CONTROLLER_CONFIG_INVALID_ERROR,
      "message": "当前控制器配置文件无效",
      "detail": str(error),
      "controller_kind": controller_kind,
      "config_file": config_file,
      "resettable_files": self._controller_config_resettable_files(controller_kind, global_config_error),
      "manual_action": "请手工修复该 JSON 文件，或点击重置恢复默认配置。",
    }
    if global_config_error:
      payload["global_config_error"] = global_config_error
    return payload

  @staticmethod
  def _controller_runtime_invalid_error(invalid_fields: list[str]) -> Dict[str, Any]:
    return {
      "type": CONTROLLER_RUNTIME_INVALID_ERROR,
      "message": "控制器运行态配置无效",
      "detail": "控制器运行态字段已恢复默认值，旧控制器状态已失效。",
      "invalid_fields": invalid_fields,
      "manual_action": "请重新读取控制器状态后再执行轨道上电、CV 或车辆控制操作。",
    }

  def _load_controller_config_unlocked(self, controller_kind: str, *, global_config_error: dict | None = None) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    config = self._controller_default_config(controller_kind)
    path = self._controller_config_path(controller_kind)
    if path.exists():
      try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
          raise ValueError(f"controller config must be a JSON object: {path}")
      except (OSError, json.JSONDecodeError, ValueError) as error:
        return config, self._controller_config_error(controller_kind, error, global_config_error)
      config.update({key: value for key, value in data.items() if key in CONTROLLER_CONFIG_FIELDS})
    else:
      self._save_controller_config_payload_unlocked(controller_kind, config)
    config["field_descriptions"] = self._normalized_field_descriptions(controller_kind, config.get("field_descriptions"))
    self._normalize_controller_config_transport(controller_kind, config)
    return config, None

  def _normalized_field_descriptions(self, controller_kind: str, value) -> Dict[str, str]:
    try:
      adapter = self.controller_registry.get(controller_kind)
    except ValueError:
      adapter = None
    descriptions = controller_field_descriptions(adapter)
    if isinstance(value, dict):
      for key, description in value.items():
        if isinstance(key, str) and isinstance(description, str) and description:
          descriptions[key] = description
    return descriptions

  def _normalize_controller_config_transport(self, controller_kind: str, config: Dict[str, Any]) -> None:
    adapter = self.controller_registry.get(controller_kind)
    config["transport"] = normalize_controller_transport_config(
      adapter,
      config.get("transport"),
      strict=False,
    )

  def controller_descriptor_configs(self) -> Dict[str, Dict[str, Any]]:
    with self._save_lock:
      configs = {}
      for controller_kind in self.controller_registry.kinds():
        config, _error = self._load_controller_config_unlocked(controller_kind)
        configs[controller_kind] = config
      return configs

  def controller_config_for_kind(self, controller_kind: str) -> Dict[str, Any]:
    config, _error = self.controller_config_for_kind_with_error(controller_kind)
    return config

  def controller_default_config_for_kind(self, controller_kind: str) -> Dict[str, Any]:
    with self._save_lock:
      kind = self._registered_controller_kind_or_default(controller_kind)
      return self._controller_default_config(kind)

  def controller_config_for_kind_with_error(self, controller_kind: str) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    with self._save_lock:
      kind = self._registered_controller_kind_or_default(controller_kind)
      return self._load_controller_config_unlocked(kind)

  def reset_controller_config(self, controller_kind: str) -> Dict[str, Any]:
    with self._save_lock:
      kind = self._registered_controller_kind_or_default(controller_kind)
      controller_config = self._controller_default_config(kind)
      self._save_controller_config_payload_unlocked(kind, controller_config)
      adapter = self.controller_registry.get(kind)
      config_file = self.controller_config_relative_path(kind)
      return {
        "controller_kind": kind,
        "controller_label": controller_display_name(adapter, controller_config),
        "config_file": config_file,
        "reset_files": self._controller_config_resettable_files(kind),
        "controller": controller_config,
      }

  def _controller_config_resettable_files(self, controller_kind: str, global_config_error: dict | None = None) -> list[str]:
    files = [self.controller_config_relative_path(controller_kind)]
    if self.is_app_state_corrupt_recovered_error(global_config_error):
      files.append(self.app_state_relative_path())
    return files

  def _save_controller_config_unlocked(self, controller: Dict[str, Any]) -> None:
    controller_kind = self._registered_controller_kind_or_default(controller.get("kind"))
    payload = {key: controller[key] for key in sorted(CONTROLLER_CONFIG_FIELDS) if key in controller}
    self._save_controller_config_payload_unlocked(controller_kind, payload)

  def _save_controller_config_payload_unlocked(self, controller_kind: str, payload: Dict[str, Any]) -> None:
    path = self._controller_config_path(controller_kind)
    _write_json_atomic(path, payload)

  @staticmethod
  def _has_active_controller_config_error(state: Dict[str, Any]) -> bool:
    last_error = state.get("last_error")
    return isinstance(last_error, dict) and last_error.get("type") == CONTROLLER_CONFIG_INVALID_ERROR

  @staticmethod
  def clear_controller_config_error_for_kind_change(state: Dict[str, Any], previous_kind: str, next_kind: str) -> None:
    if previous_kind == next_kind:
      return
    last_error = state.get("last_error")
    if not isinstance(last_error, dict) or last_error.get("type") != CONTROLLER_CONFIG_INVALID_ERROR:
      return
    if last_error.get("controller_kind") == next_kind:
      return
    global_config_error = last_error.get("global_config_error")
    state["last_error"] = global_config_error if AppStateStore.is_app_state_corrupt_recovered_error(global_config_error) else None

  def _controller_kind_for_config(self, state_controller: Dict[str, Any], controller_defaults: Dict[str, Any]) -> str:
    return self._registered_controller_kind_or_default(state_controller.get("kind", controller_defaults["kind"]))

  def _controller_runtime_derived_config_fields(self) -> set[str]:
    fields = set()
    for adapter in self.controller_registry.adapters():
      fields.update(getattr(adapter, "runtime_transport_fields", ()))
    return fields

  def _app_state_for_disk(self, state: Dict[str, Any]) -> Dict[str, Any]:
    disk_state = dict(state)
    controller = dict(disk_state.get("controller", {}))
    for key in CONTROLLER_CONFIG_FIELDS | self._controller_runtime_derived_config_fields():
      controller.pop(key, None)
    disk_state["controller"] = controller
    return disk_state

  @staticmethod
  def _state_controller_dict(state: Dict[str, Any]) -> Dict[str, Any]:
    state_controller = state.get("controller", {})
    return state_controller if isinstance(state_controller, dict) else {}

  def _controller_with_config(
    self,
    controller_kind: str,
    controller_defaults: Dict[str, Any],
    state_controller: Dict[str, Any],
    merged: Dict[str, Any],
    allow_state_controller_config: bool,
  ) -> tuple[Dict[str, Any], Dict[str, Any] | None]:
    controller = dict(controller_defaults)
    global_config_error = merged.get("last_error") if isinstance(merged.get("last_error"), dict) else None
    controller_config, controller_config_error = self._load_controller_config_unlocked(
      controller_kind,
      global_config_error=global_config_error if self.is_app_state_corrupt_recovered_error(global_config_error) else None,
    )
    controller.update(controller_config)
    state_controller_overrides = dict(state_controller)
    if not allow_state_controller_config:
      for key in CONTROLLER_CONFIG_FIELDS:
        state_controller_overrides.pop(key, None)
    controller.update(state_controller_overrides)
    return controller, controller_config_error

  @staticmethod
  def _merge_runtime_controller_sections(
    controller: Dict[str, Any],
    state_controller: Dict[str, Any],
    controller_defaults: Dict[str, Any],
  ) -> None:
    controller["telemetry"] = {
      **controller_defaults["telemetry"],
      **state_controller.get("telemetry", {}),
    }
    controller["device_info"] = {
      **controller_defaults["device_info"],
      **state_controller.get("device_info", {}),
    }
    controller["safety_snapshot"] = {
      **controller_defaults["safety_snapshot"],
      **state_controller.get("safety_snapshot", {}),
    }
    screen_direction_label = models.screen_direction_label(controller["device_info"].get("screen_direction_raw"))
    if screen_direction_label:
      controller["device_info"]["screen_direction_label"] = screen_direction_label

  @staticmethod
  def _normalized_track_profiles(controller: Dict[str, Any], track_profile_defaults: Dict[str, Any]) -> Dict[str, Any]:
    track_profiles = {mode: dict(profile) for mode, profile in track_profile_defaults.items()}
    for mode, profile in controller.get("track_profiles", {}).items():
      if mode in track_profiles:
        profile_defaults = track_profile_defaults[mode]
        track_profiles[mode] = models.validate_track_profile(mode, profile, defaults=profile_defaults)
        for fixed_key in (
          "output_value",
          "current_param",
          "min_target_voltage_v",
          "max_target_voltage_v",
          "max_target_current_limit_ma",
        ):
          if fixed_key in profile_defaults:
            track_profiles[mode][fixed_key] = profile_defaults[fixed_key]
          else:
            track_profiles[mode].pop(fixed_key, None)
        for key, value in profile_defaults.items():
          track_profiles[mode].setdefault(key, value)
    return track_profiles

  def _normalize_controller_transport(self, controller: Dict[str, Any]) -> list[str]:
    controller["kind"] = self._registered_controller_kind_or_default(controller.get("kind"))
    adapter = self.controller_registry.get(controller["kind"])
    self._normalize_controller_config_transport(controller["kind"], controller)
    controller["display_name"] = controller_display_name(adapter, controller)
    controller["protocol"] = controller_protocol(adapter, controller)
    invalid_runtime_fields = []
    track_mode, track_mode_invalid = self._validated_or_default_with_error(
      controller.get("track_mode", models.TRACK_MODE_N),
      models.TRACK_MODE_N,
      models.validate_profile_mode,
    )
    programming_target, programming_target_invalid = self._validated_or_default_with_error(
      controller.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK),
      models.PROGRAMMING_TARGET_PROGRAMMING_TRACK,
      models.validate_programming_target,
    )
    controller["track_mode"] = track_mode
    controller["programming_target"] = programming_target
    enabled_track_mode = self._first_enabled_track_mode(controller["track_profiles"], fallback=models.TRACK_MODE_N)
    selected_profile = controller["track_profiles"].get(track_mode)
    if isinstance(selected_profile, dict) and selected_profile.get("enabled") is False:
      controller["track_mode"] = enabled_track_mode
      invalid_runtime_fields.append("track_mode")
    if track_mode_invalid:
      invalid_runtime_fields.append("track_mode")
    if programming_target_invalid:
      invalid_runtime_fields.append("programming_target")
    apply_controller_transport_runtime(adapter, controller)
    return invalid_runtime_fields

  @staticmethod
  def _first_enabled_track_mode(track_profiles: Dict[str, Any], *, fallback: str) -> str:
    for mode in (models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G, models.TRACK_MODE_DC):
      profile = track_profiles.get(mode)
      if not isinstance(profile, dict) or profile.get("enabled") is not False:
        return mode
    return fallback

  def _with_defaults(self, state: Dict[str, Any], *, allow_state_controller_config: bool = False) -> Dict[str, Any]:
    defaults = default_state(self.controller_registry)
    controller_defaults = defaults["controller"]
    merged = dict(defaults)
    merged.update(state)
    state_controller = self._state_controller_dict(state)
    controller_kind = self._controller_kind_for_config(state_controller, controller_defaults)
    track_profile_defaults = self._controller_default_config(controller_kind).get("track_profiles", controller_defaults["track_profiles"])
    controller, controller_config_error = self._controller_with_config(
      controller_kind,
      controller_defaults,
      state_controller,
      merged,
      allow_state_controller_config,
    )
    merged["controller"] = controller
    self._merge_runtime_controller_sections(controller, state_controller, controller_defaults)
    controller["track_profiles"] = self._normalized_track_profiles(controller, track_profile_defaults)
    if controller_config_error:
      merged["last_error"] = controller_config_error
    if not isinstance(controller.get("settings"), dict):
      controller["settings"] = {}
    invalid_runtime_fields = self._normalize_controller_transport(controller)
    if invalid_runtime_fields:
      invalidate_controller_safety(controller, reason="invalid_runtime_controller_settings")
      if not controller_config_error:
        merged["last_error"] = self._controller_runtime_invalid_error(invalid_runtime_fields)
    return merged

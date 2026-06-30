"""Persistent application state for Digsight-Center."""

from datetime import datetime
import json
from pathlib import Path
import tempfile
import threading
from typing import Any, Dict

from server import models
from server.controllers.base import ControllerTransportDefaults
from server.controllers.registry import default_controller_registry


UNREGISTERED_CONTROLLER_TRANSPORT_DEFAULTS = ControllerTransportDefaults(
  udp_port=0,
  local_udp_port=0,
  checksum_algorithm="unconfirmed",
  checksum_algorithms=("unconfirmed",),
  allow_zero_local_udp_port=True,
)
CONTROLLER_CONFIG_FIELDS = {
  "ip",
  "settings",
  "udp_port",
  "local_udp_port",
  "udp_checksum_algorithm",
  "track_profiles",
}


def _default_controller_descriptor(controller_registry=None):
  registry = controller_registry or default_controller_registry()
  adapter = registry.get(registry.default_kind)
  return adapter


def default_state(controller_registry=None) -> Dict[str, Any]:
  default_adapter = _default_controller_descriptor(controller_registry)
  transport_defaults = default_adapter.transport_defaults
  return {
    "schema_version": 1,
    "controller": {
      "kind": default_adapter.kind,
      "ip": default_adapter.default_ip,
      "settings": {},
      "udp_port": transport_defaults.udp_port,
      "local_udp_port": transport_defaults.local_udp_port,
      "udp_checksum_algorithm": transport_defaults.checksum_algorithm,
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
    },
    "vehicles": [],
    "functions": [],
    "consists": [],
    "imports": [],
    "last_error": None,
  }


class AppStateStore:
  def __init__(self, path: Path, *, controller_registry=None, controller_config_dir: Path | None = None):
    self.path = Path(path)
    project_root = self.path.parent.parent if self.path.parent.name == "data" else self.path.parent
    self.controller_config_dir = Path(controller_config_dir) if controller_config_dir else project_root / "config" / "controllers"
    self.controller_registry = controller_registry or default_controller_registry()
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
    self._save_controller_config_unlocked(normalized_state["controller"])
    disk_state = self._app_state_for_disk(normalized_state)
    self.path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
      "w",
      encoding="utf-8",
      dir=self.path.parent,
      prefix=f"{self.path.name}.",
      suffix=".tmp",
      delete=False,
    ) as handle:
      temp_path = Path(handle.name)
      json.dump(disk_state, handle, ensure_ascii=False, indent=2)
      handle.write("\n")
    try:
      temp_path.replace(self.path)
    except Exception:
      temp_path.unlink(missing_ok=True)
      raise

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
      "type": "app_state_corrupt_recovered",
      "detail": str(original_error),
      "backup_file": backup_path.name,
    }
    self._save_unlocked(state)
    return state

  @staticmethod
  def _validated_or_default(value, default, validator):
    try:
      return validator(value)
    except (TypeError, ValueError):
      return default

  @staticmethod
  def _positive_int_or_default(value, default: int) -> int:
    try:
      normalized = int(value)
    except (TypeError, ValueError):
      return default
    return normalized if normalized > 0 else default

  @classmethod
  def _local_udp_port_or_default(cls, value, transport_defaults: ControllerTransportDefaults) -> int:
    try:
      normalized = int(value)
    except (TypeError, ValueError):
      return transport_defaults.local_udp_port
    if normalized < 0:
      return transport_defaults.local_udp_port
    if normalized == 0 and not transport_defaults.allow_zero_local_udp_port:
      return transport_defaults.local_udp_port
    return normalized

  def _registered_controller_kind_or_default(self, value) -> str:
    try:
      controller_kind = models.validate_controller_kind(value)
      self.controller_registry.get(controller_kind)
      return controller_kind
    except (TypeError, ValueError):
      return self.controller_registry.default_kind

  def _controller_transport_defaults(self, controller_kind: str) -> ControllerTransportDefaults:
    try:
      return self.controller_registry.get(controller_kind).transport_defaults
    except ValueError:
      return UNREGISTERED_CONTROLLER_TRANSPORT_DEFAULTS

  def _controller_default_config(self, controller_kind: str) -> Dict[str, Any]:
    try:
      adapter = self.controller_registry.get(controller_kind)
      transport_defaults = adapter.transport_defaults
      default_ip = adapter.default_ip
    except ValueError:
      transport_defaults = UNREGISTERED_CONTROLLER_TRANSPORT_DEFAULTS
      default_ip = models.CONTROLLER_DEFAULT_IP
    return {
      "ip": default_ip,
      "settings": {},
      "udp_port": transport_defaults.udp_port,
      "local_udp_port": transport_defaults.local_udp_port,
      "udp_checksum_algorithm": transport_defaults.checksum_algorithm,
      "track_profiles": models.default_track_profiles(),
    }

  def _controller_config_path(self, controller_kind: str) -> Path:
    return self.controller_config_dir / self.controller_registry.config_file_name(controller_kind)

  def _load_controller_config_unlocked(self, controller_kind: str) -> Dict[str, Any]:
    config = self._controller_default_config(controller_kind)
    path = self._controller_config_path(controller_kind)
    if path.exists():
      data = json.loads(path.read_text(encoding="utf-8"))
      if not isinstance(data, dict):
        raise ValueError(f"controller config must be a JSON object: {path}")
      config.update({key: value for key, value in data.items() if key in CONTROLLER_CONFIG_FIELDS})
    return config

  def _save_controller_config_unlocked(self, controller: Dict[str, Any]) -> None:
    controller_kind = self._registered_controller_kind_or_default(controller.get("kind"))
    path = self._controller_config_path(controller_kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {key: controller[key] for key in sorted(CONTROLLER_CONFIG_FIELDS) if key in controller}
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

  def _controller_kind_for_config(self, state_controller: Dict[str, Any], controller_defaults: Dict[str, Any]) -> str:
    return self._registered_controller_kind_or_default(state_controller.get("kind", controller_defaults["kind"]))

  @staticmethod
  def _app_state_for_disk(state: Dict[str, Any]) -> Dict[str, Any]:
    disk_state = dict(state)
    controller = dict(disk_state.get("controller", {}))
    for key in CONTROLLER_CONFIG_FIELDS:
      controller.pop(key, None)
    disk_state["controller"] = controller
    return disk_state

  def _with_defaults(self, state: Dict[str, Any], *, allow_state_controller_config: bool = False) -> Dict[str, Any]:
    defaults = default_state(self.controller_registry)
    controller_defaults = defaults["controller"]
    telemetry_defaults = controller_defaults["telemetry"]
    device_info_defaults = controller_defaults["device_info"]
    safety_snapshot_defaults = controller_defaults["safety_snapshot"]
    track_profile_defaults = controller_defaults["track_profiles"]
    merged = dict(defaults)
    merged.update(state)
    state_controller = state.get("controller", {})
    if not isinstance(state_controller, dict):
      state_controller = {}
    controller = dict(controller_defaults)
    controller_kind = self._controller_kind_for_config(state_controller, controller_defaults)
    controller.update(self._load_controller_config_unlocked(controller_kind))
    state_controller_overrides = dict(state_controller)
    if not allow_state_controller_config:
      for key in CONTROLLER_CONFIG_FIELDS:
        state_controller_overrides.pop(key, None)
    controller.update(state_controller_overrides)
    merged["controller"] = controller
    controller["telemetry"] = {
      **telemetry_defaults,
      **state_controller.get("telemetry", {}),
    }
    controller["device_info"] = {
      **device_info_defaults,
      **state_controller.get("device_info", {}),
    }
    controller["safety_snapshot"] = {
      **safety_snapshot_defaults,
      **state_controller.get("safety_snapshot", {}),
    }
    screen_direction_label = models.screen_direction_label(controller["device_info"].get("screen_direction_raw"))
    if screen_direction_label:
      controller["device_info"]["screen_direction_label"] = screen_direction_label
    track_profiles = {mode: dict(profile) for mode, profile in track_profile_defaults.items()}
    for mode, profile in controller.get("track_profiles", {}).items():
      if mode in track_profiles:
        defaults = track_profile_defaults[mode]
        track_profiles[mode].update(profile)
        track_profiles[mode]["output_value"] = defaults["output_value"]
        track_profiles[mode]["current_param"] = defaults["current_param"]
        track_profiles[mode]["max_voltage_v"] = defaults["max_voltage_v"]
        track_profiles[mode]["max_current_limit_ma"] = defaults["max_current_limit_ma"]
    controller["track_profiles"] = track_profiles
    controller["kind"] = self._registered_controller_kind_or_default(controller.get("kind"))
    if not isinstance(controller.get("settings"), dict):
      controller["settings"] = {}
    controller["track_mode"] = self._validated_or_default(
      controller.get("track_mode", models.TRACK_MODE_N),
      models.TRACK_MODE_N,
      models.validate_profile_mode,
    )
    controller["programming_target"] = self._validated_or_default(
      controller.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK),
      models.PROGRAMMING_TARGET_PROGRAMMING_TRACK,
      models.validate_programming_target,
    )
    controller["udp_port"] = self._positive_int_or_default(
      controller.get("udp_port"),
      self._controller_transport_defaults(controller["kind"]).udp_port,
    )
    controller["local_udp_port"] = self._local_udp_port_or_default(
      controller.get("local_udp_port"),
      self._controller_transport_defaults(controller["kind"]),
    )
    if (controller.get("udp_checksum_algorithm") or "unconfirmed") == "unconfirmed":
      controller["udp_checksum_algorithm"] = self._controller_transport_defaults(controller["kind"]).checksum_algorithm
    return merged

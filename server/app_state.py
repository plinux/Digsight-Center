"""Persistent application state for Digsight-Center."""

from datetime import datetime
import json
from pathlib import Path
import secrets
import tempfile
import threading
from typing import Any, Dict

from server import models


def default_state() -> Dict[str, Any]:
  return {
    "schema_version": 1,
    "controller": {
      "kind": models.CONTROLLER_KIND_DIGSIGHT,
      "ip": models.CONTROLLER_DEFAULT_IP,
      "settings": {},
      "udp_port": models.DXDCNET_DEFAULT_UDP_PORT,
      "local_udp_port": models.DXDCNET_DEFAULT_LOCAL_UDP_PORT,
      "udp_checksum_algorithm": models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM,
      "operation_token": secrets.token_urlsafe(24),
      "safety_snapshot": {
        "controller_endpoint_version": 0,
        "last_read_info_at": "",
        "booster_status_fresh": False,
        "programming_track_status_fresh": False,
      },
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
  def __init__(self, path: Path):
    self.path = Path(path)
    self._save_lock = threading.RLock()

  def load(self) -> Dict[str, Any]:
    with self._save_lock:
      return self._load_unlocked()

  def _load_unlocked(self) -> Dict[str, Any]:
    if not self.path.exists():
      state = default_state()
      self._save_unlocked(state)
      return state
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
      json.dump(self._with_defaults(state), handle, ensure_ascii=False, indent=2)
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
    state = default_state()
    state["last_error"] = {
      "type": "app_state_corrupt_recovered",
      "detail": str(original_error),
      "backup_file": backup_path.name,
    }
    self._save_unlocked(state)
    return state

  def _with_defaults(self, state: Dict[str, Any]) -> Dict[str, Any]:
    defaults = default_state()
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
    controller.update(state_controller)
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
    for mode, profile in state_controller.get("track_profiles", {}).items():
      if mode in track_profiles:
        defaults = track_profile_defaults[mode]
        track_profiles[mode].update(profile)
        track_profiles[mode]["output_value"] = defaults["output_value"]
        track_profiles[mode]["current_param"] = defaults["current_param"]
        track_profiles[mode]["max_voltage_v"] = defaults["max_voltage_v"]
        track_profiles[mode]["max_current_limit_ma"] = defaults["max_current_limit_ma"]
    controller["track_profiles"] = track_profiles
    try:
      controller["kind"] = models.validate_controller_kind(controller.get("kind", models.CONTROLLER_KIND_DIGSIGHT))
    except (TypeError, ValueError):
      controller["kind"] = models.CONTROLLER_KIND_DIGSIGHT
    if not isinstance(controller.get("settings"), dict):
      controller["settings"] = {}
    try:
      controller["track_mode"] = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      controller["track_mode"] = models.TRACK_MODE_N
    try:
      controller["programming_target"] = models.validate_programming_target(
        controller.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK)
      )
    except (TypeError, ValueError):
      controller["programming_target"] = models.PROGRAMMING_TARGET_PROGRAMMING_TRACK
    try:
      if int(controller.get("udp_port", 0)) <= 0:
        controller["udp_port"] = models.DXDCNET_DEFAULT_UDP_PORT
    except (TypeError, ValueError):
      controller["udp_port"] = models.DXDCNET_DEFAULT_UDP_PORT
    try:
      if int(controller.get("local_udp_port", 0)) <= 0:
        controller["local_udp_port"] = models.DXDCNET_DEFAULT_LOCAL_UDP_PORT
    except (TypeError, ValueError):
      controller["local_udp_port"] = models.DXDCNET_DEFAULT_LOCAL_UDP_PORT
    if (controller.get("udp_checksum_algorithm") or "unconfirmed") == "unconfirmed":
      controller["udp_checksum_algorithm"] = models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM
    return merged

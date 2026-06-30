"""DXDCNet controller read-info response parser."""

from datetime import datetime

from server import models
from server.controller_safety import mark_controller_safety_fresh
from server.controllers.dxdcnet_constants import (
  CURRENT_LIMIT_PARAM_TO_MODE,
  PARAM_RAILCOM,
  PARAM_SCREEN_BRIGHTNESS,
  PARAM_SCREEN_DIRECTION,
)
from server.controllers.dxdcnet_info_helpers import apply_parameter_spec, merge_device_info, version_fields
from digsight_dxdcnet.constants import (
  CMD_DEVICE_STATUS,
  CMD_MAC_ADDRESS,
  CMD_PARAMETER_VALUE,
  CMD_VERSION_DATA,
  DEVICE_TYPE_BOOSTER,
  DEVICE_TYPE_COMMAND_STATION,
  DEVICE_TYPE_SPECIAL,
)
from digsight_dxdcnet.device_status import (
  parse_booster_status,
  parse_command_station_status,
  parse_mac_response,
  parse_parameter_response,
  parse_version_response,
)
from digsight_dxdcnet.matchers import first_matching_frame
from digsight_dxdcnet.programming_track import (
  PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED,
  ProgrammingTrackSafety,
  ProgrammingTrackStatus,
)


class DXDCNetControllerInfoParser:
  def apply(self, controller: dict, track_mode: str, current_param: int, collected: dict, read_warnings: list) -> dict:
    warnings = list(read_warnings)
    command_station_status = None
    booster_status = None
    parameter_value = None

    self._apply_version(controller, collected, warnings)
    self._apply_core_version(controller, collected, warnings)
    self._apply_wireless_version(controller, collected, warnings)
    self._apply_railcom(controller, collected, warnings)
    self._apply_screen_brightness(controller, collected, warnings)
    self._apply_screen_direction(controller, collected, warnings)
    self._apply_mac(controller, collected, warnings)
    command_station_status = self._apply_command_station_status(controller, collected, warnings)
    booster_status = self._apply_booster_status(controller, collected, warnings)
    parameter_value = self._apply_current_limits(controller, track_mode, current_param, collected, warnings)

    safe_for_cv = self._update_programming_track_status(
      controller,
      track_mode,
      command_station_status,
      booster_status,
      parameter_value,
      warnings,
    )
    mark_controller_safety_fresh(
      controller,
      booster_status_fresh=booster_status is not None,
      programming_track_status_fresh=command_station_status is not None and booster_status is not None,
    )
    return {
      "safe_for_cv": safe_for_cv,
      "warnings": warnings,
    }

  def _apply_version(self, controller: dict, collected: dict, warnings: list) -> None:
    version_frame = first_matching_frame(collected.get("version", []), CMD_VERSION_DATA)
    if version_frame is None:
      warnings.append("version_response_missing")
      return
    try:
      version = version_fields(
        parse_version_response(version_frame.payload),
        source="dxdcnet_version_0x85",
        response_hex=version_frame.to_debug_dict()["payload_hex"],
      )
      merge_device_info(controller, **version)
    except ValueError as exc:
      warnings.append(f"version_parse_error:{exc}")

  def _apply_core_version(self, controller: dict, collected: dict, warnings: list) -> None:
    version_core_frame = first_matching_frame(collected.get("version_core", []), CMD_VERSION_DATA, DEVICE_TYPE_SPECIAL)
    if version_core_frame is None:
      warnings.append("core_version_response_missing")
      return
    try:
      version = version_fields(
        parse_version_response(version_core_frame.payload),
        source="dxdcnet_version_0x85_special_15",
      )
      merge_device_info(
        controller,
        **{
          "device_name": controller.get("device_info", {}).get("device_name") or "DXDC9000",
          "device_name_source": "official_app_d9000_default",
          "core_version": version["app_version"],
          "core_hardware_version_raw": version["hardware_version_raw"],
          "core_software_version_raw": version["software_version_raw"],
          "core_version_source": version["source"],
        },
      )
    except ValueError as exc:
      warnings.append(f"core_version_parse_error:{exc}")

  def _apply_wireless_version(self, controller: dict, collected: dict, warnings: list) -> None:
    version_wireless_frame = first_matching_frame(collected.get("version_wireless", []), CMD_VERSION_DATA, DEVICE_TYPE_BOOSTER)
    if version_wireless_frame is None:
      warnings.append("wireless_version_response_missing")
      return
    try:
      version = version_fields(
        parse_version_response(version_wireless_frame.payload),
        source="dxdcnet_version_0x85_booster_1",
      )
      merge_device_info(
        controller,
        **{
          "wireless_version": version["app_version"],
          "wireless_hardware_version_raw": version["hardware_version_raw"],
          "wireless_software_version_raw": version["software_version_raw"],
          "wireless_version_source": version["source"],
        },
      )
    except ValueError as exc:
      warnings.append(f"wireless_version_parse_error:{exc}")

  def _apply_railcom(self, controller: dict, collected: dict, warnings: list) -> None:
    railcom_frame = first_matching_frame(collected.get("railcom", []), CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION)
    if railcom_frame is None:
      warnings.append("railcom_response_missing")
      return
    try:
      railcom = parse_parameter_response(railcom_frame.payload)
      apply_parameter_spec(
        controller,
        railcom,
        expected_param=PARAM_RAILCOM,
        warning_prefix="railcom",
        fields=lambda value: {
          "railcom_enabled": (value["value"] & 0x80) == 0x80,
          "railcom_value_raw": value["value"],
          "railcom_source": "dxdcnet_parameter_0x03",
        },
        warnings=warnings,
      )
    except ValueError as exc:
      warnings.append(f"railcom_parse_error:{exc}")

  def _apply_screen_brightness(self, controller: dict, collected: dict, warnings: list) -> None:
    screen_brightness_frame = first_matching_frame(
      collected.get("screen_brightness", []),
      CMD_PARAMETER_VALUE,
      DEVICE_TYPE_COMMAND_STATION,
    )
    if screen_brightness_frame is None:
      warnings.append("screen_brightness_response_missing")
      return
    try:
      brightness = parse_parameter_response(screen_brightness_frame.payload)
      apply_parameter_spec(
        controller,
        brightness,
        expected_param=PARAM_SCREEN_BRIGHTNESS,
        warning_prefix="screen_brightness",
        fields=lambda value: {
          "screen_brightness": value["value"],
          "screen_brightness_raw": value["value"],
          "screen_brightness_source": "dxdcnet_parameter_0x7e",
        },
        warnings=warnings,
      )
    except ValueError as exc:
      warnings.append(f"screen_brightness_parse_error:{exc}")

  def _apply_screen_direction(self, controller: dict, collected: dict, warnings: list) -> None:
    screen_direction_frame = first_matching_frame(
      collected.get("screen_direction", []),
      CMD_PARAMETER_VALUE,
      DEVICE_TYPE_COMMAND_STATION,
    )
    if screen_direction_frame is None:
      warnings.append("screen_direction_response_missing")
      return
    try:
      direction = parse_parameter_response(screen_direction_frame.payload)
      apply_parameter_spec(
        controller,
        direction,
        expected_param=PARAM_SCREEN_DIRECTION,
        warning_prefix="screen_direction",
        fields=lambda value: {
          "screen_direction_raw": value["value"],
          "screen_direction_label": models.screen_direction_label(value["value"]),
          "screen_direction_source": "dxdcnet_parameter_0x80",
        },
        warnings=warnings,
      )
    except ValueError as exc:
      warnings.append(f"screen_direction_parse_error:{exc}")

  def _apply_mac(self, controller: dict, collected: dict, warnings: list) -> None:
    mac_frames = [
      frame for frame in collected.get("mac", [])
      if frame.command == CMD_MAC_ADDRESS and frame.device_type == DEVICE_TYPE_COMMAND_STATION
    ]
    mac_parts = {}
    for frame in mac_frames:
      try:
        mac_part = parse_mac_response(frame.payload)
        mac_parts[mac_part["address_type"]] = mac_part
      except ValueError as exc:
        warnings.append(f"mac_parse_error:{exc}")
    if not mac_parts:
      warnings.append("mac_response_missing")
      return
    low_hex = mac_parts.get(0, {}).get("app_order_hex", "")
    high_hex = mac_parts.get(1, {}).get("app_order_hex", "")
    mac_hex = low_hex + high_hex
    merge_device_info(
      controller,
      **{
        "mac_address": mac_hex,
        "mac_address_parts": mac_parts,
        "factory_number": mac_hex,
        "factory_number_source": "dxdcnet_mac_0x0c",
      },
    )
    if 0 not in mac_parts or 1 not in mac_parts:
      warnings.append("mac_response_incomplete")

  def _apply_command_station_status(self, controller: dict, collected: dict, warnings: list):
    command_station_frame = first_matching_frame(
      collected.get("command_station_status", []),
      CMD_DEVICE_STATUS,
      DEVICE_TYPE_COMMAND_STATION,
    )
    if command_station_frame is None:
      warnings.append("command_station_status_missing")
      return None
    try:
      command_station_status = parse_command_station_status(command_station_frame.payload)
      command_station_status["source"] = "dxdcnet_status_0x23"
      command_station_status["payload_hex"] = command_station_frame.payload.hex(" ")
      controller["command_station_status"] = command_station_status
      return command_station_status
    except ValueError as exc:
      warnings.append(f"command_station_status_parse_error:{exc}")
      return None

  def _apply_booster_status(self, controller: dict, collected: dict, warnings: list):
    booster_frame = first_matching_frame(collected.get("booster_status", []), CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER)
    if booster_frame is None:
      warnings.append("booster_status_missing")
      self._clear_cached_track_status(controller)
      controller["controller_reachable"] = False
      controller["controller_unreachable_reason"] = "booster_status_missing"
      return None
    try:
      booster_status = parse_booster_status(booster_frame.payload)
      booster_status["source"] = "dxdcnet_status_0x23"
      booster_status["payload_hex"] = booster_frame.payload.hex(" ")
      controller["booster_status"] = booster_status
      controller["controller_reachable"] = True
      controller["controller_unreachable_reason"] = ""
      controller["last_controller_seen_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
      voltage = booster_status["output_voltage_v"]
      current = booster_status["output_current_a"]
      controller["telemetry"] = {
        **controller.get("telemetry", {}),
        "temperature_c": booster_status["temperature_c"],
        "track_voltage_v": voltage,
        "track_current_a": current,
        "track_power_w": round(voltage * current, 3),
      }
      return booster_status
    except ValueError as exc:
      warnings.append(f"booster_status_parse_error:{exc}")
      self._clear_cached_track_status(controller)
      controller["controller_reachable"] = False
      controller["controller_unreachable_reason"] = "booster_status_parse_error"
      return None

  def _clear_cached_track_status(self, controller: dict) -> None:
    controller.pop("booster_status", None)
    controller.pop("programming_track_status", None)

  def _apply_current_limits(self, controller: dict, track_mode: str, current_param: int, collected: dict, warnings: list):
    profiles = controller.get("track_profiles", models.default_track_profiles())
    parameter_value = None
    for param_address, mode in CURRENT_LIMIT_PARAM_TO_MODE.items():
      parameter_frame = first_matching_frame(collected.get(f"current_limit_{mode}", []), CMD_PARAMETER_VALUE)
      if parameter_frame is None:
        warnings.append(f"current_limit_{mode}_response_missing")
        continue
      try:
        parsed_parameter = parse_parameter_response(parameter_frame.payload)
        if parsed_parameter["param_address"] == param_address:
          profiles.setdefault(mode, models.default_track_profiles()[mode])
          profiles[mode]["target_current_limit_ma"] = parsed_parameter.get("current_limit_ma")
          profiles[mode]["current_limit_raw"] = parsed_parameter["value"]
          if parsed_parameter["param_address"] == current_param:
            parameter_value = parsed_parameter
        else:
          warnings.append(f"current_limit_{mode}_param_mismatch")
      except ValueError as exc:
        warnings.append(f"current_limit_{mode}_parse_error:{exc}")
    controller["track_profiles"] = profiles
    return parameter_value

  def _update_programming_track_status(
    self,
    controller: dict,
    track_mode: str,
    command_station_status: dict | None,
    booster_status: dict | None,
    parameter_value: dict | None,
    warnings: list,
  ) -> bool:
    del parameter_value
    if command_station_status is None or booster_status is None:
      controller.pop("programming_track_status", None)
      return False
    default_profile = models.default_track_profiles()[track_mode]
    output_value = int(booster_status.get("set_voltage_raw", -1)) if booster_status else -1
    programming_track_current_limit_ma = command_station_status.get("programming_track_current_limit_ma") if command_station_status else None
    programming_track_current_limit_confirmed = programming_track_current_limit_ma is not None
    status = {
      "source": "dxdcnet_status_0x23_unsafe",
      "track_mode": track_mode,
      "dcc_mode": bool(booster_status.get("dcc_mode", False)) if booster_status else False,
      "programming_track_busy": bool(command_station_status.get("programming_track_busy", True)) if command_station_status else True,
      "programming_track_current_ma": int(command_station_status.get("programming_track_current_raw", 999)) if command_station_status else 999,
      "programming_track_current_raw": int(command_station_status.get("programming_track_current_raw", 0)) if command_station_status else None,
      "output_value": output_value,
      "expected_output_value": default_profile["output_value"],
      "current_limit_ma": int(programming_track_current_limit_ma or 0),
      "current_limit_confirmed": programming_track_current_limit_confirmed,
      "current_param": default_profile["current_param"],
    }
    if booster_status and not booster_status.get("dcc_mode", False):
      warnings.append("booster_dc_mode_reported")
    if programming_track_current_limit_ma is None:
      warnings.append("programming_track_current_limit_unconfirmed")
    try:
      ProgrammingTrackSafety().validate(ProgrammingTrackStatus(
        track_mode=status["track_mode"],
        dcc_mode=status["dcc_mode"],
        programming_track_busy=status["programming_track_busy"],
        programming_track_current_ma=status["programming_track_current_ma"],
        output_value=status["output_value"],
        current_limit_ma=status["current_limit_ma"],
        current_limit_confirmed=status["current_limit_confirmed"],
      ))
    except ValueError as exc:
      if str(exc) != PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED:
        warnings.append(f"programming_track_safety_failed:{exc}")
      controller["programming_track_status"] = status
      return False
    status["source"] = "dxdcnet_status_0x23"
    controller["programming_track_status"] = status
    return True

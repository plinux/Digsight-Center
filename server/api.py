"""HTTP API routing."""

import base64
import binascii
import copy
from datetime import datetime
import ipaddress
import json
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
import uuid

from server import response
from server.controller_safety import ControllerSafetySnapshot, invalidate_controller_safety, mark_controller_safety_fresh
from server.controller_probe import probe_ip, probe_ip_with_runner
from server.controllers.registry import default_controller_registry
from server.cv_catalog import cv_meaning, default_cv_catalog, manufacturer_name
from server.cv_read_session import CVReadSessionRegistry
from server.cv_metadata import cv_metadata
from digsight_dxdcnet.constants import (
  CMD_DEVICE_STATUS,
  CMD_LOCO_CONTROL_ACK,
  CMD_LOCO_FUNCTION,
  CMD_LOCO_SPEED,
  CMD_MAC_ADDRESS,
  CMD_PARAMETER_VALUE,
  CMD_PROGRAM_TRACK_ACK,
  CMD_PROGRAM_TRACK_VALUE,
  CMD_VERSION_DATA,
  DEVICE_TYPE_BOOSTER,
  DEVICE_TYPE_COMMAND_STATION,
  DEVICE_TYPE_SPECIAL,
  DEVICE_TYPE_THROTTLE,
  PROGRAMMER_ACK_ACK,
  PROGRAMMER_ACK_BUSY,
  PROGRAMMER_OP_MAIN_LOCO_POM,
)
from digsight_dxdcnet.device_commands import (
  build_mac_request_frame,
  build_parameter_read_frame,
  build_parameter_write_frame,
  build_status_request_frame,
  build_track_output_frame,
  build_version_request_frame,
)
from digsight_dxdcnet.device_status import (
  parse_booster_status,
  parse_command_station_status,
  parse_mac_response,
  parse_parameter_response,
  parse_version_response,
)
from digsight_dxdcnet.frames import decode_udp_frame
from digsight_dxdcnet.loco_control import (
  build_loco_control_request_frame,
  build_loco_function_frames,
  build_loco_speed_frame,
  parse_loco_control_ack,
  parse_loco_function_feedback,
  parse_loco_speed_feedback,
  validate_loco_address,
  validate_loco_speed,
)
from digsight_dxdcnet.matchers import (
  build_programmer_ack_matcher,
  build_programmer_value_matcher,
  build_raw_frame_matcher,
  first_matching_frame,
)
from digsight_dxdcnet.programming_track import (
  CVReadPlan,
  CVWritePlan,
  PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED,
  ProgrammingTrackSafety,
  ProgrammingTrackStatus,
)
from digsight_dxdcnet.programmer import build_cv_read_frame, build_cv_write_frame, parse_programmer_ack, parse_programmer_value
from digsight_dxdcnet.session import DXDCNetSessionManager
from server.importers.base import ConfigImportRequest
from server.importers.registry import default_import_registry
from server import models
from train_dcc.address import build_vehicle_address_writes, decode_vehicle_address
from train_dcc.cv import validate_cv_number


PARAM_RAILCOM = 0x03
PARAM_SCREEN_BRIGHTNESS = 0x7E
PARAM_SCREEN_DIRECTION = 0x80
SCREEN_DIRECTION_LABELS = models.SCREEN_DIRECTION_LABELS
CURRENT_LIMIT_PARAM_TO_MODE = {
  models.N_CURRENT_PARAM: models.TRACK_MODE_N,
  models.HO_CURRENT_PARAM: models.TRACK_MODE_HO,
  models.G_CURRENT_PARAM: models.TRACK_MODE_G,
  models.DC_CURRENT_PARAM: models.TRACK_MODE_DC,
}
MODE_TO_CURRENT_LIMIT_PARAM = {mode: param for param, mode in CURRENT_LIMIT_PARAM_TO_MODE.items()}


class ControllerParameterWriteError(RuntimeError):
  def __init__(self, message: str, debug: dict | None = None):
    super().__init__(message)
    self.debug = debug or {}


class JsonBodyError(RuntimeError):
  pass


class ApiRouter:
  def __init__(
    self,
    state_store,
    image_dir: Path = Path("data/vehicle-images"),
    probe_runner=None,
    udp_transport=None,
    dxdcnet_session=None,
    cv_read_sessions=None,
    vehicle_store=None,
    import_registry=None,
    controller_registry=None,
  ):
    self.state_store = state_store
    self.image_dir = Path(image_dir)
    self.probe_runner = probe_runner
    self.udp_transport = udp_transport
    self.dxdcnet_session = dxdcnet_session or DXDCNetSessionManager(udp_transport)
    self.cv_read_sessions = cv_read_sessions or CVReadSessionRegistry()
    self.vehicle_store = vehicle_store
    self.import_registry = import_registry or default_import_registry(self.image_dir)
    self.controller_registry = controller_registry or default_controller_registry()

  def handle_json(self, method: str, path: str, body: bytes, state: dict, request_meta=None):
    route = urlparse(path).path
    try:
      if method == "GET":
        return self._handle_get_route(route, state)
      if method == "POST":
        return self._handle_post_route(route, body, state)
      if method == "PATCH":
        return self._handle_patch_route(route, body, state)
      if method == "DELETE":
        return self._handle_delete_route(route, state)
    except JsonBodyError as exc:
      return response.failure("invalid_json", "请求 JSON 无效", str(exc)), 400
    return response.failure("not_found", "API 路径不存在", route), 404

  def _handle_get_route(self, route: str, state: dict):
    if route == "/api/state":
      if self.vehicle_store:
        state = self._state_with_vehicle_store_data(state)
      return response.success(self._public_state(state)), 200
    if route == "/api/vehicles":
      if self.vehicle_store:
        return response.success([self._vehicle_with_store_functions(vehicle) for vehicle in self.vehicle_store.list_vehicles()]), 200
      return response.success(state["vehicles"]), 200
    if route == "/api/categories":
      if self.vehicle_store:
        return response.success(self.vehicle_store.list_categories()), 200
      return response.success(state.get("categories", [])), 200
    if route == "/api/consists":
      if self.vehicle_store:
        return response.success(self.vehicle_store.list_consists()), 200
      return response.success(state["consists"]), 200
    if route == "/api/cv/metadata":
      return response.success(cv_metadata()), 200
    if route == "/api/controller/info":
      return response.success(self._controller_info(state)), 200
    return self._not_found(route)

  def _controller_adapter(self, controller: dict):
    return self.controller_registry.get(controller.get("kind", models.CONTROLLER_KIND_DIGSIGHT))

  def _handle_post_route(self, route: str, body: bytes, state: dict):
    if route == "/api/vehicles":
      return self._handle_create_vehicle(body, state)
    if route == "/api/vehicle-images":
      return self._handle_vehicle_image_upload(body)
    if route == "/api/categories":
      return self._handle_create_category(body)
    if route == "/api/controller/read-info":
      return self._handle_controller_read_info(state)

    if route == "/api/track-power":
      return self._handle_track_power(body, state)

    if route == "/api/dc-control":
      return self._handle_dc_control(body, state)

    if route == "/api/controller/connect":
      return self._handle_controller_connect(body, state)

    if route == "/api/controller/probe":
      return self._handle_controller_probe(body, state)

    if route == "/api/controller/disconnect":
      state["controller"]["last_probe_ok"] = False
      self._save(state)
      return response.success({"connected": False}), 200

    if route in {"/api/loco/speed", "/api/loco/function"}:
      return self._handle_loco_control(route, body, state)

    if route == "/api/cv/read":
      return self._handle_cv_read(body, state)

    if route == "/api/cv/read-all":
      return self._handle_cv_read_all(body, state)

    if route == "/api/cv/read-all/cancel":
      return self._handle_cv_read_all_cancel(body)

    if route == "/api/cv/write":
      return self._handle_cv_write(body, state)

    if route == "/api/chip-info/read":
      return self._handle_chip_info_read(body, state)

    if route == "/api/address/read":
      return self._handle_address_read(body, state)

    if route == "/api/address/write":
      return self._handle_address_write(body, state)

    if route == "/api/consists":
      return self._handle_create_consist(body, state)

    if route.startswith("/api/consists/") and route.endswith(("/speed", "/stop")):
      return self._handle_consist_speed(route, body, state)

    return self._not_found(route)

  def _handle_patch_route(self, route: str, body: bytes, state: dict):
    if route == "/api/vehicles/order":
      return self._handle_reorder_vehicles(body, state)
    if route.startswith("/api/categories/"):
      return self._handle_patch_category(route, body)
    if route == "/api/controller/track-mode":
      return self._handle_controller_track_mode(body, state)
    if route == "/api/controller/settings":
      return self._handle_controller_settings(body, state)
    if route.startswith("/api/vehicles/"):
      return self._handle_patch_vehicle(route, body, state)
    if route.startswith("/api/consists/"):
      return self._handle_patch_consist(route, body, state)
    return self._not_found(route)

  def _handle_delete_route(self, route: str, state: dict):
    if route.startswith("/api/categories/"):
      return self._handle_delete_category(route)
    if route.startswith("/api/vehicles/"):
      return self._handle_delete_vehicle(route, state)
    if route.startswith("/api/consists/"):
      return self._handle_delete_consist(route, state)
    return self._not_found(route)

  def _not_found(self, route: str):
    return response.failure("not_found", "API 路径不存在", route), 404

  def _resource_id(self, route: str) -> str:
    return route.rsplit("/", 1)[-1]

  def _vehicle_store_not_ready(self, *, code: str = "vehicle_store_not_ready", message: str = "车辆库尚未启用", status: int = 409):
    return response.failure(code, message, ""), status

  def _handle_controller_connect(self, body: bytes, state: dict):
    request = self._json_body(body)
    try:
      ip = self._validate_controller_ip(request.get("ip", models.CONTROLLER_DEFAULT_IP))
    except ValueError as exc:
      return response.failure("invalid_controller_ip", "控制器 IP 格式无效", str(exc)), 400
    try:
      udp_port = self._validate_udp_port(request.get("udp_port", models.DXDCNET_DEFAULT_UDP_PORT))
      local_udp_port = self._validate_udp_port(request.get("local_udp_port", models.DXDCNET_DEFAULT_LOCAL_UDP_PORT))
      checksum_algorithm = self._validate_checksum_algorithm(request.get("udp_checksum_algorithm", models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_connection", "控制器连接参数无效", str(exc)), 400
    controller = state["controller"]
    previous_identity = self._controller_transport_identity(controller)
    next_identity = self._controller_transport_identity(
      controller,
      ip=ip,
      udp_port=udp_port,
      local_udp_port=local_udp_port,
      checksum_algorithm=checksum_algorithm,
    )
    if next_identity != previous_identity:
      self._invalidate_controller_runtime_safety(controller, reason="controller_transport_changed")
    controller["ip"] = ip
    controller["udp_port"] = udp_port
    controller["local_udp_port"] = local_udp_port
    controller["udp_checksum_algorithm"] = checksum_algorithm
    self._save(state)
    return response.success({
      "ip": ip,
      "udp_port": udp_port,
      "local_udp_port": local_udp_port,
      "udp_checksum_algorithm": checksum_algorithm,
      "connected": udp_port > 0,
    }), 200

  def _controller_transport_identity(
    self,
    controller: dict,
    *,
    ip=None,
    udp_port=None,
    local_udp_port=None,
    checksum_algorithm=None,
  ) -> tuple:
    return (
      controller.get("kind", models.CONTROLLER_KIND_DIGSIGHT),
      controller.get("ip") if ip is None else ip,
      self._transport_port_value(controller.get("udp_port", 0) if udp_port is None else udp_port),
      self._transport_port_value(controller.get("local_udp_port", 0) if local_udp_port is None else local_udp_port),
      controller.get("udp_checksum_algorithm") if checksum_algorithm is None else checksum_algorithm,
    )

  def _transport_port_value(self, value) -> int:
    try:
      return int(value)
    except (TypeError, ValueError):
      return 0

  def _current_editable_track_mode(self, state: dict) -> str:
    track_mode = str(state.get("controller", {}).get("track_mode", "")).lower()
    if track_mode in {models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G}:
      return track_mode
    return ""

  def _apply_default_track_mode(self, request: dict, state: dict) -> None:
    if request.get("track_mode"):
      return
    track_mode = self._current_editable_track_mode(state)
    if track_mode:
      request["track_mode"] = track_mode

  def import_config_bytes(
    self,
    format_name: str,
    file_name: str,
    body: bytes,
    state: dict,
    include_format_list: bool = True,
    request_meta=None,
  ):
    safe_file_name = Path(file_name or "import.config").name or "import.config"
    try:
      importer = self.import_registry.get(format_name)
      import_result = importer.import_bytes(ConfigImportRequest(format=format_name, file_name=safe_file_name, content=body))
    except ValueError as exc:
      return response.failure("import_failed", "导入配置失败", str(exc)), 400
    self._merge_import_result(
      state,
      import_result.format,
      import_result.vehicles,
      import_result.functions,
      import_result.categories,
      import_result.consists,
      import_result.summary,
    )
    if include_format_list:
      return response.success({"summary": import_result.summary, "formats": self.import_registry.descriptors()}), 200
    return response.success(import_result.summary), 200

  def import_z21_bytes(self, file_name: str, body: bytes, state: dict, request_meta=None):
    return self.import_config_bytes(
      "z21_layout_config",
      file_name,
      body,
      state,
      include_format_list=False,
      request_meta=None,
    )

  def _merge_import_result(
    self,
    state: dict,
    format_name: str,
    vehicles: list,
    functions: list,
    categories: list,
    consists: list,
    summary: dict,
  ) -> None:
    if self.vehicle_store:
      if format_name != "z21_layout_config":
        raise ValueError(f"vehicle store import is not implemented for {format_name}")
      self.vehicle_store.replace_imported_z21_data(summary, vehicles, categories, functions, consists)
      self._state_with_vehicle_store_data(state)
      return
    state["vehicles"] = vehicles
    state["functions"] = functions
    state["categories"] = categories
    state["consists"] = consists
    state.setdefault("imports", []).append(summary)
    self._save(state)

  def _handle_controller_probe(self, body: bytes, state: dict):
    request = self._json_body(body)
    try:
      ip = self._validate_controller_ip(request.get("ip") or state["controller"].get("ip") or models.CONTROLLER_DEFAULT_IP)
    except ValueError as exc:
      return response.failure("invalid_controller_ip", "控制器 IP 格式无效", str(exc)), 400
    result = probe_ip_with_runner(ip, self.probe_runner) if self.probe_runner else probe_ip(ip)
    if ip != state["controller"].get("ip"):
      self._invalidate_controller_runtime_safety(state["controller"], reason="controller_endpoint_changed")
    state["controller"]["ip"] = ip
    state["controller"]["last_probe_ok"] = result.ok
    state["controller"]["last_probe_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    self._save(state)
    status = 200 if result.ok else 502
    return response.success({
      "ip": ip,
      "reachable": result.ok,
      "detail": result.detail,
    }), status

  def _controller_info(self, state: dict) -> dict:
    controller = state["controller"]
    adapter = self._controller_adapter(controller)
    readiness_warnings = self._controller_readiness_warnings(controller)
    booster_status = controller.get("booster_status", {})
    if not isinstance(booster_status, dict):
      booster_status = {}
    cv_safety = self._cached_cv_safety(controller)
    controller_reachable = bool(controller.get("controller_reachable", False))
    short_circuit = bool(booster_status.get("short_circuit") or booster_status.get("current_alarm"))
    return {
      "ip": controller.get("ip"),
      "controller_kind": adapter.kind,
      "controller_label": adapter.label,
      "controller_capabilities": adapter.capabilities.__dict__,
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

  def _public_state(self, state: dict) -> dict:
    public_state = copy.deepcopy(state)
    controller = public_state.get("controller", {})
    if isinstance(controller, dict):
      controller.pop("operation_token", None)
    return public_state

  def _cached_cv_safety(self, controller: dict) -> dict:
    warnings = []
    try:
      track_mode = models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      return {
        "safe_for_cv": False,
        "programming_track_status": controller.get("programming_track_status", {}),
        "warnings": ["unsafe_track_mode"],
      }
    programming_status = self._programming_track_status_from_controller(controller)
    if programming_status is None:
      return {
        "safe_for_cv": False,
        "programming_track_status": controller.get("programming_track_status", {}),
        "warnings": ["programming_track_status_unconfirmed"],
      }
    if programming_status.track_mode != track_mode:
      warnings.append("programming_track_status_stale")
    try:
      ProgrammingTrackSafety().validate(programming_status)
    except ValueError:
      warnings.append("programming_track_safety_failed")
    return {
      "safe_for_cv": not warnings,
      "programming_track_status": controller.get("programming_track_status", {}),
      "warnings": warnings,
    }

  def _apply_controller_read_info(self, controller: dict, track_mode: str, current_param: int, collected: dict, read_warnings: list) -> dict:
    warnings = list(read_warnings)
    command_station_status = None
    booster_status = None
    parameter_value = None

    version_frame = self._first_matching_frame(collected.get("version", []), CMD_VERSION_DATA)
    if version_frame is None:
      warnings.append("version_response_missing")
    else:
      try:
        version = parse_version_response(version_frame.payload)
        version.update({
          "source": "dxdcnet_version_0x85",
          "response_hex": version_frame.to_debug_dict()["payload_hex"],
        })
        controller["device_info"] = {
          **controller.get("device_info", {}),
          **version,
        }
      except ValueError as exc:
        warnings.append(f"version_parse_error:{exc}")

    version_core_frame = self._first_matching_frame(collected.get("version_core", []), CMD_VERSION_DATA, DEVICE_TYPE_SPECIAL)
    if version_core_frame is None:
      warnings.append("core_version_response_missing")
    else:
      try:
        version = parse_version_response(version_core_frame.payload)
        controller["device_info"] = {
          **controller.get("device_info", {}),
          "device_name": controller.get("device_info", {}).get("device_name") or "DXDC9000",
          "device_name_source": "official_app_d9000_default",
          "core_version": version["app_version"],
          "core_hardware_version_raw": version["hardware_version_raw"],
          "core_software_version_raw": version["software_version_raw"],
          "core_version_source": "dxdcnet_version_0x85_special_15",
        }
      except ValueError as exc:
        warnings.append(f"core_version_parse_error:{exc}")

    version_wireless_frame = self._first_matching_frame(collected.get("version_wireless", []), CMD_VERSION_DATA, DEVICE_TYPE_BOOSTER)
    if version_wireless_frame is None:
      warnings.append("wireless_version_response_missing")
    else:
      try:
        version = parse_version_response(version_wireless_frame.payload)
        controller["device_info"] = {
          **controller.get("device_info", {}),
          "wireless_version": version["app_version"],
          "wireless_hardware_version_raw": version["hardware_version_raw"],
          "wireless_software_version_raw": version["software_version_raw"],
          "wireless_version_source": "dxdcnet_version_0x85_booster_1",
        }
      except ValueError as exc:
        warnings.append(f"wireless_version_parse_error:{exc}")

    railcom_frame = self._first_matching_frame(collected.get("railcom", []), CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION)
    if railcom_frame is None:
      warnings.append("railcom_response_missing")
    else:
      try:
        railcom = parse_parameter_response(railcom_frame.payload)
        if railcom["param_address"] == PARAM_RAILCOM:
          controller["device_info"] = {
            **controller.get("device_info", {}),
            "railcom_enabled": (railcom["value"] & 0x80) == 0x80,
            "railcom_value_raw": railcom["value"],
            "railcom_source": "dxdcnet_parameter_0x03",
          }
        else:
          warnings.append("railcom_param_mismatch")
      except ValueError as exc:
        warnings.append(f"railcom_parse_error:{exc}")

    screen_brightness_frame = self._first_matching_frame(
      collected.get("screen_brightness", []),
      CMD_PARAMETER_VALUE,
      DEVICE_TYPE_COMMAND_STATION,
    )
    if screen_brightness_frame is None:
      warnings.append("screen_brightness_response_missing")
    else:
      try:
        brightness = parse_parameter_response(screen_brightness_frame.payload)
        if brightness["param_address"] == PARAM_SCREEN_BRIGHTNESS:
          controller["device_info"] = {
            **controller.get("device_info", {}),
            "screen_brightness": brightness["value"],
            "screen_brightness_raw": brightness["value"],
            "screen_brightness_source": "dxdcnet_parameter_0x7e",
          }
        else:
          warnings.append("screen_brightness_param_mismatch")
      except ValueError as exc:
        warnings.append(f"screen_brightness_parse_error:{exc}")

    screen_direction_frame = self._first_matching_frame(
      collected.get("screen_direction", []),
      CMD_PARAMETER_VALUE,
      DEVICE_TYPE_COMMAND_STATION,
    )
    if screen_direction_frame is None:
      warnings.append("screen_direction_response_missing")
    else:
      try:
        direction = parse_parameter_response(screen_direction_frame.payload)
        if direction["param_address"] == PARAM_SCREEN_DIRECTION:
          controller["device_info"] = {
            **controller.get("device_info", {}),
            "screen_direction_raw": direction["value"],
            "screen_direction_label": models.screen_direction_label(direction["value"]),
            "screen_direction_source": "dxdcnet_parameter_0x80",
          }
        else:
          warnings.append("screen_direction_param_mismatch")
      except ValueError as exc:
        warnings.append(f"screen_direction_parse_error:{exc}")

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
    if mac_parts:
      low_hex = mac_parts.get(0, {}).get("app_order_hex", "")
      high_hex = mac_parts.get(1, {}).get("app_order_hex", "")
      mac_hex = low_hex + high_hex
      controller["device_info"] = {
        **controller.get("device_info", {}),
        "mac_address": mac_hex,
        "mac_address_parts": mac_parts,
        "factory_number": mac_hex,
        "factory_number_source": "dxdcnet_mac_0x0c",
      }
      if 0 not in mac_parts or 1 not in mac_parts:
        warnings.append("mac_response_incomplete")
    else:
      warnings.append("mac_response_missing")

    command_station_frame = self._first_matching_frame(
      collected.get("command_station_status", []),
      CMD_DEVICE_STATUS,
      DEVICE_TYPE_COMMAND_STATION,
    )
    if command_station_frame is None:
      warnings.append("command_station_status_missing")
    else:
      try:
        command_station_status = parse_command_station_status(command_station_frame.payload)
        command_station_status["source"] = "dxdcnet_status_0x23"
        command_station_status["payload_hex"] = command_station_frame.payload.hex(" ")
        controller["command_station_status"] = command_station_status
      except ValueError as exc:
        warnings.append(f"command_station_status_parse_error:{exc}")

    booster_frame = self._first_matching_frame(collected.get("booster_status", []), CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER)
    if booster_frame is None:
      warnings.append("booster_status_missing")
      controller["controller_reachable"] = False
      controller["controller_unreachable_reason"] = "booster_status_missing"
    else:
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
      except ValueError as exc:
        warnings.append(f"booster_status_parse_error:{exc}")
        controller["controller_reachable"] = False
        controller["controller_unreachable_reason"] = "booster_status_parse_error"

    profiles = controller.get("track_profiles", models.default_track_profiles())
    for param_address, mode in CURRENT_LIMIT_PARAM_TO_MODE.items():
      parameter_frame = self._first_matching_frame(collected.get(f"current_limit_{mode}", []), CMD_PARAMETER_VALUE)
      if parameter_frame is None:
        warnings.append(f"current_limit_{mode}_response_missing")
        continue
      try:
        parsed_parameter = parse_parameter_response(parameter_frame.payload)
        if parsed_parameter["param_address"] == param_address:
          profiles.setdefault(mode, models.default_track_profiles()[mode])
          profiles[mode]["current_limit_ma"] = parsed_parameter.get("current_limit_ma")
          profiles[mode]["current_limit_raw"] = parsed_parameter["value"]
          if parsed_parameter["param_address"] == current_param:
            parameter_value = parsed_parameter
        else:
          warnings.append(f"current_limit_{mode}_param_mismatch")
      except ValueError as exc:
        warnings.append(f"current_limit_{mode}_parse_error:{exc}")
    controller["track_profiles"] = profiles

    safe_for_cv = self._update_programming_track_status(
      controller,
      track_mode,
      command_station_status,
      booster_status,
      parameter_value,
      warnings,
    )
    self._mark_safety_snapshot_fresh(
      controller,
      booster_status_fresh=booster_status is not None,
      programming_track_status_fresh=command_station_status is not None and booster_status is not None,
    )
    return {
      "safe_for_cv": safe_for_cv,
      "warnings": warnings,
    }

  def _first_matching_frame(self, frames: list, command: int, device_type: int | None = None):
    return first_matching_frame(frames, command, device_type)

  def _build_raw_frame_matcher(self, command: int, device_type: int | None = None):
    return build_raw_frame_matcher(command, device_type)

  def _build_cv_value_matcher(self, client_id: int, cv_number: int, pom_address: int | None = None):
    return build_programmer_value_matcher(client_id, cv_number, pom_address=pom_address)

  def _build_cv_ack_matcher(self, client_id: int):
    return build_programmer_ack_matcher(client_id)

  def _update_programming_track_status(
    self,
    controller: dict,
    track_mode: str,
    command_station_status: dict | None,
    booster_status: dict | None,
    parameter_value: dict | None,
    warnings: list,
  ) -> bool:
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

  def _handle_controller_settings(self, body: bytes, state: dict):
    request = self._json_body(body)
    previous_kind = state["controller"].get("kind", models.CONTROLLER_KIND_DIGSIGHT)
    next_kind = previous_kind
    if "kind" in request:
      try:
        next_kind = models.validate_controller_kind(request.get("kind"))
        self.controller_registry.get(next_kind)
      except (TypeError, ValueError) as exc:
        return response.failure("invalid_controller_kind", "控制器类型无效", str(exc)), 400
    try:
      previous_ip = state["controller"].get("ip", models.CONTROLLER_DEFAULT_IP)
      next_ip = previous_ip
      if "ip" in request:
        next_ip = self._validate_controller_ip(request.get("ip"))
      previous_track_mode = state["controller"].get("track_mode", models.TRACK_MODE_N)
      next_track_mode = previous_track_mode
      if "track_mode" in request:
        next_track_mode = models.validate_profile_mode(request.get("track_mode"))
      previous_programming_target = state["controller"].get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK)
      next_programming_target = previous_programming_target
      if "programming_target" in request:
        next_programming_target = models.validate_programming_target(request.get("programming_target"))
      apply_to_device = bool(request.get("apply_to_device", False))
      requested_profile_modes = set()
      current_profiles = state["controller"].get("track_profiles", models.default_track_profiles())
      next_profiles = {mode: dict(profile) for mode, profile in current_profiles.items()}
      for mode, profile in request.get("track_profiles", {}).items():
        normalized_mode = models.validate_profile_mode(mode)
        requested_profile_modes.add(normalized_mode)
        next_profiles[normalized_mode] = models.validate_track_profile(normalized_mode, profile)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_settings", "控制器参数无效", str(exc)), 400
    candidate_controller = copy.deepcopy(state["controller"])
    if next_kind != previous_kind:
      self._invalidate_controller_runtime_safety(candidate_controller, reason="controller_kind_changed")
    elif next_ip != previous_ip:
      self._invalidate_controller_runtime_safety(candidate_controller, reason="controller_endpoint_changed")
    elif next_track_mode != previous_track_mode:
      self._invalidate_controller_runtime_safety(candidate_controller, reason="track_mode_changed")
    elif next_programming_target != previous_programming_target:
      self._invalidate_controller_runtime_safety(candidate_controller, reason="programming_target_changed")
    candidate_controller["kind"] = next_kind
    candidate_controller["ip"] = next_ip
    if next_kind != previous_kind:
      candidate_controller["udp_port"] = models.DXDCNET_DEFAULT_UDP_PORT
      candidate_controller["local_udp_port"] = models.DXDCNET_DEFAULT_LOCAL_UDP_PORT
      candidate_controller["udp_checksum_algorithm"] = models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM
    else:
      candidate_controller.setdefault("udp_port", models.DXDCNET_DEFAULT_UDP_PORT)
      candidate_controller.setdefault("local_udp_port", models.DXDCNET_DEFAULT_LOCAL_UDP_PORT)
      candidate_controller.setdefault("udp_checksum_algorithm", models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM)
    candidate_controller["track_mode"] = next_track_mode
    candidate_controller["programming_target"] = next_programming_target
    device_results = []
    if apply_to_device and requested_profile_modes:
      readiness_warnings = self._controller_readiness_warnings(candidate_controller)
      if readiness_warnings:
        return response.failure(
          "protocol_not_ready",
          "DXDCNet UDP 端口或校验算法尚未确认",
          "控制器轨道输出参数需要先确认 DXDCNet UDP 端口和校验算法",
          {"warnings": readiness_warnings},
        ), 409
      try:
        device_results = self._apply_track_profile_parameters_to_controller(
          candidate_controller,
          next_profiles,
          sorted(requested_profile_modes),
        )
      except ControllerParameterWriteError as exc:
        return response.failure(
          "controller_parameter_write_failed",
          "控制器轨道输出参数写入失败",
          str(exc),
          exc.debug,
        ), 502
    candidate_controller["track_profiles"] = next_profiles
    state["controller"] = candidate_controller
    self._save(state)
    warnings = [] if device_results else ["saved_locally_only"]
    return response.success({
      "applied_to_device": bool(device_results),
      "device_results": device_results,
      "kind": next_kind,
      "ip": next_ip,
      "udp_port": candidate_controller["udp_port"],
      "local_udp_port": candidate_controller["local_udp_port"],
      "udp_checksum_algorithm": candidate_controller["udp_checksum_algorithm"],
      "track_mode": next_track_mode,
      "programming_target": next_programming_target,
      "track_profiles": next_profiles,
      "warnings": warnings,
    }), 200

  def _handle_controller_track_mode(self, body: bytes, state: dict):
    request = self._json_body(body)
    try:
      next_track_mode = models.validate_profile_mode(request.get("track_mode"))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_track_mode", "轨道模式无效", str(exc)), 400
    candidate_controller = copy.deepcopy(state["controller"])
    previous_track_mode = candidate_controller.get("track_mode", models.TRACK_MODE_N)
    if next_track_mode != previous_track_mode:
      self._invalidate_controller_runtime_safety(candidate_controller, reason="track_mode_changed")
    candidate_controller["track_mode"] = next_track_mode
    state["controller"] = candidate_controller
    self._save(state)
    warnings = ["saved_locally_only"]
    return response.success({
      "track_mode": next_track_mode,
      "warnings": warnings,
    }), 200

  def _apply_track_profile_parameters_to_controller(self, controller: dict, profiles: dict, modes: list[str]) -> list[dict]:
    results = []
    client_id = self._controller_client_id(controller)
    for mode in modes:
      profile = profiles.get(mode, {})
      current_limit_ma = profile.get("current_limit_ma")
      if current_limit_ma in ("", None):
        continue
      param_address = int(profile.get("current_param", MODE_TO_CURRENT_LIMIT_PARAM[mode]))
      raw_value = int(int(current_limit_ma) / models.CURRENT_STEP_MA)
      if raw_value < 1 or raw_value > 0xFF:
        raise ControllerParameterWriteError(
          f"{profile.get('name', mode)} 限流值不能转换为 D9000 参数原始值",
          {"mode": mode, "current_limit_ma": current_limit_ma, "raw_value": raw_value},
        )
      write_frame = build_parameter_write_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, param_address, raw_value)
      read_frame = build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, param_address)
      write_frames = self._exchange_dxdcnet(
        controller,
        write_frame,
        timeout_seconds=float(controller.get("parameter_write_timeout_seconds", 0.25)),
        max_packets=4,
      )
      read_frames = self._exchange_dxdcnet(
        controller,
        read_frame,
        timeout_seconds=float(controller.get("parameter_readback_timeout_seconds", 0.25)),
        max_packets=8,
        stop_when=self._build_raw_frame_matcher(CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION),
      )
      parameter_frame = self._first_matching_frame(read_frames, CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION)
      if parameter_frame is None:
        raise ControllerParameterWriteError(
          f"{profile.get('name', mode)} 限流参数写入后未读到确认回包",
          {
            "mode": mode,
            "param_address": param_address,
            "expected_raw_value": raw_value,
            "write_request_hex": write_frame.hex(" "),
            "read_request_hex": read_frame.hex(" "),
            "write_responses": [frame.to_debug_dict() for frame in write_frames],
            "read_responses": [frame.to_debug_dict() for frame in read_frames],
          },
        )
      parsed = parse_parameter_response(parameter_frame.payload)
      if parsed["param_address"] != param_address or int(parsed["value"]) != raw_value:
        raise ControllerParameterWriteError(
          f"{profile.get('name', mode)} 限流参数读回值不一致",
          {
            "mode": mode,
            "param_address": param_address,
            "expected_raw_value": raw_value,
            "actual": parsed,
            "write_request_hex": write_frame.hex(" "),
            "read_request_hex": read_frame.hex(" "),
          },
        )
      profile["current_limit_raw"] = raw_value
      results.append({
        "mode": mode,
        "param_address": param_address,
        "raw_value": raw_value,
        "current_limit_ma": int(current_limit_ma),
        "write_request_hex": write_frame.hex(" "),
        "read_request_hex": read_frame.hex(" "),
      })
    return results

  def _default_safety_snapshot(self, controller: dict) -> dict:
    return ControllerSafetySnapshot.from_controller(controller).to_dict()

  def _invalidate_controller_runtime_safety(self, controller: dict, *, reason: str) -> None:
    invalidate_controller_safety(controller, reason=reason)

  def _mark_safety_snapshot_fresh(
    self,
    controller: dict,
    *,
    booster_status_fresh: bool | None = None,
    programming_track_status_fresh: bool | None = None,
  ) -> None:
    mark_controller_safety_fresh(
      controller,
      booster_status_fresh=booster_status_fresh,
      programming_track_status_fresh=programming_track_status_fresh,
    )

  def _fresh_booster_status_failure(self, controller: dict):
    if self._default_safety_snapshot(controller)["booster_status_fresh"]:
      return None
    return response.failure(
      "protocol_not_ready",
      "轨道状态尚未重新确认",
      "控制器端点或模式已变化，需要重新读取控制器状态",
      {"warnings": ["booster_status_stale"]},
    ), 409

  def _handle_track_power(self, body: bytes, state: dict):
    request = self._json_body(body)
    if not isinstance(request.get("powered"), bool):
      return response.failure("invalid_track_power", "轨道输出参数无效", "powered must be true or false"), 400
    powered = bool(request["powered"])
    controller = state["controller"]
    readiness_warnings = self._controller_readiness_warnings(controller)
    if readiness_warnings:
      return response.failure(
        "protocol_not_ready",
        "DXDCNet UDP 参数尚未确认",
        "不能发送真实轨道通电或断电命令",
        {"warnings": readiness_warnings},
      ), 409
    try:
      client_id = self._controller_client_id(controller)
      track_mode = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError) as exc:
      return response.failure(
        "invalid_controller_settings",
        "控制器本地参数无效",
        str(exc),
      ), 409

    profiles = controller.get("track_profiles", models.default_track_profiles())
    profile = profiles.get(track_mode, models.default_track_profiles().get(track_mode, {}))
    output_value = self._track_output_value(track_mode, profile, powered)
    direction = "forward"
    if track_mode == models.TRACK_MODE_DC:
      try:
        direction = self._validate_dc_direction(controller.get("dc_control", {}).get("direction", "forward"))
      except (TypeError, ValueError):
        direction = "forward"
    return self._send_track_output(
      state,
      powered=powered,
      track_mode=track_mode,
      output_value=output_value,
      dc_direction_positive=direction != "reverse",
      dc_direction=direction if track_mode == models.TRACK_MODE_DC else None,
    )

  def _handle_dc_control(self, body: bytes, state: dict):
    controller = state["controller"]
    try:
      track_mode = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_settings", "控制器本地参数无效", str(exc)), 409
    if track_mode != models.TRACK_MODE_DC:
      return response.failure(
        "unsafe_track_mode",
        "DC 控制只允许在 DC 模式下执行",
        "请先切换到 DC 模式；N/HO/G 使用 DCC 车辆控制",
        {"warnings": ["operation_mode_not_dc"]},
      ), 409
    readiness_warnings = self._controller_readiness_warnings(controller)
    if readiness_warnings:
      return response.failure(
        "protocol_not_ready",
        "DXDCNet UDP 参数尚未确认",
        "不能发送真实 DC 控制命令",
        {"warnings": readiness_warnings},
      ), 409
    request = self._json_body(body)
    try:
      voltage = self._validate_dc_voltage(controller, request.get("voltage_v", 0))
      direction = self._validate_dc_direction(request.get("direction", "forward"))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_dc_control", "DC 控制参数无效", str(exc)), 400
    powered = voltage > 0
    output_value = max(0, min(255, int(round(voltage * 10))))
    controller["dc_control"] = {
      "voltage_v": voltage,
      "direction": direction,
      "powered": powered,
      "output_value": output_value,
    }
    return self._send_track_output(
      state,
      powered=powered,
      track_mode=models.TRACK_MODE_DC,
      output_value=output_value,
      dc_direction_positive=direction != "reverse",
      dc_direction=direction,
      voltage_v=voltage,
    )

  def _validate_dc_direction(self, value) -> str:
    direction = str(value or "forward").strip().lower()
    if direction not in {"forward", "reverse"}:
      raise ValueError("DC direction must be forward or reverse")
    return direction

  def _validate_dc_voltage(self, controller: dict, value) -> float:
    profiles = controller.get("track_profiles", models.default_track_profiles())
    profile = profiles.get(models.TRACK_MODE_DC, models.default_track_profiles()[models.TRACK_MODE_DC])
    max_voltage = float(profile.get("max_voltage_v") or models.default_track_profiles()[models.TRACK_MODE_DC]["max_voltage_v"])
    voltage = float(value)
    if voltage < 0 or voltage > max_voltage:
      raise ValueError(f"DC voltage must be 0..{max_voltage} V")
    return round(voltage, 1)

  def _send_track_output(
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
    controller = state["controller"]
    try:
      client_id = self._controller_client_id(controller)
    except (TypeError, ValueError) as exc:
      return response.failure(
        "invalid_controller_settings",
        "控制器本地参数无效",
        str(exc),
      ), 409
    dcc_mode = track_mode != models.TRACK_MODE_DC
    request_frame = build_track_output_frame(
      client_id,
      1,
      powered,
      output_value,
      dcc_mode=dcc_mode,
      dc_direction_positive=dc_direction_positive,
    )
    try:
      frames = self._exchange_dxdcnet(
        controller,
        request_frame,
        timeout_seconds=float(controller.get("track_power_timeout_seconds", 1.5)),
        max_packets=8,
        stop_when=self._build_raw_frame_matcher(CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER),
      )
    except TimeoutError as exc:
      self._mark_controller_unreachable(state, "track_power_timeout")
      return response.failure(
        "track_power_timeout",
        "轨道输出命令超时",
        str(exc),
        {"request_hex": request_frame.hex(" "), "powered": powered},
      ), 504
    except (OSError, ValueError) as exc:
      self._mark_controller_unreachable(state, "track_power_transport_error")
      return response.failure(
        "track_power_transport_error",
        "轨道输出通信失败",
        str(exc),
        {"request_hex": request_frame.hex(" "), "powered": powered},
      ), 502

    booster_frame = self._first_matching_frame(frames, CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER)
    if booster_frame is None:
      self._mark_controller_unreachable(state, "track_power_status_missing")
      return response.failure(
        "track_power_status_missing",
        "控制器未返回轨道输出状态",
        "No 0x23 booster status response matched the track power command",
        {
          "request_hex": request_frame.hex(" "),
          "powered": powered,
          "responses": [frame.to_debug_dict() for frame in frames],
        },
      ), 504
    try:
      booster_status = self._store_booster_status(controller, booster_frame)
    except ValueError as exc:
      self._mark_controller_unreachable(state, "track_power_status_parse_error")
      return response.failure(
        "track_power_status_parse_error",
        "轨道输出状态解析失败",
        str(exc),
        {"request_hex": request_frame.hex(" "), "response": booster_frame.to_debug_dict()},
      ), 502
    self._save(state)
    if bool(booster_status.get("power_on")) != powered:
      return response.failure(
        "track_power_state_mismatch",
        "轨道输出状态未达到目标",
        f"目标状态为{'通电' if powered else '断电'}，回包状态为{'通电' if booster_status.get('power_on') else '断电'}",
        {
          "request_hex": request_frame.hex(" "),
          "response": booster_frame.to_debug_dict(),
          "booster_status": booster_status,
        },
      ), 502
    response_dcc_mode = bool(booster_status.get("dcc_mode", False))
    if powered and response_dcc_mode != dcc_mode:
      return response.failure(
        "unsafe_track_mode",
        "控制器回报的轨道模式与目标模式不一致",
        f"目标模式为{'DCC' if dcc_mode else 'DC'}，回包模式为{'DCC' if response_dcc_mode else 'DC'}",
        {
          "request_hex": request_frame.hex(" "),
          "response": booster_frame.to_debug_dict(),
          "booster_status": booster_status,
        },
      ), 409
    data = {
      "powered": powered,
      "track_mode": track_mode,
      "dcc_mode": dcc_mode,
      "output_value": output_value,
      "request_hex": request_frame.hex(" "),
      "booster_status": booster_status,
      "telemetry": controller.get("telemetry", {}),
    }
    if track_mode == models.TRACK_MODE_DC:
      data["direction"] = dc_direction or ("forward" if dc_direction_positive else "reverse")
      data["voltage_v"] = round(output_value / 10, 1) if voltage_v is None else voltage_v
    return response.success(data), 200

  def _track_output_value(self, track_mode: str, profile: dict, powered: bool) -> int:
    if not powered:
      return 0
    if track_mode == models.TRACK_MODE_DC:
      voltage = float(profile.get("voltage_v") or models.default_track_profiles()[models.TRACK_MODE_DC]["voltage_v"])
      return max(0, min(255, int(round(voltage * 10))))
    return max(0, min(255, int(profile.get("output_value", 0))))

  def _store_booster_status(self, controller: dict, booster_frame) -> dict:
    booster_status = parse_booster_status(booster_frame.payload)
    booster_status["source"] = "dxdcnet_status_0x23"
    booster_status["payload_hex"] = booster_frame.payload.hex(" ")
    controller["booster_status"] = booster_status
    controller["controller_reachable"] = True
    controller["controller_unreachable_reason"] = ""
    controller["last_controller_seen_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    self._mark_safety_snapshot_fresh(controller, booster_status_fresh=True)
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

  def _mark_controller_unreachable(self, state: dict, reason: str):
    controller = state["controller"]
    self._invalidate_controller_runtime_safety(controller, reason=reason)
    self._save(state)

  def _controller_info_timeout_seconds(self, controller: dict, request_name: str) -> float:
    if "controller_info_timeout_seconds" in controller:
      return self._clamp_timeout_seconds(controller.get("controller_info_timeout_seconds"), 0.05, 1.5)
    if request_name in {"command_station_status", "booster_status"}:
      return self._clamp_timeout_seconds(
        controller.get("controller_info_status_timeout_seconds", models.CONTROLLER_INFO_STATUS_TIMEOUT_SECONDS),
        0.05,
        1.5,
      )
    return self._clamp_timeout_seconds(
      controller.get("controller_info_poll_timeout_seconds", models.CONTROLLER_INFO_POLL_TIMEOUT_SECONDS),
      0.05,
      1.5,
    )

  def _clamp_timeout_seconds(self, value, minimum: float, maximum: float) -> float:
    try:
      numeric = float(value)
    except (TypeError, ValueError):
      numeric = maximum
    return max(minimum, min(maximum, numeric))

  def _handle_controller_read_info(self, state: dict):
    controller = state["controller"]
    warnings = self._controller_readiness_warnings(controller)
    if warnings:
      detail = "UDP port and checksum algorithm are unconfirmed"
      if warnings == ["udp_checksum_algorithm_unconfirmed"]:
        detail = "UDP checksum algorithm is unconfirmed"
      return response.failure(
        "protocol_not_ready",
        "DXDCNet UDP 端口或校验算法尚未确认",
        detail,
        {"warnings": warnings},
      ), 409
    try:
      client_id = self._controller_client_id(controller)
      track_mode = models.validate_profile_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_controller_settings", "控制器本地参数无效", str(exc)), 400

    profiles = controller.get("track_profiles", models.default_track_profiles())
    profile = profiles.get(track_mode, models.default_track_profiles()[track_mode])
    current_param = int(profile.get("current_param", models.default_track_profiles()[track_mode]["current_param"]))
    request_specs = [
      ("command_station_status", build_status_request_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0), CMD_DEVICE_STATUS, DEVICE_TYPE_COMMAND_STATION),
      ("booster_status", build_status_request_frame(client_id, DEVICE_TYPE_BOOSTER, 1), CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER),
      ("version", build_version_request_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0), CMD_VERSION_DATA, DEVICE_TYPE_COMMAND_STATION),
      ("version_core", build_version_request_frame(client_id, DEVICE_TYPE_SPECIAL, 15), CMD_VERSION_DATA, DEVICE_TYPE_SPECIAL),
      ("version_wireless", build_version_request_frame(client_id, DEVICE_TYPE_BOOSTER, 1), CMD_VERSION_DATA, DEVICE_TYPE_BOOSTER),
      ("railcom", build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, PARAM_RAILCOM), CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION),
      ("screen_brightness", build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, PARAM_SCREEN_BRIGHTNESS), CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION),
      ("screen_direction", build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, PARAM_SCREEN_DIRECTION), CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION),
      ("mac", build_mac_request_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 1), None, None),
    ]
    for param_address, mode in CURRENT_LIMIT_PARAM_TO_MODE.items():
      request_specs.append((
        f"current_limit_{mode}",
        build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, param_address),
        CMD_PARAMETER_VALUE,
        DEVICE_TYPE_COMMAND_STATION,
      ))

    request_debug = []
    collected = {}
    read_warnings = []
    for name, request_frame, expected_command, expected_device_type in request_specs:
      timeout_seconds = self._controller_info_timeout_seconds(controller, name)
      try:
        frames = self._exchange_dxdcnet(
          controller,
          request_frame,
          timeout_seconds=timeout_seconds,
          max_packets=8,
          stop_when=self._build_raw_frame_matcher(expected_command, expected_device_type) if expected_command is not None else None,
        )
      except TimeoutError:
        frames = []
        read_warnings.append(f"{name}_timeout")
      except (OSError, ValueError) as exc:
        frames = []
        read_warnings.append(f"{name}_transport_error:{exc}")
      collected[name] = frames
      request_debug.append({
        "name": name,
        "request_hex": request_frame.hex(" "),
        "timeout_seconds": timeout_seconds,
        "response_count": len(frames),
        "responses": [frame.to_debug_dict() for frame in frames],
      })

    parsed = self._apply_controller_read_info(controller, track_mode, current_param, collected, read_warnings)
    controller["last_read_info_at"] = datetime.now().astimezone().isoformat(timespec="seconds")
    self._save(state)
    return response.success(
      {
        "controller": self._controller_info(state),
        "safe_for_cv": parsed["safe_for_cv"],
        "warnings": parsed["warnings"],
      },
      {
        "warnings": parsed["warnings"],
        "requests": request_debug,
      },
    ), 200

  def _controller_readiness_warnings(self, controller: dict):
    warnings = []
    if int(controller.get("udp_port", 0)) <= 0:
      warnings.append("udp_port_unconfirmed")
    if (controller.get("udp_checksum_algorithm") or "unconfirmed") == "unconfirmed":
      warnings.append("udp_checksum_algorithm_unconfirmed")
    return warnings

  def _loco_control_readiness_warnings(self, controller: dict):
    warnings = self._controller_readiness_warnings(controller)
    if not bool(controller.get("last_probe_ok")) and not bool(controller.get("controller_reachable")):
      warnings.append("controller_not_confirmed")
    return warnings

  def _first_loco_speed_feedback(self, frames: list):
    for frame in frames:
      if frame.command == CMD_LOCO_SPEED + 0x08:
        return parse_loco_speed_feedback(frame)
    return None

  def _first_loco_function_feedback(self, frames: list):
    for frame in frames:
      if frame.command == CMD_LOCO_FUNCTION + 0x08:
        return parse_loco_function_feedback(frame)
    return None

  def _first_loco_control_ack(self, frames: list, address: int):
    for frame in frames:
      if frame.command != CMD_LOCO_CONTROL_ACK:
        continue
      try:
        ack = parse_loco_control_ack(frame)
      except ValueError:
        continue
      if int(ack.get("address", 0)) == int(address):
        return ack
    return None

  def _build_loco_control_ack_matcher(self, address: int):
    def matches(raw: bytes) -> bool:
      try:
        frame = decode_udp_frame(raw)
        if not frame.checksum_valid or frame.command != CMD_LOCO_CONTROL_ACK:
          return False
        ack = parse_loco_control_ack(frame)
      except ValueError:
        return False
      return int(ack.get("address", 0)) == int(address)
    return matches

  def _request_loco_control(self, controller: dict, address: int, client_id: int):
    request_frame = build_loco_control_request_frame(address=address, client_id=client_id)
    frames = self._exchange_dxdcnet(
      controller,
      request_frame,
      timeout_seconds=float(controller.get("loco_control_request_timeout_seconds", 0.2)),
      max_packets=4,
      stop_when=self._build_loco_control_ack_matcher(address),
    )
    return {
      "request_hex": request_frame.hex(" "),
      "feedback": self._first_loco_control_ack(frames, address),
    }

  def _digital_operation_mode_failure(self, controller: dict, operation_name: str):
    try:
      models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      return response.failure(
        "unsafe_track_mode",
        "当前操作模式不支持 DCC 数码操作",
        f"{operation_name} 只允许在 N、HO 或 G 的 DCC 数码模式下执行",
        {"warnings": ["operation_mode_not_digital"]},
      ), 409
    return None


  def _exchange_dxdcnet(self, controller: dict, request_frame: bytes, timeout_seconds: float | None = None, max_packets: int = 32, stop_when=None):
    adapter = self._controller_adapter(controller)
    if adapter.kind != models.CONTROLLER_KIND_DIGSIGHT:
      raise ValueError(f"controller {adapter.kind} does not support DXDCNet frame exchange")
    return adapter.exchange(
      self.dxdcnet_session,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      stop_when=stop_when,
      transport=self.udp_transport,
    )

  def _controller_client_id(self, controller: dict) -> int:
    client_id = int(controller.get("client_id", 1))
    if client_id < 0 or client_id > 127:
      raise ValueError("DXDCNet client id must be in 0..127")
    return client_id


  def _programming_track_status_from_controller(self, controller: dict):
    status = controller.get("programming_track_status") or {}
    if status.get("source") != "dxdcnet_status_0x23":
      return None
    current_limit_ma = int(status.get("current_limit_ma", 0))
    return ProgrammingTrackStatus(
      track_mode=str(status.get("track_mode", "")).lower(),
      dcc_mode=bool(status.get("dcc_mode", False)),
      programming_track_busy=bool(status.get("programming_track_busy", False)),
      programming_track_current_ma=int(status.get("programming_track_current_ma", 0)),
      output_value=int(status.get("output_value", -1)),
      current_limit_ma=current_limit_ma,
      current_limit_confirmed=bool(status.get("current_limit_confirmed", current_limit_ma > 0)),
    )


  def _save(self, state):
    if self.state_store:
      self.state_store.save(self._persistent_state(state))

  def _persistent_state(self, state: dict) -> dict:
    if not self.vehicle_store:
      return state
    persistent_state = dict(state)
    persistent_state["vehicles"] = []
    persistent_state["functions"] = []
    persistent_state["categories"] = []
    persistent_state["consists"] = []
    persistent_state["imports"] = []
    return persistent_state

  def _state_with_vehicle_store_data(self, state: dict) -> dict:
    self._refresh_state_vehicle_store_data(state)
    return state

  def _refresh_state_vehicle_store_data(self, state: dict) -> None:
    if not self.vehicle_store:
      return
    state["vehicles"] = self.vehicle_store.list_vehicles()
    state["functions"] = self.vehicle_store.list_all_functions()
    state["categories"] = self.vehicle_store.list_categories()
    state["consists"] = self.vehicle_store.list_consists()

  def _vehicle_with_store_functions(self, vehicle: dict) -> dict:
    payload = dict(vehicle)
    payload["functions"] = self.vehicle_store.list_functions(vehicle["id"]) if self.vehicle_store else []
    return payload

  def _json_body(self, body: bytes):
    try:
      decoded = body.decode("utf-8")
    except UnicodeDecodeError as exc:
      raise JsonBodyError("request body must be UTF-8 JSON") from exc
    try:
      value = json.loads(decoded or "{}")
    except json.JSONDecodeError as exc:
      raise JsonBodyError(str(exc)) from exc
    if not isinstance(value, dict):
      raise JsonBodyError("request JSON root must be an object")
    return value

  def _find_by_id(self, items, item_id):
    return next((item for item in items if item.get("id") == item_id), None)

  def _validate_vehicle_address(self, address) -> int:
    value = int(address)
    if value < models.DCC_ADDRESS_MIN or value > models.DCC_ADDRESS_MAX:
      raise ValueError(f"DCC address must be in range {models.DCC_ADDRESS_MIN}..{models.DCC_ADDRESS_MAX}")
    return value

  def _validate_vehicle_image(self, file_name: str, content: bytes) -> str:
    if not content:
      raise ValueError("image content is empty")
    if len(content) > 8 * 1024 * 1024:
      raise ValueError("image is larger than 8MB")
    extension = Path(file_name).suffix.lower()
    signatures = {
      ".png": [b"\x89PNG\r\n\x1a\n"],
      ".jpg": [b"\xff\xd8\xff"],
      ".jpeg": [b"\xff\xd8\xff"],
      ".webp": [b"RIFF"],
    }
    if extension not in signatures:
      raise ValueError("only PNG, JPEG and WebP images are supported")
    if extension == ".webp":
      if len(content) < 12 or not content.startswith(b"RIFF") or content[8:12] != b"WEBP":
        raise ValueError("file content does not match WebP")
      return extension
    if not any(content.startswith(signature) for signature in signatures[extension]):
      raise ValueError("file content does not match extension")
    return ".jpg" if extension == ".jpeg" else extension

  def _validate_cv_value(self, value) -> int:
    cv_value = int(value)
    if cv_value < 0 or cv_value > 255:
      raise ValueError("CV value must be in range 0..255")
    return cv_value

  def _validate_cv_read_all_numbers(self, cv_numbers) -> list[int]:
    if cv_numbers is None:
      return list(range(1, 1025))
    if not isinstance(cv_numbers, list):
      raise TypeError("cv_numbers must be a list")
    validated = []
    seen = set()
    for value in cv_numbers:
      cv_number = validate_cv_number(int(value))
      if cv_number in seen:
        continue
      seen.add(cv_number)
      validated.append(cv_number)
    if not validated:
      raise ValueError("cv_numbers cannot be empty")
    return validated

  def _validate_cv_read_mode(self, read_mode) -> str:
    mode = str(read_mode or "known").lower()
    if mode not in {"known", "full"}:
      raise ValueError("read_mode must be known or full")
    return mode

  def _validate_controller_ip(self, ip_value) -> str:
    ip_text = str(ip_value or "").strip()
    address = ipaddress.ip_address(ip_text)
    if address.version != 4:
      raise ValueError("controller IP must be IPv4")
    return str(address)

  def _validate_udp_port(self, port_value) -> int:
    port = int(port_value)
    if port < 1 or port > 65535:
      raise ValueError("UDP port must be in range 1..65535")
    return port

  def _validate_checksum_algorithm(self, checksum_algorithm) -> str:
    normalized = str(checksum_algorithm or "").strip().lower()
    if normalized != "xor":
      raise ValueError("Only the confirmed DXDCNet xor checksum is enabled")
    return normalized

  def _validate_consist_members(self, members):
    if not isinstance(members, list) or not members:
      return response.failure("invalid_consist", "编组至少需要一辆车", ""), 400
    if len(members) > models.CONSIST_MAX_MEMBERS:
      return response.failure(
        "invalid_consist",
        f"编组最多 {models.CONSIST_MAX_MEMBERS} 辆",
        f"当前请求包含 {len(members)} 辆",
      ), 400
    return None

  def _sync_consist_member_addresses(self, state: dict, vehicle_id: str, address: int) -> None:
    if self.vehicle_store:
      self.vehicle_store.update_consist_member_address(vehicle_id, address)
    for consist in state["consists"]:
      for member in consist.get("members", []):
        if member.get("vehicle_id") == vehicle_id:
          member["address"] = address

  def _remove_consist_members_for_vehicle(self, state: dict, vehicle_id: str) -> None:
    for consist in state["consists"]:
      consist["members"] = [
        member for member in consist.get("members", [])
        if member.get("vehicle_id") != vehicle_id
      ]

  def _sync_vehicle_address_if_present(self, state: dict, vehicle_id, address: int) -> bool:
    if not vehicle_id:
      return False
    vehicle = self._find_by_id(state["vehicles"], vehicle_id)
    if vehicle is None:
      return False
    vehicle["address"] = address
    self._sync_consist_member_addresses(state, vehicle_id, address)
    self._save(state)
    return True

  def _replace_vehicle_functions(self, state: dict, vehicle_id: str, functions: list) -> None:
    state["functions"] = [fn for fn in state["functions"] if fn.get("vehicle_id") != vehicle_id]
    for index, function in enumerate(functions):
      function_number = int(function.get("function_number", index))
      if function_number < 0 or function_number > 68:
        raise ValueError("function number must be in range F0..F68")
      state["functions"].append({
        "id": function.get("id") or f"local-function-{vehicle_id}-{function_number}-{index}",
        "vehicle_id": vehicle_id,
        "function_number": function_number,
        "label": function.get("label") or f"F{function_number}",
        "icon_name": function.get("icon_name", ""),
        "button_type": int(function.get("button_type", 0)),
        "trigger_mode": self._validate_function_trigger_mode(function.get("trigger_mode", "toggle")),
        "duration_ms": max(0, int(function.get("duration_ms", function.get("time", 0)) or 0)),
        "position": int(function.get("position", index)),
        "show_function_number": bool(function.get("show_function_number", True)),
        "is_configured": bool(function.get("is_configured", True)),
      })
    state["functions"].sort(key=lambda fn: (fn.get("vehicle_id", ""), int(fn.get("position", 0)), int(fn.get("function_number", 0))))

  def _vehicle_with_functions(self, state: dict, vehicle: dict) -> dict:
    payload = dict(vehicle)
    payload["functions"] = [fn for fn in state["functions"] if fn.get("vehicle_id") == vehicle.get("id")]
    return payload

  def _validate_function_trigger_mode(self, value) -> str:
    mode = str(value or "toggle").strip().lower()
    if mode not in {"toggle", "momentary", "timed"}:
      raise ValueError(f"invalid function trigger mode: {value}")
    return mode

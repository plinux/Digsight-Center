"""Digsight DXDCNet controller adapter."""

import json

from digsight_dxdcnet.constants import (
  CMD_DEVICE_STATUS,
  CMD_LOCO_CONTROL_ACK,
  CMD_LOCO_FUNCTION,
  CMD_LOCO_SPEED,
  CMD_PARAMETER_VALUE,
  CMD_VERSION_DATA,
  DEVICE_TYPE_BOOSTER,
  DEVICE_TYPE_COMMAND_STATION,
  DEVICE_TYPE_SPECIAL,
  DEVICE_TYPE_THROTTLE,
  PROGRAMMER_ACK_NOACK,
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
from digsight_dxdcnet.device_status import parse_booster_status, parse_parameter_response
from digsight_dxdcnet.frames import decode_udp_frame
from digsight_dxdcnet.loco_control import (
  build_loco_control_request_frame,
  build_loco_function_frames,
  build_loco_speed_frame,
  parse_loco_control_ack,
  parse_loco_function_feedback,
  parse_loco_speed_feedback,
)
from digsight_dxdcnet.matchers import (
  build_programmer_ack_matcher,
  build_programmer_value_matcher,
  build_raw_frame_matcher,
  first_matching_frame,
)
from digsight_dxdcnet.programmer import build_cv_read_frame, build_cv_write_frame
from digsight_dxdcnet.programmer_responses import (
  classify_programmer_responses,
  programmer_ack_category,
  should_retry_busy_ack,
)
from digsight_dxdcnet.programming_track import (
  CVReadPlan,
  CVWritePlan,
  ProgrammingTrackSafety,
  ProgrammingTrackStatus,
)
from digsight_dxdcnet.session import DXDCNetSessionManager
from digsight_dxdcnet.udp_transport import UDPTransport

from server import models
from server.controllers.base import (
  ControllerCapabilities,
  ControllerFrameList,
  ControllerInfoReadRequest,
  ControllerInfoReadResult,
  ControllerOperationNotSupported,
  ControllerParameterWriteError,
  ControllerTransportDescriptor,
  CvCommandRequest,
  CvCommandResult,
  LocoCommandResult,
  LocoControlGrantRequest,
  LocoControlGrantResult,
  LocoFunctionRequest,
  LocoSpeedRequest,
  TrackOutputRequest,
  TrackOutputResult,
)
from server.controllers.common import (
  INFO_SECTION_DEVICE,
  INFO_SECTION_WORK,
  controller_info_sections,
)
from server.controllers.dxdcnet_constants import (
  CURRENT_LIMIT_PARAM_TO_MODE,
  PARAM_RAILCOM,
  PARAM_SCREEN_BRIGHTNESS,
  PARAM_SCREEN_DIRECTION,
)
from server.controllers.dxdcnet_info_parser import DXDCNetControllerInfoParser
from server.udp_transport_config import normalize_transport_config, transport_port_value


class DigsightDXDCNetControllerAdapter:
  kind = "digsight_controller"
  label = "动芯 拾Pro"
  default_display_name = "动芯 拾Pro"
  protocol = models.CONTROLLER_PROTOCOL_DXDCNET
  cv_method_prefix = "dxdcnet_programmer"
  supported_protocols = (models.CONTROLLER_PROTOCOL_DXDCNET,)
  config_file_name = "Digsight_D9000.json"
  default_ip = models.CONTROLLER_DEFAULT_IP
  runtime_transport_fields = ("udp_port", "local_udp_port", "udp_checksum_algorithm")
  field_descriptions = {
    "protocol": "该控制器使用的通讯协议名称；动芯拾Pro当前使用 DXDCNet。",
    "settings.railcom_enabled": "RailCom 开关；动芯 D9000 参数 0x03 使用 0x80 表示开、0x00 表示关。",
    "transport.kind": "传输类型；动芯拾Pro的 DXDCNet 协议当前使用 udp。",
    "transport.udp_port": "控制器远端 UDP 端口；动芯拾Pro当前默认使用 12000。",
    "transport.local_udp_port": "本机绑定的 UDP 端口；动芯拾Pro真实硬件通讯当前使用 6667。",
    "transport.udp_checksum_algorithm": "UDP 帧校验算法；动芯拾Pro当前使用 xor。",
    "track_profiles.<mode>.current_param": "动芯 D9000 限流参数地址；N/HO/G/DC 分别对应 0x81/0x82/0x83/0x84。",
  }
  capabilities = ControllerCapabilities(
    track_power=True,
    dc_control=True,
    read_info=True,
    cv_programming=True,
    loco_control=True,
    controller_settings=True,
    railcom_settings=True,
    sound_editor=True,
  )
  transport_descriptor = ControllerTransportDescriptor(
    kind="udp",
    defaults={
      "udp_port": models.DXDCNET_DEFAULT_UDP_PORT,
      "local_udp_port": models.DXDCNET_DEFAULT_LOCAL_UDP_PORT,
      "udp_checksum_algorithm": models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM,
    },
    endpoint_required_paths=("transport.udp_port",),
    metadata={
      "checksum_algorithms": (models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM,),
      "allow_zero_local_udp_port": False,
    },
  )
  info_sections = controller_info_sections(
    {
      "title": INFO_SECTION_DEVICE,
      "rows": [
        {"label": "设备名称", "path": "device_info.device_name"},
        {"label": "出厂编号", "path": "device_info.factory_number"},
        {"label": "MAC", "path": "device_info.mac_address", "format": "mac"},
        {"label": "内核版本", "path": "device_info.core_version"},
        {"label": "无线版本", "path": "device_info.wireless_version"},
        {"label": "RAILCOM", "path": "device_info.railcom_enabled", "format": "boolean"},
        {"label": "屏幕亮度", "path": "device_info.screen_brightness"},
        {
          "label": "屏幕方向",
          "path": "device_info.screen_direction_raw",
          "format": "screen_direction",
          "label_path": "device_info.screen_direction_label",
        },
        {"label": "硬件版本", "path": "device_info.hardware_version"},
        {"label": "软件版本", "path": "device_info.software_version"},
        {"label": "固件版本", "path": "device_info.firmware_version"},
      ],
    },
    {
      "title": INFO_SECTION_WORK,
      "rows": [
        {"label": "轨道电源", "path": "booster_status.power_on", "format": "power_state"},
        {"label": "短路状态", "path": "booster_status.short_circuit", "format": "short_circuit_state"},
        {"label": "温度", "path": "telemetry.temperature_c", "unit": "℃"},
        {"label": "电压", "path": "telemetry.track_voltage_v", "unit": "V"},
        {"label": "电流", "path": "telemetry.track_current_a", "unit": "A"},
        {"label": "功率", "path": "telemetry.track_power_w", "unit": "W"},
      ],
    },
  )

  def __init__(self, info_parser=None):
    self.info_parser = info_parser or DXDCNetControllerInfoParser()

  def create_session_manager(self, *, transport=None, context=None):
    return DXDCNetSessionManager(transport)

  def normalize_transport_config(self, transport, *, strict: bool) -> dict:
    return normalize_transport_config(transport, self.transport_descriptor, strict=strict)

  def endpoint_identity(self, controller: dict) -> tuple:
    return (
      ("transport", "udp"),
      ("ip", str(controller.get("ip") or "")),
      ("udp_port", str(controller.get("udp_port") or "")),
      ("local_udp_port", str(controller.get("local_udp_port") or "")),
      ("udp_checksum_algorithm", str(controller.get("udp_checksum_algorithm") or "").casefold()),
    )

  def session_identity(self, controller: dict) -> tuple:
    return (
      ("settings", json.dumps(controller.get("settings") or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))),
    )

  def apply_transport_runtime(self, controller: dict) -> None:
    transport = controller.get("transport") if isinstance(controller.get("transport"), dict) else {}
    defaults = self.transport_descriptor.defaults
    controller["udp_port"] = transport_port_value(transport.get("udp_port", defaults.get("udp_port", 0)))
    controller["local_udp_port"] = transport_port_value(transport.get("local_udp_port", defaults.get("local_udp_port", 0)))
    controller["udp_checksum_algorithm"] = str(
      transport.get("udp_checksum_algorithm", defaults.get("udp_checksum_algorithm", "unconfirmed"))
    )

  def main_track_loco_pom_op(self) -> int:
    return PROGRAMMER_OP_MAIN_LOCO_POM

  def exchange(
    self,
    session_manager,
    controller: dict,
    request_frame: bytes,
    *,
    timeout_seconds: float | None = None,
    max_packets: int = 32,
    stop_when=None,
    transport=None,
  ):
    active_transport = transport or UDPTransport(
      timeout_seconds=float(timeout_seconds if timeout_seconds is not None else controller.get("cv_timeout_seconds", 10.0)),
      retries=0,
    )
    raw_responses = session_manager.exchange(
      controller.get("ip") or models.CONTROLLER_DEFAULT_IP,
      int(controller.get("udp_port", 0)),
      request_frame,
      local_port=int(controller.get("local_udp_port", 0)),
      max_packets=max_packets,
      stop_when=stop_when,
      transport=active_transport,
    )
    frames = []
    diagnostic_frames = []
    for raw in raw_responses:
      frame = decode_udp_frame(raw)
      diagnostic_frames.append(frame)
      if frame.checksum_valid:
        frames.append(frame)
    return ControllerFrameList(frames, diagnostic_frames=diagnostic_frames)

  def _debug_responses(self, frames) -> list[dict]:
    diagnostic_frames = getattr(frames, "diagnostic_frames", frames)
    return [frame.to_debug_dict() for frame in diagnostic_frames]

  def read_info_frames(self, session_manager, controller: dict, requests: list, *, transport=None) -> dict:
    collected = {}
    read_warnings = []
    request_debug = []
    for spec in requests:
      name = spec["name"]
      request_frame = spec["request_frame"]
      expected_command = spec.get("expected_command")
      expected_device_type = spec.get("expected_device_type")
      timeout_seconds = spec.get("timeout_seconds", float(controller.get("read_info_timeout_seconds", 0.4)))
      stop_when = spec.get("stop_when")
      try:
        frames = self.exchange(
          session_manager,
          controller,
          request_frame,
          timeout_seconds=timeout_seconds,
          max_packets=8,
          stop_when=stop_when,
          transport=transport,
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
        "responses": self._debug_responses(frames),
      })
    return {
      "collected": collected,
      "warnings": read_warnings,
      "requests": request_debug,
    }

  def read_controller_info(
    self,
    session_manager,
    controller: dict,
    request: ControllerInfoReadRequest,
    *,
    transport=None,
  ) -> ControllerInfoReadResult:
    client_id = self.controller_client_id(controller)
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
    raw_result = self.read_info_frames(
      session_manager,
      controller,
      [
        {
          "name": name,
          "request_frame": request_frame,
          "expected_command": expected_command,
          "expected_device_type": expected_device_type,
          "timeout_seconds": self._controller_info_timeout_seconds(controller, name),
          "stop_when": build_raw_frame_matcher(expected_command, expected_device_type) if expected_command is not None else None,
        }
        for name, request_frame, expected_command, expected_device_type in request_specs
      ],
      transport=transport,
    )
    return ControllerInfoReadResult(
      collected=raw_result["collected"],
      warnings=raw_result["warnings"],
      requests=raw_result["requests"],
    )

  def parse_controller_info(self, controller: dict, request: ControllerInfoReadRequest, result: ControllerInfoReadResult) -> dict:
    return self.info_parser.apply(
      controller,
      request.track_mode,
      request.current_param,
      result.collected,
      result.warnings,
    )

  def runtime_readiness_warnings(self, controller: dict) -> list[str]:
    warnings = []
    if str(controller.get("ip") or "").strip() in ("", models.CONTROLLER_DEFAULT_IP):
      warnings.append("controller_ip_unconfigured")
    if int(controller.get("udp_port", 0)) <= 0:
      warnings.append("udp_port_unconfirmed")
    if (controller.get("udp_checksum_algorithm") or "unconfirmed") == "unconfirmed":
      warnings.append("udp_checksum_algorithm_unconfirmed")
    return warnings

  def loco_control_readiness_warnings(self, controller: dict) -> list[str]:
    warnings = self.runtime_readiness_warnings(controller)
    if not bool(controller.get("last_probe_ok")) and not bool(controller.get("controller_reachable")):
      warnings.append("controller_not_confirmed")
    return warnings

  def status_not_ready_message(self) -> str:
    return "控制器通信参数尚未确认"

  def readiness_warning_detail(self, warnings: list[str]) -> str:
    warning_set = set(warnings)
    if warning_set == {"controller_ip_unconfigured"}:
      return "控制器 IP 尚未配置"
    if warning_set == {"udp_checksum_algorithm_unconfirmed"}:
      return "控制器 UDP 校验算法未确认"
    if "udp_port_unconfirmed" in warning_set and "udp_checksum_algorithm_unconfirmed" in warning_set:
      return "控制器 UDP 端口和校验算法未确认"
    if "udp_port_unconfirmed" in warning_set:
      return "控制器 UDP 端口未确认"
    return "控制器通信端点尚未确认"

  def is_booster_status_confirmed(self, controller: dict) -> bool:
    booster_status = controller.get("booster_status")
    return isinstance(booster_status, dict) and booster_status.get("source") == "dxdcnet_status_0x23"

  def programming_track_status(self, controller: dict):
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

  def validate_programming_track_safety(self, programming_status) -> None:
    ProgrammingTrackSafety().validate(programming_status)

  def send_track_output(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=8,
      stop_when=stop_when,
      transport=transport,
    )

  def send_track_output_request(
    self,
    session_manager,
    controller: dict,
    request: TrackOutputRequest,
    *,
    transport=None,
  ) -> TrackOutputResult:
    client_id = self.controller_client_id(controller)
    request_frame = build_track_output_frame(
      client_id,
      1,
      request.powered,
      request.output_value,
      dcc_mode=request.track_mode != models.TRACK_MODE_DC,
      dc_direction_positive=request.dc_direction_positive,
    )
    frames = self.send_track_output(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=request.timeout_seconds,
      stop_when=build_raw_frame_matcher(CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER),
      transport=transport,
    )
    booster_frame = first_matching_frame(frames, CMD_DEVICE_STATUS, DEVICE_TYPE_BOOSTER)
    booster_status = {}
    if booster_frame is not None:
      booster_status = parse_booster_status(booster_frame.payload)
      booster_status["source"] = "dxdcnet_status_0x23"
      booster_status["payload_hex"] = booster_frame.payload.hex(" ")
    return TrackOutputResult(
      request_hex=request_frame.hex(" "),
      frames=frames,
      booster_status=booster_status,
      debug={"responses": self._debug_responses(frames)},
    )

  def read_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    return self._exchange_cv_command_frames(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      stop_when=stop_when,
      transport=transport,
    )

  def read_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    request_frame = self._build_cv_request_frame(request)
    frames = self.read_cv(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=request.timeout_seconds,
      max_packets=request.max_packets,
      stop_when=build_programmer_value_matcher(request.client_id, request.cv_number, pom_address=request.pom_address),
      transport=transport,
    )
    return CvCommandResult(request_hex=request_frame.hex(" "), frames=frames)

  def write_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    return self._exchange_cv_command_frames(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      stop_when=stop_when,
      transport=transport,
    )

  def _exchange_cv_command_frames(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      stop_when=stop_when,
      transport=transport,
    )

  def write_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    request_frame = self._build_cv_request_frame(request)
    frames = self.write_cv(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=request.timeout_seconds,
      max_packets=request.max_packets,
      stop_when=build_programmer_ack_matcher(request.client_id),
      transport=transport,
    )
    return CvCommandResult(request_hex=request_frame.hex(" "), frames=frames)

  def classify_cv_responses(self, frames: list, *, client_id: int, cv_number: int, pom_address: int | None = None):
    return classify_programmer_responses(
      frames,
      client_id=client_id,
      cv_number=cv_number,
      pom_address=pom_address,
    )

  def cv_ack_category(self, ack) -> str:
    return programmer_ack_category(ack.ack_mode)

  def should_retry_cv_write_ack(self, ack, *, attempt: int, retry_count: int) -> bool:
    return should_retry_busy_ack(ack.ack_mode, attempt=attempt, retry_count=retry_count)

  def is_main_track_cv_read_no_ack(self, ack) -> bool:
    return ack.ack_mode == PROGRAMMER_ACK_NOACK

  def cv_ack_debug(self, ack) -> dict:
    return {
      "ack": ack.ack_name,
      "ack_mode": ack.ack_mode,
    }

  def request_loco_control_grant(
    self,
    session_manager,
    controller: dict,
    request: LocoControlGrantRequest,
    *,
    transport=None,
  ) -> LocoControlGrantResult:
    self._ensure_dcc_128_loco_request(request)
    request_frame = build_loco_control_request_frame(address=request.address, client_id=request.client_id)
    frames = self._request_loco_control_frames(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=float(controller.get("loco_control_request_timeout_seconds", 0.2)),
      stop_when=self._build_loco_control_ack_matcher(request.address),
      transport=transport,
    )
    feedback = self._first_loco_control_ack(frames, request.address)
    if feedback is not None:
      feedback["granted_to_client"] = (
        bool(feedback.get("granted"))
        and int(feedback.get("granted_device_type", -1)) == DEVICE_TYPE_THROTTLE
        and int(feedback.get("granted_id", -1)) == int(request.client_id)
      )
    return LocoControlGrantResult(
      request_hex=request_frame.hex(" "),
      address=request.address,
      feedback=feedback,
      frames=frames,
    )

  def send_loco_speed_request(
    self,
    session_manager,
    controller: dict,
    request: LocoSpeedRequest,
    *,
    transport=None,
  ) -> LocoCommandResult:
    self._ensure_dcc_128_loco_request(request)
    request_frames, extra = self._build_loco_speed_frames(request)
    feedback, collected_frames = self._send_loco_feedback_frames(
      session_manager,
      controller,
      request_frames,
      request.address,
      CMD_LOCO_SPEED + 0x08,
      parse_loco_speed_feedback,
      transport=transport,
    )
    return LocoCommandResult(
      request_hex=request_frames[-1].hex(" "),
      request_hexes=[frame.hex(" ") for frame in request_frames],
      feedback=feedback,
      extra=extra,
      frames=collected_frames,
    )

  def send_loco_function_request(
    self,
    session_manager,
    controller: dict,
    request: LocoFunctionRequest,
    *,
    transport=None,
  ) -> LocoCommandResult:
    self._ensure_dcc_128_loco_request(request)
    request_frames, extra = self._build_loco_function_frames(request)
    feedback, collected_frames = self._send_loco_feedback_frames(
      session_manager,
      controller,
      request_frames,
      request.address,
      CMD_LOCO_FUNCTION + 0x08,
      parse_loco_function_feedback,
      transport=transport,
    )
    return LocoCommandResult(
      request_hex=request_frames[-1].hex(" "),
      request_hexes=[frame.hex(" ") for frame in request_frames],
      feedback=feedback,
      extra=extra,
      frames=collected_frames,
    )

  def _request_loco_control_frames(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=4,
      stop_when=stop_when,
      transport=transport,
    )

  def _send_loco_feedback_frames(
    self,
    session_manager,
    controller: dict,
    request_frames: list[bytes],
    address: int,
    feedback_command: int,
    feedback_parser,
    *,
    transport=None,
  ):
    feedback = None
    collected_frames = []
    for request_frame in request_frames:
      frames = self._send_loco_feedback_frame(
        session_manager,
        controller,
        request_frame,
        timeout_seconds=float(controller.get("loco_control_timeout_seconds", 0.5)),
        stop_when=self._build_loco_feedback_matcher(address, feedback_command, feedback_parser),
        transport=transport,
      )
      collected_frames.extend(frames)
      feedback = self._first_loco_feedback(
        frames,
        address,
        feedback_command,
        feedback_parser,
      ) or feedback
    return feedback, collected_frames

  def _send_loco_feedback_frame(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=8,
      stop_when=stop_when,
      transport=transport,
    )

  def _build_loco_speed_frames(self, request: LocoSpeedRequest) -> tuple[list[bytes], dict]:
    return [
      build_loco_speed_frame(
        address=request.address,
        speed=request.speed,
        direction=request.direction,
        client_id=request.client_id,
      )
    ], {"direction": request.direction}

  def _build_loco_function_frames(self, request: LocoFunctionRequest) -> tuple[list[bytes], dict]:
    return build_loco_function_frames(
      address=request.address,
      function_states=request.function_states,
      client_id=request.client_id,
      function_number=request.function_number,
    ), {}

  def _ensure_dcc_128_loco_request(self, request) -> None:
    protocol = models.validate_control_protocol(request.control_protocol)
    steps = models.validate_speed_steps(protocol, request.speed_steps)
    if protocol != models.CONTROL_PROTOCOL_DCC or steps != models.DEFAULT_SPEED_STEPS:
      raise ControllerOperationNotSupported(f"loco_protocol_{protocol}_{steps}", self.kind)

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

  def _build_loco_feedback_matcher(self, address: int, command: int, parser):
    def matches(raw: bytes) -> bool:
      try:
        frame = decode_udp_frame(raw)
        if not frame.checksum_valid or frame.command != command:
          return False
        feedback = parser(frame)
      except ValueError:
        return False
      return int(feedback.get("address", 0)) == int(address)
    return matches

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

  def _first_loco_feedback(self, frames: list, address: int, command: int, parser):
    for frame in frames:
      if frame.command != command:
        continue
      try:
        feedback = parser(frame)
      except ValueError:
        continue
      if int(feedback.get("address", 0)) == int(address):
        return feedback
    return None

  def apply_track_profile_parameters(self, session_manager, controller: dict, profiles: dict, modes: list[str], *, transport=None) -> list[dict]:
    results = []
    client_id = self.controller_client_id(controller)
    for mode in modes:
      profile = profiles.get(mode, {})
      target_current_limit_ma = profile.get("target_current_limit_ma")
      if target_current_limit_ma in ("", None):
        continue
      param_address = int(profile.get("current_param", models.default_track_profiles()[mode]["current_param"]))
      raw_value = int(int(target_current_limit_ma) / models.CURRENT_STEP_MA)
      if raw_value < 1 or raw_value > 0xFF:
        raise ControllerParameterWriteError(
          f"{profile.get('name', mode)} 限流值不能转换为 D9000 参数原始值",
          {"mode": mode, "target_current_limit_ma": target_current_limit_ma, "raw_value": raw_value},
        )
      write_frame = build_parameter_write_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, param_address, raw_value)
      read_frame = build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, param_address)
      write_frames = self.exchange(
        session_manager,
        controller,
        write_frame,
        timeout_seconds=float(controller.get("parameter_write_timeout_seconds", 0.25)),
        max_packets=4,
        transport=transport,
      )
      read_frames = self.exchange(
        session_manager,
        controller,
        read_frame,
        timeout_seconds=float(controller.get("parameter_readback_timeout_seconds", 0.25)),
        max_packets=8,
        stop_when=build_raw_frame_matcher(CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION),
        transport=transport,
      )
      parameter_frame = first_matching_frame(read_frames, CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION)
      if parameter_frame is None:
        raise ControllerParameterWriteError(
          f"{profile.get('name', mode)} 限流参数写入后未读到确认回包",
          {
            "mode": mode,
            "param_address": param_address,
            "expected_raw_value": raw_value,
            "write_request_hex": write_frame.hex(" "),
            "read_request_hex": read_frame.hex(" "),
            "write_responses": self._debug_responses(write_frames),
            "read_responses": self._debug_responses(read_frames),
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
        "target_current_limit_ma": int(target_current_limit_ma),
        "write_request_hex": write_frame.hex(" "),
        "read_request_hex": read_frame.hex(" "),
      })
    return results

  def apply_controller_private_settings(self, session_manager, controller: dict, settings: dict, keys: list[str], *, transport=None) -> list[dict]:
    results = []
    for key in keys:
      if key != "railcom_enabled":
        raise ControllerOperationNotSupported(f"controller_setting:{key}", self.kind)
      results.append(self._apply_railcom_setting(
        session_manager,
        controller,
        bool(settings.get("railcom_enabled")),
        transport=transport,
      ))
    return results

  def _apply_railcom_setting(self, session_manager, controller: dict, enabled: bool, *, transport=None) -> dict:
    client_id = self.controller_client_id(controller)
    raw_value = 0x80 if enabled else 0x00
    write_frame = build_parameter_write_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, PARAM_RAILCOM, raw_value)
    read_frame = build_parameter_read_frame(client_id, DEVICE_TYPE_COMMAND_STATION, 0, PARAM_RAILCOM)
    write_frames = self.exchange(
      session_manager,
      controller,
      write_frame,
      timeout_seconds=float(controller.get("parameter_write_timeout_seconds", 0.25)),
      max_packets=4,
      transport=transport,
    )
    read_frames = self.exchange(
      session_manager,
      controller,
      read_frame,
      timeout_seconds=float(controller.get("parameter_readback_timeout_seconds", 0.25)),
      max_packets=8,
      stop_when=build_raw_frame_matcher(CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION),
      transport=transport,
    )
    parameter_frame = first_matching_frame(read_frames, CMD_PARAMETER_VALUE, DEVICE_TYPE_COMMAND_STATION)
    if parameter_frame is None:
      raise ControllerParameterWriteError(
        "RailCom 参数写入后未读到确认回包",
        {
          "setting": "railcom_enabled",
          "param_address": PARAM_RAILCOM,
          "expected_raw_value": raw_value,
          "write_request_hex": write_frame.hex(" "),
          "read_request_hex": read_frame.hex(" "),
          "write_responses": self._debug_responses(write_frames),
          "read_responses": self._debug_responses(read_frames),
        },
      )
    parsed = parse_parameter_response(parameter_frame.payload)
    if parsed["param_address"] != PARAM_RAILCOM or int(parsed["value"]) != raw_value:
      raise ControllerParameterWriteError(
        "RailCom 参数读回值不一致",
        {
          "setting": "railcom_enabled",
          "param_address": PARAM_RAILCOM,
          "expected_raw_value": raw_value,
          "actual": parsed,
          "write_request_hex": write_frame.hex(" "),
          "read_request_hex": read_frame.hex(" "),
        },
      )
    controller.setdefault("device_info", {})["railcom_enabled"] = enabled
    controller["device_info"]["railcom_raw"] = raw_value
    controller["device_info"]["railcom_source"] = "dxdcnet_param_0x03"
    return {
      "setting": "railcom_enabled",
      "param_address": PARAM_RAILCOM,
      "raw_value": raw_value,
      "enabled": enabled,
      "write_request_hex": write_frame.hex(" "),
      "read_request_hex": read_frame.hex(" "),
    }

  def controller_client_id(self, controller: dict) -> int:
    client_id = int(controller.get("client_id", 1))
    if client_id < 0 or client_id > 127:
      raise ValueError("DXDCNet client id must be in 0..127")
    return client_id

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

  def _build_cv_request_frame(self, request: CvCommandRequest) -> bytes:
    if request.value is None:
      if request.op is None:
        return CVReadPlan(cv_number=request.cv_number).request_frame(client_id=request.client_id)
      return build_cv_read_frame(
        request.cv_number,
        client_id=request.client_id,
        op=int(request.op),
        pom_address=request.pom_address,
      )
    if request.op is None:
      return CVWritePlan(cv_number=request.cv_number, value=request.value).request_frame(client_id=request.client_id)
    return build_cv_write_frame(
      request.cv_number,
      request.value,
      client_id=request.client_id,
      op=int(request.op),
      pom_address=request.pom_address,
    )

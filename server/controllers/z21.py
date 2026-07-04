"""Roco/Fleischmann Z21 LAN controller adapters."""

from dataclasses import dataclass
from typing import Callable

from z21_lan import (
  DEFAULT_Z21_PORT,
  LAN_GET_BROADCASTFLAGS,
  LAN_GET_COMMON_SETTINGS,
  LAN_GET_HWINFO,
  LAN_GET_MMDCC_SETTINGS,
  LAN_GET_SERIAL_NUMBER,
  LAN_SET_COMMON_SETTINGS,
  LAN_SET_MMDCC_SETTINGS,
  LAN_SYSTEMSTATE_DATACHANGED,
  LAN_X,
  Z21CvAck,
  Z21Dataset,
  Z21LocoInfo,
  Z21SessionManager,
  build_x_cv_pom_read_byte,
  build_x_cv_pom_write_byte,
  build_x_cv_read_direct,
  build_x_cv_write_direct,
  build_get_common_settings,
  build_get_mmdcc_settings,
  build_set_loco_mode,
  build_get_broadcast_flags,
  build_get_hwinfo,
  build_get_serial_number,
  build_get_system_state,
  build_set_mmdcc_settings,
  build_set_common_settings,
  build_x_get_firmware_version,
  build_x_get_loco_info,
  build_x_set_loco_drive,
  build_x_set_loco_function,
  build_x_set_track_power_off,
  build_x_set_track_power_on,
  decode_datasets,
  parse_broadcast_flags,
  parse_common_settings,
  parse_cv_result,
  parse_hwinfo,
  parse_loco_info,
  parse_mmdcc_settings,
  parse_serial_number,
  parse_system_state,
  parse_xbus_ack,
  synthetic_pom_write_ack,
)

from server import models
from server.controller_safety import mark_controller_safety_fresh
from server.controllers.base import (
  ControllerCapabilities,
  ControllerParameterWriteError,
  CvCommandRequest,
  CvCommandResult,
  ControllerInfoReadResult,
  ControllerTransportDescriptor,
  LocoCommandResult,
  LocoControlGrantRequest,
  LocoControlGrantResult,
  LocoFunctionRequest,
  LocoSpeedRequest,
  TrackOutputResult,
)
from server.controllers.common import (
  INFO_SECTION_DEVICE,
  INFO_SECTION_WORK,
  controller_info_sections,
  controller_not_ready_message,
  endpoint_readiness_detail,
  endpoint_readiness_warnings,
  read_only_controller_client_id,
  read_only_programming_track_status,
  read_only_session_identity,
  track_profiles_with_limits,
  update_cv_safety_from_programming_status,
  validate_transport_port,
)


@dataclass(frozen=True)
class Z21ModelProfile:
  kind: str
  label: str
  config_file_name: str
  max_current_ma: int
  enabled_modes: set[str]
  model_note: str


@dataclass(frozen=True)
class Z21ReadInfoSpec:
  name: str
  expected_header: int
  request_bytes: bytes
  parser: Callable[[bytes], dict] | None


@dataclass
class Z21CvClassification:
  value: object | None = None
  value_frame: object | None = None
  ack: object | None = None
  ack_frame: object | None = None
  parse_warnings: list | None = None

  def __post_init__(self):
    if self.parse_warnings is None:
      self.parse_warnings = []


@dataclass(frozen=True)
class Z21ProgrammingTrackStatus:
  track_mode: str
  dcc_mode: bool
  programming_track_busy: bool
  programming_track_current_ma: int
  output_value: int
  current_limit_ma: int
  current_limit_confirmed: bool = False


Z21_DEFAULT_TRACK_VOLTAGE_V = 16.0
Z21_MIN_TRACK_VOLTAGE_V = 11.0
Z21_MAX_TRACK_VOLTAGE_V = 23.0
Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING = "programming_track_voltage_v"


Z21_STD_PROFILE = Z21ModelProfile(
  kind=models.CONTROLLER_KIND_Z21_STD,
  label="Z21",
  config_file_name="Z21.json",
  max_current_ma=3000,
  enabled_modes={models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G},
  model_note="Z21 标准版使用 Z21 LAN 协议，官方 FAQ 标称主轨最大 3A、电压可配置。",
)
Z21_START_PROFILE = Z21ModelProfile(
  kind=models.CONTROLLER_KIND_Z21_START,
  label="z21 start",
  config_file_name="Z21_Start.json",
  max_current_ma=3000,
  enabled_modes={models.TRACK_MODE_N, models.TRACK_MODE_HO},
  model_note="z21 start 使用 Z21 LAN 协议，官方页面标称最大 3A，默认配置面向 N/HO。",
)
Z21_XL_PROFILE = Z21ModelProfile(
  kind=models.CONTROLLER_KIND_Z21_XL,
  label="Z21 XL",
  config_file_name="Z21_XL.json",
  max_current_ma=6000,
  enabled_modes={models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G},
  model_note="Z21 XL 使用 Z21 LAN 协议，官方页面标称 6A 主轨输出，面向 0/1/2/G 等大比例。",
)


class Z21LanControllerAdapter:
  """Adapter for one Z21 LAN controller model profile."""

  protocol = models.CONTROLLER_PROTOCOL_Z21_LAN
  cv_method_prefix = "z21_lan"
  supported_protocols = (models.CONTROLLER_PROTOCOL_Z21_LAN,)
  default_ip = models.CONTROLLER_DEFAULT_IP
  runtime_transport_fields = ("udp_port", "local_udp_port")
  capabilities = ControllerCapabilities(
    track_power=True,
    dc_control=False,
    read_info=True,
    cv_programming=True,
    loco_control=True,
    controller_settings=False,
    railcom_settings=True,
  )
  transport_descriptor = ControllerTransportDescriptor(
    kind="udp",
    defaults={
      "udp_port": DEFAULT_Z21_PORT,
      "local_udp_port": 0,
    },
    endpoint_required_paths=("transport.udp_port",),
    metadata={
      "allow_zero_local_udp_port": True,
    },
  )
  info_sections = controller_info_sections(
    {
      "title": INFO_SECTION_DEVICE,
      "rows": [
        {"label": "硬件类型", "path": "device_info.hardware_type_label"},
        {"label": "硬件类型值", "path": "device_info.hardware_type_hex"},
        {"label": "固件版本", "path": "device_info.firmware_version_hex"},
        {"label": "序列号", "path": "device_info.serial_number"},
        {"label": "广播标志", "path": "device_info.broadcast_flags_hex"},
      ],
    },
    {
      "title": INFO_SECTION_WORK,
      "rows": [
        {"label": "主轨电流", "path": "booster_status.main_track_current_ma", "unit": "mA"},
        {"label": "主轨平滑电流", "path": "booster_status.filtered_main_track_current_ma", "unit": "mA"},
        {"label": "编程轨电流", "path": "booster_status.programming_track_current_ma", "unit": "mA"},
        {"label": "输出电压", "path": "booster_status.output_voltage_v", "unit": "V"},
        {"label": "电源适配器电压", "path": "booster_status.supply_voltage_v", "unit": "V"},
        {"label": "温度", "path": "telemetry.temperature_c", "unit": "℃"},
        {"label": "轨道电源", "path": "booster_status.power_on", "format": "power_state"},
        {"label": "短路状态", "path": "booster_status.short_circuit", "format": "short_circuit_state"},
      ],
    },
  )

  def __init__(self, profile: Z21ModelProfile):
    self.profile = profile
    self.kind = profile.kind
    self.label = profile.label
    self.default_display_name = profile.label
    self.config_file_name = profile.config_file_name
    self.capabilities = ControllerCapabilities(
      track_power=True,
      dc_control=False,
      read_info=True,
      cv_programming=True,
      loco_control=True,
      controller_settings=profile.kind != models.CONTROLLER_KIND_Z21_START,
      railcom_settings=True,
      profile_settings_on_track_mode=profile.kind != models.CONTROLLER_KIND_Z21_START,
    )
    self.default_track_profiles = track_profiles_with_limits(
      enabled_modes=profile.enabled_modes,
      target_voltage_v=Z21_DEFAULT_TRACK_VOLTAGE_V,
      min_target_voltage_v=Z21_MIN_TRACK_VOLTAGE_V,
      max_target_voltage_v=Z21_MAX_TRACK_VOLTAGE_V,
      controller_output_fields=False,
      current_limit_fields=False,
    )
    self.default_settings = {
      Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING: Z21_DEFAULT_TRACK_VOLTAGE_V,
    }
    self.track_output_setting_keys = (Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING,)
    self.track_output_setting_specs = [{
      "key": Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING,
      "label": "编程轨电压 V",
      "type": "number",
      "min": Z21_MIN_TRACK_VOLTAGE_V,
      "max": Z21_MAX_TRACK_VOLTAGE_V,
      "step": 0.1,
      "unit": "V",
      "note": "Z21 编程轨电压固定使用该值；N/HO/G 的主轨目标电压仍按当前比例分别保存并在切换比例时写入。",
    }]
    self.field_descriptions = {
      "protocol": "该控制器使用的通讯协议名称；Z21、z21 start 和 Z21 XL 均使用 Z21LAN。",
      "settings.railcom_enabled": "RailCom cutout 开关；Z21 LAN Common Settings offset 0 写入后用同一字段读回校验。",
      f"settings.{Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING}": "Z21 编程轨电压，使用 MMDCC offset 0x0e 写入，默认 16V，官方设置范围为 11..23V。",
      "transport.kind": "传输类型；Z21 LAN 协议使用 udp。",
      "transport.udp_port": "控制器远端 UDP 端口；Z21 LAN 默认使用 21105。",
      "transport.local_udp_port": "本机绑定的 UDP 端口；0 表示由系统自动分配临时端口。",
      "track_profiles.<mode>.enabled": "Z21 不按 N/HO/G 区分控制器输出模式；本字段只控制本系统车辆比例入口是否可选，DC 不支持。",
      "track_profiles.<mode>.target_voltage_v": "Z21 的 N/HO/G 入口保存该比例的主轨目标电压；切换到对应比例时会用 MMDCC offset 0x0c 写入主轨输出电压，默认均为 16V；Z21 官方设置范围为 11..23V。",
      "track_profiles.<mode>.min_target_voltage_v": "Z21 轨道输出电压最小配置值，官方设置范围下限为 11V。",
      "track_profiles.<mode>.max_target_voltage_v": "Z21 轨道输出电压最大配置值，官方设置范围上限为 23V。",
    }

  def create_session_manager(self, *, transport=None, context=None):
    return Z21SessionManager(transport)

  def normalize_transport_config(self, transport, *, strict: bool) -> dict:
    source = transport if isinstance(transport, dict) else {}
    default_remote_port = self.transport_descriptor.defaults["udp_port"]
    try:
      udp_port = validate_transport_port(source.get("udp_port", default_remote_port), "Z21 UDP port")
      local_udp_port = validate_transport_port(source.get("local_udp_port", 0), "Z21 local UDP port", allow_zero=True)
    except (TypeError, ValueError):
      if strict:
        raise
      udp_port = default_remote_port
      local_udp_port = 0
    return {
      "kind": self.transport_descriptor.kind,
      "udp_port": udp_port,
      "local_udp_port": local_udp_port,
    }

  def apply_transport_runtime(self, controller: dict) -> None:
    transport = controller.get("transport") if isinstance(controller.get("transport"), dict) else {}
    controller["udp_port"] = validate_transport_port(
      transport.get("udp_port", self.transport_descriptor.defaults["udp_port"]),
      "Z21 UDP port",
    )
    controller["local_udp_port"] = validate_transport_port(
      transport.get("local_udp_port", self.transport_descriptor.defaults["local_udp_port"]),
      "Z21 local UDP port",
      allow_zero=True,
    )

  def endpoint_identity(self, controller: dict) -> tuple:
    return (
      ("transport", "udp"),
      ("ip", str(controller.get("ip") or "")),
      ("udp_port", str(controller.get("udp_port") or "")),
      ("local_udp_port", str(controller.get("local_udp_port") or "")),
    )

  def session_identity(self, controller: dict) -> tuple:
    return read_only_session_identity(controller)

  def normalize_controller_private_setting(self, key: str, value):
    if key != Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING:
      raise ValueError(f"unsupported controller setting: {key}")
    return _z21_voltage_mv(value) / 1000

  def runtime_readiness_warnings(self, controller: dict) -> list[str]:
    return endpoint_readiness_warnings(controller, port_field="udp_port", port_warning="udp_port_unconfirmed")

  def loco_control_readiness_warnings(self, controller: dict) -> list[str]:
    return self.runtime_readiness_warnings(controller)

  def status_not_ready_message(self) -> str:
    return controller_not_ready_message()

  def readiness_warning_detail(self, warnings: list[str]) -> str:
    return endpoint_readiness_detail(warnings, port_warning="udp_port_unconfirmed", port_detail="控制器 UDP 端口未确认")

  def controller_client_id(self, controller: dict) -> int:
    return read_only_controller_client_id(controller)

  def read_controller_info(self, session_manager, controller: dict, request, *, transport=None) -> ControllerInfoReadResult:
    host = controller.get("ip") or models.CONTROLLER_DEFAULT_IP
    port = int(controller.get("udp_port", self.transport_descriptor.defaults["udp_port"]))
    local_port = int(controller.get("local_udp_port", self.transport_descriptor.defaults["local_udp_port"]))
    specs = [
      Z21ReadInfoSpec("serial_number", LAN_GET_SERIAL_NUMBER, build_get_serial_number(), parse_serial_number),
      Z21ReadInfoSpec("hardware_info", LAN_GET_HWINFO, build_get_hwinfo(), parse_hwinfo),
      Z21ReadInfoSpec("broadcast_flags", LAN_GET_BROADCASTFLAGS, build_get_broadcast_flags(), parse_broadcast_flags),
      Z21ReadInfoSpec("common_settings", LAN_GET_COMMON_SETTINGS, build_get_common_settings(), parse_common_settings),
      Z21ReadInfoSpec("system_state", LAN_SYSTEMSTATE_DATACHANGED, build_get_system_state(), parse_system_state),
      Z21ReadInfoSpec("firmware_version", LAN_X, build_x_get_firmware_version(), None),
    ]
    collected = {}
    warnings = []
    request_debug = []
    for spec in specs:
      try:
        responses = session_manager.exchange(host, port, spec.request_bytes, local_port=local_port, max_packets=4)
        dataset = _first_dataset_with_header(responses, spec.expected_header)
        parsed = spec.parser(dataset.payload) if spec.parser else {"payload_hex": dataset.payload.hex(" ")}
        collected[spec.name] = parsed
        request_debug.append({
          "name": spec.name,
          "request_hex": spec.request_bytes.hex(" "),
          "response_count": len(responses),
          "response_headers": [decoded.header for raw in responses for decoded in decode_datasets(raw)],
        })
      except TimeoutError:
        warnings.append(f"{spec.name}_timeout")
      except (OSError, ValueError) as exc:
        warnings.append(f"{spec.name}_read_error:{exc}")
    return ControllerInfoReadResult(
      collected=collected,
      warnings=warnings,
      requests=request_debug,
    )

  def send_track_output_request(
    self,
    session_manager,
    controller: dict,
    request,
    *,
    transport=None,
  ) -> TrackOutputResult:
    host = controller.get("ip") or models.CONTROLLER_DEFAULT_IP
    port = int(controller.get("udp_port", self.transport_descriptor.defaults["udp_port"]))
    local_port = int(controller.get("local_udp_port", self.transport_descriptor.defaults["local_udp_port"]))
    request_bytes = build_x_set_track_power_on() if request.powered else build_x_set_track_power_off()
    responses = []
    warnings = []
    try:
      responses.extend(session_manager.exchange(
        host,
        port,
        request_bytes,
        local_port=local_port,
        max_packets=4,
        stop_when=_dataset_header_matcher(LAN_SYSTEMSTATE_DATACHANGED),
      ))
    except TimeoutError as exc:
      warnings.append(f"track_power_command_timeout:{exc}")
    if _first_dataset_with_header_or_none(responses, LAN_SYSTEMSTATE_DATACHANGED) is None:
      responses.extend(session_manager.exchange(
        host,
        port,
        build_get_system_state(),
        local_port=local_port,
        max_packets=4,
        stop_when=_dataset_header_matcher(LAN_SYSTEMSTATE_DATACHANGED),
      ))
    dataset = _first_dataset_with_header(responses, LAN_SYSTEMSTATE_DATACHANGED)
    system_state = parse_system_state(dataset.payload)
    booster_status = _z21_booster_status_from_system_state(system_state, payload_hex=dataset.payload.hex(" "))
    return TrackOutputResult(
      request_hex=request_bytes.hex(" "),
      frames=responses,
      booster_status=booster_status,
      debug={
        "responses": _debug_responses(responses),
        "warnings": warnings,
      },
    )

  def read_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    if request.pom_address is None:
      request_bytes = build_x_cv_read_direct(request.cv_number)
    else:
      request_bytes = build_x_cv_pom_read_byte(request.pom_address, request.cv_number)
    responses = self._exchange_z21(
      session_manager,
      controller,
      request_bytes,
      max_packets=request.max_packets,
      stop_when=_z21_cv_response_matcher(),
      timeout_seconds=self._cv_timeout_seconds(controller, request.timeout_seconds),
    )
    return CvCommandResult(
      request_hex=request_bytes.hex(" "),
      frames=_decode_z21_response_datasets(responses),
    )

  def write_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    if request.value is None:
      raise ValueError("Z21 CV write requires a value")
    if request.pom_address is None:
      request_bytes = build_x_cv_write_direct(request.cv_number, request.value)
      responses = self._exchange_z21(
        session_manager,
        controller,
        request_bytes,
        max_packets=request.max_packets,
        stop_when=_z21_cv_response_matcher(),
        timeout_seconds=self._cv_timeout_seconds(controller, request.timeout_seconds),
      )
      frames = _decode_z21_response_datasets(responses)
    else:
      request_bytes = build_x_cv_pom_write_byte(request.pom_address, request.cv_number, request.value)
      frames = [self._send_z21_no_reply_command(
        session_manager,
        controller,
        request_bytes,
        synthetic_pom_write_ack(),
        max_packets=request.max_packets,
      )]
    return CvCommandResult(request_hex=request_bytes.hex(" "), frames=frames)

  def classify_cv_responses(self, frames: list, *, client_id: int, cv_number: int, pom_address: int | None = None):
    classification = Z21CvClassification(parse_warnings=[])
    for frame in _iter_z21_cv_frames(frames):
      if isinstance(frame, Z21CvAck):
        classification.ack = frame
        classification.ack_frame = frame
        continue
      try:
        value = parse_cv_result(frame.payload, pom_address=pom_address)
      except ValueError:
        try:
          ack = parse_xbus_ack(frame.payload)
        except ValueError as exc:
          classification.parse_warnings.append(str(exc))
          continue
        classification.ack = ack
        classification.ack_frame = frame
        continue
      if int(value.cv_number) != int(cv_number):
        continue
      classification.value = value
      classification.value_frame = frame
      classification.ack = Z21CvAck(
        "ack",
        "LAN_X_CV_RESULT",
        "Z21 returned CV value",
        frame.payload.hex(" "),
      )
      classification.ack_frame = frame
      return classification
    return classification

  def cv_ack_category(self, ack) -> str:
    return "ack" if getattr(ack, "ack_mode", "") == "ack" else "rejected"

  def should_retry_cv_write_ack(self, ack, *, attempt: int, retry_count: int) -> bool:
    return False

  def is_main_track_cv_read_no_ack(self, ack) -> bool:
    return getattr(ack, "ack_mode", "") == "no_ack"

  def cv_ack_debug(self, ack) -> dict:
    if hasattr(ack, "to_debug_dict"):
      return ack.to_debug_dict()
    return {"ack": str(ack)}

  def request_loco_control_grant(
    self,
    session_manager,
    controller: dict,
    request: LocoControlGrantRequest,
    *,
    transport=None,
  ) -> LocoControlGrantResult:
    return LocoControlGrantResult(
      request_hex="",
      address=request.address,
      feedback={
        "granted_to_client": True,
        "grant_not_required": True,
        "protocol": self.protocol,
      },
      frames=[],
    )

  def send_loco_speed_request(
    self,
    session_manager,
    controller: dict,
    request: LocoSpeedRequest,
    *,
    transport=None,
  ) -> LocoCommandResult:
    setup_hexes, mode_warnings = self._apply_loco_protocol_mode(session_manager, controller, request)
    z21_speed_steps = _z21_drive_speed_steps(request.control_protocol, request.speed_steps)
    command_speed = models.scale_loco_speed_for_steps(request.speed, request.control_protocol, request.speed_steps)
    request_bytes = build_x_set_loco_drive(
      request.address,
      command_speed,
      request.direction,
      speed_steps=z21_speed_steps,
    )
    feedback, frames, warnings = self._send_loco_command_and_poll(
      session_manager,
      controller,
      request.address,
      request_bytes,
    )
    return LocoCommandResult(
      request_hex=request_bytes.hex(" "),
      request_hexes=[*setup_hexes, request_bytes.hex(" ")],
      feedback=feedback,
      extra={
        "direction": request.direction,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "command_speed": command_speed,
        "warnings": [*mode_warnings, *warnings],
      },
      frames=frames,
    )

  def send_loco_function_request(
    self,
    session_manager,
    controller: dict,
    request: LocoFunctionRequest,
    *,
    transport=None,
  ) -> LocoCommandResult:
    enabled = bool(request.function_states.get(str(request.function_number), request.function_states.get(request.function_number, False)))
    setup_hexes, mode_warnings = self._apply_loco_protocol_mode(session_manager, controller, request)
    request_bytes = build_x_set_loco_function(request.address, request.function_number, enabled)
    feedback, frames, warnings = self._send_loco_command_and_poll(
      session_manager,
      controller,
      request.address,
      request_bytes,
    )
    return LocoCommandResult(
      request_hex=request_bytes.hex(" "),
      request_hexes=[*setup_hexes, request_bytes.hex(" ")],
      feedback=feedback,
      extra={
        "function_number": request.function_number,
        "function_enabled": enabled,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "warnings": [*mode_warnings, *warnings],
      },
      frames=frames,
    )

  def _apply_loco_protocol_mode(self, session_manager, controller: dict, request) -> tuple[list[str], list[str]]:
    control_protocol = models.validate_control_protocol(request.control_protocol)
    if control_protocol == models.CONTROL_PROTOCOL_M4:
      raise ValueError("Z21 does not support M4 loco protocol")
    models.validate_speed_steps(control_protocol, request.speed_steps)
    mode_request = build_set_loco_mode(request.address, control_protocol)
    warnings = []
    try:
      self._exchange_z21(
        session_manager,
        controller,
        mode_request,
        max_packets=1,
        timeout_seconds=0.1,
      )
    except TimeoutError as exc:
      warnings.append(f"loco_mode_no_reply:{exc}")
    return [mode_request.hex(" ")], warnings

  def _send_loco_command_and_poll(self, session_manager, controller: dict, address: int, request_bytes: bytes):
    frames = []
    warnings = []
    try:
      responses = self._exchange_z21(
        session_manager,
        controller,
        request_bytes,
        max_packets=4,
        stop_when=_z21_loco_info_matcher(address),
      )
      frames.extend(_decode_z21_response_datasets(responses))
    except TimeoutError as exc:
      warnings.append(f"loco_command_no_reply:{exc}")
    if _first_loco_info(frames, address) is None:
      try:
        poll_responses = self._exchange_z21(
          session_manager,
          controller,
          build_x_get_loco_info(address),
          max_packets=4,
          stop_when=_z21_loco_info_matcher(address),
        )
        frames.extend(_decode_z21_response_datasets(poll_responses))
      except TimeoutError as exc:
        warnings.append(f"loco_info_poll_timeout:{exc}")
    loco_info = _first_loco_info(frames, address)
    return (
      loco_info.to_debug_dict() if loco_info is not None else None,
      frames,
      warnings,
    )

  def _send_z21_no_reply_command(self, session_manager, controller: dict, request_bytes: bytes, fallback_ack: Z21CvAck, *, max_packets: int):
    try:
      responses = self._exchange_z21(
        session_manager,
        controller,
        request_bytes,
        max_packets=max_packets,
        stop_when=_z21_cv_response_matcher(),
      )
    except TimeoutError:
      return fallback_ack
    frames = _decode_z21_response_datasets(responses)
    return frames[0] if frames else fallback_ack

  def _exchange_z21(
    self,
    session_manager,
    controller: dict,
    request_bytes: bytes,
    *,
    max_packets: int = 8,
    stop_when=None,
    timeout_seconds: float | None = None,
  ):
    return session_manager.exchange(
      controller.get("ip") or models.CONTROLLER_DEFAULT_IP,
      int(controller.get("udp_port", self.transport_descriptor.defaults["udp_port"])),
      request_bytes,
      local_port=int(controller.get("local_udp_port", self.transport_descriptor.defaults["local_udp_port"])),
      max_packets=max_packets,
      stop_when=stop_when,
      timeout_seconds=timeout_seconds,
    )

  def _cv_timeout_seconds(self, controller: dict, timeout_seconds: float | None) -> float:
    return float(timeout_seconds if timeout_seconds is not None else controller.get("cv_timeout_seconds", 10.0))

  def apply_controller_private_settings(self, session_manager, controller: dict, settings: dict, keys: list[str], *, transport=None) -> list[dict]:
    results = []
    for key in keys:
      if key != "railcom_enabled":
        raise ValueError(f"unsupported controller setting: {key}")
      results.append(self._apply_railcom_setting(session_manager, controller, bool(settings.get("railcom_enabled"))))
    return results

  def _apply_railcom_setting(self, session_manager, controller: dict, enabled: bool) -> dict:
    before_settings, read_request_hex, read_responses = self._read_common_settings(session_manager, controller)
    next_settings = before_settings.with_railcom(enabled)
    write_request = build_set_common_settings(next_settings)
    write_warnings = []
    try:
      write_responses = self._exchange_z21(
        session_manager,
        controller,
        write_request,
        max_packets=1,
        stop_when=_dataset_header_matcher(LAN_SET_COMMON_SETTINGS),
        timeout_seconds=0.25,
      )
    except TimeoutError as exc:
      write_responses = []
      write_warnings.append(f"write_no_direct_reply:{exc}")
    readback_settings, readback_request_hex, readback_responses = self._read_common_settings(session_manager, controller)
    if bool(readback_settings.enable_railcom) != bool(enabled):
      raise ControllerParameterWriteError(
        "Z21 RailCom 设置写入后读回不一致",
        {
          "target_enabled": bool(enabled),
          "read_before": before_settings.to_debug_dict(),
          "read_back": readback_settings.to_debug_dict(),
          "read_request_hex": read_request_hex,
          "write_request_hex": write_request.hex(" "),
          "readback_request_hex": readback_request_hex,
          "read_responses": _debug_responses(read_responses),
          "write_responses": _debug_responses(write_responses),
          "readback_responses": _debug_responses(readback_responses),
          "warnings": write_warnings,
        },
      )
    controller.setdefault("settings", {})["railcom_enabled"] = bool(enabled)
    controller.setdefault("device_info", {})["railcom_enabled"] = bool(enabled)
    controller["device_info"]["railcom_source"] = "z21_common_settings_offset_0"
    controller["device_info"]["common_settings"] = readback_settings.to_debug_dict()
    return {
      "setting": "railcom_enabled",
      "enabled": bool(enabled),
      "read_request_hex": read_request_hex,
      "write_request_hex": write_request.hex(" "),
      "readback_request_hex": readback_request_hex,
      "warnings": write_warnings,
    }

  def apply_track_profile_parameters(self, session_manager, controller: dict, profiles: dict, modes: list[str], *, transport=None) -> list[dict]:
    results = []
    current_settings = None
    current_read_request_hex = ""
    current_read_responses = []
    programming_voltage_mv = _z21_programming_voltage_mv(controller)
    for mode in modes:
      profile = profiles.get(mode)
      if not isinstance(profile, dict) or "target_voltage_v" not in profile:
        continue
      target_voltage_mv = _z21_voltage_mv(profile["target_voltage_v"])
      if current_settings is None:
        current_settings, current_read_request_hex, current_read_responses = self._read_mmdcc_settings(session_manager, controller)
      before_settings = current_settings
      read_request_hex = current_read_request_hex
      read_responses = current_read_responses
      next_settings = before_settings.with_voltages(
        output_voltage_mv=target_voltage_mv,
        programming_voltage_mv=programming_voltage_mv,
      )
      write_request = build_set_mmdcc_settings(next_settings)
      write_warnings = []
      try:
        write_responses = self._exchange_z21(
          session_manager,
          controller,
          write_request,
          max_packets=1,
          stop_when=_dataset_header_matcher(LAN_SET_MMDCC_SETTINGS),
          timeout_seconds=0.25,
        )
      except TimeoutError as exc:
        write_responses = []
        write_warnings.append(f"write_no_direct_reply:{exc}")
      readback_settings, readback_request_hex, readback_responses = self._read_mmdcc_settings(session_manager, controller)
      current_settings = readback_settings
      current_read_request_hex = readback_request_hex
      current_read_responses = readback_responses
      if (
        int(readback_settings.output_voltage_mv) != target_voltage_mv
        or int(readback_settings.programming_voltage_mv) != programming_voltage_mv
      ):
        raise ControllerParameterWriteError(
          f"Z21 {mode} 电压写入后读回不一致",
          {
            "mode": mode,
            "target_output_voltage_mv": target_voltage_mv,
            "target_programming_voltage_mv": programming_voltage_mv,
            "read_before": before_settings.to_debug_dict(),
            "read_back": readback_settings.to_debug_dict(),
            "read_request_hex": read_request_hex,
            "write_request_hex": write_request.hex(" "),
            "readback_request_hex": readback_request_hex,
            "read_responses": _debug_responses(read_responses),
            "write_responses": _debug_responses(write_responses),
            "readback_responses": _debug_responses(readback_responses),
            "warnings": write_warnings,
          },
        )
      voltage_v = target_voltage_mv / 1000
      controller.setdefault("booster_status", {})["output_voltage_v"] = voltage_v
      controller.setdefault("telemetry", {})["track_voltage_v"] = voltage_v
      results.append({
        "mode": mode,
        "setting": "z21_mmdcc_voltage",
        "output_voltage_mv": readback_settings.output_voltage_mv,
        "programming_voltage_mv": readback_settings.programming_voltage_mv,
        "target_output_voltage_v": voltage_v,
        "target_programming_voltage_v": programming_voltage_mv / 1000,
        "read_request_hex": read_request_hex,
        "write_request_hex": write_request.hex(" "),
        "readback_request_hex": readback_request_hex,
        "warnings": write_warnings,
      })
    return results

  def _read_mmdcc_settings(self, session_manager, controller: dict):
    request = build_get_mmdcc_settings()
    try:
      responses = self._exchange_z21(
        session_manager,
        controller,
        request,
        max_packets=4,
        stop_when=_dataset_header_matcher(LAN_GET_MMDCC_SETTINGS),
      )
      dataset = _first_dataset_with_header(responses, LAN_GET_MMDCC_SETTINGS)
      return parse_mmdcc_settings(dataset.payload), request.hex(" "), responses
    except (TimeoutError, OSError, ValueError) as exc:
      raise ControllerParameterWriteError(
        "Z21 MMDCC 设置读取失败",
        {
          "request_hex": request.hex(" "),
          "error": str(exc),
        },
      ) from exc

  def _read_common_settings(self, session_manager, controller: dict):
    request = build_get_common_settings()
    try:
      responses = self._exchange_z21(
        session_manager,
        controller,
        request,
        max_packets=4,
        stop_when=_dataset_header_matcher(LAN_GET_COMMON_SETTINGS),
      )
      dataset = _first_dataset_with_header(responses, LAN_GET_COMMON_SETTINGS)
      return parse_common_settings(dataset.payload), request.hex(" "), responses
    except (TimeoutError, OSError, ValueError) as exc:
      raise ControllerParameterWriteError(
        "Z21 Common Settings 读取失败",
        {
          "request_hex": request.hex(" "),
          "error": str(exc),
        },
      ) from exc

  def parse_controller_info(self, controller: dict, request, result: ControllerInfoReadResult) -> dict:
    controller["track_mode"] = request.track_mode
    device_info = {
      **controller.get("device_info", {}),
      **result.collected.get("serial_number", {}),
      **result.collected.get("hardware_info", {}),
      **result.collected.get("broadcast_flags", {}),
      "source": "z21_lan_read_info",
      "configured_model": self.profile.label,
    }
    common_settings = result.collected.get("common_settings")
    if common_settings is not None:
      device_info.update({
        "railcom_enabled": bool(common_settings.enable_railcom),
        "railcom_source": "z21_common_settings_offset_0",
        "common_settings": common_settings.to_debug_dict(),
      })
    system_state = result.collected.get("system_state") if isinstance(result.collected.get("system_state"), dict) else None
    track_voltage_v = system_state.get("vcc_voltage_v") if system_state else None
    current_a = _ma_to_a(system_state.get("main_track_current_ma")) if system_state else None
    telemetry = {
      **controller.get("telemetry", {}),
      "temperature_c": system_state.get("temperature_c") if system_state else None,
      "track_voltage_v": track_voltage_v,
      "track_current_a": current_a,
      "track_power_w": _power_w(track_voltage_v, current_a),
    }
    controller["controller_reachable"] = not bool(result.warnings)
    controller["controller_unreachable_reason"] = "" if controller["controller_reachable"] else "; ".join(result.warnings)
    controller["last_probe_ok"] = controller["controller_reachable"]
    controller["device_info"] = device_info
    controller["telemetry"] = telemetry
    if system_state:
      controller["booster_status"] = _z21_booster_status_from_system_state(system_state)
    else:
      controller.pop("booster_status", None)
    mark_controller_safety_fresh(
      controller,
      booster_status_fresh=bool(system_state),
      programming_track_status_fresh=bool(system_state),
    )
    warnings = list(result.warnings)
    safe_for_cv = update_cv_safety_from_programming_status(
      controller,
      self,
      warnings,
      source="z21_system_state",
    )
    return {
      "safe_for_cv": safe_for_cv,
      "warnings": warnings,
    }

  def is_booster_status_confirmed(self, controller: dict) -> bool:
    booster_status = controller.get("booster_status")
    return isinstance(booster_status, dict) and booster_status.get("source") == "z21_system_state"

  def programming_track_status(self, controller: dict):
    booster_status = controller.get("booster_status") if isinstance(controller.get("booster_status"), dict) else {}
    if booster_status.get("source") != "z21_system_state":
      return read_only_programming_track_status(controller)
    try:
      track_mode = models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      track_mode = str(controller.get("track_mode") or "")
    return Z21ProgrammingTrackStatus(
      track_mode=track_mode,
      dcc_mode=True,
      programming_track_busy=bool(booster_status.get("programming_mode_active", False)),
      programming_track_current_ma=int(booster_status.get("programming_track_current_ma", 0) or 0),
      output_value=0,
      current_limit_ma=0,
      current_limit_confirmed=False,
    )

  def validate_programming_track_safety(self, programming_status) -> None:
    if programming_status.track_mode not in {models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G}:
      raise ValueError("编程轨必须使用 N、HO 或 G 的 DCC 数码模式")
    if not programming_status.dcc_mode:
      raise ValueError("编程轨必须是 DCC 模式，不能是 DC 模式")
    if programming_status.programming_track_busy:
      raise ValueError("编程轨正忙")
    if int(programming_status.programming_track_current_ma) > 100:
      raise ValueError("编程轨空闲电流超过安全阈值")


def _first_dataset_with_header(responses: list[bytes], expected_header: int):
  dataset = _first_dataset_with_header_or_none(responses, expected_header)
  if dataset is not None:
    return dataset
  raise ValueError(f"no Z21 dataset with header 0x{expected_header:04x}")


def _first_dataset_with_header_or_none(responses: list[bytes], expected_header: int):
  for raw in responses:
    for dataset in decode_datasets(raw):
      if dataset.header == expected_header:
        return dataset
  return None


def _dataset_header_matcher(expected_header: int):
  def matcher(raw: bytes) -> bool:
    return _first_dataset_with_header_or_none([raw], expected_header) is not None
  return matcher


def _z21_cv_response_matcher():
  def matcher(raw: bytes) -> bool:
    for dataset in decode_datasets(raw):
      if dataset.header != LAN_X:
        continue
      try:
        parse_cv_result(dataset.payload)
        return True
      except ValueError:
        try:
          parse_xbus_ack(dataset.payload)
          return True
        except ValueError:
          continue
    return False
  return matcher


def _z21_loco_info_matcher(address: int):
  def matcher(raw: bytes) -> bool:
    for dataset in decode_datasets(raw):
      if dataset.header != LAN_X:
        continue
      try:
        info = parse_loco_info(dataset.payload)
      except ValueError:
        continue
      if int(info.address) == int(address):
        return True
    return False
  return matcher


def _decode_z21_response_datasets(responses: list[bytes]) -> list[Z21Dataset]:
  datasets = []
  for raw in responses:
    datasets.extend(decode_datasets(raw))
  return datasets


def _iter_z21_cv_frames(frames: list):
  for frame in frames or []:
    if isinstance(frame, (Z21Dataset, Z21CvAck)):
      yield frame
      continue
    if isinstance(frame, (bytes, bytearray, memoryview)):
      for dataset in decode_datasets(bytes(frame)):
        yield dataset


def _first_loco_info(frames: list, address: int) -> Z21LocoInfo | None:
  for frame in frames or []:
    if not isinstance(frame, Z21Dataset) or frame.header != LAN_X:
      continue
    try:
      info = parse_loco_info(frame.payload)
    except ValueError:
      continue
    if int(info.address) == int(address):
      return info
  return None


def _z21_voltage_mv(value) -> int:
  voltage = float(value)
  if voltage < Z21_MIN_TRACK_VOLTAGE_V or voltage > Z21_MAX_TRACK_VOLTAGE_V:
    raise ValueError(f"Z21 voltage must be in {Z21_MIN_TRACK_VOLTAGE_V:g}..{Z21_MAX_TRACK_VOLTAGE_V:g}V")
  return int(round(voltage * 1000))


def _z21_programming_voltage_mv(controller: dict) -> int:
  settings = controller.get("settings") if isinstance(controller.get("settings"), dict) else {}
  return _z21_voltage_mv(settings.get(Z21_PROGRAMMING_TRACK_VOLTAGE_SETTING, Z21_DEFAULT_TRACK_VOLTAGE_V))


def _z21_drive_speed_steps(control_protocol: str, speed_steps: int) -> int:
  protocol = models.validate_control_protocol(control_protocol)
  steps = models.validate_speed_steps(protocol, speed_steps)
  if protocol == models.CONTROL_PROTOCOL_DCC:
    return steps
  if protocol == models.CONTROL_PROTOCOL_MOTOROLA:
    return 14 if steps == 1 else 28
  raise ValueError("Z21 does not support M4 loco protocol")


def _z21_booster_status_from_system_state(system_state: dict, *, payload_hex: str | None = None) -> dict:
  voltage = system_state.get("vcc_voltage_v")
  current = _ma_to_a(system_state.get("main_track_current_ma"))
  booster_status = {
    **system_state,
    "source": "z21_system_state",
    "power_on": not bool(system_state.get("track_voltage_off")),
    "short_circuit": bool(system_state.get("short_circuit") or system_state.get("internal_short")),
    "dcc_mode": True,
    "output_voltage_v": voltage,
    "output_current_a": current,
    "temperature_c": system_state.get("temperature_c"),
  }
  if payload_hex is not None:
    booster_status["payload_hex"] = payload_hex
  return booster_status


def _debug_responses(responses: list[bytes]) -> list[dict]:
  debug = []
  for raw in responses:
    try:
      datasets = decode_datasets(raw)
      for dataset in datasets:
        debug.append({
          "header": f"0x{dataset.header:04x}",
          "payload_hex": dataset.payload.hex(" "),
          "raw_hex": dataset.to_bytes().hex(" "),
        })
    except ValueError as exc:
      debug.append({
        "raw_hex": raw.hex(" "),
        "error": str(exc),
      })
  return debug


def _ma_to_a(value):
  if value is None:
    return None
  return int(value) / 1000


def _power_w(voltage, current):
  if voltage is None or current is None:
    return None
  return round(float(voltage) * float(current), 3)

"""ESU ECoS controller adapter."""

from dataclasses import dataclass

from esu_ecos import (
  BOOSTER_CURRENT_LIMIT_MAX_MA,
  BOOSTER_CURRENT_LIMIT_MIN_MA,
  DEFAULT_ECOS_PORT,
  ECoSBlock,
  ECoSProgrammerEvent,
  ECoSSessionManager,
  SYSTEM_BOOSTER_OBJECT_ID,
  build_booster_current_limit_write_commands,
  build_booster_monitor_commands,
  build_booster_query_command,
  build_create_loco_command,
  build_get_command,
  build_basic_info_commands,
  build_loco_function_command,
  build_loco_query_command,
  build_loco_speed_command,
  build_power_command,
  build_programmer_cv_read_commands,
  build_programmer_cv_write_commands,
  build_railcom_command,
  build_railcomplus_command,
  build_release_command,
  build_request_command,
  ecos_loco_protocol_name,
  parse_basic_info,
  parse_blocks,
  parse_booster_monitor_info,
  parse_booster_query_results,
  parse_loco_query_results,
  parse_programmer_event,
)

from server import models
from server.controller_safety import mark_controller_safety_fresh
from server.controllers.base import (
  ControllerCapabilities,
  ControllerOperationNotSupported,
  CvCommandRequest,
  CvCommandResult,
  ControllerInfoReadResult,
  ControllerParameterWriteError,
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


ECOS_DEFAULT_CURRENT_LIMIT_MA = 4000
ECOS_CURRENT_LIMIT_STEP_MA = 100
ECOS_SHORT_CIRCUIT_DELAY_SETTING = "short_circuit_detection_delay_ms"
ECOS_DEFAULT_SHORT_CIRCUIT_DELAY_MS = 0
ECOS_MAX_SHORT_CIRCUIT_DELAY_MS = 5000


@dataclass(frozen=True)
class ECoSCvValue:
  cv_number: int
  value: int
  pom_address: int | None = None
  event: ECoSProgrammerEvent | None = None

  def to_debug_dict(self) -> dict:
    return {
      "cv": self.cv_number,
      "value": self.value,
      "pom_address": self.pom_address,
      "event": self.event.to_debug_dict() if self.event else None,
    }


@dataclass(frozen=True)
class ECoSCvAck:
  ack_mode: str
  ack_name: str
  detail: str
  event: ECoSProgrammerEvent | None = None

  def to_debug_dict(self) -> dict:
    return {
      "ack": self.ack_name,
      "ack_mode": self.ack_mode,
      "detail": self.detail,
      "event": self.event.to_debug_dict() if self.event else None,
    }


@dataclass
class ECoSCvClassification:
  value: object | None = None
  value_frame: object | None = None
  ack: object | None = None
  ack_frame: object | None = None
  parse_warnings: list | None = None

  def __post_init__(self):
    if self.parse_warnings is None:
      self.parse_warnings = []


@dataclass(frozen=True)
class ECoSProgrammingTrackStatus:
  track_mode: str
  dcc_mode: bool
  programming_track_busy: bool
  programming_track_current_ma: int
  output_value: int
  current_limit_ma: int
  current_limit_confirmed: bool = False


class ECoSControllerAdapter:
  """Adapter for ESU ECoS/ECoS2 PC Interface controllers."""

  kind = models.CONTROLLER_KIND_ECOS_50200
  label = "ESU ECoS 50200"
  default_display_name = "ESU ECoS 50200"
  protocol = models.CONTROLLER_PROTOCOL_ECOS
  cv_method_prefix = "ecos_programmer"
  supported_protocols = (models.CONTROLLER_PROTOCOL_ECOS,)
  config_file_name = "ESU_ECoS_50200.json"
  default_ip = models.CONTROLLER_DEFAULT_IP
  runtime_transport_fields = ("tcp_port",)
  default_track_profiles = track_profiles_with_limits(
    enabled_modes={models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G},
    current_limit_ma=ECOS_DEFAULT_CURRENT_LIMIT_MA,
    min_current_limit_ma=BOOSTER_CURRENT_LIMIT_MIN_MA,
    max_current_limit_ma=BOOSTER_CURRENT_LIMIT_MAX_MA,
    current_step_ma=ECOS_CURRENT_LIMIT_STEP_MA,
    voltage_fields=False,
    controller_output_fields=False,
  )
  default_settings = {
    ECOS_SHORT_CIRCUIT_DELAY_SETTING: ECOS_DEFAULT_SHORT_CIRCUIT_DELAY_MS,
  }
  device_private_setting_keys = ("railcomplus_enabled",)
  track_output_setting_keys = (ECOS_SHORT_CIRCUIT_DELAY_SETTING,)
  track_output_setting_specs = [{
    "key": ECOS_SHORT_CIRCUIT_DELAY_SETTING,
    "label": "短路检测延迟 ms",
    "type": "number",
    "min": 0,
    "max": ECOS_MAX_SHORT_CIRCUIT_DELAY_MS,
    "step": 100,
    "unit": "ms",
    "note": "ECoS 界面项 Short-circuit detection delay。官方手册建议：DCC 兼容 Booster（例如 Lenz）用 0ms，LDT Booster 用 1500ms，Märklin 6017 Booster 用 2000ms，其它品牌从 0ms 开始测试。当前 PC Interface 写入字段未确认，本项目只保存本地配置。",
  }]
  field_descriptions = {
    "protocol": "该控制器使用的通讯协议名称；ESU ECoS 50200/50210/50220 使用同一 PC Interface，均可使用该配置。",
    "settings.railcom_enabled": "RailCom 开关；ECoS 基础对象 1 的 railcom[0|1] 字段。关闭 RailCom 会联动关闭 RailComPlus。",
    "settings.railcomplus_enabled": "RailComPlus 开关；ECoS 基础对象 1 的 railcomplus[0|1] 字段。RailComPlus 只能在 RailCom 已开启时开启。",
    f"settings.{ECOS_SHORT_CIRCUIT_DELAY_SETTING}": "ECoS Booster Configuration 的 Short-circuit detection delay，本地保存用于记录 Booster 类型建议；当前 PC Interface 写入字段未确认，不下发到控制器。",
    "transport.kind": "传输类型；ESU ECoS PC Interface 使用 tcp。",
    "transport.tcp_port": "控制器 TCP 端口；ESU ECoS PC Interface 默认使用 15471。",
    "track_profiles.<mode>.enabled": "ECoS PC Interface 使用 DCC 数码输出，不支持本系统 DC 控制页；N/HO/G 只用于车辆比例筛选和限流配置。",
    "track_profiles.<mode>.target_current_limit_ma": "ECoS System booster 的限流值，写入 PC Interface booster 对象 limit[mA]；默认 4000mA。",
    "track_profiles.<mode>.min_target_current_limit_ma": "ECoS System booster 限流最小配置值；当前按已验证界面和保守范围使用 1000mA。",
    "track_profiles.<mode>.max_target_current_limit_ma": "ECoS System booster 限流最大配置值；当前按已验证界面和保守范围使用 6000mA。",
    "track_profiles.<mode>.current_step_ma": "ECoS System booster 限流输入步进。",
  }
  capabilities = ControllerCapabilities(
    track_power=True,
    dc_control=False,
    read_info=True,
    cv_programming=True,
    loco_control=True,
    controller_settings=True,
    railcom_settings=True,
  )
  transport_descriptor = ControllerTransportDescriptor(
    kind="tcp",
    defaults={
      "tcp_port": DEFAULT_ECOS_PORT,
    },
    endpoint_required_paths=("transport.tcp_port",),
  )
  info_sections = controller_info_sections(
    {
      "title": INFO_SECTION_DEVICE,
      "rows": [
        {"label": "型号", "path": "device_info.commandstationtype"},
        {"label": "硬件版本", "path": "device_info.hardwareversion"},
        {"label": "应用版本", "path": "device_info.applicationversion"},
        {"label": "协议版本", "path": "device_info.protocolversion"},
        {"label": "RailCom", "path": "device_info.railcom"},
        {"label": "RailComPlus", "path": "device_info.railcomplus"},
      ],
    },
    {
      "title": INFO_SECTION_WORK,
      "rows": [
        {"label": "Booster", "path": "booster_status.name"},
        {"label": "状态", "path": "booster_status.status"},
        {"label": "轨道电源", "path": "booster_status.power_on", "format": "power_state"},
        {"label": "短路状态", "path": "booster_status.short_circuit", "format": "short_circuit_state"},
        {"label": "主轨电流", "path": "booster_status.main_track_current_ma", "unit": "mA"},
        {"label": "返回电流", "path": "booster_status.return_current_ma", "unit": "mA"},
        {"label": "输出电压", "path": "booster_status.output_voltage_v", "unit": "V"},
        {"label": "温度", "path": "telemetry.temperature_c", "unit": "℃"},
        {"label": "限流", "path": "booster_status.limit_ma", "unit": "mA"},
      ],
    },
  )

  def create_session_manager(self, *, transport=None, context=None):
    return ECoSSessionManager(transport)

  def normalize_transport_config(self, transport, *, strict: bool) -> dict:
    source = transport if isinstance(transport, dict) else {}
    default_port = self.transport_descriptor.defaults["tcp_port"]
    try:
      tcp_port = validate_transport_port(source.get("tcp_port", default_port), "ECoS TCP port")
    except (TypeError, ValueError):
      if strict:
        raise
      tcp_port = default_port
    return {
      "kind": self.transport_descriptor.kind,
      "tcp_port": tcp_port,
    }

  def apply_transport_runtime(self, controller: dict) -> None:
    transport = controller.get("transport") if isinstance(controller.get("transport"), dict) else {}
    controller["tcp_port"] = validate_transport_port(
      transport.get("tcp_port", self.transport_descriptor.defaults["tcp_port"]),
      "ECoS TCP port",
    )

  def endpoint_identity(self, controller: dict) -> tuple:
    return (
      ("transport", "tcp"),
      ("ip", str(controller.get("ip") or "")),
      ("tcp_port", str(controller.get("tcp_port") or "")),
    )

  def session_identity(self, controller: dict) -> tuple:
    return read_only_session_identity(controller)

  def normalize_controller_private_setting(self, key: str, value):
    if key == "railcomplus_enabled":
      if not isinstance(value, bool):
        raise ValueError("settings.railcomplus_enabled must be true or false")
      return bool(value)
    if key != ECOS_SHORT_CIRCUIT_DELAY_SETTING:
      raise ValueError(f"unsupported controller setting: {key}")
    delay_ms = int(value)
    if delay_ms < 0 or delay_ms > ECOS_MAX_SHORT_CIRCUIT_DELAY_MS:
      raise ValueError(f"settings.{ECOS_SHORT_CIRCUIT_DELAY_SETTING} must be in 0..{ECOS_MAX_SHORT_CIRCUIT_DELAY_MS}ms")
    return delay_ms

  def runtime_readiness_warnings(self, controller: dict) -> list[str]:
    return endpoint_readiness_warnings(controller, port_field="tcp_port", port_warning="tcp_port_unconfirmed")

  def loco_control_readiness_warnings(self, controller: dict) -> list[str]:
    return self.runtime_readiness_warnings(controller)

  def status_not_ready_message(self) -> str:
    return controller_not_ready_message()

  def readiness_warning_detail(self, warnings: list[str]) -> str:
    return endpoint_readiness_detail(warnings, port_warning="tcp_port_unconfirmed", port_detail="控制器 TCP 端口未确认")

  def controller_client_id(self, controller: dict) -> int:
    return read_only_controller_client_id(controller)

  def read_controller_info(self, session_manager, controller: dict, request, *, transport=None) -> ControllerInfoReadResult:
    basic_commands = build_basic_info_commands()
    basic_text = session_manager.exchange(
      controller.get("ip") or models.CONTROLLER_DEFAULT_IP,
      int(controller.get("tcp_port", self.transport_descriptor.defaults["tcp_port"])),
      basic_commands,
      timeout_seconds=float(controller.get("controller_info_status_timeout_seconds", models.CONTROLLER_INFO_STATUS_TIMEOUT_SECONDS)),
      expected_replies=len(basic_commands),
    )
    query_command = build_booster_query_command()
    query_text = self._exchange_ecos(
      session_manager,
      controller,
      [query_command],
      timeout_seconds=float(controller.get("controller_info_poll_timeout_seconds", models.CONTROLLER_INFO_POLL_TIMEOUT_SECONDS)),
      expected_replies=1,
    )
    boosters = parse_booster_query_results(query_text)
    booster_object_id = _select_system_booster_object_id(boosters)
    monitor_commands = build_booster_monitor_commands(booster_object_id)
    monitor_text = self._exchange_ecos(
      session_manager,
      controller,
      monitor_commands,
      timeout_seconds=float(controller.get("controller_info_poll_timeout_seconds", models.CONTROLLER_INFO_POLL_TIMEOUT_SECONDS)),
      expected_replies=len(monitor_commands),
    )
    return ControllerInfoReadResult(
      collected={
        "basic_info_text": basic_text,
        "basic_info": _required_basic_info(basic_text),
        "booster_query_text": query_text,
        "boosters": boosters,
        "booster_object_id": booster_object_id,
        "booster_monitor_text": monitor_text,
        "booster_monitor": parse_booster_monitor_info(monitor_text, object_id=booster_object_id),
      },
      warnings=[],
      requests=[{
        "name": "ecos_basic_info",
        "commands": basic_commands,
        "response_text": basic_text,
      }, {
        "name": "ecos_booster_query",
        "commands": [query_command],
        "response_text": query_text,
      }, {
        "name": "ecos_booster_monitor",
        "commands": monitor_commands,
        "response_text": monitor_text,
      }],
    )

  def send_track_output_request(
    self,
    session_manager,
    controller: dict,
    request,
    *,
    transport=None,
  ) -> TrackOutputResult:
    commands = [
      build_power_command(request.powered),
      build_get_command(1, ("status",)),
    ]
    text = self._exchange_ecos(
      session_manager,
      controller,
      commands,
      timeout_seconds=request.timeout_seconds,
      expected_replies=len(commands),
    )
    blocks = parse_blocks(text)
    status = _ecos_status_from_blocks(blocks) or ("GO" if request.powered else "STOP")
    return TrackOutputResult(
      request_hex=_commands_hex(commands),
      frames=blocks,
      booster_status={
        "source": "ecos_object_1",
        "status": status,
        "power_on": status.upper() == "GO",
        "short_circuit": False,
        "dcc_mode": True,
        "output_voltage_v": None,
        "output_current_a": None,
        "temperature_c": None,
      },
      debug={"responses": [block.to_debug_dict() for block in blocks]},
    )

  def read_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    if request.pom_address is not None:
      raise ControllerOperationNotSupported("main_track_cv_read", self.kind)
    commands = [
      *build_programmer_cv_read_commands(request.cv_number),
      build_release_command(5, "view"),
    ]
    text = self._exchange_ecos(
      session_manager,
      controller,
      commands,
      timeout_seconds=request.timeout_seconds,
      expected_replies=len(commands),
      expected_events=1,
    )
    return CvCommandResult(request_hex=_commands_hex(commands), frames=parse_blocks(text))

  def write_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    if request.pom_address is not None:
      raise ControllerOperationNotSupported("main_track_cv_write", self.kind)
    if request.value is None:
      raise ValueError("ECoS CV write requires a value")
    commands = [
      *build_programmer_cv_write_commands(request.cv_number, request.value),
      build_release_command(5, "view"),
    ]
    text = self._exchange_ecos(
      session_manager,
      controller,
      commands,
      timeout_seconds=request.timeout_seconds,
      expected_replies=len(commands),
      expected_events=1,
    )
    return CvCommandResult(request_hex=_commands_hex(commands), frames=parse_blocks(text))

  def classify_cv_responses(self, frames: list, *, client_id: int, cv_number: int, pom_address: int | None = None):
    classification = ECoSCvClassification(parse_warnings=[])
    try:
      event = parse_programmer_event(frames)
    except ValueError as exc:
      classification.parse_warnings.append(str(exc))
      return classification
    state = str(event.state or "").lower()
    if state in {"success", "ok"} and event.cv_number == int(cv_number):
      classification.ack = ECoSCvAck("ack", "ECOS_PROGRAMMER_SUCCESS", "ECoS programmer reported success", event)
      classification.ack_frame = event
      if event.value is not None:
        classification.value = ECoSCvValue(event.cv_number, int(event.value), pom_address, event)
        classification.value_frame = event
      return classification
    if state in {"success", "ok"}:
      classification.parse_warnings.append(f"ECoS programmer returned CV{event.cv_number}, expected CV{cv_number}")
      return classification
    classification.ack = ECoSCvAck("rejected", "ECOS_PROGRAMMER_REJECTED", f"ECoS programmer state: {event.state}", event)
    classification.ack_frame = event
    return classification

  def cv_ack_category(self, ack) -> str:
    return "ack" if getattr(ack, "ack_mode", "") == "ack" else "rejected"

  def should_retry_cv_write_ack(self, ack, *, attempt: int, retry_count: int) -> bool:
    return False

  def is_main_track_cv_read_no_ack(self, ack) -> bool:
    return False

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
    ecos_protocol = ecos_loco_protocol_name(request.control_protocol, request.speed_steps)
    object_id, frames = self._resolve_loco_object_id(session_manager, controller, request.address, ecos_protocol)
    return LocoControlGrantResult(
      request_hex=_commands_hex([build_loco_query_command()]),
      address=request.address,
      feedback={
        "granted_to_client": True,
        "grant_not_required": False,
        "object_id": object_id,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "ecos_loco_protocol": ecos_protocol,
      },
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
    ecos_protocol = ecos_loco_protocol_name(request.control_protocol, request.speed_steps)
    object_id, resolve_frames = self._resolve_loco_object_id(session_manager, controller, request.address, ecos_protocol)
    command_speed = models.scale_loco_speed_for_steps(request.speed, request.control_protocol, request.speed_steps)
    commands = [
      build_request_command(object_id, "control"),
      build_loco_speed_command(object_id, command_speed, direction=request.direction),
      build_release_command(object_id, "control"),
    ]
    text = self._exchange_ecos(session_manager, controller, commands, expected_replies=len(commands))
    command_frames = parse_blocks(text)
    return LocoCommandResult(
      request_hex=_commands_hex([commands[1]]),
      request_hexes=[_command_hex(command) for command in commands],
      feedback={
        "object_id": object_id,
        "address": request.address,
        "speed": request.speed,
        "command_speed": command_speed,
        "direction": request.direction,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "ecos_loco_protocol": ecos_protocol,
      },
      extra={
        "direction": request.direction,
        "object_id": object_id,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "command_speed": command_speed,
        "ecos_loco_protocol": ecos_protocol,
      },
      frames=[*resolve_frames, *command_frames],
    )

  def send_loco_function_request(
    self,
    session_manager,
    controller: dict,
    request: LocoFunctionRequest,
    *,
    transport=None,
  ) -> LocoCommandResult:
    ecos_protocol = ecos_loco_protocol_name(request.control_protocol, request.speed_steps)
    object_id, resolve_frames = self._resolve_loco_object_id(session_manager, controller, request.address, ecos_protocol)
    enabled = bool(request.function_states.get(str(request.function_number), request.function_states.get(request.function_number, False)))
    commands = [
      build_request_command(object_id, "control"),
      build_loco_function_command(object_id, request.function_number, enabled),
      build_release_command(object_id, "control"),
    ]
    text = self._exchange_ecos(session_manager, controller, commands, expected_replies=len(commands))
    command_frames = parse_blocks(text)
    return LocoCommandResult(
      request_hex=_commands_hex([commands[1]]),
      request_hexes=[_command_hex(command) for command in commands],
      feedback={
        "object_id": object_id,
        "address": request.address,
        "function_number": request.function_number,
        "function_enabled": enabled,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "ecos_loco_protocol": ecos_protocol,
      },
      extra={
        "function_number": request.function_number,
        "function_enabled": enabled,
        "object_id": object_id,
        "protocol": self.protocol,
        "control_protocol": request.control_protocol,
        "speed_steps": request.speed_steps,
        "ecos_loco_protocol": ecos_protocol,
      },
      frames=[*resolve_frames, *command_frames],
    )

  def _resolve_loco_object_id(self, session_manager, controller: dict, address: int, ecos_protocol: str) -> tuple[int, list[ECoSBlock]]:
    query_command = build_loco_query_command()
    query_text = self._exchange_ecos(session_manager, controller, [query_command], expected_replies=1)
    query_blocks = parse_blocks(query_text)
    locos = parse_loco_query_results(query_blocks, address=address)
    if locos:
      return int(locos[0]["object_id"]), query_blocks
    create_command = build_create_loco_command(address, f"Digsight {address}", ecos_protocol)
    create_text = self._exchange_ecos(session_manager, controller, [create_command], expected_replies=1)
    create_blocks = parse_blocks(create_text)
    second_query_text = self._exchange_ecos(session_manager, controller, [query_command], expected_replies=1)
    second_query_blocks = parse_blocks(second_query_text)
    locos = parse_loco_query_results(second_query_blocks, address=address)
    if not locos:
      raise ValueError(f"ECoS did not return loco object for address {address}")
    return int(locos[0]["object_id"]), [*query_blocks, *create_blocks, *second_query_blocks]

  def _exchange_ecos(
    self,
    session_manager,
    controller: dict,
    commands,
    *,
    timeout_seconds: float | None = None,
    expected_replies: int = 1,
    expected_events: int = 0,
  ) -> str:
    return session_manager.exchange(
      controller.get("ip") or models.CONTROLLER_DEFAULT_IP,
      int(controller.get("tcp_port", self.transport_descriptor.defaults["tcp_port"])),
      commands,
      timeout_seconds=timeout_seconds,
      expected_replies=expected_replies,
      expected_events=expected_events,
    )

  def apply_controller_private_settings(self, session_manager, controller: dict, settings: dict, keys: list[str], *, transport=None) -> list[dict]:
    requested_keys = set(keys)
    unsupported = requested_keys - {"railcom_enabled", "railcomplus_enabled"}
    if unsupported:
      raise ValueError(f"unsupported controller setting: {sorted(unsupported)[0]}")
    if not requested_keys:
      return []
    return [self._apply_railcom_settings(session_manager, controller, settings, requested_keys)]

  def _apply_railcom_settings(self, session_manager, controller: dict, settings: dict, requested_keys: set[str]) -> dict:
    current_railcom = _optional_bool_from_device_value(
      controller.get("device_info", {}).get("railcom")
      if isinstance(controller.get("device_info"), dict)
      else None
    )
    current_railcomplus = _optional_bool_from_device_value(
      controller.get("device_info", {}).get("railcomplus")
      if isinstance(controller.get("device_info"), dict)
      else None
    )
    target_railcom = bool(settings.get("railcom_enabled")) if "railcom_enabled" in requested_keys else bool(current_railcom)
    if current_railcom is None and "railcom_enabled" not in requested_keys:
      target_railcom = bool(settings.get("railcom_enabled", False))
    target_railcomplus = (
      bool(settings.get("railcomplus_enabled"))
      if "railcomplus_enabled" in requested_keys
      else bool(current_railcomplus)
    )
    if current_railcomplus is None and "railcomplus_enabled" not in requested_keys:
      target_railcomplus = bool(settings.get("railcomplus_enabled", False))
    if target_railcomplus and "railcom_enabled" in requested_keys and not bool(settings.get("railcom_enabled")):
      raise ValueError("settings.railcomplus_enabled requires settings.railcom_enabled")
    if target_railcomplus:
      target_railcom = True
      settings["railcom_enabled"] = True
    if not target_railcom:
      target_railcomplus = False
      settings["railcomplus_enabled"] = False

    commands = []
    if "railcom_enabled" in requested_keys or target_railcomplus:
      commands.append(build_railcom_command(target_railcom))
    if target_railcom:
      if "railcomplus_enabled" in requested_keys or target_railcomplus:
        commands.append(build_railcomplus_command(target_railcomplus))
    commands.append(build_get_command(1, ("railcom", "railcomplus")))
    text = self._exchange_ecos(
      session_manager,
      controller,
      commands,
      expected_replies=len(commands),
    )
    blocks = parse_blocks(text)
    readback = parse_basic_info(blocks)
    readback_railcom = _optional_bool_from_device_value(readback.get("railcom"))
    readback_railcomplus = _optional_bool_from_device_value(readback.get("railcomplus"))
    if readback_railcom != target_railcom or readback_railcomplus != target_railcomplus:
      raise ControllerParameterWriteError(
        "ECoS RailCom 设置写入后读回不一致",
        {
          "target_railcom_enabled": target_railcom,
          "target_railcomplus_enabled": target_railcomplus,
          "readback_railcom_enabled": readback_railcom,
          "readback_railcomplus_enabled": readback_railcomplus,
          "write_request_hex": _commands_hex(commands),
          "responses": [block.to_debug_dict() for block in blocks],
        },
      )
    settings["railcom_enabled"] = target_railcom
    settings["railcomplus_enabled"] = target_railcomplus
    controller.setdefault("settings", {})["railcom_enabled"] = target_railcom
    controller["settings"]["railcomplus_enabled"] = target_railcomplus
    controller.setdefault("device_info", {})["railcom"] = "1" if target_railcom else "0"
    controller["device_info"]["railcomplus"] = "1" if target_railcomplus else "0"
    controller["device_info"]["railcom_source"] = "ecos_object_1"
    controller["device_info"]["railcomplus_source"] = "ecos_object_1"
    return {
      "setting": "ecos_railcom",
      "railcom_enabled": target_railcom,
      "railcomplus_enabled": target_railcomplus,
      "write_request_hex": _commands_hex(commands),
    }

  def apply_track_profile_parameters(self, session_manager, controller: dict, profiles: dict, modes: list[str], *, transport=None) -> list[dict]:
    results = []
    for mode in modes:
      profile = profiles.get(mode)
      if not isinstance(profile, dict) or "target_current_limit_ma" not in profile:
        continue
      current_limit_ma = profile.get("target_current_limit_ma")
      if current_limit_ma in ("", None):
        continue
      target_current_limit_ma = int(current_limit_ma)
      booster_object_id = int(controller.get("booster_status", {}).get("booster_object_id") or SYSTEM_BOOSTER_OBJECT_ID)
      commands = build_booster_current_limit_write_commands(booster_object_id, target_current_limit_ma)
      text = self._exchange_ecos(
        session_manager,
        controller,
        commands,
        expected_replies=len(commands),
      )
      blocks = parse_blocks(text)
      readback = parse_booster_monitor_info(blocks, object_id=booster_object_id)
      readback_current_limit_ma = _optional_int(readback.get("limit"))
      if readback_current_limit_ma != target_current_limit_ma:
        raise ControllerParameterWriteError(
          f"ECoS {mode} 限流写入后读回不一致",
          {
            "mode": mode,
            "booster_object_id": booster_object_id,
            "target_current_limit_ma": target_current_limit_ma,
            "readback_current_limit_ma": readback_current_limit_ma,
            "write_request_hex": _commands_hex(commands),
            "responses": [block.to_debug_dict() for block in blocks],
          },
        )
      controller.setdefault("track_profiles", {}).setdefault(mode, {}).update({
        "target_current_limit_ma": target_current_limit_ma,
      })
      controller.setdefault("booster_status", {}).update({
        "source": f"ecos_booster_{booster_object_id}",
        "booster_object_id": booster_object_id,
        "limit_ma": readback_current_limit_ma,
      })
      results.append({
        "mode": mode,
        "setting": "ecos_booster_current_limit",
        "booster_object_id": booster_object_id,
        "target_current_limit_ma": target_current_limit_ma,
        "readback_current_limit_ma": readback_current_limit_ma,
        "write_request_hex": _commands_hex(commands),
      })
    return results

  def parse_controller_info(self, controller: dict, request, result: ControllerInfoReadResult) -> dict:
    controller["track_mode"] = request.track_mode
    info = dict(result.collected.get("basic_info") or {})
    monitor = dict(result.collected.get("booster_monitor") or {})
    booster_object_id = int(result.collected.get("booster_object_id") or monitor.get("object_id") or SYSTEM_BOOSTER_OBJECT_ID)
    status = str(info.get("status") or "").upper()
    booster_status = _ecos_booster_status_from_monitor(
      monitor,
      fallback_status=status,
      booster_object_id=booster_object_id,
    )
    controller["controller_reachable"] = True
    controller["controller_unreachable_reason"] = ""
    controller["last_probe_ok"] = True
    controller["device_info"] = {
      **controller.get("device_info", {}),
      **info,
      "source": "ecos_object_1",
    }
    controller["booster_status"] = booster_status
    controller["telemetry"] = {
      **controller.get("telemetry", {}),
      "temperature_c": booster_status.get("temperature_c"),
      "track_voltage_v": booster_status.get("output_voltage_v"),
      "track_current_a": booster_status.get("output_current_a"),
      "track_power_w": _power_w(booster_status.get("output_voltage_v"), booster_status.get("output_current_a")),
    }
    mark_controller_safety_fresh(controller, booster_status_fresh=True, programming_track_status_fresh=True)
    warnings = list(result.warnings)
    safe_for_cv = update_cv_safety_from_programming_status(
      controller,
      self,
      warnings,
      source=f"ecos_booster_{booster_object_id}",
    )
    return {
      "safe_for_cv": safe_for_cv,
      "warnings": warnings,
    }

  def is_booster_status_confirmed(self, controller: dict) -> bool:
    booster_status = controller.get("booster_status")
    source = str(booster_status.get("source") or "") if isinstance(booster_status, dict) else ""
    return source == "ecos_object_1" or source.startswith("ecos_booster_")

  def programming_track_status(self, controller: dict):
    if not self.is_booster_status_confirmed(controller):
      return read_only_programming_track_status(controller)
    try:
      track_mode = models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      track_mode = str(controller.get("track_mode") or "")
    return ECoSProgrammingTrackStatus(
      track_mode=track_mode,
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=0,
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


def _required_basic_info(text: str) -> dict:
  info = parse_basic_info(text)
  if not info:
    raise ValueError("ECoS basic information response was missing")
  return info


def _ecos_status_from_blocks(blocks: list[ECoSBlock]) -> str:
  for block in blocks:
    if block.kind != "REPLY" or not block.command.startswith("get(1,"):
      continue
    info = parse_basic_info(blocks)
    status = str(info.get("status") or "").strip().upper()
    if status:
      return status
    for line in block.lines:
      if "status[" not in line:
        continue
      return line.split("status[", 1)[1].split("]", 1)[0].strip().upper()
  return ""


def _select_system_booster_object_id(boosters: list[dict]) -> int:
  for booster in boosters:
    if str(booster.get("name") or "").strip().lower() == "system booster":
      return int(booster["object_id"])
  if boosters:
    return int(boosters[0]["object_id"])
  return SYSTEM_BOOSTER_OBJECT_ID


def _ecos_booster_status_from_monitor(monitor: dict, *, fallback_status: str, booster_object_id: int) -> dict:
  status = str(monitor.get("status") or fallback_status or "").strip().upper()
  main_current_ma, return_current_ma = _current_values_ma(monitor.get("current"))
  output_voltage_v = _mv_to_v(monitor.get("voltage"))
  temperature_c = _optional_int(monitor.get("temperature"))
  current_a = _ma_to_a(main_current_ma)
  short_circuit = status in {"SHORT", "OVERLOAD", "ERROR"}
  return {
    "source": f"ecos_booster_{booster_object_id}",
    "booster_object_id": int(booster_object_id),
    "name": str(monitor.get("name") or "System booster"),
    "status": status,
    "power_on": status == "GO",
    "short_circuit": short_circuit,
    "dcc_mode": True,
    "main_track_current_ma": main_current_ma,
    "return_current_ma": return_current_ma,
    "output_voltage_v": output_voltage_v,
    "output_current_a": current_a,
    "temperature_c": temperature_c,
    "limit_ma": _optional_int(monitor.get("limit")),
    "raw_monitor": dict(monitor),
  }


def _current_values_ma(value) -> tuple[int | None, int | None]:
  if isinstance(value, list):
    first = _optional_int(value[0]) if value else None
    second = _optional_int(value[1]) if len(value) > 1 else None
    return first, second
  parsed = _optional_int(value)
  return parsed, None


def _optional_int(value) -> int | None:
  if value in ("", None):
    return None
  return int(value)


def _optional_bool_from_device_value(value) -> bool | None:
  if isinstance(value, bool):
    return value
  if value in ("", None):
    return None
  try:
    return bool(int(value))
  except (TypeError, ValueError):
    normalized = str(value).strip().lower()
    if normalized in {"true", "on", "enabled", "go", "开启"}:
      return True
    if normalized in {"false", "off", "disabled", "stop", "关闭"}:
      return False
  return None


def _mv_to_v(value) -> float | None:
  mv = _optional_int(value)
  return None if mv is None else mv / 1000


def _ma_to_a(value) -> float | None:
  ma = _optional_int(value)
  return None if ma is None else ma / 1000


def _power_w(voltage_v, current_a) -> float | None:
  if voltage_v is None or current_a is None:
    return None
  return float(voltage_v) * float(current_a)


def _commands_hex(commands) -> str:
  return "\n".join(_command_hex(command) for command in commands)


def _command_hex(command: str) -> str:
  return str(command).encode("ascii").hex(" ")

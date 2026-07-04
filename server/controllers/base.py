"""Controller adapter contracts."""

from dataclasses import dataclass, field
from typing import Protocol


class ControllerFrameList(list):
  """List of valid controller frames with raw diagnostic frames attached."""

  def __init__(self, frames=None, *, diagnostic_frames=None):
    super().__init__(frames or [])
    self.diagnostic_frames = list(diagnostic_frames if diagnostic_frames is not None else self)


@dataclass(frozen=True)
class ControllerCapabilities:
  track_power: bool
  dc_control: bool
  read_info: bool
  cv_programming: bool
  loco_control: bool
  controller_settings: bool
  railcom_settings: bool = False
  profile_settings_on_track_mode: bool = False

  def to_dict(self) -> dict:
    return {
      "track_power": self.track_power,
      "dc_control": self.dc_control,
      "read_info": self.read_info,
      "cv_programming": self.cv_programming,
      "loco_control": self.loco_control,
      "controller_settings": self.controller_settings,
      "railcom_settings": self.railcom_settings,
      "profile_settings_on_track_mode": self.profile_settings_on_track_mode,
    }


@dataclass(frozen=True)
class ControllerTransportDescriptor:
  kind: str
  defaults: dict
  endpoint_required_paths: tuple[str, ...] = ()
  metadata: dict = field(default_factory=dict)

  def default_config(self) -> dict:
    return {"kind": self.kind, **self.defaults}

  def to_dict(self) -> dict:
    return {
      "kind": self.kind,
      "defaults": dict(self.defaults),
      "metadata": {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in self.metadata.items()
      },
      "endpoint_readiness": {
        "required_paths": list(self.endpoint_required_paths),
      },
    }


def configured_controller_text(config: dict | None, key: str, fallback: str) -> str:
  if isinstance(config, dict):
    value = str(config.get(key) or "").strip()
    if value:
      return value
  return fallback


def controller_display_name(adapter, config: dict | None = None) -> str:
  return configured_controller_text(config, "display_name", getattr(adapter, "default_display_name", adapter.label))


def controller_protocol(adapter, config: dict | None = None) -> str:
  return configured_controller_text(config, "protocol", getattr(adapter, "protocol", ""))


def controller_supported_protocols(adapter) -> tuple[str, ...]:
  protocols = getattr(adapter, "supported_protocols", None)
  if protocols is None:
    protocol = str(getattr(adapter, "protocol", "") or "").strip()
    return (protocol,) if protocol else ()
  return tuple(str(protocol).strip() for protocol in protocols if str(protocol).strip())


def apply_controller_transport_runtime(adapter, controller: dict) -> None:
  apply_runtime = getattr(adapter, "apply_transport_runtime", None)
  if callable(apply_runtime):
    apply_runtime(controller)


def normalize_controller_transport_config(adapter, transport, *, strict: bool) -> dict:
  normalize = getattr(adapter, "normalize_transport_config", None)
  if callable(normalize):
    return normalize(transport, strict=strict)
  descriptor = adapter.transport_descriptor
  source = transport if isinstance(transport, dict) else {}
  return {
    **descriptor.default_config(),
    **source,
    "kind": str(source.get("kind") or descriptor.kind),
  }


def controller_readiness_detail(adapter, warnings: list[str]) -> str:
  detail_provider = getattr(adapter, "readiness_warning_detail", None)
  if callable(detail_provider):
    return detail_provider(warnings)
  return adapter.status_not_ready_message()


@dataclass(frozen=True)
class TrackOutputRequest:
  powered: bool
  track_mode: str
  output_value: int
  dc_direction_positive: bool = True
  timeout_seconds: float = 1.5


@dataclass
class TrackOutputResult:
  request_hex: str
  frames: list = field(default_factory=list)
  booster_status: dict = field(default_factory=dict)
  debug: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ControllerInfoReadRequest:
  track_mode: str
  current_param: int


@dataclass
class ControllerInfoReadResult:
  collected: dict
  warnings: list = field(default_factory=list)
  requests: list = field(default_factory=list)


@dataclass(frozen=True)
class CvCommandRequest:
  cv_number: int
  client_id: int
  value: int | None = None
  op: int | None = None
  pom_address: int | None = None
  timeout_seconds: float | None = None
  max_packets: int = 32


@dataclass
class CvCommandResult:
  request_hex: str
  frames: list = field(default_factory=list)


@dataclass(frozen=True)
class LocoSpeedRequest:
  address: int
  speed: int
  direction: str
  client_id: int
  control_protocol: str = "dcc"
  speed_steps: int = 128


@dataclass(frozen=True)
class LocoFunctionRequest:
  address: int
  function_states: dict
  function_number: int
  client_id: int
  control_protocol: str = "dcc"
  speed_steps: int = 128


@dataclass(frozen=True)
class LocoControlGrantRequest:
  address: int
  client_id: int
  control_protocol: str = "dcc"
  speed_steps: int = 128


@dataclass
class LocoControlGrantResult:
  request_hex: str
  address: int
  feedback: dict | None = None
  frames: list = field(default_factory=list)
  debug: dict = field(default_factory=dict)


@dataclass
class LocoCommandResult:
  request_hex: str
  request_hexes: list[str]
  feedback: dict | None = None
  extra: dict = field(default_factory=dict)
  frames: list = field(default_factory=list)


class ControllerOperationNotSupported(RuntimeError):
  """Raised when a controller adapter does not implement an optional operation."""

  def __init__(self, operation: str, controller_kind: str):
    super().__init__(f"{controller_kind} does not support {operation}")
    self.operation = operation
    self.controller_kind = controller_kind


class ControllerProtocolNotSupported(RuntimeError):
  """Raised when a controller config requests a protocol the selected adapter cannot use."""

  def __init__(self, controller_kind: str, protocol: str, supported_protocols, reason: str = ""):
    supported = tuple(supported_protocols or ())
    supported_text = ", ".join(supported) if supported else "none"
    detail = f"{controller_kind} configured protocol {protocol!r}, supported protocols: {supported_text}"
    if reason:
      detail = f"{detail}; {reason}"
    super().__init__(detail)
    self.controller_kind = controller_kind
    self.protocol = protocol
    self.supported_protocols = supported
    self.reason = reason


class ControllerParameterWriteError(RuntimeError):
  def __init__(self, message: str, debug: dict | None = None):
    super().__init__(message)
    self.debug = debug or {}


class ControllerAdapter(Protocol):
  kind: str
  label: str
  default_display_name: str
  protocol: str
  default_ip: str
  config_file_name: str
  capabilities: ControllerCapabilities
  transport_descriptor: ControllerTransportDescriptor

  def runtime_readiness_warnings(self, controller: dict) -> list[str]:
    ...

  def loco_control_readiness_warnings(self, controller: dict) -> list[str]:
    ...

  def status_not_ready_message(self) -> str:
    ...

  def controller_client_id(self, controller: dict) -> int:
    ...

  def create_session_manager(self, *, transport=None, context=None):
    ...

  def session_identity(self, controller: dict) -> tuple:
    ...

  def endpoint_identity(self, controller: dict) -> tuple:
    ...

  def apply_transport_runtime(self, controller: dict) -> None:
    ...


class ReadInfoCapability(Protocol):
  def exchange(self, session_manager, controller: dict, request_frame: bytes, **kwargs):
    ...

  def read_info_frames(self, session_manager, controller: dict, requests: list, *, transport=None) -> dict:
    ...

  def read_controller_info(self, session_manager, controller: dict, request: ControllerInfoReadRequest, *, transport=None) -> ControllerInfoReadResult:
    ...

  def parse_controller_info(self, controller: dict, request: ControllerInfoReadRequest, result: ControllerInfoReadResult) -> dict:
    ...


class TrackPowerCapability(Protocol):
  def send_track_output(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    ...

  def send_track_output_request(self, session_manager, controller: dict, request: TrackOutputRequest, *, transport=None) -> TrackOutputResult:
    ...


class CvProgrammingCapability(Protocol):
  def validate_programming_track_safety(self, programming_status) -> None:
    ...

  def read_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    ...

  def write_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    ...

  def read_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    ...

  def write_cv_request(self, session_manager, controller: dict, request: CvCommandRequest, *, transport=None) -> CvCommandResult:
    ...

  def main_track_loco_pom_op(self) -> int:
    ...

  def classify_cv_responses(self, frames: list, *, client_id: int, cv_number: int, pom_address: int | None = None):
    ...

  def cv_ack_category(self, ack) -> str:
    ...

  def should_retry_cv_write_ack(self, ack, *, attempt: int, retry_count: int) -> bool:
    ...

  def is_main_track_cv_read_no_ack(self, ack) -> bool:
    ...

  def cv_ack_debug(self, ack) -> dict:
    ...


class LocoControlCapability(Protocol):
  def request_loco_control_grant(self, session_manager, controller: dict, request: LocoControlGrantRequest, *, transport=None) -> LocoControlGrantResult:
    ...

  def send_loco_speed_request(self, session_manager, controller: dict, request: LocoSpeedRequest, *, transport=None) -> LocoCommandResult:
    ...

  def send_loco_function_request(self, session_manager, controller: dict, request: LocoFunctionRequest, *, transport=None) -> LocoCommandResult:
    ...


class ControllerSettingsCapability(Protocol):
  def apply_track_profile_parameters(self, session_manager, controller: dict, profiles: dict, modes: list[str], *, transport=None) -> list[dict]:
    ...

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
  read_info: bool
  cv_programming: bool
  loco_control: bool
  controller_settings: bool

  def to_dict(self) -> dict:
    return {
      "track_power": self.track_power,
      "read_info": self.read_info,
      "cv_programming": self.cv_programming,
      "loco_control": self.loco_control,
      "controller_settings": self.controller_settings,
    }


@dataclass(frozen=True)
class ControllerTransportDefaults:
  udp_port: int
  local_udp_port: int
  checksum_algorithm: str
  checksum_algorithms: tuple[str, ...] = ()
  allow_zero_local_udp_port: bool = True

  def __post_init__(self):
    if not self.checksum_algorithms:
      object.__setattr__(self, "checksum_algorithms", (self.checksum_algorithm,))

  def to_dict(self) -> dict:
    return {
      "udp_port": self.udp_port,
      "local_udp_port": self.local_udp_port,
      "checksum_algorithm": self.checksum_algorithm,
      "checksum_algorithms": list(self.checksum_algorithms),
      "allow_zero_local_udp_port": self.allow_zero_local_udp_port,
    }


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


@dataclass(frozen=True)
class LocoFunctionRequest:
  address: int
  function_states: dict
  function_number: int
  client_id: int


@dataclass(frozen=True)
class LocoControlGrantRequest:
  address: int
  client_id: int


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


class ControllerParameterWriteError(RuntimeError):
  def __init__(self, message: str, debug: dict | None = None):
    super().__init__(message)
    self.debug = debug or {}


class ControllerAdapter(Protocol):
  kind: str
  label: str
  default_ip: str
  config_file_name: str
  capabilities: ControllerCapabilities
  transport_defaults: ControllerTransportDefaults

  def runtime_readiness_warnings(self, controller: dict) -> list[str]:
    ...

  def loco_control_readiness_warnings(self, controller: dict) -> list[str]:
    ...

  def status_not_ready_message(self) -> str:
    ...


class ControllerStatusCapability(Protocol):
  def is_booster_status_confirmed(self, controller: dict) -> bool:
    ...

  def programming_track_status(self, controller: dict):
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

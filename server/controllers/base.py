"""Controller adapter contracts."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ControllerCapabilities:
  track_power: bool
  read_info: bool
  cv_programming: bool
  loco_control: bool
  controller_settings: bool


@dataclass
class ControllerContext:
  state: dict
  controller: dict
  request_meta: dict = field(default_factory=dict)


@dataclass
class ControllerRequestResult:
  request_hex: str
  frames: list = field(default_factory=list)
  debug: dict = field(default_factory=dict)


class ControllerAdapter(Protocol):
  kind: str
  label: str
  capabilities: ControllerCapabilities

  def exchange(self, session_manager, controller: dict, request_frame: bytes, **kwargs):
    ...

  def read_info_frames(self, session_manager, controller: dict, requests: list, *, transport=None) -> dict:
    ...

  def send_track_output(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    ...

  def read_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    ...

  def write_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    ...

  def request_loco_control(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    ...

  def send_loco_speed(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    ...

  def send_loco_function(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    ...

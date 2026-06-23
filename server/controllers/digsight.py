"""Digsight DXDCNet controller adapter."""

from digsight_dxdcnet.frames import decode_udp_frame
from digsight_dxdcnet.udp_transport import UDPTransport

from server import models
from server.controllers.base import ControllerCapabilities


class DigsightDXDCNetControllerAdapter:
  kind = "digsight_controller"
  label = "动芯 DXDCNet"
  capabilities = ControllerCapabilities(
    track_power=True,
    read_info=True,
    cv_programming=True,
    loco_control=True,
    controller_settings=True,
  )

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
    for raw in raw_responses:
      frame = decode_udp_frame(raw)
      if frame.checksum_valid:
        frames.append(frame)
    return frames

  def read_info_frames(self, session_manager, controller: dict, requests: list, *, transport=None) -> dict:
    collected = {}
    read_warnings = []
    request_debug = []
    for spec in requests:
      if isinstance(spec, dict):
        name = spec["name"]
        request_frame = spec["request_frame"]
        expected_command = spec.get("expected_command")
        expected_device_type = spec.get("expected_device_type")
        timeout_seconds = spec.get("timeout_seconds", float(controller.get("read_info_timeout_seconds", 0.4)))
        stop_when = spec.get("stop_when")
      else:
        name, request_frame, expected_command, expected_device_type = spec
        timeout_seconds = float(controller.get("read_info_timeout_seconds", 0.4))
        stop_when = None
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
        "responses": [frame.to_debug_dict() for frame in frames],
      })
    return {
      "collected": collected,
      "warnings": read_warnings,
      "requests": request_debug,
    }

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

  def read_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      stop_when=stop_when,
      transport=transport,
    )

  def write_cv(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float | None, max_packets: int, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      stop_when=stop_when,
      transport=transport,
    )

  def request_loco_control(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=4,
      stop_when=stop_when,
      transport=transport,
    )

  def send_loco_speed(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=8,
      stop_when=stop_when,
      transport=transport,
    )

  def send_loco_function(self, session_manager, controller: dict, request_frame: bytes, *, timeout_seconds: float, stop_when, transport=None):
    return self.exchange(
      session_manager,
      controller,
      request_frame,
      timeout_seconds=timeout_seconds,
      max_packets=8,
      stop_when=stop_when,
      transport=transport,
    )

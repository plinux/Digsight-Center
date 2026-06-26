"""Support boundary used by ControllerService.

ControllerService owns hardware-facing operations, but several of those
operations still need router-owned persistence, error formatting, safety cache
updates, and loco-control preflight helpers. This support object exposes those
dependencies as explicit ports so the service layer does not retain the full
HTTP router.
"""

from dataclasses import dataclass
import json

from server.controller_services.results import ServiceResult


@dataclass(frozen=True)
class ControllerServicePorts:
  mark_controller_unreachable_port: object
  mark_safety_snapshot_fresh_port: object
  save_port: object
  frame_debug_port: object
  request_debug_port: object
  cv_debug_port: object
  cv_write_busy_retry_count_port: object
  cv_write_busy_retry_delay_seconds_port: object


class ControllerServiceSupport:
  def __init__(self, ports: ControllerServicePorts):
    self._ports = ports

  def mark_controller_unreachable(self, state: dict, reason: str) -> None:
    self._ports.mark_controller_unreachable_port(state, reason)

  def mark_safety_snapshot_fresh(
    self,
    controller: dict,
    *,
    booster_status_fresh: bool | None = None,
    programming_track_status_fresh: bool | None = None,
  ) -> None:
    self._ports.mark_safety_snapshot_fresh_port(
      controller,
      booster_status_fresh=booster_status_fresh,
      programming_track_status_fresh=programming_track_status_fresh,
    )

  def save(self, state: dict) -> None:
    self._ports.save_port(state)

  def failure(self, error_type: str, message: str, detail: str = "", *, status: int = 400, debug=None):
    return ServiceResult.failure(error_type, message, detail, status=status, debug=debug)

  def frame_debug(self, frame):
    return self._ports.frame_debug_port(frame)

  def request_debug(self, frame):
    return self._ports.request_debug_port(frame)

  def cv_debug(self, *, cv, client_id, request_frame=None, responses=None, pom_address=None, extra=None):
    return self._ports.cv_debug_port(
      cv=cv,
      client_id=client_id,
      request_frame=request_frame,
      responses=responses,
      pom_address=pom_address,
      extra=extra,
    )

  def json_payload(self, body: bytes) -> dict:
    payload = json.loads(body.decode("utf-8"))
    if not isinstance(payload, dict):
      raise ValueError("JSON payload root must be an object")
    return payload

  def cv_write_busy_retry_count(self, controller: dict) -> int:
    return self._ports.cv_write_busy_retry_count_port(controller)

  def cv_write_busy_retry_delay_seconds(self, controller: dict) -> float:
    return self._ports.cv_write_busy_retry_delay_seconds_port(controller)

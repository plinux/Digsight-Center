"""HTTP-adjacent helpers shared by API support modules."""

import binascii
import json

from server import response
from server.api_support.cv_operations import CvOperationContext, cv_debug as build_cv_debug
from server.controller_services.results import ServiceResult


class JsonBodyError(RuntimeError):
  pass


def json_body(body: bytes) -> dict:
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


def resource_id(route: str) -> str:
  value = route.rsplit("/", 1)[-1]
  if not value:
    raise ValueError("resource id must not be empty")
  return value


def success(data, status: int = 200):
  return response.success(data), status


def failure(error_type: str, message: str, detail: str = "", *, status: int = 400, debug=None):
  return response.failure(error_type, message, detail, debug), status


def require_json_bool(value, field_name: str) -> bool:
  if not isinstance(value, bool):
    raise ValueError(f"{field_name} must be a JSON boolean")
  return value


def optional_json_bool(request: dict, field_name: str, default: bool = False) -> bool:
  if field_name not in request:
    return default
  return require_json_bool(request[field_name], field_name)


def service_result(result: ServiceResult):
  if result.ok:
    return response.success(result.data), result.status
  return response.failure(
    result.error_type,
    result.message,
    result.detail,
    result.debug,
  ), result.status


def frame_debug(frame):
  if hasattr(frame, "to_debug_dict"):
    return frame.to_debug_dict()
  return frame


def frame_debug_list(frames):
  diagnostic_frames = getattr(frames, "diagnostic_frames", frames)
  return [frame_debug(frame) for frame in diagnostic_frames]


def request_debug(frame):
  if frame is None:
    return None
  if hasattr(frame, "to_hex"):
    return frame.to_hex()
  if isinstance(frame, (bytes, bytearray, memoryview)):
    return bytes(frame).hex(" ")
  if hasattr(frame, "hex"):
    try:
      return frame.hex(" ")
    except TypeError:
      return frame.hex()
    except (ValueError, binascii.Error):
      return str(frame)
  return str(frame)


def cv_debug(*, cv, client_id, request_frame=None, responses=None, pom_address=None, extra=None):
  context_frame = request_frame if isinstance(request_frame, (bytes, bytearray, memoryview)) else b""
  context = CvOperationContext(
    cv_number=cv,
    client_id=client_id,
    request_frame=bytes(context_frame),
    pom_address=pom_address,
  )
  debug = build_cv_debug(context, responses=frame_debug_list(responses if responses is not None else []), extra=extra)
  debug["request_hex"] = request_debug(request_frame)
  return debug


def cv_write_busy_retry_count(controller: dict) -> int:
  try:
    value = int(controller.get("cv_write_busy_retry_count", 5))
  except (TypeError, ValueError):
    value = 5
  return max(0, min(value, 10))


def cv_write_busy_retry_delay_seconds(controller: dict) -> float:
  try:
    value = float(controller.get("cv_write_busy_retry_delay_seconds", 0.2))
  except (TypeError, ValueError):
    value = 0.2
  return max(0.0, min(value, 2.0))

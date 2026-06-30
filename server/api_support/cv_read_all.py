"""CV read-all API orchestration."""

from datetime import datetime

from server import response
from server.api_support import http_helpers
from server.api_support.cv_programming import CvOperationError
from server.cv_catalog import cv_meaning, default_cv_catalog, manufacturer_name


STOPPING_ERROR_TYPES = {
  "cv_read_timeout",
  "cv_read_transport_error",
  "controller_unreachable",
  "controller_not_reachable",
  "controller_not_connected",
}


class CvReadAllApiSupport:
  def __init__(self, context, controller_service, controller_api, cv_programming_api):
    self.context = context
    self.controller_service = controller_service
    self.controller_api = controller_api
    self.cv_programming_api = cv_programming_api

  def read_all(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    raw_session_id = request.get("session_id") or f"server-{datetime.now().timestamp()}"
    try:
      read_mode, cv_numbers = self._resolve_cv_read_all_numbers(request)
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_cv", "CV 地址列表无效", str(exc)), 400
    operation, failure = self.cv_programming_api.prepare_cv_operation(
      request,
      state,
      "CV 列表读取",
      "cv_read_all",
    )
    if failure:
      return failure
    try:
      session_id = self.context.cv_read_sessions.start(raw_session_id)
    except ValueError as exc:
      return response.failure("invalid_cv_read_session", "CV 读取会话无效", str(exc)), 400
    controller = operation["controller"]
    client_id = operation["client_id"]
    cv_context = operation["cv_context"]
    manufacturer_id = None
    manufacturer_result = None
    warnings = []
    read_results = {}
    read_errors = {}
    attempted_numbers = set()
    cancelled = False
    stopped = False
    stop_reason = ""
    try:
      if self.context.cv_read_sessions.is_cancelled(session_id):
        cancelled = True
      else:
        attempted_numbers.add(8)
        manufacturer_id, manufacturer_result, stopped, stop_reason = self._read_cv8_for_read_all(
          controller,
          client_id,
          cv_context,
          read_results,
          read_errors,
          warnings,
        )

      if cv_numbers is None:
        cv_numbers = default_cv_catalog().known_cv_numbers(manufacturer_id)

      if not cancelled and not stopped:
        cancelled, stopped, stop_reason, read_results, read_errors, attempted_numbers = self._read_cv_list_rows(
          controller,
          client_id,
          cv_context,
          session_id,
          cv_numbers,
          read_results,
          read_errors,
          attempted_numbers,
        )

      return self._build_cv_read_all_response(
        manufacturer_id=manufacturer_id,
        manufacturer_result=manufacturer_result,
        read_mode=read_mode,
        session_id=session_id,
        cancelled=cancelled,
        cv_numbers=cv_numbers,
        read_results=read_results,
        read_errors=read_errors,
        attempted_numbers=attempted_numbers,
        warnings=warnings,
        stopped=stopped,
        stop_reason=stop_reason,
      ), 200
    finally:
      self.context.cv_read_sessions.finish(session_id)

  def cancel(self, body: bytes):
    request = http_helpers.json_body(body)
    try:
      session_id = self.context.cv_read_sessions.cancel(request.get("session_id"))
    except ValueError as exc:
      return response.failure("invalid_cv_read_session", "CV 读取会话无效", str(exc)), 400
    return response.success({"session_id": session_id, "cancelled": True}), 200

  def _resolve_cv_read_all_numbers(self, request: dict):
    read_mode = self.cv_programming_api.validate_cv_read_mode(request.get("read_mode", "known"))
    requested_cv_numbers = request.get("cv_numbers")
    if requested_cv_numbers is not None:
      return "custom", self.cv_programming_api.validate_cv_read_all_numbers(requested_cv_numbers)
    if read_mode == "full":
      return read_mode, list(range(1, 1025))
    return read_mode, None

  def _read_cv_for_read_all(self, controller, client_id, cv_context, cv_number):
    return self.cv_programming_api.read_cv_direct(
      controller,
      cv_number,
      client_id,
      timeout_seconds=float(controller.get("cv_read_all_timeout_seconds", 1.0)),
      max_packets=8,
      cv_context=cv_context,
    )

  def _read_cv8_for_read_all(self, controller, client_id, cv_context, read_results, read_errors, warnings):
    try:
      result = self._read_cv_for_read_all(
        controller,
        client_id,
        cv_context,
        8,
      )
      read_results[8] = result
      return int(result["value"]), result, False, ""
    except (CvOperationError, TypeError, ValueError) as exc:
      parsed_error = self._parse_read_error(exc)
      read_errors[8] = parsed_error["message"]
      warnings.append("manufacturer_cv8_read_failed")
      if self._should_stop_after_error(parsed_error):
        warnings.append("cv_read_all_stopped")
        return None, None, True, parsed_error["type"]
      return None, None, False, ""

  def _read_cv_list_rows(
    self,
    controller,
    client_id,
    cv_context,
    session_id,
    cv_numbers,
    read_results,
    read_errors,
    attempted_numbers,
  ):
    cancelled = False
    stopped = False
    stop_reason = ""
    for cv_number in [cv for cv in cv_numbers if cv != 8]:
      if self.context.cv_read_sessions.is_cancelled(session_id):
        cancelled = True
        break
      attempted_numbers.add(cv_number)
      try:
        result = self._read_cv_for_read_all(
          controller,
          client_id,
          cv_context,
          cv_number,
        )
        read_results[cv_number] = result
      except (CvOperationError, TypeError, ValueError) as exc:
        parsed_error = self._parse_read_error(exc)
        read_errors[cv_number] = parsed_error["message"]
        if self._should_stop_after_error(parsed_error):
          stopped = True
          stop_reason = parsed_error["type"]
          break
    return cancelled, stopped, stop_reason, read_results, read_errors, attempted_numbers

  def _parse_read_error(self, exc: Exception) -> dict:
    if isinstance(exc, CvOperationError):
      result = exc.result
      return {
        "type": result.error_type or "cv_read_failed",
        "message": result.message or "CV 读取失败",
      }
    return {
      "type": type(exc).__name__,
      "message": str(exc) or "CV 读取失败",
    }

  def _should_stop_after_error(self, parsed_error: dict) -> bool:
    return parsed_error.get("type") in STOPPING_ERROR_TYPES

  def _build_cv_read_all_response(
    self,
    *,
    manufacturer_id,
    manufacturer_result,
    read_mode,
    session_id,
    cancelled,
    cv_numbers,
    read_results,
    read_errors,
    attempted_numbers,
    warnings,
    stopped,
    stop_reason,
  ):
    row_numbers = cv_numbers if not (cancelled or stopped) else [cv for cv in cv_numbers if cv in attempted_numbers]
    rows = [
      self._cv_read_all_row(cv_number, manufacturer_id, read_results.get(cv_number), read_errors)
      for cv_number in row_numbers
    ]

    return response.success({
      "manufacturer_id": manufacturer_id,
      "manufacturer_name": manufacturer_name(manufacturer_id),
      "manufacturer_cv": manufacturer_result,
      "read_mode": read_mode,
      "session_id": session_id,
      "cancelled": cancelled,
      "stopped": stopped,
      "stop_reason": stop_reason,
      "rows": rows,
      "read_count": len(rows),
      "ok_count": sum(1 for row in rows if row["ok"]),
      "method": "dxdcnet_programmer_direct_read_all_cvs",
      "warnings": warnings,
    })

  def _cv_read_all_row(self, cv_number: int, manufacturer_id, result, read_errors: dict) -> dict:
    row = {
      "cv": cv_number,
      "meaning": cv_meaning(cv_number, manufacturer_id),
      "value": None,
      "ok": False,
      "error": read_errors.get(cv_number, "CV 读取失败"),
    }
    if result is not None:
      row.update({
        "value": int(result["value"]),
        "ok": True,
        "error": "",
      })
    return row

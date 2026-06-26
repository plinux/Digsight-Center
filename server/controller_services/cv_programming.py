"""CV programming controller operations."""

import json
import time

from server import models
from server.api_support.cv_operations import readback_value_matches
from server.controllers.base import ControllerOperationNotSupported, CvCommandRequest
from server.controller_services.results import ServiceResult


class CvProgrammingService:
  def execute_cv_read(
    self,
    controller: dict,
    cv_number: int,
    client_id: int,
    timeout_seconds: float | None = None,
    max_packets: int = 32,
    cv_context: dict | None = None,
  ):
    context = cv_context or {}
    pom_address = context.get("pom_address")
    op = context.get("op")
    request_frame, frames, error_response = self._send_cv_read_request(
      controller,
      cv_number,
      client_id,
      op,
      pom_address,
      timeout_seconds,
      max_packets,
      context.get("state"),
    )
    if error_response is not None:
      return error_response

    classification = self._classify_cv_responses(
      controller,
      frames,
      client_id,
      cv_number,
      pom_address,
    )
    if classification.value is not None:
      return ServiceResult.success(self._cv_read_success_payload(
        context,
        classification,
        cv_number,
        request_frame,
        pom_address,
      ))

    if classification.ack is not None:
      return self._cv_read_ack_failure(
        controller,
        classification,
        cv_number,
        client_id,
        request_frame,
        frames,
        pom_address,
      )
    return self._cv_read_unmatched_failure(
      classification,
      cv_number,
      client_id,
      request_frame,
      frames,
      pom_address,
    )

  def _send_cv_read_request(
    self,
    controller: dict,
    cv_number: int,
    client_id: int,
    op,
    pom_address,
    timeout_seconds: float | None,
    max_packets: int,
    state: dict | None,
  ):
    request_frame = b""
    try:
      adapter = self.ensure_supported(controller, "cv_programming", "cv_read")
      result = adapter.read_cv_request(
        self.controller_session,
        controller,
        CvCommandRequest(
          cv_number=cv_number,
          client_id=client_id,
          op=int(op) if op is not None else None,
          pom_address=pom_address,
          timeout_seconds=timeout_seconds,
          max_packets=max_packets,
        ),
        transport=self.udp_transport,
      )
      return bytes.fromhex(result.request_hex), result.frames, None
    except ControllerOperationNotSupported as exc:
      return request_frame, [], self.operation_not_supported_response(exc)
    except TimeoutError as exc:
      if state is not None:
        self.service_support.mark_controller_unreachable(state, "cv_read_timeout")
      return request_frame, [], self._cv_read_failure_response(
        "cv_read_timeout",
        "读取 CV 超时",
        str(exc),
        504,
        cv_number,
        client_id,
        request_frame,
        pom_address=pom_address,
      )
    except (OSError, ValueError) as exc:
      if state is not None:
        self.service_support.mark_controller_unreachable(state, "cv_read_transport_error")
      return request_frame, [], self._cv_read_failure_response(
        "cv_read_transport_error",
        "读取 CV 通信失败",
        str(exc),
        502,
        cv_number,
        client_id,
        request_frame,
        pom_address=pom_address,
      )

  def _cv_read_success_payload(self, context: dict, classification, cv_number: int, request_frame: bytes, pom_address) -> dict:
    support = self.service_support
    value = classification.value
    data = {
      "cv": cv_number,
      "value": value.value,
      "method": "dxdcnet_programmer_main_track_pom_read" if pom_address is not None else "dxdcnet_programmer_direct_read",
      "programming_target": context.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK),
      "request_hex": support.request_debug(request_frame),
      "response": support.frame_debug(classification.value_frame),
    }
    if classification.parse_warnings:
      data["parse_warnings"] = classification.parse_warnings
    if pom_address is not None:
      data["vehicle_address"] = pom_address
      data["pom_address"] = value.pom_address
      if context.get("vehicle_id"):
        data["vehicle_id"] = context["vehicle_id"]
    return data

  def _cv_read_ack_failure(
    self,
    controller: dict,
    classification,
    cv_number: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
  ):
    ack = classification.ack
    ack_debug = self._cv_ack_debug_extra(controller, ack, classification)
    if pom_address is not None and self.adapter_for(controller).is_main_track_cv_read_no_ack(ack):
      return self._cv_read_failure_response(
        "main_track_cv_read_no_ack",
        "主轨 CV 读取未收到车辆确认",
        f"车辆地址 {pom_address} 未返回 CV{cv_number} 读取值；请确认车号、车辆在主轨且轨道已上电，并确认解码器支持主轨读回或 RailCom。也可以改用编程轨读取。",
        502,
        cv_number,
        client_id,
        request_frame,
        frames=frames,
        pom_address=pom_address,
        extra=ack_debug,
      )
    return self._cv_read_failure_response(
      "cv_read_ack_without_value",
      "控制器返回编程 ACK，但没有返回 CV 值",
      ack_debug.get("ack", "ack"),
      502,
      cv_number,
      client_id,
      request_frame,
      frames=frames,
      pom_address=pom_address,
      extra=ack_debug,
    )

  def _cv_read_unmatched_failure(
    self,
    classification,
    cv_number: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
  ):
    if classification.parse_warnings:
      return self._cv_read_failure_response(
        "cv_programmer_response_parse_error",
        "控制器返回的 CV 回包无法解析",
        "Programmer response parse failed",
        502,
        cv_number,
        client_id,
        request_frame,
        frames=frames,
        pom_address=pom_address,
        extra={"parse_warnings": classification.parse_warnings},
      )
    return self._cv_read_failure_response(
      "cv_read_no_value",
      "控制器未返回匹配的 CV 值",
      "No 0x17 programmer value response matched the requested CV and client id",
      502,
      cv_number,
      client_id,
      request_frame,
      frames=frames,
      pom_address=pom_address,
    )

  def _classify_cv_responses(self, controller: dict, frames: list, client_id: int, cv_number: int, pom_address):
    return self.adapter_for(controller).classify_cv_responses(
      frames,
      client_id=client_id,
      cv_number=cv_number,
      pom_address=pom_address,
    )

  def _cv_ack_debug_extra(self, controller: dict, ack, classification) -> dict:
    debug = dict(self.adapter_for(controller).cv_ack_debug(ack))
    debug["parse_warnings"] = classification.parse_warnings
    return debug

  def _cv_read_failure_response(
    self,
    error_type: str,
    message: str,
    detail: str,
    status: int,
    cv_number: int,
    client_id: int,
    request_frame: bytes,
    frames=None,
    pom_address=None,
    extra=None,
  ):
    support = self.service_support
    return support.failure(
      error_type,
      message,
      detail,
      status=status,
      debug=support.cv_debug(
        cv=cv_number,
        client_id=client_id,
        request_frame=request_frame,
        responses=frames,
        pom_address=pom_address,
        extra=extra,
      ),
    )


  def execute_cv_write(
    self,
    controller: dict,
    cv_number: int,
    value: int,
    client_id: int,
    cv_context: dict | None = None,
  ):
    support = self.service_support
    context = cv_context or {}
    pom_address = context.get("pom_address")
    op = context.get("op")
    retry_count = support.cv_write_busy_retry_count(controller)
    retry_delay = support.cv_write_busy_retry_delay_seconds(controller)
    busy_retries = 0
    last_busy_debug = None
    frames = []
    request_frame = b""
    for attempt in range(retry_count + 1):
      request_frame, frames, error_response = self._send_cv_write_attempt(
        controller,
        cv_number,
        value,
        client_id,
        op,
        pom_address,
        attempt,
        context.get("state"),
      )
      if error_response is not None:
        return error_response

      action, next_busy_debug, result = self._cv_write_attempt_outcome(
        controller,
        context,
        cv_number,
        value,
        client_id,
        request_frame,
        frames,
        pom_address,
        attempt,
        retry_count,
        busy_retries,
        last_busy_debug,
      )
      if action == "retry":
        busy_retries += 1
        last_busy_debug = next_busy_debug
        if retry_delay > 0:
          time.sleep(retry_delay)
        continue
      if action == "return":
        return result
      break
    return self._cv_write_final_failure(
      cv_number,
      value,
      client_id,
      request_frame,
      frames,
      pom_address,
      busy_retries,
      last_busy_debug,
    )

  def _send_cv_write_attempt(
    self,
    controller: dict,
    cv_number: int,
    value: int,
    client_id: int,
    op,
    pom_address,
    attempt: int,
    state: dict | None,
  ):
    support = self.service_support
    request_frame = b""
    try:
      adapter = self.ensure_supported(controller, "cv_programming", "cv_write")
      result = adapter.write_cv_request(
        self.controller_session,
        controller,
        CvCommandRequest(
          cv_number=cv_number,
          client_id=client_id,
          value=value,
          op=int(op) if op is not None else None,
          pom_address=pom_address,
          timeout_seconds=None,
          max_packets=32,
        ),
        transport=self.udp_transport,
      )
      return bytes.fromhex(result.request_hex), result.frames, None
    except ControllerOperationNotSupported as exc:
      return request_frame, [], self.operation_not_supported_response(exc)
    except TimeoutError as exc:
      if state is not None:
        support.mark_controller_unreachable(state, "cv_write_timeout")
      return request_frame, [], support.failure(
        "cv_write_timeout",
        "写入 CV 超时",
        str(exc),
        status=504,
        debug=support.cv_debug(
          cv=cv_number,
          client_id=client_id,
          request_frame=request_frame,
          pom_address=pom_address,
          extra={"value": value, "attempt": attempt + 1},
        ),
      )
    except (OSError, ValueError) as exc:
      if state is not None:
        support.mark_controller_unreachable(state, "cv_write_transport_error")
      return request_frame, [], support.failure(
        "cv_write_transport_error",
        "写入 CV 通信失败",
        str(exc),
        status=502,
        debug=support.cv_debug(
          cv=cv_number,
          client_id=client_id,
          request_frame=request_frame,
          pom_address=pom_address,
          extra={"value": value, "attempt": attempt + 1},
        ),
      )

  def _classify_cv_write_attempt(self, controller: dict, frames: list, client_id: int, cv_number: int, pom_address):
    return self._classify_cv_responses(controller, frames, client_id, cv_number, pom_address)

  def _cv_write_attempt_outcome(
    self,
    controller: dict,
    context: dict,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    attempt: int,
    retry_count: int,
    busy_retries: int,
    last_busy_debug,
  ):
    classification = self._classify_cv_write_attempt(controller, frames, client_id, cv_number, pom_address)
    matched_ack = classification.ack
    if matched_ack is None:
      if classification.parse_warnings:
        return "return", None, self._cv_write_parse_error_response(
          classification,
          cv_number,
          value,
          client_id,
          request_frame,
          frames,
          pom_address,
          attempt,
        )
      return "break", None, None

    ack_category = self.adapter_for(controller).cv_ack_category(matched_ack)
    if self.adapter_for(controller).should_retry_cv_write_ack(matched_ack, attempt=attempt, retry_count=retry_count):
      return "retry", self._cv_write_busy_retry_debug(
        controller,
        classification,
        cv_number,
        value,
        client_id,
        request_frame,
        frames,
        pom_address,
        attempt,
      ), None
    if ack_category == "ack":
      return "return", None, self._cv_write_success_response(
        controller,
        context,
        classification,
        cv_number,
        value,
        client_id,
        request_frame,
        busy_retries,
        pom_address,
      )
    return "return", None, self._cv_write_rejected_response(
      controller,
      classification,
      cv_number,
      value,
      client_id,
      request_frame,
      frames,
      pom_address,
      attempt,
      busy_retries,
      last_busy_debug,
    )

  def _cv_write_busy_retry_debug(
    self,
    controller: dict,
    classification,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    attempt: int,
  ) -> dict:
    ack = classification.ack
    return self._cv_write_debug(
      cv_number,
      value,
      client_id,
      request_frame,
      frames,
      pom_address,
      classification,
      attempt,
      extra=self._cv_ack_debug_extra(controller, ack, classification),
    )

  def _cv_write_final_failure(
    self,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    busy_retries: int,
    last_busy_debug,
  ):
    if last_busy_debug is not None:
      return self._cv_write_busy_exhausted_response(
        cv_number,
        value,
        client_id,
        request_frame,
        frames,
        pom_address,
        busy_retries,
        last_busy_debug,
      )
    return self._cv_write_no_ack_response(
      cv_number,
      value,
      client_id,
      request_frame,
      frames,
      pom_address,
    )

  def _cv_write_debug(
    self,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    classification,
    attempt: int,
    *,
    extra: dict | None = None,
  ) -> dict:
    debug_extra = {
      "value": value,
      "attempt": attempt + 1,
      "parse_warnings": classification.parse_warnings,
    }
    if extra:
      debug_extra.update(extra)
    return self.service_support.cv_debug(
      cv=cv_number,
      client_id=client_id,
      request_frame=request_frame,
      responses=frames,
      pom_address=pom_address,
      extra=debug_extra,
    )

  def _cv_write_success_response(
    self,
    controller: dict,
    context: dict,
    classification,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    busy_retries: int,
    pom_address,
  ):
    support = self.service_support
    data = {
      "cv": cv_number,
      "value": value,
      "method": "dxdcnet_programmer_main_track_pom_write" if pom_address is not None else "dxdcnet_programmer_direct_write",
      "programming_target": context.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK),
      "request_hex": support.request_debug(request_frame),
      "response": support.frame_debug(classification.ack_frame),
    }
    if busy_retries:
      data["busy_retries"] = busy_retries
    if classification.parse_warnings:
      data["parse_warnings"] = classification.parse_warnings
    if pom_address is not None:
      data["vehicle_address"] = pom_address
      data["vehicle_id"] = context.get("vehicle_id")
    if context.get("readback_after_write"):
      readback_failure = self._verify_cv_write_readback(
        controller,
        context,
        cv_number,
        value,
        client_id,
        request_frame,
        pom_address,
        data,
      )
      if readback_failure is not None:
        return readback_failure
    return ServiceResult.success(data)

  def _verify_cv_write_readback(
    self,
    controller: dict,
    context: dict,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    pom_address,
    data: dict,
  ):
    delay_seconds = float(controller.get("main_track_pom_verify_delay_seconds", 0.2))
    if delay_seconds > 0:
      time.sleep(delay_seconds)
    read_result = self.execute_cv_read(
      controller,
      cv_number,
      client_id,
      timeout_seconds=float(controller.get("main_track_pom_readback_timeout_seconds", controller.get("cv_timeout_seconds", 10.0))),
      max_packets=32,
      cv_context=context,
    )
    read_frame = self._readback_request_frame(read_result)
    if not read_result.ok:
      return self._cv_write_readback_failed_response(
        cv_number,
        value,
        client_id,
        request_frame,
        read_frame,
        read_result,
        pom_address,
      )
    data["readback"] = read_result.data
    if not readback_value_matches(data["readback"], value):
      return self._cv_write_readback_mismatch_response(
        cv_number,
        value,
        client_id,
        request_frame,
        data["readback"],
        pom_address,
      )
    return None

  def _readback_request_frame(self, read_result) -> bytes:
    read_request_hex = (
      (read_result.data or {}).get("request_hex") if isinstance(read_result.data, dict) else ""
    ) or (
      (read_result.debug or {}).get("request_hex") if isinstance(read_result.debug, dict) else ""
    ) or ""
    return bytes.fromhex(read_request_hex) if read_request_hex else b""

  def _cv_write_readback_failed_response(
    self,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    read_frame: bytes,
    read_result,
    pom_address,
  ):
    return ServiceResult.failure(
      "cv_write_readback_failed",
      "主轨 CV 写入后读回校验失败",
      json.dumps(self._service_result_payload(read_result), ensure_ascii=False),
      status=502,
      debug=self.service_support.cv_debug(
        cv=cv_number,
        client_id=client_id,
        request_frame=request_frame,
        pom_address=pom_address,
        extra={
          "value": value,
          "vehicle_address": pom_address,
          "readback_request_hex": self.service_support.request_debug(read_frame),
        },
      ),
    )

  def _cv_write_readback_mismatch_response(
    self,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    readback: dict,
    pom_address,
  ):
    return ServiceResult.failure(
      "cv_write_readback_mismatch",
      "主轨 CV 写入后读回值不一致",
      f"写入 {value}，读回 {readback['value']}",
      status=502,
      debug=self.service_support.cv_debug(
        cv=cv_number,
        client_id=client_id,
        request_frame=request_frame,
        pom_address=pom_address,
        extra={
          "value": value,
          "readback": readback,
          "vehicle_address": pom_address,
        },
      ),
    )

  def _service_result_payload(self, result) -> dict:
    if result.ok:
      return {"ok": True, "data": result.data, "error": None}
    return {
      "ok": False,
      "data": None,
      "error": {
        "type": result.error_type,
        "message": result.message,
        "detail": result.detail,
      },
      "debug": result.debug,
    }

  def _cv_write_rejected_response(
    self,
    controller: dict,
    classification,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    attempt: int,
    busy_retries: int,
    last_busy_debug,
  ):
    ack = classification.ack
    ack_debug = self._cv_ack_debug_extra(controller, ack, classification)
    ack_debug.update({
      "busy_retries": busy_retries,
      "last_busy": last_busy_debug,
    })
    return self.service_support.failure(
      "cv_write_rejected",
      "控制器拒绝写入 CV",
      ack_debug.get("ack", "rejected"),
      status=502,
      debug=self._cv_write_debug(
        cv_number,
        value,
        client_id,
        request_frame,
        frames,
        pom_address,
        classification,
        attempt,
        extra=ack_debug,
      ),
    )

  def _cv_write_parse_error_response(
    self,
    classification,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    attempt: int,
  ):
    return self.service_support.failure(
      "cv_programmer_response_parse_error",
      "控制器返回的 CV 回包无法解析",
      "Programmer response parse failed",
      status=502,
      debug=self._cv_write_debug(
        cv_number,
        value,
        client_id,
        request_frame,
        frames,
        pom_address,
        classification,
        attempt,
      ),
    )

  def _cv_write_busy_exhausted_response(
    self,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
    busy_retries: int,
    last_busy_debug,
  ):
    debug_extra = {
      "value": value,
      "ack": "busy",
      "busy_retries": busy_retries,
      "last_busy": last_busy_debug,
    }
    if isinstance(last_busy_debug, dict) and "ack_mode" in last_busy_debug:
      debug_extra["ack_mode"] = last_busy_debug["ack_mode"]
    return self.service_support.failure(
      "cv_write_rejected",
      "控制器拒绝写入 CV",
      "busy",
      status=502,
      debug=self.service_support.cv_debug(
        cv=cv_number,
        client_id=client_id,
        request_frame=request_frame,
        responses=frames,
        pom_address=pom_address,
        extra=debug_extra,
      ),
    )

  def _cv_write_no_ack_response(
    self,
    cv_number: int,
    value: int,
    client_id: int,
    request_frame: bytes,
    frames: list,
    pom_address,
  ):
    return self.service_support.failure(
      "cv_write_no_ack",
      "控制器未返回匹配的写入 ACK",
      "No 0x15 programmer ACK response matched the requested client id",
      status=502,
      debug=self.service_support.cv_debug(
        cv=cv_number,
        client_id=client_id,
        request_frame=request_frame,
        responses=frames,
        pom_address=pom_address,
        extra={"value": value},
      ),
    )

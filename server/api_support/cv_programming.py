"""CV, chip-info, and address programming API orchestration."""

from server import models, response
from server.api_support import http_helpers
from server.cv_catalog import manufacturer_name
from train_dcc.address import build_vehicle_address_writes, decode_vehicle_address
from train_dcc.cv import validate_cv_byte, validate_cv_number


class CvOperationError(RuntimeError):
  """Typed wrapper for a failed CV service operation."""

  def __init__(self, result):
    super().__init__(result.detail or result.message or result.error_type)
    self.result = result


class CvProgrammingApiSupport:
  def __init__(self, context, controller_service, controller_api, vehicle_library):
    self.context = context
    self.controller_service = controller_service
    self.controller_api = controller_api
    self.vehicle_library = vehicle_library

  def read_cv(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    try:
      cv_number = validate_cv_number(int(request.get("cv")))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_cv", "CV 地址无效", str(exc)), 400
    operation, failure = self.prepare_cv_operation(request, state, "CV 读取", "cv_read")
    if failure:
      return failure
    return http_helpers.service_result(
      self.controller_service.execute_cv_read(
        operation["controller"],
        cv_number,
        operation["client_id"],
        cv_context=operation["cv_context"],
      )
    )

  def write_cv(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    try:
      cv_number = validate_cv_number(int(request.get("cv")))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_cv", "CV 地址无效", str(exc)), 400
    try:
      value = validate_cv_byte(request.get("value"))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_cv_value", "CV 值无效", str(exc)), 400
    unsupported = self.cv_capability_failure(state["controller"], "cv_write")
    if unsupported:
      return unsupported
    if request.get("confirmed") is not True:
      return response.failure(
        "operation_requires_confirmation",
        "写入 CV 需要明确确认",
        "请求必须包含 confirmed=true，且 UI 必须展示编程轨当前解码器、CV、新值和风险提示",
      ), 403
    operation, failure = self.prepare_cv_operation(request, state, "CV 写入")
    if failure:
      return failure
    return http_helpers.service_result(
      self.controller_service.execute_cv_write(
        operation["controller"],
        cv_number,
        value,
        operation["client_id"],
        cv_context=operation["cv_context"],
      )
    )

  def read_chip_info(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    operation, failure = self.prepare_cv_operation(request, state, "芯片信息读取", "chip_info_read")
    if failure:
      return failure
    cvs = {}
    warnings = []
    try:
      manufacturer = self.read_cv_direct(
        operation["controller"],
        8,
        operation["client_id"],
        cv_context=operation["cv_context"],
      )
      cvs["8"] = manufacturer
      software = self.read_cv_direct(
        operation["controller"],
        7,
        operation["client_id"],
        cv_context=operation["cv_context"],
      )
      cvs["7"] = software
      manufacturer_id = int(manufacturer["value"])
      if manufacturer_id == 30:
        cvs["127"] = self.read_cv_direct(
          operation["controller"],
          127,
          operation["client_id"],
          cv_context=operation["cv_context"],
        )
        cvs["128"] = self.read_cv_direct(
          operation["controller"],
          128,
          operation["client_id"],
          cv_context=operation["cv_context"],
        )
    except CvOperationError as exc:
      return self._cv_operation_failure(exc, cvs=cvs, warnings=warnings)
    return response.success(self._build_chip_info_payload(cvs, warnings)), 200

  def read_address(self, body: bytes, state):
    request = http_helpers.json_body(body)
    operation, failure = self.prepare_cv_operation(request, state, "地址读取", "address_read")
    if failure:
      return failure
    cvs = {}
    try:
      cvs["29"] = self.read_cv_direct(
        operation["controller"],
        29,
        operation["client_id"],
        cv_context=operation["cv_context"],
      )
      cv29 = int(cvs["29"]["value"])
      if cv29 & (1 << 5):
        cvs["17"] = self.read_cv_direct(
          operation["controller"],
          17,
          operation["client_id"],
          cv_context=operation["cv_context"],
        )
        cvs["18"] = self.read_cv_direct(
          operation["controller"],
          18,
          operation["client_id"],
          cv_context=operation["cv_context"],
        )
        decoded = decode_vehicle_address(cv29, cv17=int(cvs["17"]["value"]), cv18=int(cvs["18"]["value"]))
      else:
        cvs["1"] = self.read_cv_direct(
          operation["controller"],
          1,
          operation["client_id"],
          cv_context=operation["cv_context"],
        )
        decoded = decode_vehicle_address(cv29, cv1=int(cvs["1"]["value"]))
      address = self.vehicle_library.validate_vehicle_address(decoded["address"])
    except CvOperationError as exc:
      return self._cv_operation_failure(exc, cvs=cvs)
    except (TypeError, ValueError) as exc:
      return response.failure(
        "address_read_failed",
        "读取车辆地址失败",
        str(exc),
        {"cvs": cvs},
      ), 502
    synced = self.vehicle_library.sync_vehicle_address_if_present(state, request.get("vehicle_id"), address)
    return response.success({
      "address": address,
      "address_type": decoded["address_type"],
      "method": "dxdcnet_programmer_direct_read_address_cvs",
      "cvs": cvs,
      "vehicle_synced": synced,
    }), 200

  def write_address(self, body: bytes, state: dict):
    request = http_helpers.json_body(body)
    try:
      address = self.vehicle_library.validate_vehicle_address(request.get("address"))
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_address", "车辆地址超出范围", str(exc)), 400
    unsupported = self.cv_capability_failure(state["controller"], "address_write")
    if unsupported:
      return unsupported
    if request.get("confirmed") is not True:
      return response.failure(
        "operation_requires_confirmation",
        "写入地址需要明确确认",
        "请求必须包含 confirmed=true，且 UI 必须展示新地址和风险提示",
      ), 403
    operation, failure = self.prepare_cv_operation(request, state, "地址写入")
    if failure:
      return failure
    try:
      cv29 = int(self.read_cv_direct(
        operation["controller"],
        29,
        operation["client_id"],
        cv_context=operation["cv_context"],
      )["value"])
      plan = build_vehicle_address_writes(address, cv29)
      written_cvs = {}
      for write in plan["writes"]:
        result = self.write_cv_direct(
          operation["controller"],
          write["cv"],
          write["value"],
          operation["client_id"],
          cv_context=operation["cv_context"],
        )
        written_cvs[str(write["cv"])] = result
    except CvOperationError as exc:
      return self._cv_operation_failure(exc, extra_debug={"address": address})
    except (TypeError, ValueError) as exc:
      return response.failure(
        "address_write_failed",
        "写入车辆地址失败",
        str(exc),
        {"address": address},
      ), 502
    synced = self.vehicle_library.sync_vehicle_address_if_present(state, request.get("vehicle_id"), address)
    return response.success({
      "address": address,
      "address_type": plan["address_type"],
      "method": "dxdcnet_programmer_direct_write_address_cvs",
      "cvs": written_cvs,
      "vehicle_synced": synced,
    }), 200

  def prepare_cv_operation(self, request: dict, state: dict, operation_name: str, capability_operation: str | None = None):
    controller = state["controller"]
    if capability_operation:
      unsupported = self.cv_capability_failure(controller, capability_operation)
      if unsupported:
        return None, unsupported
    blocked_body, blocked_status, cv_context = self.resolve_context(request, state, operation_name)
    if blocked_body:
      return None, (blocked_body, blocked_status)
    client_id, error_response = self.controller_client_id_or_failure(controller)
    if error_response:
      return None, error_response
    return {
      "controller": controller,
      "client_id": client_id,
      "cv_context": cv_context,
    }, None

  def cv_capability_failure(self, controller: dict, capability_operation: str):
    return self.controller_api.controller_capability_failure(
      controller,
      "cv_programming",
      capability_operation,
    )

  def resolve_context(self, request: dict, state: dict, operation_name: str):
    controller = state["controller"]
    try:
      programming_target = models.validate_programming_target(
        request.get("programming_target", controller.get("programming_target", models.PROGRAMMING_TARGET_PROGRAMMING_TRACK))
      )
    except (TypeError, ValueError) as exc:
      return response.failure("invalid_programming_target", "CV 编程位置无效", str(exc)), 400, None

    if programming_target == models.PROGRAMMING_TARGET_MAIN_TRACK:
      return self._main_track_context(request, state, operation_name)
    return self._programming_track_context(request, state)

  def read_cv_direct(
    self,
    controller: dict,
    cv_number: int,
    client_id: int,
    timeout_seconds: float | None = None,
    max_packets: int = 32,
    cv_context: dict | None = None,
  ) -> dict:
    result = self.controller_service.execute_cv_read(
      controller,
      cv_number,
      client_id,
      timeout_seconds=timeout_seconds,
      max_packets=max_packets,
      cv_context=cv_context,
    )
    return self._service_result_data_or_raise(result)

  def write_cv_direct(
    self,
    controller: dict,
    cv_number: int,
    value: int,
    client_id: int,
    cv_context: dict | None = None,
  ) -> dict:
    result = self.controller_service.execute_cv_write(controller, cv_number, value, client_id, cv_context=cv_context)
    return self._service_result_data_or_raise(result)

  def validate_cv_read_all_numbers(self, cv_numbers) -> list[int]:
    if cv_numbers is None:
      return list(range(1, 1025))
    if not isinstance(cv_numbers, list):
      raise TypeError("cv_numbers must be a list")
    validated = []
    seen = set()
    for value in cv_numbers:
      cv_number = validate_cv_number(int(value))
      if cv_number in seen:
        continue
      seen.add(cv_number)
      validated.append(cv_number)
    if not validated:
      raise ValueError("cv_numbers cannot be empty")
    return validated

  def validate_cv_read_mode(self, read_mode) -> str:
    mode = str(read_mode or "known").lower()
    if mode not in {"known", "full"}:
      raise ValueError("read_mode must be known or full")
    return mode

  def programming_track_status_from_controller(self, controller: dict):
    return self.controller_api.controller_adapter(controller).programming_track_status(controller)

  def controller_client_id_or_failure(self, controller: dict):
    try:
      return self.controller_service.controller_client_id(controller), None
    except (TypeError, ValueError) as exc:
      return None, (response.failure("invalid_controller_settings", "控制器本地参数无效", str(exc)), 409)

  def _main_track_context(self, request: dict, state: dict, operation_name: str):
    controller = state["controller"]
    vehicle_id = str(request.get("vehicle_id") or "").strip()
    if not vehicle_id:
      return response.failure(
        "vehicle_required_for_main_track_programming",
        "主轨编程需要选择车辆",
        f"{operation_name}选择主轨时必须提供 vehicle_id，后端需要车辆地址作为 POM 目标",
        {"programming_target": models.PROGRAMMING_TARGET_MAIN_TRACK, "warnings": ["main_track_vehicle_required"]},
      ), 400, None
    vehicle = self._lookup_vehicle_for_programming(state, vehicle_id)
    if vehicle is None:
      return response.failure(
        "vehicle_not_found",
        "车辆不存在",
        f"主轨编程目标车辆不存在：{vehicle_id}",
        {"programming_target": models.PROGRAMMING_TARGET_MAIN_TRACK, "vehicle_id": vehicle_id},
      ), 404, None
    try:
      vehicle_address = self.vehicle_library.validate_vehicle_address(vehicle.get("address"))
    except (TypeError, ValueError) as exc:
      return response.failure(
        "invalid_vehicle_address",
        "主轨编程目标车辆地址无效",
        str(exc),
        {"programming_target": models.PROGRAMMING_TARGET_MAIN_TRACK, "vehicle_id": vehicle_id},
      ), 400, None
    blocked = self._main_track_cv_preflight(controller, operation_name)
    if blocked:
      return blocked[0], blocked[1], None
    adapter = self.controller_api.controller_adapter(controller)
    return None, None, {
      "state": state,
      "programming_target": models.PROGRAMMING_TARGET_MAIN_TRACK,
      "op": adapter.main_track_loco_pom_op(),
      "pom_address": vehicle_address,
      "vehicle_id": vehicle_id,
      "vehicle_address": vehicle_address,
      "readback_after_write": True,
    }

  def _programming_track_context(self, request: dict, state: dict):
    controller = state["controller"]
    blocked = self._cv_protocol_preflight(controller)
    if blocked:
      return blocked[0], blocked[1], None
    return None, None, {
      "state": state,
      "programming_target": models.PROGRAMMING_TARGET_PROGRAMMING_TRACK,
      "op": None,
      "pom_address": None,
      "vehicle_id": request.get("vehicle_id"),
      "vehicle_address": None,
      "readback_after_write": False,
    }

  def _lookup_vehicle_for_programming(self, state: dict, vehicle_id: str):
    if self.context.vehicle_store:
      vehicle = self.context.vehicle_store.get_vehicle(vehicle_id)
      if vehicle is not None:
        return vehicle
    return self.vehicle_library.find_by_id(state.get("vehicles", []), vehicle_id)

  def _main_track_cv_preflight(self, controller: dict, operation_name: str):
    blocked = self.controller_service.digital_operation_mode_failure(controller, operation_name)
    if blocked:
      return http_helpers.service_result(blocked)
    stale_booster = self.controller_api.fresh_booster_status_failure(controller)
    if stale_booster:
      return stale_booster
    readiness_warnings = self.controller_service.controller_readiness_warnings(controller)
    if readiness_warnings:
      adapter = self.controller_api.controller_adapter(controller)
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        f"不能发送真实主轨 POM 命令：{operation_name}",
        {"warnings": readiness_warnings},
      ), 409
    adapter = self.controller_api.controller_adapter(controller)
    if not adapter.is_booster_status_confirmed(controller):
      return response.failure(
        "protocol_not_ready",
        "主轨状态尚未确认",
        "需要先读取控制器或执行通电操作，得到确认后的轨道状态后再执行主轨 POM",
        {"warnings": ["booster_status_unconfirmed"]},
      ), 409
    booster_status = controller.get("booster_status") or {}
    if not booster_status.get("power_on", False):
      return response.failure(
        "main_track_power_required",
        "主轨编程需要先给轨道通电",
        "官方 App 主轨 POM 路径要求主轨已上电；请先点击“通电”并确认状态灯变绿",
        {"warnings": ["main_track_power_required"]},
      ), 409
    if not booster_status.get("dcc_mode", False):
      return response.failure(
        "unsafe_track_mode",
        "当前主轨不是 DCC 数码输出",
        f"{operation_name} 只允许在 N、HO 或 G 的 DCC 数码模式下执行",
        {"warnings": ["main_track_not_dcc"]},
      ), 409

  def _cv_protocol_preflight(self, controller: dict):
    try:
      track_mode = models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      return response.failure(
        "unsafe_track_mode",
        "当前编程轨连接的是 DCC 解码芯片，只允许 N、HO 或 G 操作模式",
        "请切换到 N、HO 或 G 的 DCC 模式，并确认电压、电流保护和编程轨电流读数",
      ), 409
    readiness_warnings = self.controller_service.controller_readiness_warnings(controller)
    if readiness_warnings:
      adapter = self.controller_api.controller_adapter(controller)
      return response.failure(
        "protocol_not_ready",
        adapter.status_not_ready_message(),
        "只允许连接探测和模拟测试，不发送真实 CV 读取命令",
        {"warnings": readiness_warnings},
      ), 409
    programming_status = self.programming_track_status_from_controller(controller)
    if programming_status is None:
      return response.failure(
        "protocol_not_ready",
        "编程轨安全状态尚未确认",
        "需要先读取并解析控制器状态，不使用前端状态直接发送 CV 命令",
        {"warnings": ["programming_track_status_unconfirmed"]},
      ), 409
    if programming_status.track_mode != track_mode:
      return response.failure(
        "protocol_not_ready",
        "操作模式变化后需要重新读取控制器状态",
        "当前缓存的编程轨安全状态与顶部操作模式不一致",
        {"warnings": ["programming_track_status_stale"]},
      ), 409
    try:
      self.controller_api.controller_adapter(controller).validate_programming_track_safety(programming_status)
    except ValueError as exc:
      return response.failure(
        "unsafe_programming_track",
        "编程轨安全校验失败",
        str(exc),
        {"warnings": ["programming_track_safety_failed"]},
      ), 409

  def _service_result_data_or_raise(self, result) -> dict:
    if result.ok:
      return result.data
    raise CvOperationError(result)

  def _build_chip_info_payload(self, cvs: dict, warnings: list) -> dict:
    manufacturer_id = int(cvs["8"]["value"])
    software_version = int(cvs["7"]["value"])
    chip_info = {
      "manufacturer_id": manufacturer_id,
      "manufacturer_name": manufacturer_name(manufacturer_id),
      "software_version": software_version,
      "model": None,
      "hardware_version": None,
      "cvs": cvs,
      "warnings": list(warnings),
    }
    if manufacturer_id == 30 and "127" in cvs and "128" in cvs:
      cv127 = int(cvs["127"]["value"])
      chip_info["model"] = ((cv127 & 0x1F) * 256) + int(cvs["128"]["value"])
      chip_info["hardware_version"] = (cv127 & 0xE0) >> 5
    return chip_info

  def _cv_operation_failure(
    self,
    exc: CvOperationError,
    *,
    cvs: dict | None = None,
    warnings: list | None = None,
    extra_debug: dict | None = None,
  ):
    result = exc.result
    if isinstance(result.debug, dict):
      debug = dict(result.debug)
    elif result.debug is None:
      debug = {}
    else:
      debug = {"debug": result.debug}
    if cvs is not None:
      debug["cvs"] = cvs
    if warnings is not None:
      debug["warnings"] = warnings
    if extra_debug:
      debug.update(extra_debug)
    return response.failure(
      result.error_type or "cv_operation_failed",
      result.message or "CV 操作失败",
      result.detail or "",
      debug,
    ), result.status

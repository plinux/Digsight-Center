"""Controller-domain operation facade used by ApiRouter."""

from server import models
from server.controllers.base import (
  ControllerOperationNotSupported,
  ControllerProtocolNotSupported,
  controller_protocol,
  controller_supported_protocols,
)
from server.controller_services.cv_programming import CvProgrammingService
from server.controller_services.loco_control import LocoCommandService
from server.controller_services.results import ServiceResult
from server.controller_services.track_power import TrackPowerService


class ControllerService(TrackPowerService, CvProgrammingService, LocoCommandService):
  def __init__(self, *, service_support, controller_registry, controller_session_registry, controller_transport):
    self.service_support = service_support
    self.controller_registry = controller_registry
    self.controller_session_registry = controller_session_registry
    self.controller_transport = controller_transport

  def adapter_for(self, controller: dict):
    return self.controller_registry.get(controller.get("kind") or self.controller_registry.default_kind)

  def controller_session_for(self, controller: dict):
    adapter = self.adapter_for(controller)
    return self.controller_session_for_adapter(adapter, controller)

  def controller_session_for_adapter(self, adapter, controller: dict):
    protocol = controller_protocol(adapter, controller)
    supported_protocols = controller_supported_protocols(adapter)
    supported_keys = {value.casefold() for value in supported_protocols}
    if protocol.casefold() not in supported_keys:
      raise ControllerProtocolNotSupported(adapter.kind, protocol, supported_protocols)
    try:
      endpoint_identity = None
      endpoint_identity_factory = getattr(adapter, "endpoint_identity", None)
      if callable(endpoint_identity_factory):
        endpoint_identity = endpoint_identity_factory(controller)
      session_identity = None
      session_identity_factory = getattr(adapter, "session_identity", None)
      if callable(session_identity_factory):
        session_identity = session_identity_factory(controller)
      return self.controller_session_registry.session_for_controller(
        adapter.kind,
        protocol,
        controller,
        endpoint_identity=endpoint_identity,
        session_identity=session_identity,
      )
    except ValueError as exc:
      raise ControllerProtocolNotSupported(
        adapter.kind,
        protocol,
        supported_protocols,
        reason=str(exc),
      ) from exc

  def ensure_supported(self, controller: dict, capability_name: str, operation_name: str):
    adapter = self.adapter_for(controller)
    if not bool(getattr(adapter.capabilities, capability_name)):
      raise ControllerOperationNotSupported(operation_name, adapter.kind)
    return adapter

  def controller_client_id(self, controller: dict) -> int:
    return self.adapter_for(controller).controller_client_id(controller)

  def operation_not_supported_response(self, exc: ControllerOperationNotSupported):
    return ServiceResult.failure(
      "controller_operation_not_supported",
      "当前控制器不支持该操作",
      str(exc),
      status=409,
      debug={
        "controller_kind": exc.controller_kind,
        "operation": exc.operation,
      },
    )

  def protocol_not_supported_response(self, exc: ControllerProtocolNotSupported):
    return ServiceResult.failure(
      "controller_protocol_not_supported",
      "当前控制器配置了不支持的协议",
      str(exc),
      status=409,
      debug={
        "controller_kind": exc.controller_kind,
        "protocol": exc.protocol,
        "supported_protocols": list(exc.supported_protocols),
      },
    )

  def controller_readiness_warnings(self, controller: dict):
    return self.adapter_for(controller).runtime_readiness_warnings(controller)

  def loco_control_readiness_warnings(self, controller: dict):
    return self.adapter_for(controller).loco_control_readiness_warnings(controller)

  def digital_operation_mode_failure(self, controller: dict, operation_name: str):
    try:
      models.validate_track_mode(controller.get("track_mode", models.TRACK_MODE_N))
    except (TypeError, ValueError):
      return ServiceResult.failure(
        "unsafe_track_mode",
        "当前操作模式不支持 DCC 数码操作",
        f"{operation_name} 只允许在 N、HO 或 G 的 DCC 数码模式下执行",
        status=409,
        debug={"warnings": ["operation_mode_not_digital"]},
      )
    return None

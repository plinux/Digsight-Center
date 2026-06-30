"""Controller protocol session factory registry."""

from dataclasses import dataclass
import json

from server.controllers.base import controller_supported_protocols


@dataclass(frozen=True)
class ControllerSessionContext:
  protocol: str
  controller_kind: str
  endpoint_identity: tuple
  session_identity: tuple

  @classmethod
  def from_controller(
    cls,
    controller_kind: str,
    protocol: str,
    controller: dict,
    *,
    endpoint_identity=None,
    session_identity=None,
  ):
    return cls(
      protocol=str(protocol or "").strip(),
      controller_kind=str(controller_kind or "").strip(),
      endpoint_identity=tuple(endpoint_identity if endpoint_identity is not None else default_endpoint_identity(controller)),
      session_identity=tuple(session_identity if session_identity is not None else default_session_identity(controller)),
    )

  def cache_key(self):
    return (
      self.protocol.casefold(),
      self.controller_kind,
      self.endpoint_identity,
      self.session_identity,
    )


class ControllerSessionRegistry:
  def __init__(self, *, controller_transport=None):
    self.controller_transport = controller_transport
    self._factories = {}
    self._sessions = {}

  def register(self, controller_kind: str, protocol: str, factory):
    factory_key = self._factory_key(controller_kind, protocol)
    self._factories[factory_key] = factory

  def session_for_controller(self, controller_kind: str, protocol: str, controller: dict, *, endpoint_identity=None, session_identity=None):
    factory_key = self._factory_key(controller_kind, protocol)
    if factory_key not in self._factories:
      raise ValueError(f"Unsupported controller session: {controller_kind}/{protocol}")
    context = ControllerSessionContext.from_controller(
      controller_kind,
      protocol,
      controller,
      endpoint_identity=endpoint_identity,
      session_identity=session_identity,
    )
    session_key = context.cache_key()
    if session_key not in self._sessions:
      self._sessions[session_key] = self._factories[factory_key](self.controller_transport, context)
    return self._sessions[session_key]

  @classmethod
  def _factory_key(cls, controller_kind: str, protocol: str) -> tuple[str, str]:
    kind_key = cls._controller_kind_key(controller_kind)
    protocol_key = cls._protocol_key(protocol)
    return (kind_key, protocol_key)

  @staticmethod
  def _controller_kind_key(controller_kind: str) -> str:
    value = str(controller_kind or "").strip()
    if not value:
      raise ValueError("Controller kind is not configured")
    return value

  @staticmethod
  def _protocol_key(protocol: str) -> str:
    value = str(protocol or "").strip()
    if not value:
      raise ValueError("Controller protocol is not configured")
    return value.casefold()


def stable_json_identity(value) -> str:
  try:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  except TypeError:
    return repr(value)


def default_endpoint_identity(controller: dict) -> tuple:
  transport = controller.get("transport", {})
  return (
    ("ip", str(controller.get("ip") or "").strip()),
    ("transport", stable_json_identity(transport if isinstance(transport, dict) else {})),
  )


def default_session_identity(controller: dict) -> tuple:
  return (
    ("settings", stable_json_identity(controller.get("settings", {}))),
  )


def _register_adapter_sessions(registry: ControllerSessionRegistry, adapter) -> None:
  create_session_manager = getattr(adapter, "create_session_manager", None)
  if not callable(create_session_manager):
    return
  for protocol in controller_supported_protocols(adapter):
    registry.register(
      adapter.kind,
      protocol,
      lambda transport, context, active_adapter=adapter: active_adapter.create_session_manager(
        transport=transport,
        context=context,
      ),
    )


def default_controller_session_registry(controller_registry=None, controller_transport=None) -> ControllerSessionRegistry:
  if controller_registry is None:
    from server.controllers.registry import default_controller_registry
    controller_registry = default_controller_registry()
  registry = ControllerSessionRegistry(controller_transport=controller_transport)
  for adapter in controller_registry.adapters():
    _register_adapter_sessions(registry, adapter)
  return registry

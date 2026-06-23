"""Controller adapter registry."""

from server.controllers.digsight import DigsightDXDCNetControllerAdapter


class ControllerRegistry:
  def __init__(self):
    self._adapters = {}

  def register(self, adapter):
    self._adapters[adapter.kind] = adapter

  def get(self, kind: str):
    adapter = self._adapters.get(kind)
    if adapter is None:
      raise ValueError(f"Unsupported controller kind: {kind}")
    return adapter

  def descriptors(self) -> list[dict]:
    return [
      {
        "kind": adapter.kind,
        "label": adapter.label,
        "capabilities": adapter.capabilities.__dict__,
      }
      for adapter in self._adapters.values()
    ]


def default_controller_registry():
  registry = ControllerRegistry()
  registry.register(DigsightDXDCNetControllerAdapter())
  return registry

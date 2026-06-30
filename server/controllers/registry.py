"""Controller adapter registry."""

from server import models
from server.controllers.digsight import DigsightDXDCNetControllerAdapter


class ControllerRegistry:
  def __init__(self, default_kind: str | None = None):
    self._adapters = {}
    self._default_kind = default_kind

  def register(self, adapter, *, default: bool = False):
    self._adapters[adapter.kind] = adapter
    if default:
      self._default_kind = adapter.kind

  def get(self, kind: str):
    adapter = self._adapters.get(kind)
    if adapter is None:
      raise ValueError(f"Unsupported controller kind: {kind}")
    return adapter

  @property
  def default_kind(self) -> str:
    if not self._adapters:
      raise ValueError("No controllers registered")
    if self._default_kind is None:
      raise ValueError("Default controller is not configured")
    if self._default_kind not in self._adapters:
      raise ValueError(f"Default controller is not registered: {self._default_kind}")
    return self._default_kind

  def descriptors(self) -> list[dict]:
    return [self._descriptor(adapter) for adapter in sorted(self._adapters.values(), key=self._descriptor_sort_key)]

  def config_file_name(self, kind: str) -> str:
    adapter = self.get(kind)
    return adapter.config_file_name

  def config_file_names(self) -> list[str]:
    return [self.config_file_name(adapter.kind) for adapter in sorted(self._adapters.values(), key=self._descriptor_sort_key)]

  def _descriptor_sort_key(self, adapter):
    default_rank = 0 if adapter.kind == self._default_kind else 1
    return (default_rank, adapter.label, adapter.kind)

  def _descriptor(self, adapter) -> dict:
    return {
      "kind": adapter.kind,
      "label": adapter.label,
      "default_ip": getattr(adapter, "default_ip", ""),
      "config_file_name": self.config_file_name(adapter.kind),
      "capabilities": adapter.capabilities.to_dict(),
      "transport_defaults": adapter.transport_defaults.to_dict(),
    }


def default_controller_registry():
  registry = ControllerRegistry()
  registry.register(DigsightDXDCNetControllerAdapter(), default=True)
  return registry

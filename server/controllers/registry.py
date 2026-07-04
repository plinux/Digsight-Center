"""Controller adapter registry."""

from server.controllers.base import controller_display_name, controller_protocol
from server.controllers.digsight import DigsightDXDCNetControllerAdapter
from server.controllers.ecos import ECoSControllerAdapter
from server.descriptor_paths import validate_descriptor_file_name
from server.public_paths import CONTROLLER_CONFIG_PUBLIC_PREFIX, CONTROLLER_CONFIG_RELATIVE_PREFIX


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

  def kinds(self) -> list[str]:
    return [adapter.kind for adapter in self._sorted_adapters()]

  def adapters(self) -> list:
    return self._sorted_adapters()

  def descriptors(self, controller_configs: dict | None = None) -> list[dict]:
    configs = controller_configs or {}
    return [
      self._descriptor(adapter, configs.get(adapter.kind))
      for adapter in self._sorted_adapters()
    ]

  def config_file_name(self, kind: str) -> str:
    adapter = self.get(kind)
    return validate_descriptor_file_name(adapter.config_file_name, "controller config_file_name")

  def config_file_names(self) -> list[str]:
    return [self.config_file_name(adapter.kind) for adapter in self._sorted_adapters()]

  def _sorted_adapters(self) -> list:
    return sorted(self._adapters.values(), key=self._descriptor_sort_key)

  def _descriptor_sort_key(self, adapter):
    default_rank = 0 if adapter.kind == self._default_kind else 1
    return (default_rank, adapter.label, adapter.kind)

  def _descriptor(self, adapter, config: dict | None = None) -> dict:
    display_name = controller_display_name(adapter, config)
    protocol = controller_protocol(adapter, config)
    config_file_name = validate_descriptor_file_name(adapter.config_file_name, "controller config_file_name")
    transport_descriptor = adapter.transport_descriptor.to_dict()
    configured_ip = str((config or {}).get("ip") or getattr(adapter, "default_ip", ""))
    return {
      "kind": adapter.kind,
      "label": display_name,
      "display_name": display_name,
      "protocol": protocol,
      "default_ip": getattr(adapter, "default_ip", ""),
      "configured_ip": configured_ip,
      "config_file_name": config_file_name,
      "config_file": f"{CONTROLLER_CONFIG_RELATIVE_PREFIX}{config_file_name}",
      "config_public_path": f"{CONTROLLER_CONFIG_PUBLIC_PREFIX}{config_file_name}",
      "capabilities": adapter.capabilities.to_dict(),
      "transport_descriptor": transport_descriptor,
      "endpoint_readiness": transport_descriptor["endpoint_readiness"],
    }


def default_controller_registry():
  registry = ControllerRegistry()
  registry.register(DigsightDXDCNetControllerAdapter(), default=True)
  registry.register(ECoSControllerAdapter())
  return registry

"""Configuration import adapter registry."""

from server.importers.base import ConfigImporter
from server.importers.z21 import Z21ConfigImporter


class ImportRegistry:
  def __init__(self, default_format: str | None = None):
    self._importers = {}
    self._default_format = default_format

  def register(self, importer: ConfigImporter, *, default: bool = False):
    self._importers[importer.descriptor.format] = importer
    if default:
      self._default_format = importer.descriptor.format

  def get(self, format_name: str) -> ConfigImporter:
    importer = self._importers.get(format_name)
    if importer is None:
      raise ValueError(f"Unsupported import format: {format_name}")
    return importer

  @property
  def default_format(self) -> str:
    if not self._importers:
      raise ValueError("No import formats registered")
    if self._default_format is None:
      raise ValueError("Default import format is not configured")
    if self._default_format not in self._importers:
      raise ValueError(f"Default import format is not registered: {self._default_format}")
    return self._default_format

  def descriptors(self) -> list[dict]:
    return [
      {
        "format": importer.descriptor.format,
        "label": importer.descriptor.label,
        "extensions": list(importer.descriptor.extensions),
        "public_files": list(importer.descriptor.public_files),
      }
      for importer in sorted(self._importers.values(), key=self._descriptor_sort_key)
    ]

  def _descriptor_sort_key(self, importer: ConfigImporter):
    default_rank = 0 if importer.descriptor.format == self._default_format else 1
    return (default_rank, importer.descriptor.label, importer.descriptor.format)


def default_import_registry(image_dir):
  registry = ImportRegistry()
  registry.register(Z21ConfigImporter(image_dir), default=True)
  return registry

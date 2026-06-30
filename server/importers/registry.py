"""Configuration import adapter registry."""

from server.importers.base import ConfigImporter
from server.importers.z21 import Z21ConfigImporter


class ImportRegistry:
  def __init__(self):
    self._importers = {}

  def register(self, importer: ConfigImporter):
    self._importers[importer.descriptor.format] = importer

  def get(self, format_name: str) -> ConfigImporter:
    importer = self._importers.get(format_name)
    if importer is None:
      raise ValueError(f"Unsupported import format: {format_name}")
    return importer

  def descriptors(self) -> list[dict]:
    return [
      {
        "format": importer.descriptor.format,
        "label": importer.descriptor.label,
        "extensions": list(importer.descriptor.extensions),
        "public_files": list(importer.descriptor.public_files),
      }
      for importer in self._importers.values()
    ]


def default_import_registry(image_dir):
  registry = ImportRegistry()
  registry.register(Z21ConfigImporter(image_dir))
  return registry

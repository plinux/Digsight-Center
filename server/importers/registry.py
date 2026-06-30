"""Configuration import adapter registry."""

from server.descriptor_paths import validate_public_descriptor_path
from server.importers.base import ConfigImporter
from server.importers.z21 import Z21ConfigImporter
from server.public_paths import FUNCTION_ICON_MAPPING_PUBLIC_PREFIX, IMPORTER_CONFIG_PUBLIC_PREFIX


IMPORTER_PUBLIC_PATH_PREFIXES = (
  FUNCTION_ICON_MAPPING_PUBLIC_PREFIX,
  IMPORTER_CONFIG_PUBLIC_PREFIX,
)
FUNCTION_ICON_MAPPING_PUBLIC_PATH_PREFIXES = (
  FUNCTION_ICON_MAPPING_PUBLIC_PREFIX,
)


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
      self._descriptor(importer)
      for importer in self._sorted_importers()
    ]

  def _descriptor(self, importer: ConfigImporter) -> dict:
    return {
      "format": importer.descriptor.format,
      "label": importer.descriptor.label,
      "extensions": list(importer.descriptor.extensions),
      "public_files": self._public_paths(importer.descriptor.public_files, "import public_files"),
      "function_icon_mapping_files": self._public_paths(
        importer.descriptor.function_icon_mapping_files,
        "import function_icon_mapping_files",
        FUNCTION_ICON_MAPPING_PUBLIC_PATH_PREFIXES,
      ),
    }

  def _public_paths(
    self,
    paths: list[str],
    field_name: str,
    allowed_prefixes: tuple[str, ...] = IMPORTER_PUBLIC_PATH_PREFIXES,
  ) -> list[str]:
    return [
      validate_public_descriptor_path(path, field_name, allowed_prefixes)
      for path in paths
    ]

  def _descriptor_sort_key(self, importer: ConfigImporter):
    default_rank = 0 if importer.descriptor.format == self._default_format else 1
    return (default_rank, importer.descriptor.label, importer.descriptor.format)

  def _sorted_importers(self) -> list[ConfigImporter]:
    return sorted(self._importers.values(), key=self._descriptor_sort_key)


def default_import_registry(image_dir):
  registry = ImportRegistry()
  registry.register(Z21ConfigImporter(image_dir), default=True)
  return registry

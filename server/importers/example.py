"""Code-only example configuration importer contract.

This importer is intentionally not registered by default. It documents the
shape required by future layout/configuration import formats without exposing a
placeholder option in the UI.
"""

from server.importers.base import (
  CATEGORY_MERGE_SOURCE_LOCAL,
  ConfigImportRequest,
  ConfigImportResult,
  ImportFormatDescriptor,
)


class ExampleConfigImporter:
  """Non-functional sample importer for future external layout formats."""

  descriptor = ImportFormatDescriptor(
    format="example_layout_config",
    label="样例配置格式",
    extensions=[".example"],
  )
  category_merge_strategy = CATEGORY_MERGE_SOURCE_LOCAL

  def import_bytes(self, request: ConfigImportRequest) -> ConfigImportResult:
    raise NotImplementedError(
      "example_layout_config only documents the importer contract; "
      "future importers must parse bytes into normalized vehicles, functions, "
      "categories, consists, summary, warnings, errors, and source metadata; "
      "imported images must be represented by normalized vehicle image_path values; "
      "category_merge_strategy defines how imported categories are merged; "
      "replace_scope limits replacement to specific source keys or track modes"
    )

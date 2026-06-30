"""Z21 .z21 configuration import adapter."""

from pathlib import Path
import sqlite3
import tempfile
import zipfile

from server.importers.base import (
  CATEGORY_MERGE_SHARED_BY_NORMALIZED_NAME,
  ConfigImportRequest,
  ConfigImportResult,
  ImportFormatDescriptor,
  ImportSource,
)
from server.importers.z21_parser import Z21Importer


class Z21ConfigImporter:
  descriptor = ImportFormatDescriptor(
    format="z21_layout_config",
    label="Z21 .z21",
    extensions=[".z21"],
    public_files=["/config/function-icon-mappings/z21.json"],
  )

  def __init__(self, image_dir: Path | str):
    self.image_dir = Path(image_dir)

  def import_bytes(self, request: ConfigImportRequest) -> ConfigImportResult:
    if request.format != self.descriptor.format:
      raise ValueError(f"Z21 importer cannot handle format {request.format!r}")
    safe_file_name = Path(request.file_name or "import.z21").name or "import.z21"
    with tempfile.TemporaryDirectory() as temp_dir:
      temp_path = Path(temp_dir) / safe_file_name
      temp_path.write_bytes(request.content)
      try:
        z21_result = Z21Importer(self.image_dir).import_file(temp_path)
      except (ValueError, zipfile.BadZipFile, sqlite3.Error) as exc:
        raise ValueError(f"Z21 configuration import failed: {exc}") from exc
    summary = dict(z21_result.summary)
    summary["file_name"] = request.file_name
    warnings = list(summary.get("warnings") or [])
    track_mode = str(summary.get("track_mode") or "").strip().lower()
    return ConfigImportResult(
      format=self.descriptor.format,
      source=ImportSource(
        format=self.descriptor.format,
        key="z21",
        label=self.descriptor.label,
        category_merge_strategy=CATEGORY_MERGE_SHARED_BY_NORMALIZED_NAME,
      ),
      vehicles=z21_result.vehicles,
      functions=z21_result.functions,
      categories=z21_result.categories,
      consists=z21_result.consists,
      summary=summary,
      warnings=warnings,
      errors=[],
      source_mappings={},
      replace_scope={"track_modes": [track_mode] if track_mode else []},
    )

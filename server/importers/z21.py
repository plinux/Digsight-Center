"""Z21 .z21 configuration import adapter."""

from pathlib import Path
import tempfile

from server.importers.base import ConfigImportRequest, ConfigImportResult, ImportFormatDescriptor
from server.importers.z21_parser import Z21Importer


class Z21ConfigImporter:
  descriptor = ImportFormatDescriptor(format="z21_layout_config", label="Z21 .z21", extensions=[".z21"])

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
      except Exception as exc:
        raise ValueError(f"Z21 configuration import failed: {exc}") from exc
    summary = dict(z21_result.summary)
    summary["file_name"] = request.file_name
    warnings = list(summary.get("warnings") or [])
    return ConfigImportResult(
      format=self.descriptor.format,
      vehicles=z21_result.vehicles,
      functions=z21_result.functions,
      categories=z21_result.categories,
      consists=z21_result.consists,
      images=[],
      summary=summary,
      warnings=warnings,
      errors=[],
    )

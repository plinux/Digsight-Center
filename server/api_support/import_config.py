"""Configuration import API support."""

from pathlib import Path

from server import response
from server.importers.base import ConfigImportRequest


class ConfigImportApiSupport:
  def __init__(self, context):
    self.context = context

  def import_config_bytes(
    self,
    format_name: str,
    file_name: str,
    body: bytes,
    state: dict,
    include_format_list: bool = True,
    options=None,
  ):
    safe_file_name = Path(file_name or "import.config").name or "import.config"
    try:
      importer = self.context.import_registry.get(format_name)
      import_result = importer.import_bytes(ConfigImportRequest(
        format=format_name,
        file_name=safe_file_name,
        content=body,
        options=dict(options or {}),
      ))
    except ValueError as exc:
      return response.failure("import_failed", "导入配置失败", str(exc)), 400
    self.merge_import_result(state, import_result)
    if include_format_list:
      return response.success({"summary": import_result.summary, "formats": self.context.import_registry.descriptors()}), 200
    return response.success(import_result.summary), 200

  def merge_import_result(self, state: dict, import_result) -> None:
    self.context.vehicle_store.replace_imported_config_data(import_result)
    self.context.state_with_vehicle_store_data(state)
    self.context.save(state)

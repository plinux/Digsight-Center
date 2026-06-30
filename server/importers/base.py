"""Common configuration import adapter contracts."""

from dataclasses import dataclass, field
from typing import Protocol

CATEGORY_MERGE_SOURCE_LOCAL = "source_local"
CATEGORY_MERGE_SHARED_BY_NORMALIZED_NAME = "shared_by_normalized_name"


@dataclass(frozen=True)
class ImportFormatDescriptor:
  format: str
  label: str
  extensions: list[str] = field(default_factory=list)
  public_files: list[str] = field(default_factory=list)
  function_icon_mapping_files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ConfigImportRequest:
  format: str
  file_name: str
  content: bytes
  options: dict = field(default_factory=dict)


@dataclass(frozen=True)
class ImportSource:
  format: str
  key: str
  label: str
  category_merge_strategy: str = CATEGORY_MERGE_SOURCE_LOCAL


@dataclass
class ConfigImportResult:
  format: str
  source: ImportSource
  vehicles: list
  functions: list
  categories: list
  consists: list
  summary: dict
  warnings: list
  errors: list
  source_mappings: dict = field(default_factory=dict)
  replace_scope: dict = field(default_factory=dict)


class ConfigImporter(Protocol):
  descriptor: ImportFormatDescriptor

  def import_bytes(self, request: ConfigImportRequest) -> ConfigImportResult:
    """Import external configuration bytes into normalized project records."""

"""Common configuration import adapter contracts."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class ImportFormatDescriptor:
  format: str
  label: str
  extensions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ConfigImportRequest:
  format: str
  file_name: str
  content: bytes
  options: dict = field(default_factory=dict)


@dataclass
class ConfigImportResult:
  format: str
  vehicles: list
  functions: list
  categories: list
  consists: list
  images: list
  summary: dict
  warnings: list
  errors: list


class ConfigImporter(Protocol):
  descriptor: ImportFormatDescriptor

  def import_bytes(self, request: ConfigImportRequest) -> ConfigImportResult:
    """Import external configuration bytes into normalized project records."""

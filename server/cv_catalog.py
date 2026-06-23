"""Config-driven CV description catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_DIR = REPO_ROOT / "config" / "cv"
_DEFAULT_CACHE = {"signature": None, "catalog": None}


@dataclass(frozen=True)
class CvCatalog:
  source: str
  manufacturer_ids: dict[str, str]
  unassigned_notes: dict[str, str]
  profile_map: dict[str, str]
  standard_definitions: dict[int, str]
  standard_explicit_numbers: set[int]
  vendor_profiles: dict[str, dict[str, Any]]
  vendor_explicit_numbers: dict[str, set[int]]

  def manufacturer_name(self, manufacturer_id: int | None) -> str:
    if manufacturer_id is None:
      return "未知厂家"
    key = str(int(manufacturer_id))
    profile_name = self.profile_map.get(key)
    if profile_name:
      profile = self.vendor_profiles.get(profile_name, {})
      configured_name = profile.get("manufacturer_name")
      if configured_name:
        return str(configured_name)
    if key in self.manufacturer_ids:
      return self.manufacturer_ids[key]
    if key in self.unassigned_notes:
      return self.unassigned_notes[key]
    return f"厂家 ID {manufacturer_id}"

  def cv_meaning(self, cv_number: int, manufacturer_id: int | None = None) -> str:
    cv = _validate_cv_number(cv_number)
    profile_name = self.profile_map.get(str(int(manufacturer_id))) if manufacturer_id is not None else None
    if profile_name:
      profile = self.vendor_profiles.get(profile_name, {})
      vendor_meaning = profile.get("cv_definitions", {}).get(str(cv))
      if vendor_meaning:
        return str(vendor_meaning)
    return self.standard_definitions.get(cv, "未知/厂家自定义")

  def known_cv_numbers(self, manufacturer_id: int | None = None) -> list[int]:
    numbers = set(self.standard_explicit_numbers)
    profile_name = self.profile_map.get(str(int(manufacturer_id))) if manufacturer_id is not None else None
    if profile_name:
      numbers.update(self.vendor_explicit_numbers.get(profile_name, set()))
    numbers.add(8)
    return sorted(numbers)

  def payload(self) -> dict:
    return {
      "source": self.source,
      "standard_definitions": {
        str(cv): meaning for cv, meaning in sorted(self.standard_definitions.items())
      },
      "standard_explicit_numbers": sorted(self.standard_explicit_numbers),
      "profile_map": dict(sorted(self.profile_map.items(), key=lambda item: int(item[0]))),
      "vendor_explicit_numbers": {
        profile_name: sorted(numbers)
        for profile_name, numbers in sorted(self.vendor_explicit_numbers.items())
      },
      "vendor_profiles": {
        profile_name: {
          **profile,
          "cv_definitions": dict(sorted(
            profile.get("cv_definitions", {}).items(),
            key=lambda item: int(item[0]),
          )),
        }
        for profile_name, profile in sorted(self.vendor_profiles.items())
      },
    }


def load_cv_catalog(config_dir: Path | str | None = None) -> CvCatalog:
  root = Path(config_dir or DEFAULT_CONFIG_DIR)
  manufacturers = _read_json(root / "manufacturers.json")
  standard = _read_json(root / "standard.json")
  profile_map_data = _read_json(root / "profile-map.json")
  profile_map = {
    str(int(manufacturer_id)): str(profile_name)
    for manufacturer_id, profile_name in profile_map_data.get("manufacturer_profiles", {}).items()
  }
  standard_definitions = _definition_table(standard)
  standard_explicit_numbers = _explicit_cv_numbers(standard)
  vendor_profiles = {}
  vendor_explicit_numbers = {}
  profiles_dir = root / "profiles"
  for profile_file in sorted(profiles_dir.glob("*.json")):
    profile_name = profile_file.stem
    profile = _read_json(profile_file)
    vendor_explicit_numbers[profile_name] = _explicit_cv_numbers(profile)
    profile["cv_definitions"] = {
      str(cv): meaning for cv, meaning in sorted(_definition_table(profile).items())
    }
    vendor_profiles[profile_name] = profile
  return CvCatalog(
    source=str(root),
    manufacturer_ids={
      str(int(manufacturer_id)): str(name)
      for manufacturer_id, name in manufacturers.get("known_ids", {}).items()
    },
    unassigned_notes={
      str(int(manufacturer_id)): str(note)
      for manufacturer_id, note in manufacturers.get("unassigned_notes", {}).items()
    },
    profile_map=profile_map,
    standard_definitions=standard_definitions,
    standard_explicit_numbers=standard_explicit_numbers,
    vendor_profiles=vendor_profiles,
    vendor_explicit_numbers=vendor_explicit_numbers,
  )


def default_cv_catalog() -> CvCatalog:
  signature = _config_signature(DEFAULT_CONFIG_DIR)
  if _DEFAULT_CACHE["signature"] != signature:
    _DEFAULT_CACHE["signature"] = signature
    _DEFAULT_CACHE["catalog"] = load_cv_catalog(DEFAULT_CONFIG_DIR)
  return _DEFAULT_CACHE["catalog"]


def manufacturer_name(manufacturer_id: int | None) -> str:
  return default_cv_catalog().manufacturer_name(manufacturer_id)


def cv_meaning(cv_number: int, manufacturer_id: int | None = None) -> str:
  return default_cv_catalog().cv_meaning(cv_number, manufacturer_id)


def cv_catalog_payload() -> dict:
  return default_cv_catalog().payload()


def _read_json(path: Path) -> dict:
  try:
    return json.loads(path.read_text(encoding="utf-8"))
  except FileNotFoundError as exc:
    raise FileNotFoundError(f"CV 配置文件不存在: {path}") from exc
  except json.JSONDecodeError as exc:
    raise ValueError(f"CV 配置文件不是合法 JSON: {path}: {exc}") from exc


def _config_signature(config_dir: Path) -> tuple:
  files = [
    config_dir / "manufacturers.json",
    config_dir / "profile-map.json",
    config_dir / "standard.json",
    *sorted((config_dir / "profiles").glob("*.json")),
  ]
  return tuple((str(path), path.stat().st_mtime_ns) for path in files)


def _definition_table(data: dict) -> dict[int, str]:
  definitions = {}
  for cv_number, meaning in data.get("cv_definitions", {}).items():
    definitions[_validate_cv_number(cv_number)] = str(meaning)
  for cv_range in data.get("cv_ranges", []):
    start = _validate_cv_number(cv_range["start"])
    end = _validate_cv_number(cv_range["end"])
    if end < start:
      raise ValueError(f"CV 范围无效: {start}..{end}")
    template = str(cv_range["meaning_template"])
    index_offset = int(cv_range.get("index_offset", 0))
    for cv in range(start, end + 1):
      index0 = cv - start + index_offset
      definitions.setdefault(
        cv,
        template.format(cv=cv, index0=index0, index1=index0 + 1),
      )
  return definitions


def _explicit_cv_numbers(data: dict) -> set[int]:
  return {_validate_cv_number(cv_number) for cv_number in data.get("cv_definitions", {})}


def _validate_cv_number(value: int | str) -> int:
  cv_number = int(value)
  if cv_number < 1 or cv_number > 1024:
    raise ValueError("CV number must be in 1..1024")
  return cv_number

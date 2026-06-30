"""Validation helpers for registry descriptor paths."""

from pathlib import PurePosixPath


def validate_descriptor_file_name(value, field_name: str) -> str:
  text = str(value or "").strip()
  if not text:
    raise ValueError(f"{field_name} must not be empty")
  if "\\" in text or "/" in text:
    raise ValueError(f"{field_name} must be a file name, not a path: {text}")
  path = PurePosixPath(text)
  if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
    raise ValueError(f"{field_name} contains unsafe path components: {text}")
  return text


def validate_public_descriptor_path(value, field_name: str, allowed_prefixes: tuple[str, ...]) -> str:
  text = str(value or "").strip()
  if not text:
    raise ValueError(f"{field_name} must not be empty")
  if "\\" in text or not text.startswith("/"):
    raise ValueError(f"{field_name} must be an absolute public URL path: {text}")
  if "//" in text:
    raise ValueError(f"{field_name} contains an empty path segment: {text}")
  parts = PurePosixPath(text).parts
  if any(part in ("", ".", "..") for part in parts):
    raise ValueError(f"{field_name} contains unsafe path components: {text}")
  if not any(text.startswith(prefix) for prefix in allowed_prefixes):
    raise ValueError(f"{field_name} is outside allowed public prefixes: {text}")
  return text

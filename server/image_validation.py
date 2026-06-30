"""Shared validation for locally stored vehicle images."""

from pathlib import Path


DEFAULT_MAX_VEHICLE_IMAGE_BYTES = 1536 * 1024


def validate_vehicle_image(
  file_name: str,
  content: bytes,
  *,
  max_bytes: int = DEFAULT_MAX_VEHICLE_IMAGE_BYTES,
  allowed_extensions: tuple[str, ...] = (".png", ".jpg", ".jpeg", ".webp"),
) -> str:
  if not content:
    raise ValueError("image content is empty")
  if len(content) > max_bytes:
    raise ValueError(f"image is larger than {round(max_bytes / 1024 / 1024, 1)}MB after compression")
  extension = Path(file_name).suffix.lower()
  normalized_allowed = tuple(ext.lower() for ext in allowed_extensions)
  if extension not in normalized_allowed:
    raise ValueError(f"only {', '.join(_extension_label(ext) for ext in normalized_allowed)} images are supported")
  if extension == ".webp":
    if len(content) < 12 or not content.startswith(b"RIFF") or content[8:12] != b"WEBP":
      raise ValueError("file content does not match WebP")
    return extension
  signatures = {
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
  }
  signature = signatures.get(extension)
  if signature is None or not content.startswith(signature):
    raise ValueError(f"file content does not match {_extension_label(extension)}")
  return ".jpg" if extension == ".jpeg" else extension


def _extension_label(extension: str) -> str:
  labels = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WebP",
  }
  return labels.get(extension, extension.lstrip(".").upper())

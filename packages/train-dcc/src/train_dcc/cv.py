"""DCC CV validation helpers."""


def validate_cv_number(cv_number: int) -> int:
  """Return a DCC CV number after validating the standard 1..1024 range."""
  value = int(cv_number)
  if value < 1 or value > 1024:
    raise ValueError("CV number must be in range 1..1024")
  return value


def validate_cv_byte(value: int) -> int:
  """Return a CV byte value after validating the 0..255 range."""
  normalized = int(value)
  if normalized < 0 or normalized > 0xFF:
    raise ValueError("CV byte value must be in range 0..255")
  return normalized

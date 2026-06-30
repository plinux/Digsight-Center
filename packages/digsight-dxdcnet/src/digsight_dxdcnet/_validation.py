"""Private validation helpers for DXDCNet command builders."""


def validate_int_range(name: str, value: int, minimum: int, maximum: int) -> int:
  """Return an integer after validating the inclusive DXDCNet field range."""
  try:
    numeric_value = int(value)
  except (TypeError, ValueError) as exc:
    raise ValueError(f"{name} must be an integer in {minimum}..{maximum}") from exc
  if numeric_value < minimum or numeric_value > maximum:
    raise ValueError(f"{name} must be in {minimum}..{maximum}")
  return numeric_value


def validate_byte(name: str, value: int) -> int:
  """Return a single byte value after validating the 0..255 range."""
  return validate_int_range(name, value, 0, 0xFF)

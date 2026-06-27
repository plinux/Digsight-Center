"""DCC vehicle address CV helpers."""

from train_dcc.cv import validate_cv_byte

LONG_ADDRESS_ENABLE_MASK = 1 << 5
SHORT_ADDRESS_MAX = 127
LOCO_ADDRESS_MAX = 9999
LOCO_SPEED_128_MAX = 126


def validate_loco_address(value) -> int:
  """Validate the locomotive address range accepted by the controller UI."""
  address = int(value)
  if address < 1 or address > LOCO_ADDRESS_MAX:
    raise ValueError(f"loco address must be in 1..{LOCO_ADDRESS_MAX}")
  return address


def validate_loco_speed_128(value) -> int:
  """Validate the 128-step speed command range used by DCC loco control."""
  speed = int(value)
  if speed < 0 or speed > LOCO_SPEED_128_MAX:
    raise ValueError(f"loco speed must be in 0..{LOCO_SPEED_128_MAX}")
  return speed


def decode_vehicle_address(cv29: int, cv1: int | None = None, cv17: int | None = None, cv18: int | None = None) -> dict:
  """Decode the active DCC vehicle address from standard address CVs."""
  cv29_value = validate_cv_byte(cv29)
  if cv29_value & LONG_ADDRESS_ENABLE_MASK:
    if cv17 is None or cv18 is None:
      raise ValueError("CV17 and CV18 are required when CV29 bit5 enables long address")
    cv17_value = validate_cv_byte(cv17)
    cv18_value = validate_cv_byte(cv18)
    if (cv17_value & 0xC0) != 0xC0:
      raise ValueError("CV17 long address marker bits must both be 1")
    address = ((cv17_value & 0x3F) << 8) | cv18_value
    if address <= 0:
      raise ValueError("DCC long address 0 is invalid")
    return {"address": address, "address_type": "long"}
  if cv1 is None:
    raise ValueError("CV1 is required when CV29 bit5 selects short address")
  cv1_value = validate_cv_byte(cv1)
  if cv1_value & 0x80:
    raise ValueError("CV1 bit7 must be 0 for a short address")
  address = cv1_value & 0x7F
  if address <= 0:
    raise ValueError("DCC short address 0 is invalid")
  return {"address": address, "address_type": "short"}


def build_vehicle_address_writes(address: int, cv29: int) -> dict:
  """Build ordered CV writes for a DCC vehicle address update."""
  address_value = int(address)
  cv29_value = validate_cv_byte(cv29)
  if address_value <= 0:
    raise ValueError("DCC address must be positive")
  if address_value <= SHORT_ADDRESS_MAX:
    return {
      "address": address_value,
      "address_type": "short",
      "writes": [
        {"cv": 1, "value": address_value},
        {"cv": 29, "value": cv29_value & ~LONG_ADDRESS_ENABLE_MASK},
      ],
    }
  if address_value > 10239:
    raise ValueError("DCC long address must be in range 1..10239")
  return {
    "address": address_value,
    "address_type": "long",
    "writes": [
      {"cv": 17, "value": 0xC0 | ((address_value >> 8) & 0x3F)},
      {"cv": 18, "value": address_value & 0xFF},
      {"cv": 29, "value": cv29_value | LONG_ADDRESS_ENABLE_MASK},
    ],
  }

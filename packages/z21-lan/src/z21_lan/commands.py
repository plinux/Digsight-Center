"""Z21 LAN command builders."""

from z21_lan.constants import (
  LAN_GET_BROADCASTFLAGS,
  LAN_GET_COMMON_SETTINGS,
  LAN_GET_HWINFO,
  LAN_GET_LOCO_MODE,
  LAN_GET_MMDCC_SETTINGS,
  LAN_GET_SERIAL_NUMBER,
  LAN_SET_COMMON_SETTINGS,
  LAN_SET_LOCO_MODE,
  LAN_SET_MMDCC_SETTINGS,
  LAN_SYSTEMSTATE_GETDATA,
  LAN_X,
  X_CV_POM,
  X_CV_POM_READ_BYTE,
  X_CV_POM_WRITE_BYTE,
  X_CV_READ_DIRECT,
  X_CV_WRITE_DIRECT,
  X_GET_FIRMWARE_VERSION,
  X_GET_LOCO_INFO,
  X_SET_LOCO_DRIVE,
  X_SET_LOCO_DRIVE_14,
  X_SET_LOCO_DRIVE_28,
  X_SET_LOCO_DRIVE_128,
  X_SET_LOCO_FUNCTION,
  X_SET_TRACK_POWER_OFF,
  X_SET_TRACK_POWER_ON,
)
from z21_lan.dataset import encode_dataset
from z21_lan.xbus import build_lan_x_payload


def build_get_serial_number() -> bytes:
  return encode_dataset(LAN_GET_SERIAL_NUMBER)


def build_get_hwinfo() -> bytes:
  return encode_dataset(LAN_GET_HWINFO)


def build_get_broadcast_flags() -> bytes:
  return encode_dataset(LAN_GET_BROADCASTFLAGS)


def build_get_system_state() -> bytes:
  return encode_dataset(LAN_SYSTEMSTATE_GETDATA)


def build_get_common_settings() -> bytes:
  return encode_dataset(LAN_GET_COMMON_SETTINGS)


def build_set_common_settings(settings) -> bytes:
  if hasattr(settings, "to_payload"):
    payload = settings.to_payload()
  else:
    payload = bytes(settings or b"")
  if len(payload) != 10:
    raise ValueError("Z21 common settings payload must be exactly 10 bytes")
  return encode_dataset(LAN_SET_COMMON_SETTINGS, payload)


def build_get_mmdcc_settings() -> bytes:
  return encode_dataset(LAN_GET_MMDCC_SETTINGS)


def build_set_mmdcc_settings(settings) -> bytes:
  if hasattr(settings, "to_payload"):
    payload = settings.to_payload()
  else:
    payload = bytes(settings or b"")
  if len(payload) != 16:
    raise ValueError("Z21 MMDCC settings payload must be exactly 16 bytes")
  return encode_dataset(LAN_SET_MMDCC_SETTINGS, payload)


def build_x_get_firmware_version() -> bytes:
  return encode_dataset(LAN_X, build_lan_x_payload(*X_GET_FIRMWARE_VERSION))


def build_x_set_track_power_off() -> bytes:
  return encode_dataset(LAN_X, build_lan_x_payload(*X_SET_TRACK_POWER_OFF))


def build_x_set_track_power_on() -> bytes:
  return encode_dataset(LAN_X, build_lan_x_payload(*X_SET_TRACK_POWER_ON))


def build_x_get_loco_info(address: int) -> bytes:
  address_high, address_low = encode_loco_address(address)
  return encode_dataset(LAN_X, build_lan_x_payload(*X_GET_LOCO_INFO, address_high, address_low))


def build_get_loco_mode(address: int) -> bytes:
  address_high, address_low = _encode_plain_loco_address(address)
  return encode_dataset(LAN_GET_LOCO_MODE, bytes([address_high, address_low]))


def build_set_loco_mode(address: int, control_protocol: str) -> bytes:
  address_high, address_low = _encode_plain_loco_address(address)
  return encode_dataset(LAN_SET_LOCO_MODE, bytes([address_high, address_low, _loco_mode_value(control_protocol)]))


def build_x_set_loco_drive(address: int, speed: int, direction: str = "forward", *, speed_steps: int = 128) -> bytes:
  address_high, address_low = encode_loco_address(address)
  speed_value = _validate_speed(speed, speed_steps)
  direction_value = _direction_bit(direction)
  return encode_dataset(
    LAN_X,
    build_lan_x_payload(
      X_SET_LOCO_DRIVE,
      _drive_step_code(speed_steps),
      address_high,
      address_low,
      direction_value | speed_value,
    ),
  )


def build_x_set_loco_drive_128(address: int, speed: int, direction: str = "forward") -> bytes:
  return build_x_set_loco_drive(address, speed, direction, speed_steps=128)


def build_x_set_loco_function(address: int, function_number: int, enabled) -> bytes:
  address_high, address_low = encode_loco_address(address)
  function_value = _function_switch_value(function_number, enabled)
  return encode_dataset(
    LAN_X,
    build_lan_x_payload(*X_SET_LOCO_FUNCTION, address_high, address_low, function_value),
  )


def build_x_cv_read_direct(cv_number: int) -> bytes:
  cv_high, cv_low = encode_cv_address(cv_number)
  return encode_dataset(LAN_X, build_lan_x_payload(*X_CV_READ_DIRECT, cv_high, cv_low))


def build_x_cv_write_direct(cv_number: int, value: int) -> bytes:
  cv_high, cv_low = encode_cv_address(cv_number)
  return encode_dataset(LAN_X, build_lan_x_payload(*X_CV_WRITE_DIRECT, cv_high, cv_low, _validate_byte(value, "CV value")))


def build_x_cv_pom_read_byte(address: int, cv_number: int) -> bytes:
  address_high, address_low = encode_loco_address(address)
  cv_high, cv_low = encode_cv_address(cv_number)
  return encode_dataset(
    LAN_X,
    build_lan_x_payload(
      *X_CV_POM,
      address_high,
      address_low,
      X_CV_POM_READ_BYTE | cv_high,
      cv_low,
      0,
    ),
  )


def build_x_cv_pom_write_byte(address: int, cv_number: int, value: int) -> bytes:
  address_high, address_low = encode_loco_address(address)
  cv_high, cv_low = encode_cv_address(cv_number)
  return encode_dataset(
    LAN_X,
    build_lan_x_payload(
      *X_CV_POM,
      address_high,
      address_low,
      X_CV_POM_WRITE_BYTE | cv_high,
      cv_low,
      _validate_byte(value, "CV value"),
    ),
  )


def encode_loco_address(address: int) -> tuple[int, int]:
  loco_address = int(address)
  if loco_address < 1 or loco_address > 10239:
    raise ValueError("Z21 loco address must be in 1..10239")
  address_high = (loco_address >> 8) & 0x3F
  if loco_address >= 128:
    address_high |= 0xC0
  return address_high, loco_address & 0xFF


def _encode_plain_loco_address(address: int) -> tuple[int, int]:
  loco_address = int(address)
  if loco_address < 1 or loco_address > 10239:
    raise ValueError("Z21 loco address must be in 1..10239")
  return (loco_address >> 8) & 0xFF, loco_address & 0xFF


def encode_cv_address(cv_number: int) -> tuple[int, int]:
  cv = int(cv_number)
  if cv < 1 or cv > 1024:
    raise ValueError("Z21 CV number must be in 1..1024")
  encoded = cv - 1
  return (encoded >> 8) & 0x03, encoded & 0xFF


def _drive_step_code(speed_steps: int) -> int:
  normalized = int(speed_steps)
  codes = {
    14: X_SET_LOCO_DRIVE_14,
    28: X_SET_LOCO_DRIVE_28,
    128: X_SET_LOCO_DRIVE_128,
  }
  if normalized not in codes:
    raise ValueError("Z21 speed steps must be 14, 28 or 128")
  return codes[normalized]


def _validate_speed(speed: int, speed_steps: int) -> int:
  normalized_steps = int(speed_steps)
  speed_value = int(speed)
  max_speed = 126 if normalized_steps == 128 else normalized_steps
  if speed_value < 0 or speed_value > max_speed:
    raise ValueError(f"Z21 {normalized_steps}-step speed must be in 0..{max_speed}")
  return speed_value


def _loco_mode_value(control_protocol: str) -> int:
  normalized = str(control_protocol or "dcc").strip().lower()
  if normalized == "dcc":
    return 0
  if normalized in {"motorola", "mm"}:
    return 1
  raise ValueError("Z21 loco mode must be dcc or motorola")


def _validate_byte(value: int, label: str) -> int:
  byte_value = int(value)
  if byte_value < 0 or byte_value > 0xFF:
    raise ValueError(f"{label} must be in 0..255")
  return byte_value


def _direction_bit(direction: str) -> int:
  normalized = str(direction or "forward").strip().lower()
  if normalized not in {"forward", "reverse"}:
    raise ValueError("Z21 direction must be forward or reverse")
  return 0x80 if normalized == "forward" else 0


def _function_switch_value(function_number: int, enabled) -> int:
  function_index = int(function_number)
  if function_index < 0 or function_index > 31:
    raise ValueError("Z21 function number must be in 0..31")
  if isinstance(enabled, bool):
    operation = 0x40 if enabled else 0x00
  else:
    normalized = str(enabled or "").strip().lower()
    operations = {
      "off": 0x00,
      "false": 0x00,
      "0": 0x00,
      "on": 0x40,
      "true": 0x40,
      "1": 0x40,
      "toggle": 0x80,
    }
    if normalized not in operations:
      raise ValueError("Z21 function operation must be on, off or toggle")
    operation = operations[normalized]
  return operation | function_index

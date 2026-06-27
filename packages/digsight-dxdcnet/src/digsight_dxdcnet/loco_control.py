"""DXDCNet locomotive speed and function command helpers."""

from digsight_dxdcnet.constants import (
  CMD_LOCO_CONTROL_ACK,
  CMD_LOCO_CONTROL_REQUEST,
  CMD_LOCO_FUNCTION,
  CMD_LOCO_SPEED,
  DEVICE_TYPE_THROTTLE,
  SPEED_MODE_128,
)
from digsight_dxdcnet.frames import DXDCNetFrame, build_udp_frame

FUNCTION_GROUPS = (
  (0x00, 0, 12),
  (0x40, 13, 20),
  (0x80, 21, 28),
  (0x98, 29, 36),
  (0x99, 37, 44),
  (0x9A, 45, 52),
  (0x9B, 53, 60),
  (0x9C, 61, 68),
)


def validate_loco_address(address: int) -> int:
  value = int(address)
  if value < 1 or value > 9999:
    raise ValueError("loco address must be in 1..9999")
  return value


def validate_loco_speed(speed: int) -> int:
  value = int(speed)
  if value < 0 or value > 126:
    raise ValueError("loco speed must be in 0..126")
  return value


def validate_speed_mode(speed_mode: int) -> int:
  value = int(speed_mode)
  if value < 0 or value > 0x07:
    raise ValueError("speed mode must be in 0..7")
  return value


def direction_bit(direction: str) -> int:
  normalized = str(direction or "forward").lower()
  if normalized == "forward":
    return 1
  if normalized == "reverse":
    return 0
  raise ValueError("direction must be forward or reverse")


def direction_name(direction: int) -> str:
  return "forward" if direction & 0x01 else "reverse"


def encode_loco_address(address: int) -> bytes:
  address = validate_loco_address(address)
  low = address & 0xFF
  high = (address >> 8) & 0x3F
  if address > 0x7F:
    high |= 0x80
  return bytes([low, high])


def decode_loco_address(payload: bytes) -> int:
  return (payload[0] & 0xFF) + ((payload[1] & 0x3F) << 8)


def build_loco_speed_frame(
  address: int,
  speed: int,
  direction: str,
  speed_mode: int = SPEED_MODE_128,
  client_id: int = 1,
) -> bytes:
  address = validate_loco_address(address)
  speed = validate_loco_speed(speed)
  speed_mode = validate_speed_mode(speed_mode)
  payload = encode_loco_address(address) + bytes([
    (direction_bit(direction) << 7) | speed,
    speed_mode & 0x07,
  ])
  return build_udp_frame(DEVICE_TYPE_THROTTLE, client_id, CMD_LOCO_SPEED, payload)


def build_loco_control_request_frame(address: int, client_id: int = 1) -> bytes:
  payload = encode_loco_address(address)
  return build_udp_frame(DEVICE_TYPE_THROTTLE, client_id, CMD_LOCO_CONTROL_REQUEST, payload)


def build_loco_function_frame(address: int, function_states: dict, client_id: int = 1, function_number: int | None = None) -> bytes:
  return build_loco_function_frames(address, function_states, client_id, function_number)[0]


def build_loco_function_frames(
  address: int,
  function_states: dict,
  client_id: int = 1,
  function_number: int | None = None,
) -> list[bytes]:
  address = validate_loco_address(address)
  states = normalize_function_states(function_states)
  if function_number is not None:
    group_codes = [function_group_for_number(function_number)]
  else:
    group_codes = function_groups_for_states(states)
  return [
    build_udp_frame(DEVICE_TYPE_THROTTLE, client_id, CMD_LOCO_FUNCTION, encode_loco_function_payload(address, states, group_code))
    for group_code in group_codes
  ]


def normalize_function_states(function_states: dict | None) -> dict[int, bool]:
  states = {}
  for key, value in dict(function_states or {}).items():
    function_number = int(key)
    if function_number < 0 or function_number > 68:
      continue
    if not isinstance(value, bool):
      raise ValueError("function state values must be boolean")
    states[function_number] = value
  return states


def function_group_for_number(function_number: int) -> int:
  value = int(function_number)
  for group_code, start, end in FUNCTION_GROUPS:
    if start <= value <= end:
      return group_code
  raise ValueError("function number must be in F0..F68")


def function_groups_for_states(function_states: dict[int, bool]) -> list[int]:
  group_codes = []
  for function_number in sorted(function_states):
    group_code = function_group_for_number(function_number)
    if group_code not in group_codes:
      group_codes.append(group_code)
  return group_codes or [0x00]


def function_numbers_for_group(group_code: int) -> list[int]:
  if group_code == 0x00:
    return list(range(0, 13))
  for code, start, end in FUNCTION_GROUPS:
    if code == group_code:
      return list(range(start, end + 1))
  raise ValueError(f"unsupported function group: 0x{group_code:02X}")


def encode_loco_function_payload(address: int, function_states: dict[int, bool], group_code: int) -> bytes:
  if group_code == 0x00:
    third = encode_f0_to_f4(function_states)
    fourth = encode_f5_to_f12(function_states)
  else:
    third = group_code
    fourth = encode_function_group_bits(function_states, function_numbers_for_group(group_code))
  return encode_loco_address(address) + bytes([third, fourth])


def encode_f0_to_f4(function_states: dict[int, bool]) -> int:
  value = 0
  if function_states.get(0):
    value |= 0x10
  for function_number, bit in ((1, 0), (2, 1), (3, 2), (4, 3)):
    if function_states.get(function_number):
      value |= 1 << bit
  return value


def encode_f5_to_f12(function_states: dict[int, bool]) -> int:
  value = 0
  for function_number in range(5, 13):
    if function_states.get(function_number):
      value |= 1 << (function_number - 5)
  return value


def encode_function_group_bits(function_states: dict[int, bool], function_numbers: list[int]) -> int:
  value = 0
  for bit, function_number in enumerate(function_numbers):
    if function_states.get(function_number):
      value |= 1 << bit
  return value


def parse_loco_speed_feedback(frame: DXDCNetFrame) -> dict:
  if frame.command != CMD_LOCO_SPEED + 0x08:
    raise ValueError("DXDCNet frame is not a loco speed feedback")
  if len(frame.payload) < 4:
    raise ValueError("Loco speed feedback payload must contain address, speed and mode")
  direction_and_speed = frame.payload[2] & 0xFF
  return {
    "address": parse_loco_address(frame.payload),
    "speed": direction_and_speed & 0x7F,
    "direction": direction_name((direction_and_speed >> 7) & 0x01),
    "speed_mode": frame.payload[3] & 0x07,
  }


def parse_loco_function_feedback(frame: DXDCNetFrame) -> dict:
  if frame.command != CMD_LOCO_FUNCTION + 0x08:
    raise ValueError("DXDCNet frame is not a loco function feedback")
  if len(frame.payload) < 4:
    raise ValueError("Loco function feedback payload must contain address and function bits")
  return {
    "address": parse_loco_address(frame.payload),
    "function_states": decode_loco_function_states(frame.payload[2], frame.payload[3]),
  }


def parse_loco_control_ack(frame: DXDCNetFrame) -> dict:
  if frame.command != CMD_LOCO_CONTROL_ACK:
    raise ValueError("DXDCNet frame is not a loco control ACK")
  if len(frame.payload) < 4:
    raise ValueError("Loco control ACK payload must contain address, device type and device id")
  granted_id = frame.payload[3] & 0x7F
  return {
    "address": parse_loco_address(frame.payload),
    "granted_device_type": frame.payload[2] & 0x0F,
    "granted_id": granted_id,
    "granted": granted_id != 0,
  }


def parse_loco_address(payload: bytes) -> int:
  return decode_loco_address(payload)


def decode_f0_to_f12(third: int, fourth: int) -> dict[str, bool]:
  states = {
    "0": bool(third & 0x10),
    "1": bool(third & 0x01),
    "2": bool(third & 0x02),
    "3": bool(third & 0x04),
    "4": bool(third & 0x08),
  }
  for function_number in range(5, 13):
    states[str(function_number)] = bool(fourth & (1 << (function_number - 5)))
  return states


def decode_loco_function_states(third: int, fourth: int) -> dict[str, bool]:
  group_code = third & 0xFF
  if group_code < 0x40:
    return decode_f0_to_f12(third, fourth)
  states = {}
  for bit, function_number in enumerate(function_numbers_for_group(group_code)):
    states[str(function_number)] = bool(fourth & (1 << bit))
  return states

"""DXDCNet UDP frame encode/decode helpers."""

from dataclasses import dataclass, field
from typing import List

from digsight_dxdcnet.constants import WARNING_CHECKSUM_INVALID, WARNING_LENGTH_MISMATCH


@dataclass
class DXDCNetFrame:
  device_type: int
  length: int
  source_id: int
  command: int
  payload: bytes
  checksum: int
  checksum_valid: bool = False
  warnings: List[str] = field(default_factory=list)

  def to_debug_dict(self):
    return {
      "device_type": self.device_type,
      "length": self.length,
      "source_id": self.source_id,
      "command": self.command,
      "payload_hex": self.payload.hex(" "),
      "checksum": self.checksum,
      "checksum_valid": self.checksum_valid,
      "warnings": list(self.warnings),
    }


def calculate_udp_checksum(raw_without_checksum: bytes) -> int:
  checksum = 0
  for value in raw_without_checksum:
    checksum ^= value
  return checksum


def decode_udp_frame(raw: bytes) -> DXDCNetFrame:
  if len(raw) < 6:
    raise ValueError("DXDCNet UDP frame is shorter than 6 bytes")
  if raw[0:2] != b"\xff\xff":
    raise ValueError("DXDCNet UDP frame must start with ff ff")

  device_and_length = raw[2]
  device_type = (device_and_length >> 4) & 0x0F
  length = device_and_length & 0x0F
  source_id = raw[3] & 0x7F
  command = raw[4] & 0xFF
  payload = raw[5:-1]
  checksum = raw[-1]
  warnings = []
  checksum_valid = calculate_udp_checksum(raw[:-1]) == checksum
  if not checksum_valid:
    warnings.append(WARNING_CHECKSUM_INVALID)
  if length != len(raw) - 2:
    warnings.append(WARNING_LENGTH_MISMATCH)
  return DXDCNetFrame(
    device_type=device_type,
    length=length,
    source_id=source_id,
    command=command,
    payload=payload,
    checksum=checksum,
    checksum_valid=checksum_valid,
    warnings=warnings,
  )


def encode_udp_frame(frame: DXDCNetFrame) -> bytes:
  device_and_length = ((frame.device_type & 0x0F) << 4) | (frame.length & 0x0F)
  return bytes([
    0xFF,
    0xFF,
    device_and_length,
    frame.source_id & 0x7F,
    frame.command & 0xFF,
  ]) + bytes(frame.payload) + bytes([frame.checksum & 0xFF])


def build_udp_frame(device_type: int, source_id: int, command: int, payload: bytes) -> bytes:
  device_type = _validate_frame_field("device_type", device_type, 0x0F)
  source_id = _validate_frame_field("source_id", source_id, 0x7F)
  command = _validate_frame_field("command", command, 0xFF)
  payload = bytes(payload)
  length = 4 + len(payload)
  if length > 0x0F:
    raise ValueError("DXDCNet UDP payload is too long for the 4-bit length field")
  raw_without_checksum = bytes([
    0xFF,
    0xFF,
    (device_type << 4) | length,
    source_id,
    command,
  ]) + payload
  return raw_without_checksum + bytes([calculate_udp_checksum(raw_without_checksum)])


def _validate_frame_field(name: str, value: int, maximum: int) -> int:
  try:
    numeric_value = int(value)
  except (TypeError, ValueError) as exc:
    raise ValueError(f"{name} must be an integer in 0..0x{maximum:02x}") from exc
  if numeric_value < 0 or numeric_value > maximum:
    raise ValueError(f"{name} must be in 0..0x{maximum:02x}")
  return numeric_value

"""DCC packet builders."""

from typing import Iterable, List

from train_dcc.cv import validate_cv_byte, validate_cv_number


def dcc_xor(packet_bytes: Iterable[int]) -> int:
  """Return the DCC packet error-detection XOR byte."""
  checksum = 0
  for value in packet_bytes:
    checksum ^= validate_cv_byte(value)
  return checksum


def build_service_mode_cv_verify_packet(cv_number: int, value: int) -> bytes:
  """Build a direct-mode service-mode CV verify packet."""
  return _build_direct_cv_packet(cv_number, value, instruction_bits=0b01)


def build_service_mode_cv_write_packet(cv_number: int, value: int) -> bytes:
  """Build a direct-mode service-mode CV write packet."""
  return _build_direct_cv_packet(cv_number, value, instruction_bits=0b11)


def _build_direct_cv_packet(cv_number: int, value: int, instruction_bits: int) -> bytes:
  cv_number = validate_cv_number(cv_number)
  value = validate_cv_byte(value)
  cv_offset = cv_number - 1
  first_byte = 0x70 | ((instruction_bits & 0x03) << 2) | ((cv_offset >> 8) & 0x03)
  packet: List[int] = [first_byte, cv_offset & 0xFF, value]
  packet.append(dcc_xor(packet))
  return bytes(packet)

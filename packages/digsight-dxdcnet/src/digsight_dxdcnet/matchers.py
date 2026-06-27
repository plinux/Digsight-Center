"""Reusable DXDCNet response matching helpers."""

from collections.abc import Callable, Iterable

from digsight_dxdcnet.constants import CMD_PROGRAM_TRACK_ACK, CMD_PROGRAM_TRACK_VALUE
from digsight_dxdcnet.frames import DXDCNetFrame, decode_udp_frame
from digsight_dxdcnet.programmer import parse_programmer_ack, parse_programmer_value


def first_matching_frame(frames: Iterable[DXDCNetFrame], command: int, device_type: int | None = None):
  for frame in frames:
    if frame.command != command:
      continue
    if device_type is not None and frame.device_type != device_type:
      continue
    return frame
  return None


def build_raw_frame_matcher(command: int, device_type: int | None = None) -> Callable[[bytes], bool]:
  def matches(raw: bytes) -> bool:
    try:
      frame = decode_udp_frame(raw)
    except ValueError:
      return False
    if not frame.checksum_valid or frame.command != command:
      return False
    if device_type is not None and frame.device_type != device_type:
      return False
    return True

  return matches


def build_programmer_value_matcher(
  client_id: int,
  cv_number: int,
  pom_address: int | None = None,
) -> Callable[[bytes], bool]:
  def matches(raw: bytes) -> bool:
    try:
      frame = decode_udp_frame(raw)
      if not frame.checksum_valid or frame.command != CMD_PROGRAM_TRACK_VALUE:
        return False
      value = parse_programmer_value(frame)
    except ValueError:
      return False
    if value.device_id != client_id or value.cv_number != cv_number:
      return False
    if pom_address is not None and value.pom_address != pom_address:
      return False
    return True

  return matches


def build_programmer_ack_matcher(client_id: int) -> Callable[[bytes], bool]:
  def matches(raw: bytes) -> bool:
    try:
      frame = decode_udp_frame(raw)
      if not frame.checksum_valid or frame.command != CMD_PROGRAM_TRACK_ACK:
        return False
      ack = parse_programmer_ack(frame)
    except ValueError:
      return False
    return ack.device_id == client_id

  return matches

"""Programmer ACK/value response classification helpers."""

from dataclasses import dataclass, field

from digsight_dxdcnet.constants import (
  CMD_PROGRAM_TRACK_ACK,
  CMD_PROGRAM_TRACK_VALUE,
  PROGRAMMER_ACK_ACK,
  PROGRAMMER_ACK_BUSY,
)
from digsight_dxdcnet.programmer import ProgrammerAck, ProgrammerValue, parse_programmer_ack, parse_programmer_value


@dataclass
class ProgrammerResponseClassification:
  value: ProgrammerValue | None = None
  value_frame: object | None = None
  ack: ProgrammerAck | None = None
  ack_frame: object | None = None
  parse_warnings: list[dict] = field(default_factory=list)


def programmer_value_matches(programmer_value: ProgrammerValue, *, client_id: int, cv_number: int, pom_address: int | None = None) -> bool:
  if programmer_value.device_id != client_id or programmer_value.cv_number != cv_number:
    return False
  if pom_address is not None and programmer_value.pom_address != pom_address:
    return False
  return True


def programmer_ack_category(ack_mode: int) -> str:
  if ack_mode == PROGRAMMER_ACK_BUSY:
    return "busy"
  if ack_mode == PROGRAMMER_ACK_ACK:
    return "ack"
  return "rejected"


def should_retry_busy_ack(ack_mode: int, *, attempt: int, retry_count: int) -> bool:
  return programmer_ack_category(ack_mode) == "busy" and attempt < retry_count


def _frame_debug(frame) -> dict:
  if hasattr(frame, "to_debug_dict"):
    return frame.to_debug_dict()
  return {"frame": str(frame)}


def classify_programmer_responses(
  frames,
  *,
  client_id: int,
  cv_number: int,
  pom_address: int | None = None,
) -> ProgrammerResponseClassification:
  result = ProgrammerResponseClassification()
  for frame in frames:
    if frame.command == CMD_PROGRAM_TRACK_VALUE:
      try:
        value = parse_programmer_value(frame)
      except ValueError as exc:
        result.parse_warnings.append({
          "type": "programmer_value_parse_error",
          "detail": str(exc),
          "frame": _frame_debug(frame),
        })
        continue
      if programmer_value_matches(value, client_id=client_id, cv_number=cv_number, pom_address=pom_address):
        result.value = value
        result.value_frame = frame
    elif frame.command == CMD_PROGRAM_TRACK_ACK:
      try:
        ack = parse_programmer_ack(frame)
      except ValueError as exc:
        result.parse_warnings.append({
          "type": "programmer_ack_parse_error",
          "detail": str(exc),
          "frame": _frame_debug(frame),
        })
        continue
      if ack.device_id == client_id:
        result.ack = ack
        result.ack_frame = frame
  return result

"""DXDCNet programmer command helpers from the official Digsight app."""

from dataclasses import dataclass

from digsight_dxdcnet.constants import (
  CMD_PROGRAM_TRACK_ACK,
  CMD_PROGRAM_TRACK_STANDARD,
  CMD_PROGRAM_TRACK_VALUE,
  DEVICE_TYPE_THROTTLE,
  PROGRAMMER_ACK_NAMES,
  PROGRAMMER_MODE_DIRECT_READ,
  PROGRAMMER_MODE_DIRECT_WRITE,
  PROGRAMMER_OP_MAIN_ACCESSORY_POM,
  PROGRAMMER_OP_MAIN_LOCO_POM,
  PROGRAMMER_OP_NORMAL,
)
from digsight_dxdcnet.frames import DXDCNetFrame, build_udp_frame


def _validate_range(name: str, value: int, minimum: int, maximum: int) -> int:
  if not isinstance(value, int):
    raise ValueError(f"{name} must be an integer")
  if value < minimum or value > maximum:
    raise ValueError(f"{name} must be in {minimum}..{maximum}")
  return value


@dataclass(frozen=True)
class ProgrammerAck:
  ack_mode: int
  device_type: int
  device_id: int

  @property
  def ack_name(self) -> str:
    return PROGRAMMER_ACK_NAMES.get(self.ack_mode, f"unknown_{self.ack_mode}")


@dataclass(frozen=True)
class ProgrammerValue:
  mode: int
  register: int
  value: int
  device_type: int
  device_id: int
  pom_address: int | None = None

  @property
  def cv_number(self) -> int:
    return self.register + 1


def build_cv_read_frame(
  cv_number: int,
  client_id: int = 1,
  op: int = PROGRAMMER_OP_NORMAL,
  pom_address: int | None = None,
) -> bytes:
  return build_programmer_frame(
    client_id=client_id,
    mode=PROGRAMMER_MODE_DIRECT_READ,
    op=op,
    register=cv_number - 1,
    value=0,
    pom_address=pom_address,
  )


def build_cv_write_frame(
  cv_number: int,
  value: int,
  client_id: int = 1,
  op: int = PROGRAMMER_OP_NORMAL,
  pom_address: int | None = None,
) -> bytes:
  return build_programmer_frame(
    client_id=client_id,
    mode=PROGRAMMER_MODE_DIRECT_WRITE,
    op=op,
    register=cv_number - 1,
    value=value,
    pom_address=pom_address,
  )


def build_programmer_frame(
  client_id: int,
  mode: int,
  op: int,
  register: int,
  value: int,
  pom_address: int | None = None,
) -> bytes:
  client_id = _validate_range("client_id", client_id, 0, 0x7F)
  mode = _validate_range("mode", mode, 0, 0x07)
  op = _validate_range("op", op, 0, 0x07)
  value = _validate_range("value", value, 0, 0xFF)
  if register < 0 or register > 1023:
    raise ValueError("Programmer register must be in 0..1023")
  is_main_track_pom = op in {PROGRAMMER_OP_MAIN_LOCO_POM, PROGRAMMER_OP_MAIN_ACCESSORY_POM}
  if is_main_track_pom:
    if pom_address is None:
      raise ValueError("POM programmer frame requires pom_address")
    if pom_address < 1 or pom_address > 9999:
      raise ValueError("POM address must be in 1..9999")
  elif pom_address is not None:
    raise ValueError("pom_address is only valid for main track POM operations")
  payload_parts = [
    ((mode & 0x07) << 5) | ((op & 0x07) << 2) | ((register // 256) & 0x03),
    register % 256,
    value & 0xFF,
  ]
  if is_main_track_pom:
    payload_parts.extend([pom_address & 0xFF, (pom_address >> 8) & 0xFF])
  payload = bytes(payload_parts)
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_PROGRAM_TRACK_STANDARD,
    payload=payload,
  )


def parse_programmer_ack(frame: DXDCNetFrame) -> ProgrammerAck:
  if frame.command != CMD_PROGRAM_TRACK_ACK:
    raise ValueError("DXDCNet frame is not a programmer ACK")
  if len(frame.payload) < 3:
    raise ValueError("Programmer ACK payload must contain ack mode, device type and device id")
  return ProgrammerAck(
    ack_mode=frame.payload[0] & 0x07,
    device_type=frame.payload[1] & 0xFF,
    device_id=frame.payload[2] & 0xFF,
  )


def parse_programmer_value(frame: DXDCNetFrame) -> ProgrammerValue:
  if frame.command != CMD_PROGRAM_TRACK_VALUE:
    raise ValueError("DXDCNet frame is not a programmer value response")
  if len(frame.payload) < 5:
    raise ValueError("Programmer value payload must contain mode, register, value and source device")
  mode_and_register = frame.payload[0]
  pom_address = None
  if len(frame.payload) >= 7:
    pom_address = ((frame.payload[6] & 0xFF) * 256) + (frame.payload[5] & 0xFF)
  return ProgrammerValue(
    mode=(mode_and_register & 0xE0) >> 5,
    register=((mode_and_register & 0x03) * 256) + (frame.payload[1] & 0xFF),
    value=frame.payload[2] & 0xFF,
    device_type=frame.payload[3] & 0xFF,
    device_id=frame.payload[4] & 0xFF,
    pom_address=pom_address,
  )

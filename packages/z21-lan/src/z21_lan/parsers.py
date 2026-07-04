"""Parsers for read-only Z21 LAN payloads."""

from dataclasses import dataclass, field

from z21_lan.constants import (
  CENTRAL_STATE_EMERGENCY_STOP,
  CENTRAL_STATE_EXT_EXTERNAL_BOOSTER_SHORT,
  CENTRAL_STATE_EXT_INPUT_VOLTAGE_LOW,
  CENTRAL_STATE_EXT_INTERNAL_SHORT,
  CENTRAL_STATE_EXT_TEMPERATURE_TOO_HIGH,
  CENTRAL_STATE_PROGRAMMING_MODE_ACTIVE,
  CENTRAL_STATE_SHORT_CIRCUIT,
  CENTRAL_STATE_TRACK_VOLTAGE_OFF,
  HARDWARE_TYPE_LABELS,
  X_CV_NACK,
  X_CV_NACK_SC,
  X_CV_RESULT,
  X_LOCO_INFO,
  X_UNKNOWN_COMMAND,
)
from z21_lan.xbus import xbus_xor


@dataclass(frozen=True)
class Z21CvValue:
  cv_number: int
  value: int
  pom_address: int | None = None
  payload_hex: str = ""

  def to_debug_dict(self) -> dict:
    return {
      "cv": self.cv_number,
      "value": self.value,
      "pom_address": self.pom_address,
      "payload_hex": self.payload_hex,
    }


@dataclass(frozen=True)
class Z21CvAck:
  ack_mode: str
  ack_name: str
  detail: str
  payload_hex: str = ""
  synthetic: bool = False

  def to_debug_dict(self) -> dict:
    return {
      "ack": self.ack_name,
      "ack_mode": self.ack_mode,
      "detail": self.detail,
      "payload_hex": self.payload_hex,
      "synthetic": self.synthetic,
    }


@dataclass(frozen=True)
class Z21LocoInfo:
  address: int
  speed_steps: int
  busy: bool
  speed: int
  direction: str
  functions: dict[int, bool] = field(default_factory=dict)
  payload_hex: str = ""

  def to_debug_dict(self) -> dict:
    return {
      "address": self.address,
      "speed_steps": self.speed_steps,
      "busy": self.busy,
      "speed": self.speed,
      "direction": self.direction,
      "functions": dict(self.functions),
      "payload_hex": self.payload_hex,
    }


@dataclass(frozen=True)
class Z21CommonSettings:
  enable_railcom: bool
  enable_bit_modify_on_long_address: int
  key_stop_mode: int
  programming_type: int
  enable_loconet_current_source: int
  loconet_fast_clock_rate: int
  loconet_mode: int
  expert_settings: int
  purging: int
  bus_settings: int

  def with_railcom(self, enabled: bool):
    return Z21CommonSettings(
      enable_railcom=bool(enabled),
      enable_bit_modify_on_long_address=self.enable_bit_modify_on_long_address,
      key_stop_mode=self.key_stop_mode,
      programming_type=self.programming_type,
      enable_loconet_current_source=self.enable_loconet_current_source,
      loconet_fast_clock_rate=self.loconet_fast_clock_rate,
      loconet_mode=self.loconet_mode,
      expert_settings=self.expert_settings,
      purging=self.purging,
      bus_settings=self.bus_settings,
    )

  def to_payload(self) -> bytes:
    return bytes([
      1 if self.enable_railcom else 0,
      _validate_byte(self.enable_bit_modify_on_long_address, "enable bit modify on long address"),
      _validate_byte(self.key_stop_mode, "key stop mode"),
      _validate_byte(self.programming_type, "programming type"),
      _validate_byte(self.enable_loconet_current_source, "enable LocoNet current source"),
      _validate_byte(self.loconet_fast_clock_rate, "LocoNet fast clock rate"),
      _validate_byte(self.loconet_mode, "LocoNet mode"),
      _validate_byte(self.expert_settings, "expert settings"),
      _validate_byte(self.purging, "purging"),
      _validate_byte(self.bus_settings, "bus settings"),
    ])

  def to_debug_dict(self) -> dict:
    return {
      "enable_railcom": self.enable_railcom,
      "enable_bit_modify_on_long_address": self.enable_bit_modify_on_long_address,
      "key_stop_mode": self.key_stop_mode,
      "programming_type": self.programming_type,
      "enable_loconet_current_source": self.enable_loconet_current_source,
      "loconet_fast_clock_rate": self.loconet_fast_clock_rate,
      "loconet_mode": self.loconet_mode,
      "expert_settings": self.expert_settings,
      "purging": self.purging,
      "bus_settings": self.bus_settings,
      "payload_hex": self.to_payload().hex(" "),
    }


@dataclass(frozen=True)
class Z21MMDCCSettings:
  startup_reset_packet_count: int
  continue_reset_packet_count: int
  program_packet_count: int
  bit_verify_to_one: int
  external_short_circuit_increment: int
  internal_short_circuit_increment: int
  external_short_circuit_limit: int
  internal_short_circuit_limit: int
  programming_ack_current: int
  mmdcc_flags: int
  output_voltage_mv: int
  programming_voltage_mv: int

  @property
  def output_voltage_v(self) -> float:
    return self.output_voltage_mv / 1000

  @property
  def programming_voltage_v(self) -> float:
    return self.programming_voltage_mv / 1000

  def with_voltages(self, *, output_voltage_mv: int, programming_voltage_mv: int):
    return Z21MMDCCSettings(
      startup_reset_packet_count=self.startup_reset_packet_count,
      continue_reset_packet_count=self.continue_reset_packet_count,
      program_packet_count=self.program_packet_count,
      bit_verify_to_one=self.bit_verify_to_one,
      external_short_circuit_increment=self.external_short_circuit_increment,
      internal_short_circuit_increment=self.internal_short_circuit_increment,
      external_short_circuit_limit=self.external_short_circuit_limit,
      internal_short_circuit_limit=self.internal_short_circuit_limit,
      programming_ack_current=self.programming_ack_current,
      mmdcc_flags=self.mmdcc_flags,
      output_voltage_mv=_validate_word(output_voltage_mv, "Z21 output voltage mV"),
      programming_voltage_mv=_validate_word(programming_voltage_mv, "Z21 programming voltage mV"),
    )

  def to_payload(self) -> bytes:
    return b"".join([
      bytes([
        _validate_byte(self.startup_reset_packet_count, "startup reset packet count"),
        _validate_byte(self.continue_reset_packet_count, "continue reset packet count"),
        _validate_byte(self.program_packet_count, "program packet count"),
        _validate_byte(self.bit_verify_to_one, "bit verify to one"),
        _validate_byte(self.external_short_circuit_increment, "external short-circuit increment"),
        _validate_byte(self.internal_short_circuit_increment, "internal short-circuit increment"),
      ]),
      _validate_word(self.external_short_circuit_limit, "external short-circuit limit").to_bytes(2, "little"),
      _validate_word(self.internal_short_circuit_limit, "internal short-circuit limit").to_bytes(2, "little"),
      bytes([
        _validate_byte(self.programming_ack_current, "programming ACK current"),
        _validate_byte(self.mmdcc_flags, "MMDCC flags"),
      ]),
      _validate_word(self.output_voltage_mv, "Z21 output voltage mV").to_bytes(2, "little"),
      _validate_word(self.programming_voltage_mv, "Z21 programming voltage mV").to_bytes(2, "little"),
    ])

  def to_debug_dict(self) -> dict:
    return {
      "startup_reset_packet_count": self.startup_reset_packet_count,
      "continue_reset_packet_count": self.continue_reset_packet_count,
      "program_packet_count": self.program_packet_count,
      "bit_verify_to_one": self.bit_verify_to_one,
      "external_short_circuit_increment": self.external_short_circuit_increment,
      "internal_short_circuit_increment": self.internal_short_circuit_increment,
      "external_short_circuit_limit": self.external_short_circuit_limit,
      "internal_short_circuit_limit": self.internal_short_circuit_limit,
      "programming_ack_current": self.programming_ack_current,
      "mmdcc_flags": self.mmdcc_flags,
      "mmdcc_flags_hex": f"0x{self.mmdcc_flags:02x}",
      "output_voltage_mv": self.output_voltage_mv,
      "output_voltage_v": self.output_voltage_v,
      "programming_voltage_mv": self.programming_voltage_mv,
      "programming_voltage_v": self.programming_voltage_v,
      "payload_hex": self.to_payload().hex(" "),
    }


def parse_serial_number(payload: bytes) -> dict:
  data = _require_length(payload, 4, "serial number")
  serial_number = int.from_bytes(data[:4], "little")
  return {
    "serial_number": serial_number,
    "serial_number_hex": f"{serial_number:08x}",
  }


def parse_hwinfo(payload: bytes) -> dict:
  data = _require_length(payload, 8, "hardware info")
  hardware_type = int.from_bytes(data[:4], "little")
  firmware_version_raw = int.from_bytes(data[4:8], "little")
  return {
    "hardware_type": hardware_type,
    "hardware_type_hex": f"0x{hardware_type:08x}",
    "hardware_type_label": hardware_type_label(hardware_type),
    "firmware_version_raw": firmware_version_raw,
    "firmware_version_hex": f"0x{firmware_version_raw:08x}",
  }


def parse_broadcast_flags(payload: bytes) -> dict:
  data = _require_length(payload, 4, "broadcast flags")
  flags = int.from_bytes(data[:4], "little")
  return {
    "broadcast_flags": flags,
    "broadcast_flags_hex": f"0x{flags:08x}",
  }


def parse_system_state(payload: bytes) -> dict:
  data = _require_length(payload, 14, "system state")
  central_state = data[12]
  central_state_ext = data[13]
  return {
    "main_track_current_ma": int.from_bytes(data[0:2], "little"),
    "programming_track_current_ma": int.from_bytes(data[2:4], "little"),
    "filtered_main_track_current_ma": int.from_bytes(data[4:6], "little"),
    "temperature_c": int.from_bytes(data[6:8], "little", signed=True),
    "supply_voltage_v": int.from_bytes(data[8:10], "little") / 1000,
    "vcc_voltage_v": int.from_bytes(data[10:12], "little") / 1000,
    "central_state": central_state,
    "central_state_hex": f"0x{central_state:02x}",
    "central_state_ext": central_state_ext,
    "central_state_ext_hex": f"0x{central_state_ext:02x}",
    "emergency_stop": bool(central_state & CENTRAL_STATE_EMERGENCY_STOP),
    "track_voltage_off": bool(central_state & CENTRAL_STATE_TRACK_VOLTAGE_OFF),
    "short_circuit": bool(central_state & CENTRAL_STATE_SHORT_CIRCUIT),
    "programming_mode_active": bool(central_state & CENTRAL_STATE_PROGRAMMING_MODE_ACTIVE),
    "temperature_too_high": bool(central_state_ext & CENTRAL_STATE_EXT_TEMPERATURE_TOO_HIGH),
    "input_voltage_low": bool(central_state_ext & CENTRAL_STATE_EXT_INPUT_VOLTAGE_LOW),
    "external_booster_short": bool(central_state_ext & CENTRAL_STATE_EXT_EXTERNAL_BOOSTER_SHORT),
    "internal_short": bool(central_state_ext & CENTRAL_STATE_EXT_INTERNAL_SHORT),
  }


def parse_common_settings(payload: bytes) -> Z21CommonSettings:
  data = bytes(payload or b"")
  if len(data) != 10:
    raise ValueError("Z21 common settings payload requires exactly 10 bytes")
  return Z21CommonSettings(
    enable_railcom=data[0] != 0,
    enable_bit_modify_on_long_address=data[1],
    key_stop_mode=data[2],
    programming_type=data[3],
    enable_loconet_current_source=data[4],
    loconet_fast_clock_rate=data[5],
    loconet_mode=data[6],
    expert_settings=data[7],
    purging=data[8],
    bus_settings=data[9],
  )


def parse_mmdcc_settings(payload: bytes) -> Z21MMDCCSettings:
  data = bytes(payload or b"")
  if len(data) != 16:
    raise ValueError("Z21 MMDCC settings payload requires exactly 16 bytes")
  return Z21MMDCCSettings(
    startup_reset_packet_count=data[0],
    continue_reset_packet_count=data[1],
    program_packet_count=data[2],
    bit_verify_to_one=data[3],
    external_short_circuit_increment=data[4],
    internal_short_circuit_increment=data[5],
    external_short_circuit_limit=int.from_bytes(data[6:8], "little"),
    internal_short_circuit_limit=int.from_bytes(data[8:10], "little"),
    programming_ack_current=data[10],
    mmdcc_flags=data[11],
    output_voltage_mv=int.from_bytes(data[12:14], "little"),
    programming_voltage_mv=int.from_bytes(data[14:16], "little"),
  )


def parse_cv_result(payload: bytes, *, pom_address: int | None = None) -> Z21CvValue:
  data = _require_xbus_payload(payload, 6, "CV result")
  if tuple(data[:2]) != X_CV_RESULT:
    raise ValueError("Z21 CV result must start with XHeader 0x64 DB0 0x14")
  cv_number = ((data[2] << 8) | data[3]) + 1
  return Z21CvValue(
    cv_number=cv_number,
    value=data[4],
    pom_address=pom_address,
    payload_hex=data.hex(" "),
  )


def parse_xbus_ack(payload: bytes) -> Z21CvAck:
  data = _require_xbus_payload(payload, 3, "X-BUS ACK")
  prefix = tuple(data[:2])
  if prefix == X_CV_NACK_SC:
    return Z21CvAck("short_circuit", "LAN_X_CV_NACK_SC", "programming short circuit", data.hex(" "))
  if prefix == X_CV_NACK:
    return Z21CvAck("no_ack", "LAN_X_CV_NACK", "decoder ACK missing", data.hex(" "))
  if prefix == X_UNKNOWN_COMMAND:
    return Z21CvAck("unknown_command", "LAN_X_UNKNOWN_COMMAND", "unknown command", data.hex(" "))
  raise ValueError(f"Unsupported Z21 X-BUS ACK payload: {data.hex(' ')}")


def synthetic_pom_write_ack() -> Z21CvAck:
  return Z21CvAck(
    "ack",
    "LAN_X_CV_POM_WRITE_BYTE_SENT",
    "Z21 LAN protocol defines no reply for POM byte write",
    "",
    True,
  )


def parse_loco_info(payload: bytes) -> Z21LocoInfo:
  data = _require_xbus_payload(payload, 10, "loco info")
  if data[0] != X_LOCO_INFO:
    raise ValueError("Z21 loco info must start with XHeader 0xEF")
  address = ((data[1] & 0x3F) << 8) | data[2]
  speed_steps = _speed_steps_label(data[3] & 0x07)
  speed_direction = data[4]
  functions = _parse_loco_functions(data)
  return Z21LocoInfo(
    address=address,
    speed_steps=speed_steps,
    busy=bool(data[3] & 0x08),
    speed=speed_direction & 0x7F,
    direction="forward" if speed_direction & 0x80 else "reverse",
    functions=functions,
    payload_hex=data.hex(" "),
  )


def hardware_type_label(hardware_type: int) -> str:
  return HARDWARE_TYPE_LABELS.get(int(hardware_type), "Unknown Z21 hardware")


def _require_length(payload: bytes, minimum: int, label: str) -> bytes:
  data = bytes(payload or b"")
  if len(data) < minimum:
    raise ValueError(f"Z21 {label} payload requires at least {minimum} bytes")
  return data


def _require_xbus_payload(payload: bytes, minimum: int, label: str) -> bytes:
  data = _require_length(payload, minimum, label)
  body = data[:-1]
  checksum = data[-1]
  if xbus_xor(body) != checksum:
    raise ValueError(f"Z21 {label} X-BUS checksum mismatch")
  return data


def _validate_byte(value: int, label: str) -> int:
  byte_value = int(value)
  if byte_value < 0 or byte_value > 0xFF:
    raise ValueError(f"{label} must be in 0..255")
  return byte_value


def _validate_word(value: int, label: str) -> int:
  word_value = int(value)
  if word_value < 0 or word_value > 0xFFFF:
    raise ValueError(f"{label} must be in 0..65535")
  return word_value


def _speed_steps_label(code: int) -> int:
  if code == 0:
    return 14
  if code == 2:
    return 28
  if code == 4:
    return 128
  return code


def _parse_loco_functions(data: bytes) -> dict[int, bool]:
  functions = {}
  if len(data) > 5:
    db4 = data[5]
    functions[0] = bool(db4 & 0x10)
    functions[1] = bool(db4 & 0x01)
    functions[2] = bool(db4 & 0x02)
    functions[3] = bool(db4 & 0x04)
    functions[4] = bool(db4 & 0x08)
  for group_index, start in ((6, 5), (7, 13), (8, 21)):
    if len(data) <= group_index:
      continue
    for bit in range(8):
      functions[start + bit] = bool(data[group_index] & (1 << bit))
  if len(data) > 9:
    for bit in range(3):
      functions[29 + bit] = bool(data[9] & (1 << bit))
  return functions

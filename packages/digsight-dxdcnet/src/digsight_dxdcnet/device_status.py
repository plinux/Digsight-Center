"""DXDCNet device status response parsers."""

from digsight_dxdcnet.constants import D9000_CURRENT_LIMIT_STEP_MA


def parse_command_station_status(payload: bytes) -> dict:
  if len(payload) < 5:
    raise ValueError("Command station status payload must contain at least 5 bytes")
  return {
    "bus_voltage_raw": payload[0],
    "bus_current_raw": payload[1],
    "programming_track_voltage_raw": payload[2],
    "programming_track_current_raw": payload[3],
    "programming_track_busy": payload[4] == 0x80,
    "programming_track_status_raw": payload[4],
  }


def parse_booster_status(payload: bytes) -> dict:
  if len(payload) < 7:
    raise ValueError("Booster status payload must contain at least 7 bytes")
  status_raw = payload[6]
  current_alarm = (status_raw & 0x01) == 0x01
  return {
    "set_voltage_raw": payload[0],
    "output_voltage_v": round(payload[1] * 0.1, 3),
    "output_current_a": round(payload[2] * 0.1, 3),
    "temperature_c": payload[3],
    "status_raw": status_raw,
    "power_on": (status_raw & 0x80) == 0x80,
    "dcc_mode": (status_raw & 0x40) == 0,
    "dc_direction_positive": (status_raw & 0x20) == 0x20,
    "auto_report": (status_raw & 0x10) == 0x10,
    "voltage_alarm": (status_raw & 0x04) == 0x04,
    "temperature_alarm": (status_raw & 0x02) == 0x02,
    "current_alarm": current_alarm,
    "short_circuit": current_alarm,
  }


def parse_parameter_response(payload: bytes) -> dict:
  if len(payload) < 2:
    raise ValueError("Parameter response payload must contain address and value")
  value = payload[1]
  result = {
    "param_address": payload[0],
    "value": value,
  }
  if payload[0] in {0x81, 0x82, 0x83, 0x84}:
    result["current_limit_ma"] = value * D9000_CURRENT_LIMIT_STEP_MA
  return result


def format_app_version(hardware_raw: int, software_raw: int) -> str:
  return f"{hardware_raw / 10:.1f}.{software_raw / 10:.1f}"


def parse_version_response(payload: bytes) -> dict:
  if len(payload) < 2:
    raise ValueError("Version response payload must contain hardware and software version")
  return {
    "hardware_version_raw": payload[0],
    "software_version_raw": payload[1],
    "hardware_version": str(payload[0]),
    "software_version": str(payload[1]),
    "app_version": format_app_version(payload[0], payload[1]),
  }


def parse_mac_response(payload: bytes) -> dict:
  if len(payload) < 7:
    raise ValueError("MAC response payload must contain address type and 6 bytes")
  app_order = list(reversed(payload[1:7]))
  return {
    "address_type": payload[0] & 0x01,
    "payload_bytes": list(payload[1:7]),
    "app_order_bytes": app_order,
    "app_order_hex": "".join(f"{value:02X}" for value in app_order),
  }

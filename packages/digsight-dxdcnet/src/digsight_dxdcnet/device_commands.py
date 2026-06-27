"""DXDCNet device status, version and parameter command builders."""

from digsight_dxdcnet.constants import (
  CMD_MAC_REQUEST,
  CMD_PARAMETER_READ,
  CMD_PARAMETER_SET,
  CMD_REQUEST_DEVICE_STATUS,
  CMD_TRACK_OUTPUT,
  CMD_VERSION_REQUEST,
  DEVICE_TYPE_THROTTLE,
  TRACK_OUTPUT_AUTO_REPORT,
  TRACK_OUTPUT_DC_DIRECTION_POSITIVE,
  TRACK_OUTPUT_DC_MODE,
  TRACK_OUTPUT_POWER_ON,
)
from digsight_dxdcnet.frames import build_udp_frame


def _validate_range(name: str, value: int, minimum: int, maximum: int) -> int:
  if not isinstance(value, int):
    raise ValueError(f"{name} must be an integer")
  if value < minimum or value > maximum:
    raise ValueError(f"{name} must be in {minimum}..{maximum}")
  return value


def _validate_device_type(target_type: int) -> int:
  return _validate_range("target_type", target_type, 0, 0x0F)


def _validate_network_id(target_id: int) -> int:
  return _validate_range("target_id", target_id, 0, 0x7F)


def _validate_byte(name: str, value: int) -> int:
  return _validate_range(name, value, 0, 0xFF)


def build_request_device_status_payload(target_type: int, target_id: int) -> bytes:
  return bytes([_validate_device_type(target_type), _validate_network_id(target_id)])


def build_track_output_payload(
  target_id: int,
  powered: bool,
  output_value: int,
  dcc_mode: bool = True,
  auto_report: bool = True,
  dc_direction_positive: bool = True,
) -> bytes:
  target_id = _validate_network_id(target_id)
  output_value = _validate_byte("output_value", output_value)
  status = 0
  if powered:
    status |= TRACK_OUTPUT_POWER_ON
  if not dcc_mode:
    status |= TRACK_OUTPUT_DC_MODE
  if not dcc_mode and dc_direction_positive:
    status |= TRACK_OUTPUT_DC_DIRECTION_POSITIVE
  if auto_report:
    status |= TRACK_OUTPUT_AUTO_REPORT
  return bytes([target_id & 0x7F, status & 0xF0, (output_value if powered else 0) & 0xFF])


def build_read_parameter_payload(target_type: int, target_id: int, param_address: int) -> bytes:
  return bytes([
    _validate_device_type(target_type),
    _validate_network_id(target_id),
    _validate_byte("param_address", param_address),
  ])


def build_write_parameter_payload(target_type: int, target_id: int, param_address: int, value: int) -> bytes:
  return bytes([
    _validate_device_type(target_type),
    _validate_network_id(target_id),
    _validate_byte("param_address", param_address),
    _validate_byte("value", value),
  ])


def build_status_request_frame(client_id: int, target_type: int, target_id: int) -> bytes:
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_REQUEST_DEVICE_STATUS,
    payload=build_request_device_status_payload(target_type, target_id),
  )


def build_track_output_frame(
  client_id: int,
  target_id: int,
  powered: bool,
  output_value: int,
  dcc_mode: bool = True,
  dc_direction_positive: bool = True,
) -> bytes:
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_TRACK_OUTPUT,
    payload=build_track_output_payload(
      target_id,
      powered,
      output_value,
      dcc_mode=dcc_mode,
      dc_direction_positive=dc_direction_positive,
    ),
  )


def build_mac_request_frame(client_id: int, target_type: int, target_id: int) -> bytes:
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_MAC_REQUEST,
    payload=build_request_device_status_payload(target_type, target_id),
  )


def build_version_request_frame(client_id: int, target_type: int, target_id: int) -> bytes:
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_VERSION_REQUEST,
    payload=build_request_device_status_payload(target_type, target_id),
  )


def build_parameter_read_frame(client_id: int, target_type: int, target_id: int, param_address: int) -> bytes:
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_PARAMETER_READ,
    payload=build_read_parameter_payload(target_type, target_id, param_address),
  )


def build_parameter_write_frame(client_id: int, target_type: int, target_id: int, param_address: int, value: int) -> bytes:
  return build_udp_frame(
    device_type=DEVICE_TYPE_THROTTLE,
    source_id=client_id,
    command=CMD_PARAMETER_SET,
    payload=build_write_parameter_payload(target_type, target_id, param_address, value),
  )

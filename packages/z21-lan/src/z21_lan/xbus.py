"""X-BUS/XPressNet helpers inside Z21 LAN_X datasets."""


def xbus_xor(payload) -> int:
  """Calculate the X-BUS XOR checksum over payload bytes."""
  checksum = 0
  for value in payload:
    checksum ^= int(value) & 0xFF
  return checksum


def build_lan_x_payload(*payload_bytes: int) -> bytes:
  """Build a LAN_X payload and append the X-BUS XOR checksum."""
  payload = bytes(int(value) & 0xFF for value in payload_bytes)
  return payload + bytes([xbus_xor(payload)])

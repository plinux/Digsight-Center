"""UDP transport for DXDCNet gateway."""

import socket

UDP_PORT_MIN = 1
UDP_PORT_MAX = 65535
LOCAL_UDP_PORT_MIN = 0


def _expected_ipv4_addresses(host: str) -> set[str]:
  try:
    infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_DGRAM)
  except socket.gaierror as exc:
    raise ValueError(f"Invalid UDP host: {host}") from exc
  addresses = {info[4][0] for info in infos}
  if not addresses:
    raise ValueError(f"Invalid UDP host: {host}")
  return addresses


def _is_expected_sender(address, expected_addresses: set[str], expected_port: int) -> bool:
  return address[0] in expected_addresses and int(address[1]) == int(expected_port)


def _validate_udp_port(port: int) -> int:
  normalized = int(port)
  if normalized < UDP_PORT_MIN or normalized > UDP_PORT_MAX:
    raise ValueError("UDP port must be in range 1..65535")
  return normalized


def _validate_local_udp_port(port: int) -> int:
  normalized = int(port)
  if normalized < LOCAL_UDP_PORT_MIN or normalized > UDP_PORT_MAX:
    raise ValueError("Local UDP port must be in range 0..65535")
  return normalized


class UDPTransport:
  def __init__(self, timeout_seconds=1.0, retries=1):
    self.timeout_seconds = timeout_seconds
    self.retries = retries

  def request(self, host: str, port: int, payload: bytes) -> bytes:
    port = _validate_udp_port(port)

    expected_addresses = _expected_ipv4_addresses(host)
    last_timeout = None
    for _attempt in range(self.retries + 1):
      sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
      sock.settimeout(self.timeout_seconds)
      try:
        sock.sendto(payload, (host, port))
        while True:
          data, address = sock.recvfrom(4096)
          if _is_expected_sender(address, expected_addresses, port):
            return data
      except socket.timeout as exc:
        last_timeout = exc
      finally:
        sock.close()
    raise TimeoutError(f"UDP receive timed out after {self.timeout_seconds} seconds") from last_timeout

  def exchange(self, host: str, port: int, payload: bytes, local_port: int = 0, max_packets: int = 32, stop_when=None) -> list[bytes]:
    port = _validate_udp_port(port)
    local_port = _validate_local_udp_port(local_port)

    expected_addresses = _expected_ipv4_addresses(host)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(self.timeout_seconds)
    try:
      if local_port > 0:
        sock.bind(("0.0.0.0", local_port))
      sock.sendto(payload, (host, port))
      responses = []
      while len(responses) < max_packets:
        try:
          data, address = sock.recvfrom(4096)
        except socket.timeout:
          break
        if not _is_expected_sender(address, expected_addresses, port):
          continue
        responses.append(data)
        if stop_when and stop_when(data):
          break
      return responses
    finally:
      sock.close()

"""UDP transport helpers for Z21 LAN."""

import socket

from z21_lan.constants import DEFAULT_Z21_PORT


class Z21UDPTransport:
  """Exchange one UDP request with a Z21 controller."""

  def __init__(self, timeout_seconds: float = 1.0, retries: int = 0):
    self.timeout_seconds = float(timeout_seconds)
    self.retries = int(retries)

  def exchange(
    self,
    host: str,
    port: int = DEFAULT_Z21_PORT,
    payload: bytes = b"",
    *,
    local_port: int = 0,
    max_packets: int = 8,
    stop_when=None,
    timeout_seconds: float | None = None,
  ) -> list[bytes]:
    normalized_port = _validate_port(port, "Z21 UDP port")
    normalized_local_port = _validate_port(local_port, "Z21 local UDP port", allow_zero=True)
    expected_sources = _expected_source_addresses(host, normalized_port)
    active_timeout = float(timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
    responses = []
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
      sock.settimeout(active_timeout)
      sock.bind(("", normalized_local_port))
      for attempt in range(self.retries + 1):
        sock.sendto(bytes(payload or b""), (host, normalized_port))
        try:
          while len(responses) < max_packets:
            data, source = sock.recvfrom(4096)
            if source[0] not in expected_sources or source[1] != normalized_port:
              continue
            responses.append(data)
            if stop_when and stop_when(data):
              return responses
            if not stop_when:
              return responses
        except socket.timeout:
          if attempt >= self.retries:
            break
    if not responses:
      raise TimeoutError("Z21 UDP exchange timed out")
    return responses


class Z21SessionManager:
  """Session facade used by controller adapters."""

  def __init__(self, transport=None):
    self.transport = transport

  def exchange(
    self,
    host: str,
    port: int,
    payload: bytes,
    *,
    local_port: int = 0,
    max_packets: int = 8,
    stop_when=None,
    timeout_seconds: float | None = None,
  ) -> list[bytes]:
    transport = self.transport or Z21UDPTransport()
    kwargs = {
      "local_port": local_port,
      "max_packets": max_packets,
      "stop_when": stop_when,
    }
    if timeout_seconds is not None:
      kwargs["timeout_seconds"] = timeout_seconds
    return transport.exchange(host, port, payload, **kwargs)


def _validate_port(value, label: str, *, allow_zero: bool = False) -> int:
  port = int(value)
  minimum = 0 if allow_zero else 1
  if port < minimum or port > 65535:
    raise ValueError(f"{label} must be in {minimum}..65535")
  return port


def _expected_source_addresses(host: str, port: int) -> set[str]:
  try:
    infos = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_DGRAM)
  except socket.gaierror:
    return {host}
  return {info[4][0] for info in infos}

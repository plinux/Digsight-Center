"""TCP transport helpers for the ESU ECoS PC Interface."""

import socket

from esu_ecos.blocks import parse_blocks
from esu_ecos.commands import DEFAULT_ECOS_PORT


class ECoSTCPTransport:
  """Open a short-lived TCP connection and exchange ECoS text commands."""

  def __init__(self, timeout_seconds: float = 2.0):
    self.timeout_seconds = float(timeout_seconds)

  def exchange(
    self,
    host: str,
    port: int = DEFAULT_ECOS_PORT,
    commands=None,
    *,
    timeout_seconds: float | None = None,
    expected_replies: int = 1,
    expected_events: int = 0,
  ) -> str:
    normalized_port = int(port)
    if normalized_port <= 0 or normalized_port > 65535:
      raise ValueError("ECoS TCP port must be in 1..65535")
    command_text = _commands_text(commands)
    timeout = float(timeout_seconds if timeout_seconds is not None else self.timeout_seconds)
    with socket.create_connection((host, normalized_port), timeout=timeout) as sock:
      sock.settimeout(timeout)
      sock.sendall(command_text.encode("ascii"))
      return _read_until_expected_blocks(sock, expected_replies, expected_events)


class ECoSSessionManager:
  """Session facade used by controller adapters."""

  def __init__(self, transport=None):
    self.transport = transport

  def exchange(
    self,
    host: str,
    port: int,
    commands,
    *,
    timeout_seconds: float | None = None,
    expected_replies: int = 1,
    expected_events: int = 0,
  ) -> str:
    transport = self.transport or ECoSTCPTransport(timeout_seconds=timeout_seconds or 2.0)
    return transport.exchange(
      host,
      port,
      commands,
      timeout_seconds=timeout_seconds,
      expected_replies=expected_replies,
      expected_events=expected_events,
    )


def _commands_text(commands) -> str:
  if isinstance(commands, str):
    command_lines = [commands]
  else:
    command_lines = [str(command) for command in commands or []]
  command_lines = [line.strip() for line in command_lines if line.strip()]
  if not command_lines:
    raise ValueError("ECoS exchange requires at least one command")
  return "\n".join(command_lines) + "\n"


def _read_until_expected_blocks(sock, expected_replies: int, expected_events: int) -> str:
  chunks = []
  while True:
    try:
      chunk = sock.recv(4096)
    except socket.timeout as exc:
      raise TimeoutError("ECoS TCP exchange timed out") from exc
    if not chunk:
      break
    chunks.append(chunk)
    text = b"".join(chunks).decode("ascii", errors="replace")
    try:
      blocks = parse_blocks(text)
    except ValueError:
      continue
    reply_count = sum(1 for block in blocks if block.kind == "REPLY")
    event_count = sum(1 for block in blocks if block.kind == "EVENT")
    if reply_count >= expected_replies and event_count >= expected_events:
      return text
  if not chunks:
    raise TimeoutError("ECoS TCP exchange returned no data")
  text = b"".join(chunks).decode("ascii", errors="replace")
  try:
    blocks = parse_blocks(text)
  except ValueError as exc:
    raise TimeoutError("ECoS TCP exchange ended before a complete reply was received") from exc
  reply_count = sum(1 for block in blocks if block.kind == "REPLY")
  event_count = sum(1 for block in blocks if block.kind == "EVENT")
  raise TimeoutError(
    f"ECoS TCP exchange returned {reply_count} of {expected_replies} expected replies "
    f"and {event_count} of {expected_events} expected events"
  )

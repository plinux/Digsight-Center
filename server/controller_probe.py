"""Read-only controller reachability probing."""

from dataclasses import dataclass
import subprocess
from typing import Callable, Sequence, Tuple


ProbeRunner = Callable[[Sequence[str]], Tuple[int, str, str]]


@dataclass(frozen=True)
class ProbeResult:
  ok: bool
  detail: str


def probe_ip(ip: str) -> ProbeResult:
  """Probe a controller IP with the system ping command."""
  return probe_ip_with_runner(ip, _subprocess_runner)


def probe_ip_with_runner(ip: str, runner: ProbeRunner) -> ProbeResult:
  """Probe a controller IP using an injectable command runner."""
  command = ["ping", "-c", "2", "-W", "1000", ip]
  exit_code, stdout, stderr = runner(command)
  detail = (stdout if exit_code == 0 else stderr or stdout).strip()
  if not detail:
    detail = "reachable" if exit_code == 0 else "no response"
  return ProbeResult(ok=exit_code == 0, detail=detail)


def _subprocess_runner(command: Sequence[str]) -> Tuple[int, str, str]:
  completed = subprocess.run(
    list(command),
    capture_output=True,
    check=False,
    text=True,
    timeout=4,
  )
  return completed.returncode, completed.stdout, completed.stderr

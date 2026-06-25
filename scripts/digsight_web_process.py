#!/usr/bin/env python3
"""Classify Digsight-Center web gateway pid files."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable


ProcessExists = Callable[[int], bool]
ProcessReader = Callable[[int], str]


def read_pid_record(pid_file: Path) -> dict:
  """Read a structured JSON pid file."""
  raw = pid_file.read_text(encoding="utf-8").strip()
  record = json.loads(raw)
  if not isinstance(record, dict):
    raise ValueError("invalid JSON pid file: expected object")
  return {
    "pid": int(record.get("pid", 0)),
    "project_root": str(record.get("project_root", "")),
    "command": list(record.get("command") or []),
  }


def process_exists(pid: int) -> bool:
  """Return whether the OS still has a process with this pid."""
  try:
    os.kill(pid, 0)
  except OSError:
    return False
  return True


def process_command(pid: int) -> str:
  """Return the process command line, or an empty string when unavailable."""
  try:
    return subprocess.check_output(["ps", "-p", str(pid), "-o", "command="], text=True).strip()
  except (OSError, subprocess.CalledProcessError):
    return ""


def process_cwd(pid: int) -> str:
  """Return the process current working directory, or an empty string."""
  proc_cwd = Path(f"/proc/{pid}/cwd")
  if proc_cwd.exists():
    try:
      return str(proc_cwd.resolve())
    except OSError:
      return ""
  try:
    output = subprocess.check_output(["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"], text=True)
  except (OSError, subprocess.CalledProcessError):
    return ""
  for line in output.splitlines():
    if line.startswith("n"):
      return line[1:]
  return ""


def gateway_process_matches(
  record: dict,
  project_root: Path,
  *,
  process_exists: ProcessExists = process_exists,
  command_reader: ProcessReader = process_command,
  cwd_reader: ProcessReader = process_cwd,
) -> bool:
  """Return whether the pid record points at this project's gateway process."""
  pid = int(record.get("pid", 0))
  if pid <= 0 or not process_exists(pid):
    return False
  expected_root = project_root.resolve()
  recorded_root = Path(record.get("project_root") or project_root).resolve()
  if recorded_root != expected_root:
    return False
  command = command_reader(pid)
  if "server.main" not in command:
    return False
  cwd = cwd_reader(pid)
  return bool(cwd) and Path(cwd).resolve() == expected_root


def classify_pid_file(
  pid_file: Path,
  project_root: Path,
  *,
  process_exists: ProcessExists = process_exists,
  command_reader: ProcessReader = process_command,
  cwd_reader: ProcessReader = process_cwd,
) -> tuple[str, int, str]:
  """Classify a pid file as match, stale, mismatch, or invalid."""
  try:
    record = read_pid_record(pid_file)
  except json.JSONDecodeError as exc:
    return "invalid", 0, f"invalid JSON pid file: {exc}"
  except (OSError, ValueError) as exc:
    return "invalid", 0, str(exc)
  pid = int(record.get("pid", 0))
  if pid <= 0:
    return "invalid", 0, "missing positive pid"
  if gateway_process_matches(
    record,
    project_root,
    process_exists=process_exists,
    command_reader=command_reader,
    cwd_reader=cwd_reader,
  ):
    return "match", pid, ""
  if not process_exists(pid):
    return "stale", pid, ""
  return "mismatch", pid, command_reader(pid)


def _main(argv: list[str]) -> int:
  if len(argv) != 4 or argv[1] != "classify":
    print("Usage: digsight_web_process.py classify PID_FILE PROJECT_ROOT", file=sys.stderr)
    return 2
  status, pid, detail = classify_pid_file(Path(argv[2]), Path(argv[3]))
  print(f"{status}\t{pid}\t{detail}")
  return 0


if __name__ == "__main__":
  raise SystemExit(_main(sys.argv))

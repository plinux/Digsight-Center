#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

PYTHON_CMD="python3"
WEB_HOST="0.0.0.0"
WEB_PORT="8765"
RUNTIME_DIR="${PROJECT_ROOT}/data"
PID_FILE="${RUNTIME_DIR}/digsight-center-web.pid"
LOG_FILE="${RUNTIME_DIR}/digsight-center-web.log"

usage() {
  cat <<'USAGE'
Usage: ./scripts/start_web.sh [-H HOST] [-P PORT] [--python PYTHON]

Options:
  -H, --host HOST       HTTP listen host. Default: 0.0.0.0
  -P, --port PORT       HTTP listen port. Default: 8765
      --python PYTHON   Python 3.10+ interpreter. Default: python3
  -h, --help            Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -H|--host)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        echo "Missing value for $1" >&2
        usage >&2
        exit 2
      fi
      WEB_HOST="$2"
      shift 2
      ;;
    -P|--port)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        echo "Missing value for $1" >&2
        usage >&2
        exit 2
      fi
      WEB_PORT="$2"
      shift 2
      ;;
    --python)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        echo "Missing value for $1" >&2
        usage >&2
        exit 2
      fi
      PYTHON_CMD="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ ! "${WEB_PORT}" =~ ^[0-9]+$ ]]; then
  echo "Port must be an integer: ${WEB_PORT}" >&2
  exit 2
fi

"${PYTHON_CMD}" - <<'PY'
import sys

if sys.version_info < (3, 10):
  print(
    f"Digsight-Center requires Python 3.10 or newer; current Python is {sys.version.split()[0]}. "
    "Use --python to pass a Python 3.10+ interpreter.",
    file=sys.stderr,
  )
  raise SystemExit(2)
PY

mkdir -p "${RUNTIME_DIR}"

if [[ -f "${PID_FILE}" ]]; then
  EXISTING_PID="$(tr -d '[:space:]' < "${PID_FILE}" || true)"
  if [[ "${EXISTING_PID}" =~ ^[0-9]+$ ]] && kill -0 "${EXISTING_PID}" 2>/dev/null; then
    echo "Digsight-Center gateway is already running with PID ${EXISTING_PID}." >&2
    echo "Use ./scripts/stop_web.sh before starting it again." >&2
    exit 1
  fi
  rm -f "${PID_FILE}"
fi

"${PYTHON_CMD}" - "${PYTHON_CMD}" "${PROJECT_ROOT}" "${WEB_HOST}" "${WEB_PORT}" "${PID_FILE}" "${LOG_FILE}" <<'PY'
import os
import subprocess
import sys
import time
from pathlib import Path

python_cmd, project_root, web_host, web_port, pid_file, log_file = sys.argv[1:]
Path(log_file).parent.mkdir(parents=True, exist_ok=True)

with open(log_file, "ab", buffering=0) as log:
  process = subprocess.Popen(
    [python_cmd, "-m", "server.main", "--host", web_host, "--port", web_port],
    cwd=project_root,
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    start_new_session=True,
  )

time.sleep(0.8)
if process.poll() is not None:
  print(
    f"Digsight-Center gateway failed to start; see {log_file}",
    file=sys.stderr,
  )
  raise SystemExit(process.returncode or 1)

temporary_pid_file = f"{pid_file}.tmp"
with open(temporary_pid_file, "w", encoding="utf-8") as handle:
  handle.write(f"{process.pid}\n")
os.replace(temporary_pid_file, pid_file)

print(f"Digsight-Center gateway started in background with PID {process.pid}.")
print(f"Listening on http://{web_host}:{web_port}/")
print(f"Log file: {log_file}")
print("Use ./scripts/stop_web.sh to stop the gateway.")
PY

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

PYTHON_CMD="python3"
WEB_HOST="0.0.0.0"
WEB_PORT="8765"
TRUSTED_HOSTS=()
RUNTIME_DIR="${PROJECT_ROOT}/data"
PID_FILE="${RUNTIME_DIR}/digsight-center-web.pid"
LOG_FILE="${RUNTIME_DIR}/digsight-center-web.log"
PROCESS_HELPER="${SCRIPT_DIR}/digsight_web_process.py"

usage() {
  cat <<'USAGE'
Usage: ./scripts/start_web.sh [-H HOST] [-P PORT] [--python PYTHON]

Options:
  -H, --host HOST       HTTP listen host. Default: 0.0.0.0
  -P, --port PORT       HTTP listen port. Default: 8765
      --trusted-host HOST
                        Additional DNS host allowed by Host/Origin checks.
                        Repeat this option to allow multiple names.
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
    --trusted-host)
      if [[ $# -lt 2 || "$2" == -* ]]; then
        echo "Missing value for $1" >&2
        usage >&2
        exit 2
      fi
      TRUSTED_HOSTS+=("$2")
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
  PID_INFO="$("${PYTHON_CMD}" "${PROCESS_HELPER}" classify "${PID_FILE}" "${PROJECT_ROOT}")"
  PID_STATUS="${PID_INFO%%$'\t'*}"
  PID_REST="${PID_INFO#*$'\t'}"
  EXISTING_PID="${PID_REST%%$'\t'*}"
  if [[ "${PID_STATUS}" == "match" ]]; then
    echo "Digsight-Center gateway is already running with PID ${EXISTING_PID}." >&2
    echo "Use ./scripts/stop_web.sh before starting it again." >&2
    exit 1
  fi
  rm -f "${PID_FILE}"
fi

START_ARGS=("${PYTHON_CMD}" "${PROJECT_ROOT}" "${WEB_HOST}" "${WEB_PORT}" "${PID_FILE}" "${LOG_FILE}")
if [[ ${#TRUSTED_HOSTS[@]} -gt 0 ]]; then
  START_ARGS+=("${TRUSTED_HOSTS[@]}")
fi

"${PYTHON_CMD}" - "${START_ARGS[@]}" <<'PY'
import json
import os
import subprocess
import sys
import time
from pathlib import Path

python_cmd, project_root, web_host, web_port, pid_file, log_file = sys.argv[1:7]
trusted_hosts = sys.argv[7:]
Path(log_file).parent.mkdir(parents=True, exist_ok=True)
command = [python_cmd, "-m", "server.main", "--host", web_host, "--port", web_port]
for trusted_host in trusted_hosts:
  command.extend(["--trusted-host", trusted_host])
package_paths = [
  str(Path(project_root) / "packages" / "train-dcc" / "src"),
  str(Path(project_root) / "packages" / "digsight-dxdcnet" / "src"),
]
env = os.environ.copy()
existing_python_path = env.get("PYTHONPATH", "")
env["PYTHONPATH"] = os.pathsep.join([*package_paths, *([existing_python_path] if existing_python_path else [])])

with open(log_file, "ab", buffering=0) as log:
  process = subprocess.Popen(
    command,
    cwd=project_root,
    env=env,
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
  json.dump(
    {
      "pid": process.pid,
      "project_root": project_root,
      "command": command,
    },
    handle,
    ensure_ascii=False,
    indent=2,
  )
  handle.write("\n")
os.replace(temporary_pid_file, pid_file)

print(f"Digsight-Center gateway started in background with PID {process.pid}.")
print(f"Listening on http://{web_host}:{web_port}/")
print(f"Log file: {log_file}")
print("Use ./scripts/stop_web.sh to stop the gateway.")
PY

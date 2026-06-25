#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${PROJECT_ROOT}/data/digsight-center-web.pid"
PROCESS_HELPER="${SCRIPT_DIR}/digsight_web_process.py"
PYTHON_CMD="python3"

usage() {
  cat <<'USAGE'
Usage: ./scripts/stop_web.sh [--python PYTHON]

Stops the Digsight-Center gateway process started by ./scripts/start_web.sh.

Options:
      --python PYTHON   Python 3.10+ interpreter. Default: python3
  -h, --help            Show this help.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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

if [[ ! -f "${PID_FILE}" ]]; then
  echo "Digsight-Center gateway is not running: PID file not found."
  exit 0
fi

PID_INFO="$("${PYTHON_CMD}" "${PROCESS_HELPER}" classify "${PID_FILE}" "${PROJECT_ROOT}")"
PID_STATUS="${PID_INFO%%$'\t'*}"
PID_REST="${PID_INFO#*$'\t'}"
PID="${PID_REST%%$'\t'*}"
PID_DETAIL="${PID_REST#*$'\t'}"

if [[ "${PID_STATUS}" == "invalid" ]]; then
  echo "Invalid PID file: ${PID_FILE}" >&2
  rm -f "${PID_FILE}"
  exit 1
fi

if [[ "${PID_STATUS}" == "stale" ]]; then
  echo "Digsight-Center gateway PID ${PID} is not running; removing stale PID file."
  rm -f "${PID_FILE}"
  exit 0
fi

if [[ "${PID_STATUS}" != "match" ]]; then
  echo "Refusing to stop PID ${PID}: it does not match this Digsight-Center gateway." >&2
  if [[ -n "${PID_DETAIL}" ]]; then
    echo "Process command: ${PID_DETAIL}" >&2
  fi
  rm -f "${PID_FILE}"
  exit 1
fi

kill "${PID}"
for _ in {1..50}; do
  if ! kill -0 "${PID}" 2>/dev/null; then
    rm -f "${PID_FILE}"
    echo "Digsight-Center gateway stopped."
    exit 0
  fi
  sleep 0.1
done

echo "Digsight-Center gateway did not stop gracefully; sending SIGKILL." >&2
kill -KILL "${PID}" 2>/dev/null || true
rm -f "${PID_FILE}"
echo "Digsight-Center gateway stopped."

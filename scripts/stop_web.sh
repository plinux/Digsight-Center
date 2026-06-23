#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${PROJECT_ROOT}/data/digsight-center-web.pid"

usage() {
  cat <<'USAGE'
Usage: ./scripts/stop_web.sh

Stops the Digsight-Center gateway process started by ./scripts/start_web.sh.
USAGE
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -gt 0 ]]; then
  echo "Unknown option: $1" >&2
  usage >&2
  exit 2
fi

if [[ ! -f "${PID_FILE}" ]]; then
  echo "Digsight-Center gateway is not running: PID file not found."
  exit 0
fi

PID="$(tr -d '[:space:]' < "${PID_FILE}" || true)"
if [[ ! "${PID}" =~ ^[0-9]+$ ]]; then
  echo "Invalid PID file: ${PID_FILE}" >&2
  rm -f "${PID_FILE}"
  exit 1
fi

if ! kill -0 "${PID}" 2>/dev/null; then
  echo "Digsight-Center gateway PID ${PID} is not running; removing stale PID file."
  rm -f "${PID_FILE}"
  exit 0
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

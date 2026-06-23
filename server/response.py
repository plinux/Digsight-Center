"""HTTP JSON response helpers."""

import json
from typing import Any, Dict, Optional


def success(data: Any, debug: Optional[Dict[str, Any]] = None) -> bytes:
  payload = {
    "ok": True,
    "data": data,
    "error": None,
    "debug": debug or {"warnings": []},
  }
  return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def failure(error_type: str, message: str, detail: str = "", debug: Optional[Dict[str, Any]] = None) -> bytes:
  payload = {
    "ok": False,
    "data": None,
    "error": {
      "type": error_type,
      "message": message,
      "detail": detail,
    },
    "debug": debug or {"warnings": []},
  }
  return json.dumps(payload, ensure_ascii=False).encode("utf-8")

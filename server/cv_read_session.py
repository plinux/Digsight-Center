"""Cancelable CV list read sessions."""

from __future__ import annotations

import threading


class CVReadSessionRegistry:
  def __init__(self):
    self._lock = threading.Lock()
    self._cancelled = set()

  def start(self, session_id: str) -> str:
    normalized = self._normalize(session_id)
    with self._lock:
      self._cancelled.discard(normalized)
    return normalized

  def cancel(self, session_id: str) -> str:
    normalized = self._normalize(session_id)
    with self._lock:
      self._cancelled.add(normalized)
    return normalized

  def is_cancelled(self, session_id: str) -> bool:
    normalized = self._normalize(session_id)
    with self._lock:
      return normalized in self._cancelled

  def finish(self, session_id: str) -> None:
    normalized = self._normalize(session_id)
    with self._lock:
      self._cancelled.discard(normalized)

  def _normalize(self, session_id: str) -> str:
    text = str(session_id or "").strip()
    if not text:
      raise ValueError("session_id is required")
    if len(text) > 80:
      raise ValueError("session_id is too long")
    return text

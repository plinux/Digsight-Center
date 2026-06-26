"""Internal helpers for CV read/write API operations."""

from dataclasses import dataclass


@dataclass
class CvOperationContext:
  cv_number: int
  client_id: int
  request_frame: bytes
  pom_address: int | None = None

  @property
  def request_hex(self) -> str:
    return self.request_frame.hex(" ")


def cv_debug(context: CvOperationContext, *, responses=None, extra=None) -> dict:
  debug = {
    "cv": context.cv_number,
    "client_id": context.client_id,
    "pom_address": context.pom_address,
    "request_hex": context.request_hex,
    "responses": responses or [],
  }
  if extra:
    debug.update(extra)
  return debug


def readback_value_matches(readback: dict, expected_value: int) -> bool:
  return int(readback["value"]) == int(expected_value)


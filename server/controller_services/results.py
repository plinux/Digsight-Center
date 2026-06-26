"""Typed controller-service results independent from HTTP serialization."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ServiceResult:
  ok: bool
  data: object = None
  status: int = 200
  error_type: str = ""
  message: str = ""
  detail: str = ""
  debug: object = None

  @classmethod
  def success(cls, data, *, status: int = 200):
    return cls(ok=True, data=data, status=status)

  @classmethod
  def failure(cls, error_type: str, message: str, detail: str = "", *, status: int = 400, debug=None):
    return cls(
      ok=False,
      status=status,
      error_type=error_type,
      message=message,
      detail=detail,
      debug=debug,
    )

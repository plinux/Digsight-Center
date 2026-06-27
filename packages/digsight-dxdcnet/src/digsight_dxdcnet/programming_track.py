"""Programming-track safety and CV request planning helpers."""

from dataclasses import dataclass

from digsight_dxdcnet.programmer import build_cv_read_frame, build_cv_write_frame

SERVICE_MODE_CURRENT_LIMIT_MAX_MA = 250
PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED = "编程轨限流未确认"


@dataclass(frozen=True)
class ProgrammingTrackStatus:
  track_mode: str
  dcc_mode: bool
  programming_track_busy: bool
  programming_track_current_ma: int
  output_value: int
  current_limit_ma: int
  current_limit_confirmed: bool = True


class ProgrammingTrackSafety:
  def validate(self, status: ProgrammingTrackStatus) -> None:
    if status.track_mode not in {"n", "ho", "g"}:
      raise ValueError("编程轨必须使用 N、HO 或 G 的 DCC 数码模式")
    if not status.dcc_mode:
      raise ValueError("编程轨必须是 DCC 模式，不能是 DC 模式")
    if status.programming_track_busy:
      raise ValueError("编程轨正忙")
    if status.current_limit_confirmed and status.current_limit_ma <= 0:
      raise ValueError(PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED)
    if status.current_limit_confirmed and status.current_limit_ma > SERVICE_MODE_CURRENT_LIMIT_MAX_MA:
      raise ValueError(f"编程轨限流超过 {SERVICE_MODE_CURRENT_LIMIT_MAX_MA} mA 编程模式上限")
    if status.programming_track_current_ma > 100:
      raise ValueError("编程轨空闲电流超过安全阈值")


@dataclass(frozen=True)
class CVReadPlan:
  cv_number: int

  def request_frame(self, client_id: int = 1):
    return build_cv_read_frame(self.cv_number, client_id=client_id)


@dataclass(frozen=True)
class CVWritePlan:
  cv_number: int
  value: int

  def request_frame(self, client_id: int = 1):
    return build_cv_write_frame(self.cv_number, self.value, client_id=client_id)


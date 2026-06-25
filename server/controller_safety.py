"""Controller safety snapshot helpers."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ControllerSafetySnapshot:
  controller_endpoint_version: int = 0
  last_read_info_at: str = ""
  booster_status_fresh: bool = False
  programming_track_status_fresh: bool = False

  @classmethod
  def from_controller(cls, controller: dict):
    existing = controller.get("safety_snapshot", {})
    if not isinstance(existing, dict):
      existing = {}
    return cls(
      controller_endpoint_version=int(existing.get("controller_endpoint_version", 0) or 0),
      last_read_info_at=str(existing.get("last_read_info_at", "") or ""),
      booster_status_fresh=bool(existing.get("booster_status_fresh", False)),
      programming_track_status_fresh=bool(existing.get("programming_track_status_fresh", False)),
    )

  def to_dict(self) -> dict:
    return {
      "controller_endpoint_version": self.controller_endpoint_version,
      "last_read_info_at": self.last_read_info_at,
      "booster_status_fresh": self.booster_status_fresh,
      "programming_track_status_fresh": self.programming_track_status_fresh,
    }


def invalidate_controller_safety(controller: dict, *, reason: str) -> None:
  snapshot = ControllerSafetySnapshot.from_controller(controller)
  controller["last_probe_ok"] = False
  controller["controller_reachable"] = False
  controller["controller_unreachable_reason"] = reason
  controller.pop("booster_status", None)
  controller.pop("programming_track_status", None)
  controller["safety_snapshot"] = ControllerSafetySnapshot(
    controller_endpoint_version=snapshot.controller_endpoint_version + 1,
    last_read_info_at=snapshot.last_read_info_at,
    booster_status_fresh=False,
    programming_track_status_fresh=False,
  ).to_dict()


def mark_controller_safety_fresh(
  controller: dict,
  *,
  booster_status_fresh: bool | None = None,
  programming_track_status_fresh: bool | None = None,
) -> None:
  snapshot = ControllerSafetySnapshot.from_controller(controller)
  controller["safety_snapshot"] = ControllerSafetySnapshot(
    controller_endpoint_version=snapshot.controller_endpoint_version,
    last_read_info_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    booster_status_fresh=snapshot.booster_status_fresh if booster_status_fresh is None else bool(booster_status_fresh),
    programming_track_status_fresh=(
      snapshot.programming_track_status_fresh
      if programming_track_status_fresh is None
      else bool(programming_track_status_fresh)
    ),
  ).to_dict()

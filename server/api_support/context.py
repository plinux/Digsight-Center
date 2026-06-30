"""Explicit dependencies shared by API support modules."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from server.controller_safety import ControllerSafetySnapshot, invalidate_controller_safety, mark_controller_safety_fresh


@dataclass
class ApiSupportContext:
  state_store: Any
  vehicle_store: Any
  controller_registry: Any
  import_registry: Any
  cv_read_sessions: Any
  image_dir: Path
  controller_transport: Any

  def save(self, state: dict) -> None:
    if not self.state_store:
      return
    persistent_state = self.persistent_state(state)
    if "_expected_controller_runtime_revision" in state:
      state["_pending_persistent_state"] = persistent_state
      return
    self.state_store.save(persistent_state)

  def persistent_state(self, state: dict) -> dict:
    persistent_state = {key: value for key, value in state.items() if not key.startswith("_")}
    persistent_state["vehicles"] = []
    persistent_state["functions"] = []
    persistent_state["categories"] = []
    persistent_state["consists"] = []
    persistent_state["imports"] = []
    return persistent_state

  def state_with_vehicle_store_data(self, state: dict) -> dict:
    self.refresh_vehicle_store_data(state)
    return state

  def refresh_vehicle_store_data(self, state: dict) -> None:
    state["vehicles"] = self.vehicle_store.list_vehicles_with_details()
    state["functions"] = self.vehicle_store.list_all_functions()
    state["categories"] = self.vehicle_store.list_categories()
    state["consists"] = self.vehicle_store.list_consists()

  def default_safety_snapshot(self, controller: dict) -> dict:
    return ControllerSafetySnapshot.from_controller(controller).to_dict()

  def invalidate_controller_runtime_safety(self, controller: dict, *, reason: str) -> None:
    controller["runtime_revision"] = int(controller.get("runtime_revision", 0) or 0) + 1
    invalidate_controller_safety(controller, reason=reason)

  def mark_safety_snapshot_fresh(
    self,
    controller: dict,
    *,
    booster_status_fresh: bool | None = None,
    programming_track_status_fresh: bool | None = None,
  ) -> None:
    mark_controller_safety_fresh(
      controller,
      booster_status_fresh=booster_status_fresh,
      programming_track_status_fresh=programming_track_status_fresh,
    )

  def mark_controller_unreachable(self, state: dict, reason: str) -> None:
    controller = state["controller"]
    self.invalidate_controller_runtime_safety(controller, reason=reason)
    self.save(state)

import json
import unittest

from server.api import ApiRouter
from server.app_state import default_state
from server.controllers.base import ControllerCapabilities, ControllerOperationNotSupported
from server.controllers.registry import ControllerRegistry


class UnsupportedControllerAdapter:
  kind = "unsupported_controller"
  label = "Unsupported Controller"
  config_file_name = "unsupported_controller.json"
  capabilities = ControllerCapabilities(
    track_power=False,
    dc_control=False,
    read_info=False,
    cv_programming=False,
    loco_control=False,
    controller_settings=False,
  )

  def read_info_frames(self, *args, **kwargs):
    raise ControllerOperationNotSupported("read_info", self.kind)

  def send_track_output(self, *args, **kwargs):
    raise ControllerOperationNotSupported("track_power", self.kind)

  def read_cv(self, *args, **kwargs):
    raise ControllerOperationNotSupported("cv_programming", self.kind)

  def write_cv(self, *args, **kwargs):
    raise ControllerOperationNotSupported("cv_programming", self.kind)

  def request_loco_control_grant(self, *args, **kwargs):
    raise ControllerOperationNotSupported("loco_control", self.kind)

  def send_loco_speed_request(self, *args, **kwargs):
    raise ControllerOperationNotSupported("loco_control", self.kind)

  def send_loco_function_request(self, *args, **kwargs):
    raise ControllerOperationNotSupported("loco_control", self.kind)

  def apply_track_profile_parameters(self, *args, **kwargs):
    raise ControllerOperationNotSupported("controller_settings", self.kind)


def router_with_unsupported_controller():
  registry = ControllerRegistry()
  registry.register(UnsupportedControllerAdapter())
  return ApiRouter(None, controller_registry=registry)


def unsupported_state():
  state = default_state()
  controller = state["controller"]
  controller["kind"] = "unsupported_controller"
  controller["controller_reachable"] = True
  controller["last_controller_seen_at"] = "2026-06-25T00:00:00+08:00"
  controller["booster_status"] = {
    "source": "dxdcnet_status_0x23",
    "power_on": True,
    "dcc_mode": True,
    "track_mode": "n",
  }
  controller["programming_track_status"] = {
    "source": "dxdcnet_status_0x23",
    "busy": False,
    "current_ma": 0,
    "dcc_mode": True,
    "programming_track_busy": False,
    "programming_track_current_ma": 0,
  }
  controller["safety_snapshot"]["booster_status_fresh"] = True
  controller["safety_snapshot"]["programming_track_status_fresh"] = True
  return state


class ControllerAdapterCapabilitiesTest(unittest.TestCase):
  def assert_not_supported(self, method, route, body):
    response_body, status = router_with_unsupported_controller().handle_json(
      method,
      route,
      json.dumps(body).encode("utf-8"),
      unsupported_state(),
    )
    payload = json.loads(response_body.decode("utf-8"))
    self.assertIn(status, (409, 501))
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["error"]["type"], "controller_operation_not_supported")

  def test_read_info_requires_read_info_capability(self):
    self.assert_not_supported("POST", "/api/controller/read-info", {})

  def test_track_power_requires_track_power_capability(self):
    self.assert_not_supported("POST", "/api/track-power", {"powered": True})

  def test_dc_control_requires_dc_control_capability(self):
    self.assert_not_supported("POST", "/api/dc-control", {"voltage": 6.0, "direction": "forward"})

  def test_cv_read_requires_cv_programming_capability(self):
    self.assert_not_supported("POST", "/api/cv/read", {"cv": 1})

  def test_cv_write_requires_cv_programming_capability(self):
    self.assert_not_supported("POST", "/api/cv/write", {"cv": 1, "value": 1})

  def test_loco_speed_requires_loco_control_capability(self):
    state = unsupported_state()
    state["vehicles"] = [{
      "id": "v3",
      "name": "N 测试车",
      "address": 3,
      "track_mode": "n",
      "type": 0,
    }]
    response_body, status = router_with_unsupported_controller().handle_json(
      "POST",
      "/api/loco/speed",
      json.dumps({"vehicle_id": "v3", "speed": 1, "direction": "forward"}).encode("utf-8"),
      state,
    )
    payload = json.loads(response_body.decode("utf-8"))
    self.assertIn(status, (409, 501))
    self.assertEqual(payload["error"]["type"], "controller_operation_not_supported")


if __name__ == "__main__":
  unittest.main()

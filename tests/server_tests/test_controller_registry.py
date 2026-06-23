import unittest

from server.controllers.base import ControllerCapabilities
from server.controllers.digsight import DigsightDXDCNetControllerAdapter
from server.controllers.registry import ControllerRegistry


class FakeControllerAdapter:
  kind = "fake_controller"
  label = "Fake Controller"
  capabilities = ControllerCapabilities(
    track_power=True,
    read_info=True,
    cv_programming=False,
    loco_control=False,
    controller_settings=False,
  )


class ControllerRegistryTest(unittest.TestCase):
  def test_registry_returns_registered_adapter(self):
    registry = ControllerRegistry()
    adapter = FakeControllerAdapter()
    registry.register(adapter)
    self.assertIs(registry.get("fake_controller"), adapter)

  def test_registry_rejects_unknown_controller(self):
    registry = ControllerRegistry()
    with self.assertRaises(ValueError):
      registry.get("missing_controller")

  def test_registry_descriptors_expose_controller_capabilities(self):
    registry = ControllerRegistry()
    registry.register(FakeControllerAdapter())
    self.assertEqual(registry.descriptors(), [{
      "kind": "fake_controller",
      "label": "Fake Controller",
      "capabilities": {
        "track_power": True,
        "read_info": True,
        "cv_programming": False,
        "loco_control": False,
        "controller_settings": False,
      },
    }])


class DigsightControllerAdapterTest(unittest.TestCase):
  def test_digsight_adapter_declares_capabilities(self):
    adapter = DigsightDXDCNetControllerAdapter()
    self.assertEqual(adapter.kind, "digsight_controller")
    self.assertTrue(adapter.capabilities.track_power)
    self.assertTrue(adapter.capabilities.read_info)

  def test_digsight_adapter_exposes_semantic_operations(self):
    adapter = DigsightDXDCNetControllerAdapter()
    for method_name in [
      "exchange",
      "read_info_frames",
      "send_track_output",
      "read_cv",
      "write_cv",
      "request_loco_control",
      "send_loco_speed",
      "send_loco_function",
    ]:
      self.assertTrue(callable(getattr(adapter, method_name, None)), method_name)


if __name__ == "__main__":
  unittest.main()

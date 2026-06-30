import inspect
import unittest

from server import models
from server.controllers.base import (
  ControllerCapabilities,
  ControllerAdapter,
  ControllerSettingsCapability,
  CvProgrammingCapability,
  LocoControlCapability,
  ReadInfoCapability,
  TrackPowerCapability,
  ControllerTransportDefaults,
)
from server.controllers.digsight import DigsightDXDCNetControllerAdapter
from server.controllers.registry import ControllerRegistry
from server.controllers.registry import default_controller_registry


class FakeControllerAdapter:
  kind = "fake_controller"
  label = "Fake Controller"
  config_file_name = "Fake_Controller_Config.json"
  capabilities = ControllerCapabilities(
    track_power=True,
    read_info=True,
    cv_programming=False,
    loco_control=False,
    controller_settings=False,
  )
  transport_defaults = ControllerTransportDefaults(
    udp_port=11111,
    local_udp_port=22222,
    checksum_algorithm="xor",
  )


class LaterFakeControllerAdapter:
  kind = "later_fake_controller"
  label = "Later Fake Controller"
  config_file_name = "Later_Fake_Controller_Config.json"
  capabilities = FakeControllerAdapter.capabilities
  transport_defaults = FakeControllerAdapter.transport_defaults


class EarlyFakeControllerAdapter:
  kind = "early_fake_controller"
  label = "Early Fake Controller"
  config_file_name = "Early_Fake_Controller_Config.json"
  capabilities = FakeControllerAdapter.capabilities
  transport_defaults = FakeControllerAdapter.transport_defaults


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
      "default_ip": "",
      "config_file_name": "Fake_Controller_Config.json",
      "capabilities": {
        "track_power": True,
        "read_info": True,
        "cv_programming": False,
        "loco_control": False,
        "controller_settings": False,
      },
      "transport_defaults": {
        "udp_port": 11111,
        "local_udp_port": 22222,
        "checksum_algorithm": "xor",
        "checksum_algorithms": ["xor"],
        "allow_zero_local_udp_port": True,
      },
    }])

  def test_registry_descriptors_use_explicit_serializers(self):
    source = inspect.getsource(ControllerRegistry.descriptors)
    self.assertIn("_descriptor", source)
    self.assertNotIn("__dict__", source)

  def test_registry_descriptors_keep_default_first_then_stable_label_order(self):
    registry = ControllerRegistry(default_kind="later_fake_controller")
    registry.register(FakeControllerAdapter())
    registry.register(LaterFakeControllerAdapter())
    registry.register(EarlyFakeControllerAdapter())

    kinds = [descriptor["kind"] for descriptor in registry.descriptors()]
    self.assertEqual(kinds, [
      "later_fake_controller",
      "early_fake_controller",
      "fake_controller",
    ])

  def test_registry_config_file_name_uses_adapter_metadata(self):
    registry = ControllerRegistry()
    registry.register(FakeControllerAdapter())

    self.assertEqual(registry.config_file_name("fake_controller"), "Fake_Controller_Config.json")
    self.assertEqual(registry.config_file_names(), ["Fake_Controller_Config.json"])

  def test_registry_is_single_descriptor_source(self):
    registry_source = inspect.getsource(ControllerRegistry)
    self.assertNotIn("adapter.descriptor", registry_source)
    self.assertNotIn("callable(getattr(adapter, \"descriptor\"", registry_source)
    self.assertFalse(hasattr(DigsightDXDCNetControllerAdapter, "descriptor"))

  def test_default_kind_is_explicit_not_registration_order(self):
    registry = ControllerRegistry(default_kind="fake_controller")
    registry.register(LaterFakeControllerAdapter())
    registry.register(FakeControllerAdapter())

    self.assertEqual(registry.default_kind, "fake_controller")

  def test_default_kind_requires_explicit_default(self):
    registry = ControllerRegistry()
    registry.register(FakeControllerAdapter())

    with self.assertRaises(ValueError) as caught:
      _ = registry.default_kind
    self.assertEqual(str(caught.exception), "Default controller is not configured")


class DigsightControllerAdapterTest(unittest.TestCase):
  def test_digsight_adapter_declares_transport_defaults(self):
    adapter = DigsightDXDCNetControllerAdapter()
    self.assertEqual(adapter.config_file_name, models.CONTROLLER_CONFIG_FILES["digsight_controller"])
    self.assertEqual(adapter.transport_defaults.udp_port, 12000)
    self.assertEqual(adapter.transport_defaults.local_udp_port, 6667)
    self.assertEqual(adapter.transport_defaults.checksum_algorithm, "xor")
    self.assertEqual(adapter.transport_defaults.checksum_algorithms, ("xor",))
    self.assertFalse(adapter.transport_defaults.allow_zero_local_udp_port)
    self.assertEqual(adapter.default_ip, models.CONTROLLER_DEFAULT_IP)

  def test_controller_adapters_declare_config_file_names(self):
    self.assertEqual(DigsightDXDCNetControllerAdapter.config_file_name, "Digsight_D9000.json")

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
      "read_controller_info",
      "parse_controller_info",
      "send_track_output",
      "send_track_output_request",
      "read_cv",
      "write_cv",
      "request_loco_control_grant",
      "send_loco_speed_request",
      "send_loco_function_request",
      "apply_track_profile_parameters",
    ]:
      self.assertTrue(callable(getattr(adapter, method_name, None)), method_name)


class ControllerAdapterContractTest(unittest.TestCase):
  def test_controller_adapter_contract_is_split_by_capability(self):
    protocol_classes = [
      ControllerAdapter,
      ReadInfoCapability,
      TrackPowerCapability,
      CvProgrammingCapability,
      LocoControlCapability,
      ControllerSettingsCapability,
    ]
    for protocol_class in protocol_classes:
      with self.subTest(protocol=protocol_class.__name__):
        self.assertTrue(inspect.isclass(protocol_class))

    adapter_source = inspect.getsource(ControllerAdapter)
    self.assertNotIn("read_cv_request", adapter_source)
    self.assertNotIn("send_loco_speed_request", adapter_source)
    self.assertNotIn("apply_track_profile_parameters", adapter_source)


if __name__ == "__main__":
  unittest.main()

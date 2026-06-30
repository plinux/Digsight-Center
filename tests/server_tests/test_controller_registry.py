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
  ControllerTransportDescriptor,
)
from server.controllers.digsight import DigsightDXDCNetControllerAdapter
from server.controllers.registry import ControllerRegistry
from server.controllers.registry import default_controller_registry
import server.api_support.controller as controller_api_support
import server.controllers.digsight as digsight_module
import server.controllers.dxdcnet_constants as dxdcnet_constants
import server.controllers.dxdcnet_info_parser as info_parser_module


class FakeControllerAdapter:
  kind = "fake_controller"
  label = "Fake Controller"
  default_display_name = "Fake Controller"
  protocol = "FakeProtocol"
  config_file_name = "Fake_Controller_Config.json"
  capabilities = ControllerCapabilities(
    track_power=True,
    dc_control=False,
    read_info=True,
    cv_programming=False,
    loco_control=False,
    controller_settings=False,
  )
  transport_descriptor = ControllerTransportDescriptor(
    kind="udp",
    defaults={
      "udp_port": 11111,
      "local_udp_port": 22222,
      "udp_checksum_algorithm": "xor",
    },
  )


class LaterFakeControllerAdapter:
  kind = "later_fake_controller"
  label = "Later Fake Controller"
  default_display_name = "Later Fake Controller"
  protocol = "FakeProtocol"
  config_file_name = "Later_Fake_Controller_Config.json"
  capabilities = FakeControllerAdapter.capabilities
  transport_descriptor = FakeControllerAdapter.transport_descriptor


class EarlyFakeControllerAdapter:
  kind = "early_fake_controller"
  label = "Early Fake Controller"
  default_display_name = "Early Fake Controller"
  protocol = "FakeProtocol"
  config_file_name = "Early_Fake_Controller_Config.json"
  capabilities = FakeControllerAdapter.capabilities
  transport_descriptor = FakeControllerAdapter.transport_descriptor


class TraversalConfigControllerAdapter(FakeControllerAdapter):
  kind = "traversal_config_controller"
  label = "Traversal Config Controller"
  config_file_name = "../outside.json"


class NestedConfigControllerAdapter(FakeControllerAdapter):
  kind = "nested_config_controller"
  label = "Nested Config Controller"
  config_file_name = "nested/config.json"


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

  def test_controller_kind_validator_does_not_choose_default(self):
    with self.assertRaises(ValueError):
      models.validate_controller_kind(None)
    self.assertEqual(models.validate_controller_kind("fake_controller"), "fake_controller")

  def test_registry_descriptors_expose_controller_capabilities(self):
    registry = ControllerRegistry()
    registry.register(FakeControllerAdapter())
    self.assertEqual(registry.descriptors(), [{
      "kind": "fake_controller",
      "label": "Fake Controller",
      "display_name": "Fake Controller",
      "protocol": "FakeProtocol",
      "default_ip": "",
      "config_file_name": "Fake_Controller_Config.json",
      "config_file": "config/controllers/Fake_Controller_Config.json",
      "config_public_path": "/config/controllers/Fake_Controller_Config.json",
      "capabilities": {
        "track_power": True,
        "dc_control": False,
        "read_info": True,
        "cv_programming": False,
        "loco_control": False,
        "controller_settings": False,
      },
      "transport_descriptor": {
        "kind": "udp",
        "defaults": {
          "udp_port": 11111,
          "local_udp_port": 22222,
          "udp_checksum_algorithm": "xor",
        },
        "metadata": {},
        "endpoint_readiness": {
          "required_paths": [],
        },
      },
      "endpoint_readiness": {
        "required_paths": [],
      },
    }])

  def test_udp_transport_descriptor_does_not_infer_endpoint_readiness(self):
    descriptor = ControllerTransportDescriptor(
      kind="udp",
      defaults={
        "udp_port": 11111,
        "local_udp_port": 22222,
        "udp_checksum_algorithm": "xor",
      },
    )

    self.assertEqual(descriptor.endpoint_required_paths, ())
    self.assertEqual(descriptor.to_dict()["endpoint_readiness"], {"required_paths": []})
    self.assertNotIn("checksum_algorithms", descriptor.to_dict())
    self.assertNotIn("allow_zero_local_udp_port", descriptor.to_dict())

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

  def test_registry_rejects_controller_config_file_traversal(self):
    registry = ControllerRegistry()
    registry.register(TraversalConfigControllerAdapter())

    with self.assertRaises(ValueError):
      registry.config_file_name("traversal_config_controller")
    with self.assertRaises(ValueError):
      registry.descriptors()

  def test_registry_rejects_nested_controller_config_file_name(self):
    registry = ControllerRegistry()
    registry.register(NestedConfigControllerAdapter())

    with self.assertRaises(ValueError):
      registry.config_file_name("nested_config_controller")

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
  def test_digsight_adapter_declares_transport_descriptor(self):
    adapter = DigsightDXDCNetControllerAdapter()
    self.assertFalse(hasattr(models, "CONTROLLER_CONFIG_FILES"))
    self.assertFalse(hasattr(models, "controller_config_file_name"))
    self.assertEqual(adapter.config_file_name, "Digsight_D9000.json")
    self.assertEqual(adapter.default_display_name, "动芯 拾Pro")
    self.assertEqual(adapter.protocol, "DXDCNet")
    self.assertEqual(adapter.transport_descriptor.defaults["udp_port"], 12000)
    self.assertEqual(adapter.transport_descriptor.defaults["local_udp_port"], 6667)
    self.assertEqual(adapter.transport_descriptor.defaults["udp_checksum_algorithm"], "xor")
    self.assertEqual(adapter.transport_descriptor.metadata["checksum_algorithms"], ("xor",))
    self.assertFalse(adapter.transport_descriptor.metadata["allow_zero_local_udp_port"])
    self.assertEqual(adapter.transport_descriptor.endpoint_required_paths, ("transport.udp_port",))
    self.assertEqual(adapter.default_ip, models.CONTROLLER_DEFAULT_IP)

  def test_digsight_adapter_keeps_udp_metadata_adapter_owned(self):
    adapter = DigsightDXDCNetControllerAdapter()
    descriptor_payload = adapter.transport_descriptor.to_dict()

    self.assertNotIn("checksum_algorithms", descriptor_payload)
    self.assertNotIn("allow_zero_local_udp_port", descriptor_payload)
    self.assertEqual(descriptor_payload["metadata"]["checksum_algorithms"], ["xor"])
    self.assertFalse(descriptor_payload["metadata"]["allow_zero_local_udp_port"])

    api_support_source = inspect.getsource(controller_api_support)
    self.assertNotIn("UDP port and checksum algorithm are unconfirmed", api_support_source)
    self.assertNotIn("UDP checksum algorithm is unconfirmed", api_support_source)

  def test_digsight_adapter_treats_default_ip_as_unconfigured(self):
    adapter = DigsightDXDCNetControllerAdapter()
    controller = {
      "ip": models.CONTROLLER_DEFAULT_IP,
      "udp_port": models.DXDCNET_DEFAULT_UDP_PORT,
      "udp_checksum_algorithm": models.DXDCNET_DEFAULT_CHECKSUM_ALGORITHM,
    }

    self.assertEqual(adapter.runtime_readiness_warnings(controller), ["controller_ip_unconfigured"])

  def test_digsight_adapter_owns_udp_runtime_fields(self):
    adapter = DigsightDXDCNetControllerAdapter()
    controller = {
      "transport": {
        "udp_port": 12000,
        "local_udp_port": 6667,
        "udp_checksum_algorithm": "xor",
      }
    }

    adapter.apply_transport_runtime(controller)

    self.assertEqual(controller["udp_port"], 12000)
    self.assertEqual(controller["local_udp_port"], 6667)
    self.assertEqual(controller["udp_checksum_algorithm"], "xor")

  def test_controller_adapters_declare_config_file_names(self):
    self.assertEqual(DigsightDXDCNetControllerAdapter.config_file_name, "Digsight_D9000.json")

  def test_digsight_adapter_declares_capabilities(self):
    adapter = DigsightDXDCNetControllerAdapter()
    self.assertEqual(adapter.kind, "digsight_controller")
    self.assertTrue(adapter.capabilities.track_power)
    self.assertTrue(adapter.capabilities.dc_control)
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

  def test_dxdcnet_d9000_parameter_constants_are_shared(self):
    self.assertEqual(dxdcnet_constants.PARAM_RAILCOM, 0x03)
    self.assertEqual(dxdcnet_constants.PARAM_SCREEN_BRIGHTNESS, 0x7E)
    self.assertEqual(dxdcnet_constants.PARAM_SCREEN_DIRECTION, 0x80)
    self.assertNotIn("PARAM_RAILCOM = 0x03", inspect.getsource(digsight_module))
    self.assertNotIn("PARAM_RAILCOM = 0x03", inspect.getsource(info_parser_module))

  def test_read_info_frames_accepts_dict_specs_only(self):
    source = inspect.getsource(DigsightDXDCNetControllerAdapter.read_info_frames)
    self.assertNotIn("isinstance(spec, dict)", source)
    self.assertNotIn("name, request_frame, expected_command, expected_device_type = spec", source)
    self.assertIn('name = spec["name"]', source)


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

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
from server.controllers.ecos import ECoSControllerAdapter
from server.controllers.example import ExampleControllerAdapter
from server.controllers.registry import ControllerRegistry
from server.controllers.registry import default_controller_registry
from server.controllers.z21 import Z21_STD_PROFILE, Z21_START_PROFILE, Z21_XL_PROFILE, Z21LanControllerAdapter
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
      "configured_ip": "",
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
        "railcom_settings": False,
        "profile_settings_on_track_mode": False,
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

  def test_sound_editor_is_not_a_controller_capability(self):
    descriptors = {
      descriptor["kind"]: descriptor
      for descriptor in default_controller_registry().descriptors()
    }

    self.assertNotIn("sound_editor", descriptors[models.CONTROLLER_KIND_DIGSIGHT]["capabilities"])
    self.assertNotIn("sound_editor", descriptors[models.CONTROLLER_KIND_ECOS_50200]["capabilities"])
    self.assertNotIn("sound_editor", descriptors[models.CONTROLLER_KIND_Z21_STD]["capabilities"])

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
    self.assertFalse(hasattr(ExampleControllerAdapter, "descriptor"))

  def test_default_kind_is_explicit_not_registration_order(self):
    registry = ControllerRegistry(default_kind="fake_controller")
    registry.register(ExampleControllerAdapter())
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
    self.assertEqual(ECoSControllerAdapter.config_file_name, "ESU_ECoS_50200.json")
    self.assertEqual(Z21_STD_PROFILE.config_file_name, "Z21.json")
    self.assertEqual(Z21_START_PROFILE.config_file_name, "Z21_Start.json")
    self.assertEqual(Z21_XL_PROFILE.config_file_name, "Z21_XL.json")
    self.assertEqual(ExampleControllerAdapter.config_file_name, "example_controller.json")

  def test_digsight_adapter_declares_capabilities(self):
    adapter = DigsightDXDCNetControllerAdapter()
    self.assertEqual(adapter.kind, "digsight_controller")
    self.assertTrue(adapter.capabilities.track_power)
    self.assertTrue(adapter.capabilities.dc_control)
    self.assertTrue(adapter.capabilities.read_info)
    self.assertTrue(adapter.capabilities.railcom_settings)

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


class ExampleControllerAdapterTest(unittest.TestCase):
  def test_example_adapter_documents_future_controller_contract(self):
    adapter = ExampleControllerAdapter()
    self.assertEqual(adapter.kind, "example_controller")
    self.assertEqual(adapter.label, "样例控制器")
    self.assertEqual(adapter.default_display_name, "样例控制器")
    self.assertEqual(adapter.protocol, "ExampleProtocol")
    self.assertEqual(adapter.transport_descriptor.kind, "example_transport")
    self.assertEqual(adapter.transport_descriptor.endpoint_required_paths, ("transport.endpoint",))
    self.assertEqual(adapter.transport_descriptor.metadata, {})
    self.assertNotIn("checksum_algorithms", adapter.transport_descriptor.to_dict())
    self.assertNotIn("allow_zero_local_udp_port", adapter.transport_descriptor.to_dict())
    self.assertFalse(adapter.capabilities.track_power)
    self.assertFalse(adapter.capabilities.read_info)

  def test_example_adapter_does_not_stub_optional_capabilities(self):
    source = inspect.getsource(ExampleControllerAdapter)
    optional_methods = [
      "exchange",
      "read_info_frames",
      "read_controller_info",
      "parse_controller_info",
      "validate_programming_track_safety",
      "send_track_output",
      "send_track_output_request",
      "read_cv",
      "write_cv",
      "read_cv_request",
      "write_cv_request",
      "classify_cv_responses",
      "cv_ack_category",
      "should_retry_cv_write_ack",
      "is_main_track_cv_read_no_ack",
      "cv_ack_debug",
      "request_loco_control_grant",
      "send_loco_speed_request",
      "send_loco_function_request",
      "apply_track_profile_parameters",
    ]

    for method_name in optional_methods:
      with self.subTest(method_name=method_name):
        self.assertNotIn(f"def {method_name}(", source)

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

  def test_example_adapter_readiness_contract_is_explicitly_non_operational(self):
    adapter = ExampleControllerAdapter()
    controller = {"kind": adapter.kind}

    self.assertEqual(adapter.runtime_readiness_warnings(controller), ["controller_runtime_not_implemented"])
    self.assertEqual(adapter.loco_control_readiness_warnings(controller), ["controller_runtime_not_implemented"])
    self.assertEqual(adapter.status_not_ready_message(), "样例控制器未实现通信运行时")
    self.assertFalse(adapter.is_booster_status_confirmed(controller))
    self.assertIsNone(adapter.programming_track_status(controller))

  def test_example_adapter_client_id_policy_is_explicitly_non_operational(self):
    adapter = ExampleControllerAdapter()

    with self.assertRaises(NotImplementedError) as caught:
      adapter.controller_client_id({"kind": adapter.kind})
    self.assertEqual(str(caught.exception), "样例控制器未实现 client id 策略")

  def test_example_adapter_can_be_registered_manually_but_is_not_default(self):
    registry = ControllerRegistry()
    registry.register(ExampleControllerAdapter())
    descriptor_kinds = [descriptor["kind"] for descriptor in registry.descriptors()]
    self.assertEqual(descriptor_kinds, ["example_controller"])
    self.assertIsInstance(registry.get("example_controller"), ExampleControllerAdapter)
    default_kinds = [descriptor["kind"] for descriptor in default_controller_registry().descriptors()]
    self.assertEqual(default_kinds, [
      "digsight_controller",
      "ecos_50200_controller",
      "z21_std_controller",
      "z21_xl_controller",
      "z21_start_controller",
    ])
    self.assertNotIn("example_controller", default_kinds)

  def test_example_adapter_is_kept_as_code_sample_but_not_default(self):
    default_kinds = [descriptor["kind"] for descriptor in default_controller_registry().descriptors()]
    self.assertEqual(default_kinds, [
      "digsight_controller",
      "ecos_50200_controller",
      "z21_std_controller",
      "z21_xl_controller",
      "z21_start_controller",
    ])
    self.assertNotIn("example_controller", default_kinds)
    self.assertEqual(ExampleControllerAdapter().kind, "example_controller")


class ECoSAndZ21ControllerAdapterTest(unittest.TestCase):
  def test_ecos_adapter_declares_tcp_control_capabilities(self):
    adapter = ECoSControllerAdapter()

    self.assertEqual(adapter.kind, "ecos_50200_controller")
    self.assertEqual(adapter.protocol, "ECoS")
    self.assertEqual(adapter.transport_descriptor.kind, "tcp")
    self.assertEqual(adapter.transport_descriptor.defaults["tcp_port"], 15471)
    self.assertEqual(adapter.transport_descriptor.endpoint_required_paths, ("transport.tcp_port",))
    self.assertTrue(adapter.capabilities.read_info)
    self.assertTrue(adapter.capabilities.track_power)
    self.assertTrue(adapter.capabilities.cv_programming)
    self.assertTrue(adapter.capabilities.loco_control)
    self.assertTrue(adapter.capabilities.controller_settings)
    self.assertTrue(adapter.capabilities.railcom_settings)
    self.assertNotIn("target_voltage_v", adapter.default_track_profiles["ho"])
    self.assertEqual(adapter.default_track_profiles["ho"]["target_current_limit_ma"], 4000)
    self.assertEqual(adapter.default_track_profiles["ho"]["max_target_current_limit_ma"], 6000)
    self.assertFalse(adapter.default_track_profiles["dc"]["enabled"])
    self.assertIn("50200/50210/50220", adapter.field_descriptions["protocol"])

  def test_z21_model_profiles_declare_separate_defaults(self):
    z21 = Z21LanControllerAdapter(Z21_STD_PROFILE)
    start = Z21LanControllerAdapter(Z21_START_PROFILE)
    xl = Z21LanControllerAdapter(Z21_XL_PROFILE)

    self.assertEqual(z21.kind, "z21_std_controller")
    self.assertEqual(start.kind, "z21_start_controller")
    self.assertEqual(xl.kind, "z21_xl_controller")
    self.assertNotIn("output_value", z21.default_track_profiles["ho"])
    self.assertNotIn("current_param", z21.default_track_profiles["ho"])
    self.assertNotIn("target_current_limit_ma", z21.default_track_profiles["ho"])
    self.assertNotIn("max_target_current_limit_ma", z21.default_track_profiles["ho"])
    self.assertTrue(z21.default_track_profiles["g"]["enabled"])
    self.assertFalse(z21.default_track_profiles["dc"]["enabled"])
    self.assertTrue(z21.capabilities.controller_settings)
    self.assertFalse(start.capabilities.controller_settings)
    self.assertTrue(xl.capabilities.controller_settings)
    self.assertTrue(z21.capabilities.railcom_settings)
    self.assertTrue(start.capabilities.railcom_settings)
    self.assertTrue(xl.capabilities.railcom_settings)
    self.assertTrue(z21.capabilities.profile_settings_on_track_mode)
    self.assertFalse(start.capabilities.profile_settings_on_track_mode)
    self.assertTrue(xl.capabilities.profile_settings_on_track_mode)
    for mode in ("n", "ho", "g"):
      self.assertEqual(z21.default_track_profiles[mode]["target_voltage_v"], 16.0)
      self.assertEqual(z21.default_track_profiles[mode]["min_target_voltage_v"], 11.0)
      self.assertEqual(z21.default_track_profiles[mode]["max_target_voltage_v"], 23.0)
    self.assertFalse(start.default_track_profiles["g"]["enabled"])
    self.assertTrue(xl.default_track_profiles["g"]["enabled"])
    self.assertEqual(xl.transport_descriptor.defaults["udp_port"], 21105)
    self.assertTrue(xl.transport_descriptor.metadata["allow_zero_local_udp_port"])

  def test_default_registry_exposes_read_only_controller_adapters(self):
    registry = default_controller_registry()
    descriptors = {descriptor["kind"]: descriptor for descriptor in registry.descriptors()}

    self.assertEqual(registry.default_kind, "digsight_controller")
    self.assertEqual(set(descriptors), {
      "digsight_controller",
      "ecos_50200_controller",
      "z21_std_controller",
      "z21_start_controller",
      "z21_xl_controller",
    })
    self.assertEqual(descriptors["ecos_50200_controller"]["transport_descriptor"]["kind"], "tcp")
    self.assertEqual(descriptors["z21_std_controller"]["transport_descriptor"]["kind"], "udp")
    self.assertTrue(descriptors["ecos_50200_controller"]["capabilities"]["read_info"])
    self.assertTrue(descriptors["ecos_50200_controller"]["capabilities"]["loco_control"])
    self.assertTrue(descriptors["z21_xl_controller"]["capabilities"]["read_info"])
    self.assertTrue(descriptors["z21_xl_controller"]["capabilities"]["cv_programming"])


if __name__ == "__main__":
  unittest.main()

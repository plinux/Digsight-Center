import inspect
import json
import unittest
from types import SimpleNamespace

from server.api import ApiRouter
from server.api_support.controller import ControllerApiSupport
from server.api_support.context import ApiSupportContext
from server.api_support.controller_service import ControllerServicePorts, ControllerServiceSupport
from server.controller_service import ControllerService
from server.controller_services.results import ServiceResult
from server.controller_services.cv_programming import CvProgrammingService
from server.controller_services.loco_control import LocoCommandService
from server.controller_services.track_power import TrackPowerService
from server.controllers.digsight import DigsightDXDCNetControllerAdapter
from server.controllers.dxdcnet_info_parser import DXDCNetControllerInfoParser
from server.controllers.example import ExampleControllerAdapter
from server.controllers.registry import ControllerRegistry
from server.controllers.registry import default_controller_registry
from server.models import CONTROLLER_KIND_DIGSIGHT


class LocoCommandKindFakeAdapter:
  kind = "fake_controller"
  label = "Fake Controller"
  config_file_name = "fake_controller.json"
  capabilities = SimpleNamespace(
    track_power=False,
    dc_control=False,
    cv_programming=False,
    address_programming=False,
    loco_control=True,
    controller_settings=False,
  )

  def __init__(self):
    self.speed_calls = 0
    self.function_calls = 0
    self.control_calls = 0

  def request_loco_control_grant(self, *args, **kwargs):
    self.control_calls += 1
    return SimpleNamespace(request_hex="control-request", address=3, feedback=None)

  def send_loco_speed_request(self, *args, **kwargs):
    self.speed_calls += 1
    request = args[2]
    return SimpleNamespace(
      request_hex="speed-request",
      request_hexes=["speed-request"],
      feedback=None,
      extra={"direction": request.direction},
    )

  def send_loco_function_request(self, *args, **kwargs):
    self.function_calls += 1
    return SimpleNamespace(
      request_hex="function-request",
      request_hexes=["function-request"],
      feedback=None,
      extra={},
    )


class LocoCommandKindSupport:
  def save(self, state):
    return None

  def mark_controller_unreachable(self, state, reason):
    state["controller"]["controller_unreachable_reason"] = reason


class ControllerServiceBoundaryTest(unittest.TestCase):
  def test_api_router_is_http_facade_only(self):
    router_source = inspect.getsource(ApiRouter)
    forbidden_names = (
      "_handle_controller_connect",
      "_handle_controller_settings",
      "_handle_track_power",
      "_handle_dc_control",
      "_handle_controller_read_info",
      "_handle_vehicle_image_upload",
      "_merge_import_result",
      "_validate_vehicle_address",
      "_validate_controller_ip",
      "_validate_udp_port",
      "_validate_checksum_algorithm",
      "_validate_consist_members",
      "_sync_consist_member_addresses",
      "_sync_vehicle_address_if_present",
      "_controller_info_timeout_seconds",
      "_clamp_timeout_seconds",
      "_persistent_state",
    )
    for name in forbidden_names:
      self.assertNotIn(name, router_source)

  def test_api_support_does_not_hold_router_object(self):
    from pathlib import Path

    for path in Path("server/api_support").glob("*.py"):
      if path.name in {"__init__.py", "context.py"}:
        continue
      source = path.read_text(encoding="utf-8")
      self.assertNotIn("self.router", source, path.name)
      self.assertNotIn("router._", source, path.name)

  def test_api_support_context_does_not_hold_controller_service_back_reference(self):
    self.assertNotIn("controller_service", ApiSupportContext.__dataclass_fields__)
    from pathlib import Path

    for path in Path("server/api_support").glob("*.py"):
      if path.name in {"__init__.py"}:
        continue
      source = path.read_text(encoding="utf-8")
      self.assertNotIn("context.controller_service", source, path.name)

  def test_controller_api_does_not_hold_cv_programming_back_reference(self):
    router_source = inspect.getsource(ApiRouter)
    controller_source = inspect.getsource(ControllerApiSupport)
    self.assertNotIn("controller_api.cv_programming_api", router_source)
    self.assertNotIn("self.cv_programming_api", controller_source)
    self.assertNotIn("adapter.capabilities.__dict__", controller_source)
    self.assertIn("adapter.capabilities.to_dict()", controller_source)

  def test_removed_api_support_compatibility_wrappers_stay_removed(self):
    from pathlib import Path

    self.assertFalse(Path("server/api_support/vehicles.py").exists())
    self.assertFalse(Path("server/api_support/consists.py").exists())

  def test_router_uses_controller_service_for_hardware_domains(self):
    router_source = inspect.getsource(ApiRouter)
    self.assertIn("self.controller_service", router_source)
    self.assertIn("ControllerServicePorts(", router_source)
    self.assertIn("ControllerServiceSupport(", router_source)
    self.assertNotIn("controller_client_id_port=", router_source)
    self.assertNotIn("api_support=self", router_source)
    self.assertNotIn("ControllerServiceSupport(self)", router_source)
    self.assertNotIn("def send_track_output(", router_source)
    self.assertNotIn("def execute_cv_read(", router_source)
    self.assertNotIn("def execute_cv_write(", router_source)
    self.assertNotIn("def execute_loco_targets(", router_source)

  def test_controller_service_owns_hardware_operations(self):
    service_source = inspect.getsource(ControllerService)
    track_source = inspect.getsource(TrackPowerService)
    cv_source = inspect.getsource(CvProgrammingService)
    loco_source = inspect.getsource(LocoCommandService)
    self.assertNotIn("_impl(", service_source)
    self.assertIn("def send_track_output(", track_source)
    self.assertIn("def execute_cv_read(", cv_source)
    self.assertIn("def _cv_read_failure_response(", cv_source)
    self.assertIn("def _cv_ack_debug_extra(", cv_source)
    self.assertIn("def execute_cv_write(", cv_source)
    self.assertIn("def execute_loco_targets(", loco_source)
    self.assertIn("def _loco_control_denied_response(", loco_source)
    self.assertIn("request_loco_control_grant", loco_source)

  def test_controller_service_owns_track_power_request_policy(self):
    import server.api_support.controller as controller_api_module

    api_source = inspect.getsource(controller_api_module.ControllerApiSupport)
    module_source = inspect.getsource(controller_api_module)
    track_source = inspect.getsource(TrackPowerService)
    self.assertIn("def prepare_track_power_request(", track_source)
    self.assertIn("def prepare_dc_control_request(", track_source)
    self.assertNotIn("def track_output_value(", module_source)
    self.assertNotIn("def validate_dc_voltage(", module_source)
    self.assertNotIn("def validate_dc_direction(", module_source)
    self.assertNotIn("voltage * 10", api_source)

  def test_controller_service_does_not_build_dxdcnet_track_output_frames(self):
    service_sources = "\n".join([
      inspect.getsource(ControllerService),
      inspect.getsource(TrackPowerService),
      inspect.getsource(CvProgrammingService),
      inspect.getsource(LocoCommandService),
    ])
    self.assertNotIn("build_track_output_frame", service_sources)
    self.assertNotIn("CMD_DEVICE_STATUS", service_sources)
    self.assertNotIn("DEVICE_TYPE_BOOSTER", service_sources)
    self.assertNotIn("digsight_dxdcnet", service_sources)
    self.assertNotIn("PROGRAMMER_ACK", service_sources)
    self.assertNotIn("classify_programmer_responses", service_sources)
    self.assertNotIn("programmer_ack_category", service_sources)
    self.assertNotIn("should_retry_busy_ack", service_sources)
    self.assertNotIn("CMD_LOCO_CONTROL_ACK", service_sources)
    self.assertNotIn("decode_udp_frame", service_sources)
    self.assertNotIn("parse_loco_control_ack", service_sources)

  def test_controller_service_layer_returns_typed_results_not_http_tuples(self):
    from pathlib import Path

    service_paths = [
      Path("server/controller_service.py"),
      *Path("server/controller_services").glob("*.py"),
    ]
    for path in service_paths:
      if path.name == "results.py":
        continue
      source = path.read_text(encoding="utf-8")
      self.assertNotIn("from server import response", source, path.name)
      self.assertNotIn("response.success", source, path.name)
      self.assertNotIn("response.failure", source, path.name)

    service = ControllerService(
      service_support=LocoCommandKindSupport(),
      controller_registry=default_controller_registry(),
      controller_session=object(),
      udp_transport=object(),
    )

    failure = service.digital_operation_mode_failure({"track_mode": "dc"}, "车辆控制")

    self.assertIsInstance(failure, ServiceResult)
    self.assertFalse(failure.ok)
    self.assertEqual(failure.error_type, "unsafe_track_mode")

  def test_api_router_does_not_own_controller_protocol_frame_building(self):
    router_source = inspect.getsource(ApiRouter)
    forbidden_terms = [
      "digsight_dxdcnet",
      "train_dcc",
      "def _cv_programming_preflight(",
      "def _main_track_cv_preflight(",
      "def _cv_protocol_preflight(",
      "def _programming_track_status_from_controller(",
      "def _loco_control_preflight(",
      "def _validated_control_request(",
      "def _loco_speed_request_frames(",
      "def _first_loco_speed_feedback(",
      "def _first_loco_function_feedback(",
      "def _first_loco_control_ack(",
      "def _build_loco_control_ack_matcher(",
      "def _request_loco_control(",
      "def _loco_speed_targets(",
      "def _loco_function_targets(",
      "def _consist_member_targets(",
      "def _consist_target_direction(",
      "def _vehicle_loco_target(",
      "def _handle_consist_speed(",
      "def _exchange_dxdcnet(",
      "parse_booster_status",
    ]
    for term in forbidden_terms:
      self.assertNotIn(term, router_source)
    self.assertNotIn("build_status_request_frame(", router_source)
    self.assertNotIn("build_version_request_frame(", router_source)
    self.assertNotIn("build_parameter_read_frame(", router_source)
    self.assertNotIn("build_loco_speed_frame(", router_source)
    self.assertNotIn("build_loco_function_frames(", router_source)

  def test_controller_service_resolves_default_adapter(self):
    service = ControllerService(
      service_support=object(),
      controller_registry=default_controller_registry(),
      controller_session=object(),
      udp_transport=object(),
    )

    adapter = service.adapter_for({})

    self.assertEqual(adapter.kind, "digsight_controller")
    self.assertTrue(adapter.capabilities.track_power)

  def test_controller_service_support_defines_narrow_router_boundary(self):
    support_source = inspect.getsource(ControllerServiceSupport)
    self.assertIn("def mark_controller_unreachable(", support_source)
    self.assertIn("def cv_debug(", support_source)
    self.assertIn("def json_payload(", support_source)
    self.assertNotIn("def controller_client_id(", support_source)
    self.assertNotIn("def validated_control_request(", support_source)
    self.assertNotIn("self.router", support_source)

  def test_controller_service_support_uses_explicit_ports(self):
    ports = ControllerServicePorts(
      mark_controller_unreachable_port=lambda state, reason: state.setdefault("reasons", []).append(reason),
      mark_safety_snapshot_fresh_port=lambda controller, **kwargs: controller.setdefault("fresh", {}).update(kwargs),
      save_port=lambda state: state.setdefault("saved", True),
      frame_debug_port=lambda frame: {"frame": frame},
      request_debug_port=lambda frame: frame.hex(" "),
      cv_debug_port=lambda **kwargs: kwargs,
      cv_write_busy_retry_count_port=lambda controller: controller["retry_count"],
      cv_write_busy_retry_delay_seconds_port=lambda controller: controller["retry_delay"],
    )
    support = ControllerServiceSupport(ports)
    state = {"controller": {"client_id": 7, "retry_count": 2, "retry_delay": 0.3}}

    self.assertFalse(hasattr(support, "router"))
    self.assertFalse(hasattr(support, "_controller_client_id_port"))
    support.mark_controller_unreachable(state, "timeout")
    self.assertEqual(state["reasons"], ["timeout"])
    support.mark_safety_snapshot_fresh(state["controller"], booster_status_fresh=True)
    self.assertEqual(state["controller"]["fresh"], {"booster_status_fresh": True, "programming_track_status_fresh": None})
    self.assertEqual(support.request_debug(b"\xff\x00"), "ff 00")
    self.assertEqual(support.json_payload(b'{"ok":true}')["ok"], True)
    self.assertEqual(support.cv_write_busy_retry_count(state["controller"]), 2)

  def test_dxdcnet_adapter_owns_read_info_parsing(self):
    router_source = inspect.getsource(ApiRouter)
    adapter_source = inspect.getsource(DigsightDXDCNetControllerAdapter)
    parser_source = inspect.getsource(DXDCNetControllerInfoParser)
    self.assertNotIn("ControllerInfoParser", router_source)
    self.assertNotIn("controller_info_parser", router_source)
    self.assertIn("def parse_controller_info(", adapter_source)
    self.assertIn("self.info_parser.apply", adapter_source)
    self.assertIn("parse_booster_status", parser_source)
    self.assertIn("parse_command_station_status", parser_source)

  def test_track_power_service_updates_status_and_adapter_keeps_timeout_clamps(self):
    router = ApiRouter(None)
    adapter = DigsightDXDCNetControllerAdapter()
    controller = {
      "controller_info_timeout_seconds": "bad",
      "telemetry": {"track_power_w": 0},
      "safety_snapshot": {
        "controller_endpoint_version": 1,
        "last_read_info_at": "",
        "booster_status_fresh": False,
        "programming_track_status_fresh": False,
      },
    }
    status = router.controller_service._store_track_output_booster_status(controller, {
      "source": "dxdcnet_status_0x23",
      "power_on": True,
      "temperature_c": 30,
      "output_voltage_v": 12.0,
      "output_current_a": 0.1,
    })

    self.assertTrue(status["power_on"])
    self.assertEqual(controller["booster_status"]["source"], "dxdcnet_status_0x23")
    self.assertEqual(controller["telemetry"]["track_voltage_v"], 12.0)
    self.assertEqual(controller["telemetry"]["track_power_w"], 1.2)
    self.assertTrue(controller["safety_snapshot"]["booster_status_fresh"])
    self.assertEqual(adapter._controller_info_timeout_seconds(controller, "booster_status"), 1.5)
    self.assertEqual(adapter._clamp_timeout_seconds("0.01", 0.05, 1.5), 0.05)
    self.assertEqual(adapter._clamp_timeout_seconds("2.0", 0.05, 1.5), 1.5)

  def test_api_router_has_no_dxdcnet_exchange_escape_hatch(self):
    router_source = inspect.getsource(ApiRouter)
    self.assertNotIn("def _exchange_dxdcnet(", router_source)
    self.assertNotIn("parse_booster_status", router_source)

  def test_controller_service_cv_write_failure_helpers_return_structured_payloads(self):
    router = ApiRouter(None)
    service = router.controller_service
    classification = SimpleNamespace(
      ack=SimpleNamespace(ack_name="rejected", ack_mode=2),
      parse_warnings=["synthetic warning"],
    )
    controller = {"kind": CONTROLLER_KIND_DIGSIGHT}
    request_frame = bytes.fromhex("ff ff 17 01 15 80 00 05 00 8d")

    rejected = service._cv_write_rejected_response(
      controller,
      classification,
      1,
      5,
      1,
      request_frame,
      [],
      None,
      0,
      1,
      {"ack": "busy"},
    )
    busy = service._cv_write_busy_exhausted_response(
      1,
      5,
      1,
      request_frame,
      [],
      None,
      3,
      {"ack": "busy"},
    )
    no_ack = service._cv_write_no_ack_response(
      1,
      5,
      1,
      request_frame,
      [],
      None,
    )

    self.assertIsInstance(rejected, ServiceResult)
    self.assertEqual(rejected.status, 502)
    self.assertEqual(rejected.error_type, "cv_write_rejected")
    self.assertEqual(rejected.debug["ack"], "rejected")
    self.assertEqual(rejected.debug["busy_retries"], 1)
    self.assertEqual(busy.status, 502)
    self.assertEqual(busy.error_type, "cv_write_rejected")
    self.assertEqual(busy.debug["ack"], "busy")
    self.assertEqual(no_ack.status, 502)
    self.assertEqual(no_ack.error_type, "cv_write_no_ack")
    self.assertEqual(no_ack.debug["value"], 5)

  def test_controller_service_default_adapter_kind_stays_digsight(self):
    service = ControllerService(
      service_support=object(),
      controller_registry=default_controller_registry(),
      controller_session=object(),
      udp_transport=object(),
    )

    self.assertEqual(service.adapter_for({}).kind, CONTROLLER_KIND_DIGSIGHT)

  def test_shared_controller_runtime_names_are_protocol_neutral(self):
    sources = "\n".join([
      inspect.getsource(ApiRouter),
      inspect.getsource(ControllerService),
      inspect.getsource(ApiSupportContext),
    ])
    self.assertNotIn("dxdcnet_session", sources)
    self.assertNotIn("default_dxdcnet_session", sources)

  def test_api_support_uses_adapter_status_hooks(self):
    from pathlib import Path

    for path in Path("server/api_support").glob("*.py"):
      source = path.read_text(encoding="utf-8")
      self.assertNotIn("dxdcnet_status_0x23", source, path.name)
      self.assertNotIn("0x23 Booster", source, path.name)
      self.assertNotIn("ProgrammingTrackSafety", source, path.name)
      self.assertNotIn("digsight_dxdcnet", source, path.name)
      self.assertNotIn("digsight_dxdcnet.programming_track", source, path.name)

  def test_controller_adapter_exposes_readiness_and_status_hooks(self):
    adapter = DigsightDXDCNetControllerAdapter()
    self.assertTrue(callable(adapter.runtime_readiness_warnings))
    self.assertTrue(callable(adapter.loco_control_readiness_warnings))
    self.assertTrue(callable(adapter.is_booster_status_confirmed))
    self.assertTrue(callable(adapter.programming_track_status))
    self.assertTrue(callable(adapter.validate_programming_track_safety))
    self.assertTrue(callable(adapter.classify_cv_responses))
    self.assertTrue(callable(adapter.cv_ack_category))
    self.assertTrue(callable(adapter.should_retry_cv_write_ack))
    self.assertTrue(callable(adapter.is_main_track_cv_read_no_ack))
    self.assertTrue(callable(adapter.cv_ack_debug))
    self.assertIsInstance(adapter.status_not_ready_message(), str)

  def test_loco_command_kind_selects_adapter_method_without_feedback_heuristic(self):
    adapter = LocoCommandKindFakeAdapter()
    registry = ControllerRegistry()
    registry.register(adapter)
    service = ControllerService(
      service_support=LocoCommandKindSupport(),
      controller_registry=registry,
      controller_session=object(),
      udp_transport=object(),
    )
    state = {"controller": {"kind": adapter.kind}}

    target_results, error_response = service.execute_loco_targets(
      state,
      [{"vehicle_id": "v1", "address": 3}],
      loco_command_kind="speed",
      speed=1,
      direction="forward",
    )

    self.assertIsNone(error_response)
    self.assertEqual(adapter.speed_calls, 1)
    self.assertEqual(adapter.function_calls, 0)
    self.assertEqual(adapter.control_calls, 1)
    self.assertIsNone(target_results[0]["feedback"])

  def test_loco_service_uses_train_dcc_range_helpers(self):
    source = inspect.getsource(LocoCommandService)
    self.assertIn("validate_loco_address", source)
    self.assertIn("validate_loco_speed_128", source)
    self.assertNotIn("speed < 0", source)
    self.assertNotIn("speed > 126", source)
    self.assertNotIn("address < 1", source)
    self.assertNotIn("address > 9999", source)

  def test_controller_service_long_flows_are_split_into_helpers(self):
    track_source = inspect.getsource(TrackPowerService)
    cv_source = inspect.getsource(CvProgrammingService)
    loco_source = inspect.getsource(LocoCommandService)

    self.assertIn("def _send_track_output_request(", track_source)
    self.assertIn("def _track_output_success_payload(", track_source)
    self.assertIn("def _cv_write_attempt_outcome(", cv_source)
    self.assertIn("def _readback_request_frame(", cv_source)
    self.assertIn("def _execute_loco_target(", loco_source)

  def test_vehicle_api_requires_persistent_vehicle_store(self):
    from server.api_support.context import ApiSupportContext
    from server.api_support.import_config import ConfigImportApiSupport
    from server.api_support.vehicle_library import VehicleLibraryApiSupport

    sources = "\n".join([
      inspect.getsource(ApiSupportContext),
      inspect.getsource(ConfigImportApiSupport),
      inspect.getsource(VehicleLibraryApiSupport),
    ])

    self.assertNotIn("if self.vehicle_store:", sources)
    self.assertNotIn("if not self.vehicle_store:", sources)
    self.assertNotIn("return http_helpers.success(state", sources)
    self.assertNotIn("return self._patch_state_", sources)
    self.assertNotIn("state.setdefault(\"imports\"", sources)


if __name__ == "__main__":
  unittest.main()

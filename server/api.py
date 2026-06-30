"""HTTP API routing facade."""

import copy
from pathlib import Path
from urllib.parse import urlparse

from server import response
from server.api_support import http_helpers
from server.api_support.context import ApiSupportContext
from server.api_support.controller import ControllerApiSupport
from server.api_support.controller_service import ControllerServicePorts, ControllerServiceSupport
from server.api_support.cv_programming import CvProgrammingApiSupport
from server.api_support.cv_read_all import CvReadAllApiSupport
from server.api_support.import_config import ConfigImportApiSupport
from server.api_support.loco_control import LocoControlApiSupport
from server.api_support.resources import ResourceApiSupport
from server.api_support.routes import handler_for
from server.api_support.vehicle_library import VehicleLibraryApiSupport
from server.capabilities import gateway_capabilities
from server.controller_service import ControllerService
from server.controller_sessions import default_controller_session_registry
from server.controllers.registry import default_controller_registry
from server.cv_metadata import cv_metadata
from server.cv_read_session import CVReadSessionRegistry
from server.importers.registry import default_import_registry


class ApiRouter:
  def __init__(
    self,
    state_store,
    image_dir: Path = Path("data/vehicle-images"),
    probe_runner=None,
    controller_transport=None,
    controller_session_registry=None,
    cv_read_sessions=None,
    vehicle_store=None,
    import_registry=None,
    controller_registry=None,
  ):
    self.controller_transport = controller_transport
    self.controller_registry = controller_registry or default_controller_registry()
    self.controller_session_registry = controller_session_registry or default_controller_session_registry(
      self.controller_registry,
      controller_transport,
    )
    self.cv_read_sessions = cv_read_sessions or CVReadSessionRegistry()
    self.vehicle_store = vehicle_store
    self.import_registry = import_registry or default_import_registry(Path(image_dir))
    self.context = ApiSupportContext(
      state_store=state_store,
      vehicle_store=self.vehicle_store,
      controller_registry=self.controller_registry,
      import_registry=self.import_registry,
      cv_read_sessions=self.cv_read_sessions,
      image_dir=Path(image_dir),
      controller_transport=self.controller_transport,
    )
    controller_service_ports = ControllerServicePorts(
      mark_controller_unreachable_port=self.context.mark_controller_unreachable,
      mark_safety_snapshot_fresh_port=self.context.mark_safety_snapshot_fresh,
      save_port=self.context.save,
      frame_debug_port=http_helpers.frame_debug,
      request_debug_port=http_helpers.request_debug,
      cv_debug_port=http_helpers.cv_debug,
      cv_write_busy_retry_count_port=http_helpers.cv_write_busy_retry_count,
      cv_write_busy_retry_delay_seconds_port=http_helpers.cv_write_busy_retry_delay_seconds,
    )
    self.controller_service_support = ControllerServiceSupport(controller_service_ports)
    self.controller_service = ControllerService(
      service_support=self.controller_service_support,
      controller_registry=self.controller_registry,
      controller_session_registry=self.controller_session_registry,
      controller_transport=self.controller_transport,
    )
    self.controller_api = ControllerApiSupport(self.context, self.controller_service, probe_runner=probe_runner)
    self.vehicle_api = VehicleLibraryApiSupport(self.context)
    self.resource_api = ResourceApiSupport(self.context)
    self.import_api = ConfigImportApiSupport(self.context)
    self.cv_programming_api = CvProgrammingApiSupport(self.context, self.controller_service, self.controller_api, self.vehicle_api)
    self.cv_read_all_api = CvReadAllApiSupport(self.context, self.controller_service, self.controller_api, self.cv_programming_api)
    self.loco_control_api = LocoControlApiSupport(self.context, self.controller_service, self.controller_api, self.vehicle_api)
    self._handlers = self._build_handlers()

  def handle_json(self, method: str, path: str, body: bytes, state: dict):
    route = urlparse(path).path
    handler_name = handler_for(method, route)
    if handler_name is None:
      return self._not_found(route)
    handler = self._handlers.get(handler_name)
    if handler is None:
      return self._not_found(route)
    try:
      return handler(route, body, state)
    except http_helpers.JsonBodyError as exc:
      return response.failure("invalid_json", "请求 JSON 无效", str(exc)), 400

  def import_config_bytes(
    self,
    format_name: str,
    file_name: str,
    body: bytes,
    state: dict,
    include_format_list: bool = True,
    options=None,
  ):
    return self.import_api.import_config_bytes(
      format_name,
      file_name,
      body,
      state,
      include_format_list=include_format_list,
      options=options,
    )

  def persistent_state(self, state: dict) -> dict:
    return self.context.persistent_state(state)

  def _build_handlers(self) -> dict:
    return {
      "capabilities.get": lambda route, body, state: http_helpers.success(
        gateway_capabilities(self.controller_registry, self.import_registry, self._controller_descriptor_configs(state))
      ),
      "state.get": lambda route, body, state: self._state_response(state),
      "vehicles.list": lambda route, body, state: self.vehicle_api.list_vehicles(state),
      "categories.list": lambda route, body, state: self.vehicle_api.list_categories(state),
      "cv_metadata.get": lambda route, body, state: http_helpers.success(cv_metadata()),
      "controller.info": lambda route, body, state: http_helpers.success(self.controller_api.controller_info(state)),
      "vehicles.create": lambda route, body, state: self.vehicle_api.create_vehicle(body, state),
      "vehicles.patch": lambda route, body, state: self.vehicle_api.patch_vehicle(route, body, state),
      "vehicles.delete": lambda route, body, state: self.vehicle_api.delete_vehicle(route, state),
      "vehicles.reorder": lambda route, body, state: self.vehicle_api.reorder_vehicles(body, state),
      "vehicle_images.upload": lambda route, body, state: self.resource_api.upload_vehicle_image(body),
      "categories.create": lambda route, body, state: self.vehicle_api.create_category(body),
      "categories.patch": lambda route, body, state: self.vehicle_api.patch_category(route, body),
      "categories.delete": lambda route, body, state: self.vehicle_api.delete_category(route),
      "controller.read_info": lambda route, body, state: self.controller_api.read_info(state),
      "controller.track_power": lambda route, body, state: self.controller_api.track_power(body, state),
      "controller.dc_control": lambda route, body, state: self.controller_api.dc_control(body, state),
      "controller.reset_config": lambda route, body, state: self.controller_api.reset_config(body, state),
      "controller.probe": lambda route, body, state: self.controller_api.probe(body, state),
      "controller.track_mode": lambda route, body, state: self.controller_api.track_mode(body, state),
      "controller.settings": lambda route, body, state: self.controller_api.settings(body, state),
      "cv.read": lambda route, body, state: self.cv_programming_api.read_cv(body, state),
      "cv.read_all": lambda route, body, state: self.cv_read_all_api.read_all(body, state),
      "cv.read_all_cancel": lambda route, body, state: self.cv_read_all_api.cancel(body),
      "cv.write": lambda route, body, state: self.cv_programming_api.write_cv(body, state),
      "chip_info.read": lambda route, body, state: self.cv_programming_api.read_chip_info(body, state),
      "address.read": lambda route, body, state: self.cv_programming_api.read_address(body, state),
      "address.write": lambda route, body, state: self.cv_programming_api.write_address(body, state),
      "loco.speed": lambda route, body, state: self.loco_control_api.handle(route, body, state),
      "loco.function": lambda route, body, state: self.loco_control_api.handle(route, body, state),
      "consists.list": lambda route, body, state: self.vehicle_api.list_consists(state),
      "consists.create": lambda route, body, state: self.vehicle_api.create_consist(body, state),
      "consists.patch": lambda route, body, state: self.vehicle_api.patch_consist(route, body, state),
      "consists.delete": lambda route, body, state: self.vehicle_api.delete_consist(route, state),
      "consists.operation": lambda route, body, state: self.loco_control_api.handle_consist_operation(route, body, state),
    }

  def _state_response(self, state: dict):
    state = self.context.state_with_vehicle_store_data(state)
    return http_helpers.success(copy.deepcopy(state))

  def _controller_descriptor_configs(self, state: dict) -> dict:
    if self.context.state_store and hasattr(self.context.state_store, "controller_descriptor_configs"):
      return self.context.state_store.controller_descriptor_configs()
    controller = state.get("controller", {}) if isinstance(state, dict) else {}
    kind = controller.get("kind") if isinstance(controller, dict) else ""
    return {kind: controller} if kind else {}

  def _not_found(self, route: str):
    return http_helpers.failure("not_found", "API 路径不存在", route, status=404)

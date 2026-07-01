"""Shared API route metadata for HTTP dispatch and gateway locking."""


MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
MAX_VEHICLE_IMAGE_JSON_BODY_BYTES = 3 * 1024 * 1024
MAX_IMPORT_BODY_BYTES = 64 * 1024 * 1024

LOCK_MODE_STATEFUL = "stateful"
LOCK_MODE_SNAPSHOT = "snapshot"
LOCK_MODE_HARDWARE = "hardware"
LOCK_MODE_HARDWARE_SESSION = "hardware_session"


GET_ROUTES = {
  "/api/capabilities": "capabilities.get",
  "/api/state": "state.get",
  "/api/vehicles": "vehicles.list",
  "/api/categories": "categories.list",
  "/api/consists": "consists.list",
  "/api/cv/metadata": "cv_metadata.get",
  "/api/controller/info": "controller.info",
}

POST_ROUTES = {
  "/api/vehicles": "vehicles.create",
  "/api/vehicles/clear": "vehicles.clear",
  "/api/vehicle-images": "vehicle_images.upload",
  "/api/categories": "categories.create",
  "/api/controller/read-info": "controller.read_info",
  "/api/track-power": "controller.track_power",
  "/api/dc-control": "controller.dc_control",
  "/api/controller/reset-config": "controller.reset_config",
  "/api/controller/probe": "controller.probe",
  "/api/cv/read": "cv.read",
  "/api/cv/read-all": "cv.read_all",
  "/api/cv/read-all/cancel": "cv.read_all_cancel",
  "/api/cv/write": "cv.write",
  "/api/chip-info/read": "chip_info.read",
  "/api/address/read": "address.read",
  "/api/address/write": "address.write",
  "/api/loco/speed": "loco.speed",
  "/api/loco/function": "loco.function",
  "/api/consists": "consists.create",
}

PATCH_ROUTES = {
  "/api/vehicles/order": "vehicles.reorder",
  "/api/controller/track-mode": "controller.track_mode",
  "/api/controller/settings": "controller.settings",
}

API_MUTATION_DEFAULT = {
  "json_body": True,
  "body_limit": MAX_JSON_BODY_BYTES,
  "gateway_handler": "api",
  "lock_mode": LOCK_MODE_STATEFUL,
}

API_MUTATION_ROUTES = {
  "/api/import/config": {
    "json_body": False,
    "body_limit": MAX_IMPORT_BODY_BYTES,
    "gateway_handler": "import_config",
  },
  "/api/vehicle-images": {
    "body_limit": MAX_VEHICLE_IMAGE_JSON_BODY_BYTES,
  },
  "/api/cv/read-all": {
    "lock_mode": LOCK_MODE_HARDWARE_SESSION,
  },
  "/api/cv/read-all/cancel": {
    "lock_mode": LOCK_MODE_SNAPSHOT,
  },
  "/api/controller/read-info": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/controller/probe": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/track-power": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/dc-control": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/cv/read": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/cv/write": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/chip-info/read": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/address/read": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/address/write": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/loco/speed": {"lock_mode": LOCK_MODE_HARDWARE},
  "/api/loco/function": {"lock_mode": LOCK_MODE_HARDWARE},
}


def route_segments(route: str) -> list[str]:
  normalized = route[1:] if route.startswith("/") else route
  return normalized.split("/") if normalized else []


def resource_route(route: str, resource: str) -> bool:
  segments = route_segments(route)
  return len(segments) == 3 and segments[:2] == ["api", resource] and segments[2] != ""


def consist_operation_route(route: str) -> bool:
  segments = route_segments(route)
  return (
    len(segments) == 4
    and segments[:2] == ["api", "consists"]
    and segments[2] != ""
    and segments[3] in {"speed", "stop"}
  )


def dynamic_handler(method: str, route: str) -> str | None:
  if method == "PATCH":
    if resource_route(route, "categories"):
      return "categories.patch"
    if resource_route(route, "vehicles"):
      return "vehicles.patch"
    if resource_route(route, "consists"):
      return "consists.patch"
  if method == "DELETE":
    if resource_route(route, "categories"):
      return "categories.delete"
    if resource_route(route, "vehicles"):
      return "vehicles.delete"
    if resource_route(route, "consists"):
      return "consists.delete"
  if method == "POST" and consist_operation_route(route):
    return "consists.operation"
  return None


def handler_for(method: str, route: str) -> str | None:
  if method == "GET":
    return GET_ROUTES.get(route)
  if method == "POST":
    return POST_ROUTES.get(route) or dynamic_handler(method, route)
  if method == "PATCH":
    return PATCH_ROUTES.get(route) or dynamic_handler(method, route)
  if method == "DELETE":
    return dynamic_handler(method, route)
  return None


def mutation_route_spec(method: str, route: str) -> dict:
  spec = dict(API_MUTATION_DEFAULT)
  spec.update(API_MUTATION_ROUTES.get(route, {}))
  if method == "DELETE":
    spec["json_body"] = False
    spec["body_limit"] = 0
  if method == "POST" and consist_operation_route(route):
    spec["lock_mode"] = LOCK_MODE_HARDWARE
  return spec

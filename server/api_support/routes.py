"""Shared API route metadata for HTTP dispatch and gateway locking."""

import json


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
  "/api/vehicle-images": "vehicle_images.upload",
  "/api/categories": "categories.create",
  "/api/controller/read-info": "controller.read_info",
  "/api/track-power": "controller.track_power",
  "/api/dc-control": "controller.dc_control",
  "/api/controller/connect": "controller.connect",
  "/api/controller/probe": "controller.probe",
  "/api/controller/disconnect": "controller.disconnect",
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


def dynamic_handler(method: str, route: str) -> str | None:
  if method == "PATCH":
    if route.startswith("/api/categories/"):
      return "categories.patch"
    if route.startswith("/api/vehicles/"):
      return "vehicles.patch"
    if route.startswith("/api/consists/"):
      return "consists.patch"
  if method == "DELETE":
    if route.startswith("/api/categories/"):
      return "categories.delete"
    if route.startswith("/api/vehicles/"):
      return "vehicles.delete"
    if route.startswith("/api/consists/"):
      return "consists.delete"
  if method == "POST" and route.startswith("/api/consists/") and route.endswith(("/speed", "/stop")):
    return "consists.speed"
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


def mutation_route_spec(method: str, route: str, body: bytes) -> dict:
  spec = dict(API_MUTATION_DEFAULT)
  spec.update(API_MUTATION_ROUTES.get(route, {}))
  if method == "DELETE":
    spec["json_body"] = False
    spec["body_limit"] = 0
  if method == "POST" and route.startswith("/api/consists/") and route.endswith(("/speed", "/stop")):
    spec["lock_mode"] = LOCK_MODE_HARDWARE
  if method == "PATCH" and route == "/api/controller/settings":
    try:
      payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
      return spec
    if isinstance(payload, dict) and payload.get("apply_to_device") is True:
      spec["lock_mode"] = LOCK_MODE_HARDWARE
  return spec

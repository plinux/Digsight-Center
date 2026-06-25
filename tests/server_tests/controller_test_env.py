"""Helpers for environment-specific controller test inputs."""

from contextlib import contextmanager
import json
import ipaddress
import os
from pathlib import Path
import tempfile

from server import models
from server.api import ApiRouter
from server.app_state import default_state
from server.vehicle_store import VehicleStore


SIMULATED_CONTROLLER_IP = "192.0.2.10"
TEST_CONTROLLER_IP_ENV_VAR = "DIGSIGHT_TEST_D9000_IP"
DEFAULT_RUNTIME_CONFIG_PATH = Path("data/app-state.json")
DEFAULT_CONTROLLER_CONFIG_DIR = Path("config/controllers")


def controller_runtime_config_path() -> Path:
  return DEFAULT_RUNTIME_CONFIG_PATH


def controller_config_path(controller_kind: str) -> Path:
  return DEFAULT_CONTROLLER_CONFIG_DIR / models.controller_config_file_name(controller_kind)


def configured_controller_kind() -> str:
  path = controller_runtime_config_path()
  if not path.exists():
    return models.CONTROLLER_KIND_DIGSIGHT
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError("controller runtime config must be a JSON object")
  controller = data.get("controller", {})
  if not isinstance(controller, dict):
    raise ValueError("controller runtime config must include a controller object")
  return models.validate_controller_kind(controller.get("kind", models.CONTROLLER_KIND_DIGSIGHT))


def configured_controller_ip() -> str | None:
  env_controller_ip = str(os.environ.get(TEST_CONTROLLER_IP_ENV_VAR) or "").strip()
  if env_controller_ip:
    ipaddress.ip_address(env_controller_ip)
    return env_controller_ip
  path = controller_config_path(configured_controller_kind())
  if not path.exists():
    return None
  data = json.loads(path.read_text(encoding="utf-8"))
  if not isinstance(data, dict):
    raise ValueError("controller config must be a JSON object")
  controller_ip = str(data.get("ip") or "").strip()
  if not controller_ip or controller_ip == models.CONTROLLER_DEFAULT_IP:
    return None
  ipaddress.ip_address(controller_ip)
  return controller_ip


def require_configured_controller_ip(testcase) -> str:
  controller_ip = configured_controller_ip()
  if not controller_ip:
    testcase.skipTest(f"set {TEST_CONTROLLER_IP_ENV_VAR} to run real hardware tests")
  return controller_ip


def controller_test_ip() -> str:
  return SIMULATED_CONTROLLER_IP


def controller_ip_payload(**overrides) -> bytes:
  payload = {"ip": controller_test_ip()}
  payload.update(overrides)
  return json.dumps(payload).encode("utf-8")


def ping_command(ip=None) -> list[str]:
  return ["ping", "-c", "2", "-W", "1000", ip or controller_test_ip()]


@contextmanager
def temporary_vehicle_router(**router_kwargs):
  state_store = router_kwargs.pop("state_store", None)
  with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    vehicle_store = router_kwargs.pop("vehicle_store", VehicleStore(root / "vehicles.sqlite3"))
    image_dir = router_kwargs.pop("image_dir", root / "vehicle-images")
    router = ApiRouter(state_store, image_dir=image_dir, vehicle_store=vehicle_store, **router_kwargs)
    yield router, vehicle_store, default_state()

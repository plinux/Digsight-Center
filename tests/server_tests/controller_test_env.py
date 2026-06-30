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
from server.controllers.base import ControllerTransportDescriptor
from server.controllers.example import ExampleControllerAdapter
from server.controllers.registry import default_controller_registry
from server.vehicle_store import VehicleStore


SIMULATED_CONTROLLER_IP = "192.0.2.10"
TEST_CONTROLLER_IP_ENV_VAR = "DIGSIGHT_TEST_D9000_IP"
DEFAULT_RUNTIME_CONFIG_PATH = Path("data/app-state.json")
DEFAULT_CONTROLLER_CONFIG_DIR = Path("config/controllers")


class CustomDefaultsControllerAdapter(ExampleControllerAdapter):
  kind = "custom_defaults_controller"
  label = "Custom Defaults Controller"
  default_display_name = "Custom Defaults Controller"
  protocol = "CustomProtocol"
  default_ip = "192.0.2.44"
  config_file_name = "custom-controller-settings.json"
  runtime_transport_fields = ("udp_port", "local_udp_port", "udp_checksum_algorithm")
  transport_descriptor = ControllerTransportDescriptor(
    kind="udp",
    defaults={
      "udp_port": 21105,
      "local_udp_port": 0,
      "udp_checksum_algorithm": "none",
    },
    metadata={"checksum_algorithms": ("none",)},
  )

  def apply_transport_runtime(self, controller: dict) -> None:
    transport = controller.get("transport") if isinstance(controller.get("transport"), dict) else {}
    defaults = self.transport_descriptor.defaults
    controller["udp_port"] = int(transport.get("udp_port", defaults["udp_port"]))
    controller["local_udp_port"] = int(transport.get("local_udp_port", defaults["local_udp_port"]))
    controller["udp_checksum_algorithm"] = str(transport.get("udp_checksum_algorithm", defaults["udp_checksum_algorithm"]))


def controller_runtime_config_path() -> Path:
  return DEFAULT_RUNTIME_CONFIG_PATH


def controller_config_path(controller_kind: str) -> Path:
  return DEFAULT_CONTROLLER_CONFIG_DIR / default_controller_registry().config_file_name(controller_kind)


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
  transport = {}
  for key in ["udp_port", "local_udp_port", "udp_checksum_algorithm"]:
    if key in overrides:
      transport[key] = overrides.pop(key)
  if transport:
    payload["transport"] = transport
  payload.update(overrides)
  return json.dumps(payload).encode("utf-8")


def ping_command(ip=None) -> list[str]:
  return ["ping", "-c", "2", "-W", "1000", ip or controller_test_ip()]


def ready_loco_control_state(track_mode: str = "ho") -> dict:
  state = default_state()
  state["controller"].update({
    "ip": "192.0.2.10",
    "track_mode": track_mode,
    "udp_port": 12000,
    "local_udp_port": 6667,
    "udp_checksum_algorithm": "xor",
    "last_probe_ok": True,
    "controller_reachable": True,
    "booster_status": {
      "source": "dxdcnet_status_0x23",
      "power_on": True,
      "dcc_mode": True,
    },
    "safety_snapshot": {
      "controller_endpoint_version": 1,
      "last_read_info_at": "2026-06-22T00:00:00+08:00",
      "booster_status_fresh": True,
      "programming_track_status_fresh": True,
    },
  })
  return state


@contextmanager
def temporary_vehicle_router(**router_kwargs):
  state_store = router_kwargs.pop("state_store", None)
  with tempfile.TemporaryDirectory() as temp_dir:
    root = Path(temp_dir)
    vehicle_store = router_kwargs.pop("vehicle_store", VehicleStore(root / "vehicles.sqlite3"))
    image_dir = router_kwargs.pop("image_dir", root / "vehicle-images")
    router = ApiRouter(state_store, image_dir=image_dir, vehicle_store=vehicle_store, **router_kwargs)
    yield router, vehicle_store, default_state()

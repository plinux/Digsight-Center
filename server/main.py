"""Local HTTP gateway entrypoint for Digsight-Center."""

from dataclasses import dataclass
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import ipaddress
import json
import os
import posixpath
import socket
import sys
import threading
import time
from urllib.parse import unquote, urlparse

from server import response
from server.api import ApiRouter
from server.api_support.controller import controller_settings_apply_to_device
from server.api_support.routes import (
  API_MUTATION_ROUTES,
  LOCK_MODE_HARDWARE,
  LOCK_MODE_HARDWARE_SESSION,
  LOCK_MODE_SNAPSHOT,
  mutation_route_spec,
)
from server.app_state import AppStateStore
from server.controllers.registry import default_controller_registry
from server.importers.registry import default_import_registry
from server.public_paths import STATIC_PUBLIC_PREFIXES
from server.vehicle_store import VehicleStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
STATIC_PUBLIC_FILES = {
  "/",
  "/index.html",
  "/manual/MANUAL.html",
  "/config/function-icons.json",
}
CLIENT_HEADER_NAME = "X-Digsight-Client"
CLIENT_HEADER_VALUE = "digsight-web"
TRUSTED_DNS_HOSTS = {"localhost"}
GATEWAY_CONTEXT = None


def static_public_files(controller_registry=None, import_registry=None) -> set[str]:
  controller_registry = controller_registry or default_controller_registry()
  import_registry = import_registry or default_import_registry(PROJECT_ROOT / "data" / "vehicle-images")
  files = set(STATIC_PUBLIC_FILES)
  files.update(
    descriptor["config_public_path"]
    for descriptor in controller_registry.descriptors()
    if descriptor.get("config_public_path")
  )
  for descriptor in import_registry.descriptors():
    files.update(descriptor.get("public_files") or [])
    files.update(descriptor.get("function_icon_mapping_files") or [])
  return files


@dataclass
class GatewayContext:
  project_root: Path
  state_store: AppStateStore
  vehicle_store: VehicleStore
  api_router: ApiRouter
  started_at: float
  hardware_session_lock: threading.Lock


def create_gateway_context(project_root: Path = PROJECT_ROOT) -> GatewayContext:
  project_root = Path(project_root)
  controller_registry = default_controller_registry()
  vehicle_store = VehicleStore(project_root / "data" / "vehicles.sqlite3")
  state_store = AppStateStore(
    project_root / "data" / "app-state.json",
    controller_registry=controller_registry,
    vehicle_store=vehicle_store,
  )
  vehicle_store.ensure_initial_test_vehicles()
  api_router = ApiRouter(
    state_store,
    project_root / "data" / "vehicle-images",
    vehicle_store=vehicle_store,
    controller_registry=controller_registry,
  )
  return GatewayContext(project_root, state_store, vehicle_store, api_router, time.time(), threading.Lock())


def gateway_context() -> GatewayContext:
  global GATEWAY_CONTEXT
  if GATEWAY_CONTEXT is None:
    GATEWAY_CONTEXT = create_gateway_context()
  return GATEWAY_CONTEXT


def _hardware_session_lock(context):
  lock = getattr(context, "hardware_session_lock", None)
  if lock is None:
    lock = threading.Lock()
    setattr(context, "hardware_session_lock", lock)
  return lock


def build_health_payload(started_at: float, now: float, python_version: str) -> dict:
  return {
    "name": "Digsight-Center",
    "uptime_seconds": round(now - started_at, 3),
    "python": python_version.split()[0],
  }


def add_no_store_headers(handler) -> None:
  handler.send_header("Cache-Control", "no-store, max-age=0")
  handler.send_header("Pragma", "no-cache")
  handler.send_header("Expires", "0")


def normalized_url_path(raw_path: str) -> str:
  parsed_path = urlparse(raw_path).path
  path = posixpath.normpath(unquote(parsed_path))
  if not path.startswith("/"):
    path = f"/{path}"
  return path


def api_url_path(raw_path: str) -> str:
  path = unquote(urlparse(raw_path).path)
  if not path.startswith("/"):
    return f"/{path}"
  return path or "/"


def is_public_static_path(raw_path: str, *, controller_registry=None, import_registry=None) -> bool:
  path = normalized_url_path(raw_path)
  return path in static_public_files(controller_registry, import_registry) or any(path.startswith(prefix) for prefix in STATIC_PUBLIC_PREFIXES)


def _split_host_header(value: str) -> tuple[str, str]:
  try:
    parsed = urlparse(f"//{value}")
    host = parsed.hostname or ""
    port = str(parsed.port or "")
  except ValueError:
    return "", ""
  return host.lower(), port


def _is_ip_literal(host: str) -> bool:
  try:
    ipaddress.ip_address(host)
    return True
  except ValueError:
    return False


def _trusted_host_netloc(value: str) -> tuple[str, str] | None:
  host, port = _split_host_header(value)
  if not host:
    return None
  if _is_ip_literal(host) or host in TRUSTED_DNS_HOSTS:
    return host, port
  return None


def _trusted_request_netloc(headers) -> tuple[str, str] | None:
  return _trusted_host_netloc(headers.get("Host", ""))


def _trusted_url_netloc(value: str) -> tuple[str, str] | None:
  parsed = urlparse(value)
  if parsed.scheme not in {"http", "https"}:
    return None
  return _trusted_host_netloc(parsed.netloc)


def _origin_matches_host(headers) -> bool:
  origin = headers.get("Origin", "")
  request_netloc = _trusted_request_netloc(headers)
  if request_netloc is None:
    return False
  if not origin:
    return True
  return _trusted_url_netloc(origin) == request_netloc


def _referer_matches_host(headers) -> bool:
  referer = headers.get("Referer", "")
  request_netloc = _trusted_request_netloc(headers)
  if request_netloc is None:
    return False
  if not referer:
    return True
  return _trusted_url_netloc(referer) == request_netloc


def parse_gateway_args(argv=None):
  parser = argparse.ArgumentParser(description="Run Digsight-Center local gateway.")
  parser.add_argument("--host", default=DEFAULT_HOST, help="HTTP listen host, defaults to all IPv4 interfaces.")
  parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="HTTP listen port.")
  parser.add_argument(
    "--trusted-host",
    action="append",
    default=[],
    help="Additional DNS host allowed by Host/Origin checks.",
  )
  return parser.parse_args(argv)


class IPv6ThreadingHTTPServer(ThreadingHTTPServer):
  address_family = socket.AF_INET6

  def server_bind(self):
    if hasattr(socket, "IPV6_V6ONLY"):
      try:
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
      except OSError:
        pass
    super().server_bind()


def server_class_for_host(host: str):
  try:
    address = ipaddress.ip_address(host)
  except ValueError:
    return ThreadingHTTPServer
  return IPv6ThreadingHTTPServer if address.version == 6 else ThreadingHTTPServer


def configure_trusted_dns_hosts(hosts: list[str]) -> None:
  TRUSTED_DNS_HOSTS.clear()
  TRUSTED_DNS_HOSTS.add("localhost")
  TRUSTED_DNS_HOSTS.update(host.strip().lower() for host in hosts if host.strip())


def format_listen_url(host: str, port: int) -> str:
  try:
    address = ipaddress.ip_address(host)
  except ValueError:
    return f"http://{host}:{port}/"
  if address.version == 6:
    return f"http://[{host}]:{port}/"
  return f"http://{host}:{port}/"


def import_options_from_header(value: str) -> dict:
  if not value:
    return {}
  try:
    options = json.loads(value)
  except json.JSONDecodeError as exc:
    raise ValueError(f"X-Import-Options must be a JSON object: {exc}") from exc
  if not isinstance(options, dict):
    raise ValueError("X-Import-Options must be a JSON object")
  return options


class DigsightHandler(SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, directory=str(gateway_context().project_root), **kwargs)

  def end_headers(self) -> None:
    add_no_store_headers(self)
    super().end_headers()

  def _send_json(self, status_code: int, body: bytes, *, include_body: bool = True) -> None:
    self.send_response(status_code)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    if include_body:
      self.wfile.write(body)

  def _read_limited_body(self, limit_bytes: int):
    try:
      length = int(self.headers.get("Content-Length", "0"))
    except (TypeError, ValueError):
      return None, response.failure(
        "invalid_content_length",
        "请求长度无效",
        "Content-Length must be an integer",
      ), 400
    if length < 0:
      return None, response.failure(
        "invalid_content_length",
        "请求长度无效",
        "Content-Length must be non-negative",
      ), 400
    if length > limit_bytes:
      return None, response.failure(
        "request_too_large",
        "请求内容过大",
        f"请求体超过 {limit_bytes} 字节限制",
      ), 413
    return self.rfile.read(length), None, None

  def _reject_unsafe_mutation(self, *, json_body: bool):
    host_error_body, host_status = self._reject_untrusted_api_host()
    if host_error_body is not None:
      return host_error_body, host_status
    if self.headers.get("Sec-Fetch-Site", "").lower() == "cross-site":
      return response.failure(
        "cross_origin_request_denied",
        "跨站请求已拒绝",
        "Sec-Fetch-Site is cross-site",
      ), 403
    if not _origin_matches_host(self.headers) or not _referer_matches_host(self.headers):
      return response.failure(
        "cross_origin_request_denied",
        "跨站请求已拒绝",
        "Origin or Referer does not match Host",
      ), 403
    if self.headers.get(CLIENT_HEADER_NAME, "") != CLIENT_HEADER_VALUE:
      return response.failure(
        "missing_client_header",
        "请求来源未确认",
        f"{CLIENT_HEADER_NAME} is required",
      ), 403
    if json_body:
      content_type = self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
      if content_type not in {"application/json"} and not content_type.endswith("+json"):
        return response.failure(
          "unsupported_media_type",
          "请求类型不支持",
          "JSON API requires application/json",
        ), 415
    return None, None

  def _reject_untrusted_api_host(self):
    if _trusted_request_netloc(self.headers) is not None:
      return None, None
    return response.failure(
      "untrusted_host",
      "请求 Host 不可信",
      "Host must be an IP literal, localhost, or a configured trusted DNS host",
    ), 403

  def _run_stateful_mutation(self, mutation, *, persist=None):
    result = {}

    def mutator(state):
      response_body, status = mutation(state)
      result["response_body"] = response_body
      result["status"] = status

    gateway_context().state_store.update(mutator, persist=persist)
    return result["response_body"], result["status"]

  def _load_state_snapshot(self):
    state_store = gateway_context().state_store
    if hasattr(state_store, "load_snapshot"):
      return state_store.load_snapshot()
    return state_store.load()

  def _api_mutation_route_spec(self, method: str, path: str, body: bytes) -> dict:
    route = api_url_path(path)
    spec = mutation_route_spec(method, route)
    if controller_settings_apply_to_device(method, route, body):
      spec["lock_mode"] = LOCK_MODE_HARDWARE
    return spec

  def _handle_api_mutation(self, method: str, path: str, body: bytes):
    context = gateway_context()
    spec = self._api_mutation_route_spec(method, path, body)
    if spec["lock_mode"] == LOCK_MODE_HARDWARE:
      with _hardware_session_lock(context):
        state = self._load_state_snapshot()
        expected_revision = int(state.get("controller", {}).get("runtime_revision", 0) or 0)
        state["_expected_controller_runtime_revision"] = expected_revision
        response_body, status = context.api_router.handle_json(method, path, body, state)
        pending_state = state.pop("_pending_persistent_state", None)
        state.pop("_expected_controller_runtime_revision", None)
        if pending_state is not None:
          try:
            context.state_store.save_after_hardware(pending_state, expected_controller_revision=expected_revision)
          except ValueError as exc:
            return response.failure(
              "controller_runtime_changed",
              "控制器状态已变化",
              "硬件操作期间控制器端点、模式或安全状态已变化，请刷新状态后重试",
              {"detail": str(exc)},
            ), 409
        return response_body, status
    return self._run_stateful_mutation(
      lambda state: context.api_router.handle_json(method, path, body, state),
      persist=context.api_router.persistent_state,
    )

  def _handle_hardware_session_api_mutation(self, method: str, path: str, body: bytes):
    context = gateway_context()
    with _hardware_session_lock(context):
      return self._handle_snapshot_api(method, path, body)

  def _handle_snapshot_api_mutation(self, method: str, path: str, body: bytes):
    return self._handle_snapshot_api(method, path, body)

  def _handle_snapshot_api(self, method: str, path: str, body: bytes):
    context = gateway_context()
    state = self._load_state_snapshot()
    return context.api_router.handle_json(method, path, body, state)

  def _handle_config_import_mutation(self, format_name: str, file_name: str, body: bytes, options: dict | None = None):
    context = gateway_context()
    return self._run_stateful_mutation(
      lambda state: context.api_router.import_config_bytes(
        format_name,
        file_name,
        body,
        state,
        options=options,
      ),
      persist=context.api_router.persistent_state,
    )

  def _send_rejected_host_if_needed(self, *, include_body: bool = True) -> bool:
    error_body, status = self._reject_untrusted_api_host()
    if error_body is None:
      return False
    self._send_json(status, error_body, include_body=include_body)
    return True

  def _send_not_found(self, path: str, *, include_body: bool = True) -> None:
    self._send_json(
      404,
      response.failure("not_found", "路径不存在", normalized_url_path(path)),
      include_body=include_body,
    )

  def _handle_public_static_request(self, *, include_body: bool) -> None:
    if self._send_rejected_host_if_needed(include_body=include_body):
      return
    context = gateway_context()
    if not is_public_static_path(
      self.path,
      controller_registry=context.api_router.controller_registry,
      import_registry=context.api_router.import_registry,
    ):
      self._send_not_found(self.path, include_body=include_body)
      return
    if include_body:
      super().do_GET()
      return
    super().do_HEAD()

  def _handle_api_get_request(self) -> None:
    if self._send_rejected_host_if_needed():
      return
    context = gateway_context()
    state = context.state_store.load()
    response_body, status = context.api_router.handle_json("GET", self.path, b"", state)
    self._send_json(status, response_body)

  def _dispatch_mutation_response(self, method: str, path: str, body: bytes, spec: dict) -> tuple[bytes, int]:
    if spec["lock_mode"] == LOCK_MODE_SNAPSHOT:
      return self._handle_snapshot_api_mutation(method, path, body)
    if spec["lock_mode"] == LOCK_MODE_HARDWARE_SESSION:
      return self._handle_hardware_session_api_mutation(method, path, body)
    return self._handle_api_mutation(method, path, body)

  def _handle_import_config_mutation(self, body: bytes) -> None:
    file_name = self.headers.get("X-File-Name", "import.config")
    format_name = (self.headers.get("X-Import-Format") or "").strip()
    if not format_name:
      self._send_json(
        400,
        response.failure(
          "missing_import_format",
          "缺少导入格式",
          "导入配置必须通过 X-Import-Format 指定配置格式",
        ),
      )
      return
    try:
      import_options = import_options_from_header(self.headers.get("X-Import-Options", ""))
    except ValueError as exc:
      self._send_json(400, response.failure("invalid_import_options", "导入选项无效", str(exc)))
      return
    response_body, status = self._handle_config_import_mutation(format_name, file_name, body, import_options)
    self._send_json(status, response_body)

  def _handle_json_mutation_request(self, method: str) -> None:
    if not self.path.startswith("/api/"):
      self._send_not_found(self.path)
      return
    route = api_url_path(self.path)
    if method == "POST" and route.startswith("/api/import/") and route not in API_MUTATION_ROUTES:
      self._send_not_found(route)
      return
    spec = self._api_mutation_route_spec(method, route, b"")
    error_body, status = self._reject_unsafe_mutation(json_body=spec["json_body"])
    if error_body is not None:
      self._send_json(status, error_body)
      return
    if method == "DELETE":
      response_body, status = self._dispatch_mutation_response(method, route, b"", spec)
      self._send_json(status, response_body)
      return
    body, error_body, status = self._read_limited_body(spec["body_limit"])
    if error_body is not None:
      self._send_json(status, error_body)
      return
    if spec["gateway_handler"] == "import_config":
      self._handle_import_config_mutation(body)
      return
    response_body, status = self._dispatch_mutation_response(method, route, body, spec)
    self._send_json(status, response_body)

  def do_GET(self):
    if self.path == "/api/health":
      if self._send_rejected_host_if_needed():
        return
      body = response.success(build_health_payload(gateway_context().started_at, time.time(), sys.version))
      self._send_json(200, body)
      return
    if self.path.startswith("/api/"):
      self._handle_api_get_request()
      return
    self._handle_public_static_request(include_body=True)

  def do_HEAD(self):
    if self.path == "/api/health" or self.path.startswith("/api/"):
      if self._send_rejected_host_if_needed(include_body=False):
        return
      self._send_json(
        405,
        response.failure("method_not_allowed", "方法不允许", "HEAD is not supported for API"),
        include_body=False,
      )
      return
    self._handle_public_static_request(include_body=False)

  def do_POST(self):
    self._handle_json_mutation_request("POST")

  def do_PATCH(self):
    self._handle_json_mutation_request("PATCH")

  def do_DELETE(self):
    self._handle_json_mutation_request("DELETE")


def main():
  global GATEWAY_CONTEXT
  args = parse_gateway_args()
  configure_trusted_dns_hosts(getattr(args, "trusted_host", []))
  GATEWAY_CONTEXT = create_gateway_context(PROJECT_ROOT)
  context = gateway_context()

  os.chdir(context.project_root)
  server_class = server_class_for_host(args.host)
  server = server_class((args.host, args.port), DigsightHandler)
  print(f"Digsight-Center gateway listening on {format_listen_url(args.host, args.port)}")
  if args.host == "0.0.0.0":
    print(f"Remote clients should open http://<this-mac-lan-ip>:{args.port}/")
  elif args.host == "::":
    print(f"Remote clients should open http://[<this-mac-ipv6>]:{args.port}/")
  server.serve_forever()


if __name__ == "__main__":
  main()

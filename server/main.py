"""Local HTTP gateway entrypoint for Digsight-Center."""

from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import argparse
import ipaddress
import os
import posixpath
import socket
import sys
import time
from urllib.parse import unquote, urlparse

from server import response
from server.api import ApiRouter
from server.app_state import AppStateStore
from server.vehicle_store import VehicleStore


PROJECT_ROOT = Path(__file__).resolve().parent.parent
STARTED_AT = time.time()
STATE_STORE = AppStateStore(PROJECT_ROOT / "data" / "app-state.json")
VEHICLE_STORE = VehicleStore(PROJECT_ROOT / "data" / "vehicles.sqlite3")
VEHICLE_STORE.ensure_initial_test_vehicles()
API_ROUTER = ApiRouter(STATE_STORE, PROJECT_ROOT / "data" / "vehicle-images", vehicle_store=VEHICLE_STORE)
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765
STATIC_PUBLIC_FILES = {
  "/",
  "/index.html",
  "/manual/MANUAL.html",
  "/config/function-icons.json",
  "/config/function-icon-mappings/z21.json",
}
STATIC_PUBLIC_PREFIXES = (
  "/assets/",
  "/manual/assets/",
  "/data/vehicle-images/",
)
MAX_JSON_BODY_BYTES = 2 * 1024 * 1024
MAX_IMPORT_BODY_BYTES = 64 * 1024 * 1024
TRUSTED_DNS_HOSTS = {"localhost"}


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


def is_public_static_path(raw_path: str) -> bool:
  path = normalized_url_path(raw_path)
  return path in STATIC_PUBLIC_FILES or any(path.startswith(prefix) for prefix in STATIC_PUBLIC_PREFIXES)


def _split_host_header(value: str) -> tuple[str, str]:
  parsed = urlparse(f"//{value}")
  host = parsed.hostname or ""
  port = str(parsed.port or "")
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


class DigsightHandler(SimpleHTTPRequestHandler):
  def __init__(self, *args, **kwargs):
    super().__init__(*args, directory=str(PROJECT_ROOT), **kwargs)

  def end_headers(self) -> None:
    add_no_store_headers(self)
    super().end_headers()

  def _send_json(self, status_code: int, body: bytes) -> None:
    self.send_response(status_code)
    self.send_header("Content-Type", "application/json; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.end_headers()
    self.wfile.write(body)

  def _request_meta(self) -> dict:
    return {
      "headers": {key: value for key, value in self.headers.items()},
      "client_ip": self.client_address[0] if self.client_address else "",
    }

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

  def _run_stateful_mutation(self, mutation, *, persist=None):
    result = {}

    def mutator(state):
      response_body, status = mutation(state)
      result["response_body"] = response_body
      result["status"] = status

    STATE_STORE.update(mutator, persist=persist)
    return result["response_body"], result["status"]

  def _handle_api_mutation(self, method: str, path: str, body: bytes):
    return self._run_stateful_mutation(
      lambda state: API_ROUTER.handle_json(method, path, body, state, request_meta=self._request_meta()),
      persist=API_ROUTER._persistent_state,
    )

  def _handle_config_import_mutation(self, format_name: str, file_name: str, body: bytes):
    return self._run_stateful_mutation(
      lambda state: API_ROUTER.import_config_bytes(format_name, file_name, body, state, request_meta=self._request_meta()),
      persist=API_ROUTER._persistent_state,
    )

  def _handle_z21_import_mutation(self, file_name: str, body: bytes):
    return self._run_stateful_mutation(
      lambda state: API_ROUTER.import_z21_bytes(file_name, body, state, request_meta=self._request_meta()),
      persist=API_ROUTER._persistent_state,
    )

  def do_GET(self):
    if self.path == "/api/health":
      body = response.success(build_health_payload(STARTED_AT, time.time(), sys.version))
      self._send_json(200, body)
      return
    if self.path.startswith("/api/"):
      state = STATE_STORE.load()
      response_body, status = API_ROUTER.handle_json("GET", self.path, b"", state, request_meta=self._request_meta())
      self._send_json(status, response_body)
      return
    if not is_public_static_path(self.path):
      self._send_json(404, response.failure("not_found", "路径不存在", normalized_url_path(self.path)))
      return
    return super().do_GET()

  def do_POST(self):
    if self.path == "/api/import/config":
      body, error_body, status = self._read_limited_body(MAX_IMPORT_BODY_BYTES)
      if error_body is not None:
        self._send_json(status, error_body)
        return
      file_name = self.headers.get("X-File-Name", "import.config")
      format_name = self.headers.get("X-Import-Format", "z21_layout_config")
      response_body, status = self._handle_config_import_mutation(format_name, file_name, body)
      self._send_json(status, response_body)
      return

    if self.path == "/api/import/z21":
      body, error_body, status = self._read_limited_body(MAX_IMPORT_BODY_BYTES)
      if error_body is not None:
        self._send_json(status, error_body)
        return
      file_name = self.headers.get("X-File-Name", "import.z21")
      response_body, status = self._handle_z21_import_mutation(file_name, body)
      self._send_json(status, response_body)
      return

    if self.path.startswith("/api/"):
      body, error_body, status = self._read_limited_body(MAX_JSON_BODY_BYTES)
      if error_body is not None:
        self._send_json(status, error_body)
        return
      response_body, status = self._handle_api_mutation("POST", self.path, body)
      self._send_json(status, response_body)
      return

    self._send_json(404, response.failure("not_found", "路径不存在", self.path))

  def do_PATCH(self):
    if self.path.startswith("/api/"):
      body, error_body, status = self._read_limited_body(MAX_JSON_BODY_BYTES)
      if error_body is not None:
        self._send_json(status, error_body)
        return
      response_body, status = self._handle_api_mutation("PATCH", self.path, body)
      self._send_json(status, response_body)
      return

    self._send_json(404, response.failure("not_found", "路径不存在", self.path))

  def do_DELETE(self):
    if self.path.startswith("/api/"):
      response_body, status = self._handle_api_mutation("DELETE", self.path, b"")
      self._send_json(status, response_body)
      return

    self._send_json(404, response.failure("not_found", "路径不存在", self.path))


def main():
  args = parse_gateway_args()
  configure_trusted_dns_hosts(getattr(args, "trusted_host", []))

  os.chdir(PROJECT_ROOT)
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

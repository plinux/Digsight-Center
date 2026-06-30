import json
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
from pathlib import Path
import socket
import threading
import time
from types import SimpleNamespace
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from server import response
import server.main as gateway_main
from server.controllers.registry import ControllerRegistry
from server.importers.base import ImportFormatDescriptor
from server.importers.registry import ImportRegistry
from server.main import DigsightHandler, is_public_static_path
from server.vehicle_store import VehicleStore
from tests.server_tests.test_controller_registry import FakeControllerAdapter
from tests.server_tests.z21_fixture_builder import write_minimal_z21_archive

CLIENT_HEADERS = {"X-Digsight-Client": "digsight-web"}
JSON_CLIENT_HEADERS = {"Content-Type": "application/json", **CLIENT_HEADERS}
IMPORT_CLIENT_HEADERS = {"X-Digsight-Client": "digsight-web"}


class FakeConfigImporter:
  descriptor = ImportFormatDescriptor(
    format="fake_layout_config",
    label="Fake Layout Config",
    extensions=[".fake"],
    public_files=["/config/function-icon-mappings/fake.json"],
  )

  def import_bytes(self, request):
    raise NotImplementedError


class SilentDigsightHandler(DigsightHandler):
  def log_message(self, format, *args):
    return


class GatewaySecurityTest(unittest.TestCase):
  @classmethod
  def setUpClass(cls):
    cls.server = ThreadingHTTPServer(("127.0.0.1", 0), SilentDigsightHandler)
    cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
    cls.thread.start()
    cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

  @classmethod
  def tearDownClass(cls):
    cls.server.shutdown()
    cls.server.server_close()
    cls.thread.join(timeout=2)

  def fetch(self, path: str):
    try:
      with urlopen(f"{self.base_url}{path}", timeout=2) as response:
        return response.status, response.read()
    except HTTPError as error:
      try:
        return error.code, error.read()
      finally:
        error.close()

  def head(self, path: str):
    request = Request(f"{self.base_url}{path}", method="HEAD")
    try:
      with urlopen(request, timeout=2) as response:
        return response.status, response.headers
    except HTTPError as error:
      try:
        return error.code, error.headers
      finally:
        error.close()

  def post(self, path: str, body: bytes, headers=None):
    request = Request(f"{self.base_url}{path}", data=body, headers=headers or {}, method="POST")
    try:
      with urlopen(request, timeout=2) as response:
        return response.status, response.read()
    except HTTPError as error:
      try:
        return error.code, error.read()
      finally:
        error.close()

  def request(self, method: str, path: str, body: bytes = b"", headers=None):
    request = Request(f"{self.base_url}{path}", data=body if body else None, headers=headers or {}, method=method)
    try:
      with urlopen(request, timeout=2) as response:
        return response.status, response.read()
    except HTTPError as error:
      try:
        return error.code, error.read()
      finally:
        error.close()

  def raw_request(self, request_text: str):
    host, port = self.server.server_address
    with socket.create_connection((host, port), timeout=2) as sock:
      sock.sendall(request_text.encode("ascii"))
      sock.shutdown(socket.SHUT_WR)
      chunks = []
      while True:
        chunk = sock.recv(4096)
        if not chunk:
          break
        chunks.append(chunk)
      return b"".join(chunks)

  def raw_status_and_json(self, request_text: str):
    raw = self.raw_request(request_text)
    header, _, body = raw.partition(b"\r\n\r\n")
    status_line = header.splitlines()[0].decode("ascii")
    status = int(status_line.split()[1])
    payload = json.loads(body.decode("utf-8")) if body else {}
    return status, payload

  def test_static_server_blocks_server_source_tree(self):
    status, body = self.fetch("/server/api.py")
    self.assertEqual(status, 404)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(payload["error"]["type"], "not_found")

  def test_head_static_server_blocks_server_source_tree(self):
    status, headers = self.head("/server/api.py")
    self.assertEqual(status, 404)
    self.assertNotEqual(headers.get("Content-Type"), "text/x-python")

  def test_head_static_server_allows_public_manual(self):
    status, headers = self.head("/manual/MANUAL.html")
    self.assertEqual(status, 200)
    self.assertIn("text/html", headers.get("Content-Type", ""))

  def test_head_api_returns_method_not_allowed(self):
    status, headers = self.head("/api/health")
    self.assertEqual(status, 405)
    self.assertEqual(headers.get("Content-Type"), "application/json; charset=utf-8")

  def test_get_state_rejects_untrusted_dns_host(self):
    status, payload = self.raw_status_and_json(
      "GET /api/state HTTP/1.1\r\n"
      f"Host: attacker.example:{self.server.server_address[1]}\r\n"
      "\r\n"
    )
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "untrusted_host")

  def test_get_health_rejects_untrusted_dns_host(self):
    status, payload = self.raw_status_and_json(
      "GET /api/health HTTP/1.1\r\n"
      f"Host: attacker.example:{self.server.server_address[1]}\r\n"
      "\r\n"
    )
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "untrusted_host")

  def test_static_get_index_rejects_untrusted_dns_host(self):
    status, payload = self.raw_status_and_json(
      "GET /index.html HTTP/1.1\r\n"
      f"Host: attacker.example:{self.server.server_address[1]}\r\n"
      "\r\n"
    )
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "untrusted_host")

  def test_static_get_controller_config_rejects_untrusted_dns_host(self):
    status, payload = self.raw_status_and_json(
      "GET /config/controllers/Digsight_D9000.json HTTP/1.1\r\n"
      f"Host: attacker.example:{self.server.server_address[1]}\r\n"
      "\r\n"
    )
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "untrusted_host")

  def test_static_head_rejects_untrusted_dns_host(self):
    status, _payload = self.raw_status_and_json(
      "HEAD /config/controllers/Digsight_D9000.json HTTP/1.1\r\n"
      f"Host: attacker.example:{self.server.server_address[1]}\r\n"
      "\r\n"
    )
    self.assertEqual(status, 403)

  def test_get_state_rejects_malformed_host_port(self):
    status, payload = self.raw_status_and_json(
      "GET /api/state HTTP/1.1\r\n"
      "Host: 127.0.0.1:bad\r\n"
      "\r\n"
    )
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "untrusted_host")

  def test_static_server_blocks_runtime_app_state(self):
    status, body = self.fetch("/data/app-state.json")
    self.assertEqual(status, 404)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(payload["error"]["type"], "not_found")

  def test_static_server_blocks_runtime_vehicle_database(self):
    status, body = self.fetch("/data/vehicles.sqlite3")
    self.assertEqual(status, 404)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(payload["error"]["type"], "not_found")

  def test_static_allow_list_exposes_manual_without_exposing_internal_docs(self):
    self.assertTrue(is_public_static_path("/manual/MANUAL.html"))
    self.assertTrue(is_public_static_path("/manual/assets/manual-vehicle-control.png"))
    self.assertFalse(is_public_static_path("/docs/superpowers/plans/internal.md"))
    self.assertFalse(is_public_static_path("/docs/manual-assets/manual-vehicle-control.png"))
    self.assertFalse(is_public_static_path("/docs/real-device-test-log.md"))

  def test_static_allow_list_uses_supplied_controller_registry(self):
    registry = ControllerRegistry()
    registry.register(FakeControllerAdapter(), default=True)
    self.assertTrue(is_public_static_path(
      "/config/controllers/Fake_Controller_Config.json",
      controller_registry=registry,
    ))

  def test_static_allow_list_uses_supplied_import_registry(self):
    registry = ImportRegistry(default_format="fake_layout_config")
    registry.register(FakeConfigImporter(), default=True)
    self.assertTrue(is_public_static_path(
      "/config/function-icon-mappings/fake.json",
      import_registry=registry,
    ))

  def test_static_handler_uses_active_import_registry_public_files(self):
    class FakeStaticRouter:
      def __init__(self, import_registry):
        self.controller_registry = ControllerRegistry()
        self.import_registry = import_registry

    registry = ImportRegistry(default_format="fake_layout_config")
    registry.register(FakeConfigImporter(), default=True)
    fake_file = gateway_main.PROJECT_ROOT / "config" / "function-icon-mappings" / "fake.json"
    original_context = gateway_main.GATEWAY_CONTEXT
    try:
      fake_file.write_text('{"ok": true}\n', encoding="utf-8")
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=None,
        vehicle_store=None,
        api_router=FakeStaticRouter(registry),
        started_at=0,
      )
      status, body = self.fetch("/config/function-icon-mappings/fake.json")
      self.assertEqual(status, 200)
      self.assertEqual(json.loads(body.decode("utf-8")), {"ok": True})

      status, headers = self.head("/config/function-icon-mappings/fake.json")
      self.assertEqual(status, 200)
      self.assertIn("application/json", headers.get("Content-Type", ""))
    finally:
      gateway_main.GATEWAY_CONTEXT = original_context
      fake_file.unlink(missing_ok=True)

  def test_gateway_mutation_route_metadata_is_centralized(self):
    source = Path("server/main.py").read_text(encoding="utf-8")

    self.assertIn("API_MUTATION_ROUTES", source)
    self.assertIn("body_limit", source)
    self.assertNotIn("IMPORT_MUTATION_PATHS =", source)
    self.assertNotIn("LOCK_FREE_HARDWARE_POST_PATHS =", source)

  def test_same_origin_helpers_accept_matching_host_and_reject_foreign_hosts(self):
    headers = {
      "Host": "127.0.0.1:8765",
      "Origin": "http://127.0.0.1:8765",
      "Referer": "http://127.0.0.1:8765/",
    }
    self.assertTrue(gateway_main._origin_matches_host(headers))
    self.assertTrue(gateway_main._referer_matches_host(headers))
    self.assertFalse(gateway_main._origin_matches_host({"Host": "127.0.0.1:8765", "Origin": "https://attacker.example"}))
    self.assertFalse(gateway_main._referer_matches_host({"Host": "127.0.0.1:8765", "Referer": "ftp://127.0.0.1:8765/"}))

  def test_same_origin_helpers_reject_malformed_ports_without_raising(self):
    self.assertFalse(gateway_main._origin_matches_host({
      "Host": "127.0.0.1:8765",
      "Origin": "http://127.0.0.1:bad",
    }))
    self.assertFalse(gateway_main._referer_matches_host({
      "Host": "127.0.0.1:8765",
      "Referer": "http://[::1]:bad/",
    }))

  def test_same_origin_helpers_reject_matching_untrusted_dns_host(self):
    headers = {
      "Host": "attacker.example:8765",
      "Origin": "http://attacker.example:8765",
      "Referer": "http://attacker.example:8765/",
    }
    self.assertFalse(gateway_main._origin_matches_host(headers))
    self.assertFalse(gateway_main._referer_matches_host(headers))

  def test_same_origin_helpers_accept_ip_literal_hosts(self):
    for host in ["127.0.0.1:8765", "192.168.1.20:8765", "[::1]:8765", "[2001:db8::10]:8765"]:
      with self.subTest(host=host):
        headers = {
          "Host": host,
          "Origin": f"http://{host}",
          "Referer": f"http://{host}/",
        }
        self.assertTrue(gateway_main._origin_matches_host(headers))
        self.assertTrue(gateway_main._referer_matches_host(headers))

  def test_same_origin_helpers_accept_explicit_trusted_dns_host(self):
    original = gateway_main.TRUSTED_DNS_HOSTS
    try:
      gateway_main.TRUSTED_DNS_HOSTS = {"localhost", "layout.local"}
      headers = {
        "Host": "layout.local:8765",
        "Origin": "http://layout.local:8765",
        "Referer": "http://layout.local:8765/",
      }
      self.assertTrue(gateway_main._origin_matches_host(headers))
      self.assertTrue(gateway_main._referer_matches_host(headers))
    finally:
      gateway_main.TRUSTED_DNS_HOSTS = original

  def test_invalid_content_length_returns_structured_400(self):
    raw = self.raw_request(
      "POST /api/cv/read HTTP/1.1\r\n"
      f"Host: 127.0.0.1:{self.server.server_address[1]}\r\n"
      "Content-Type: application/json\r\n"
      "X-Digsight-Client: digsight-web\r\n"
      "Content-Length: invalid\r\n"
      "\r\n"
    )
    header, _, body = raw.partition(b"\r\n\r\n")
    self.assertIn(b" 400 ", header)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(payload["error"]["type"], "invalid_content_length")

  def test_oversized_json_body_returns_413(self):
    raw = self.raw_request(
      "POST /api/cv/read HTTP/1.1\r\n"
      f"Host: 127.0.0.1:{self.server.server_address[1]}\r\n"
      "Content-Type: application/json\r\n"
      "X-Digsight-Client: digsight-web\r\n"
      f"Content-Length: {2 * 1024 * 1024 + 1}\r\n"
      "\r\n"
    )
    header, _, body = raw.partition(b"\r\n\r\n")
    self.assertIn(b" 413 ", header)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(payload["error"]["type"], "request_too_large")

  def test_malformed_json_returns_structured_400(self):
    status, payload_body = self.post("/api/controller/connect", b"{", JSON_CLIENT_HEADERS)
    payload = json.loads(payload_body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_json")

  def test_json_mutation_rejects_non_object_json_roots(self):
    for body in [b"[]", b"null", b'"text"', b"42"]:
      with self.subTest(body=body):
        status, payload_body = self.post("/api/controller/connect", body, JSON_CLIENT_HEADERS)
        payload = json.loads(payload_body.decode("utf-8"))
        self.assertEqual(status, 400)
        self.assertEqual(payload["error"]["type"], "invalid_json")
        self.assertIn("object", payload["error"]["detail"])

  def test_cross_origin_json_mutation_is_rejected_before_router(self):
    status, body = self.post(
      "/api/track-power",
      b'{"powered":true}',
      {
        "Content-Type": "application/json",
        "Origin": "https://attacker.example",
        "Sec-Fetch-Site": "cross-site",
        "X-Digsight-Client": "digsight-web",
      },
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 403)
    self.assertEqual(payload["error"]["type"], "cross_origin_request_denied")

  def test_json_mutation_rejects_text_plain_body(self):
    status, body = self.post(
      "/api/track-power",
      b'{"powered":true}',
      {
        "Content-Type": "text/plain",
        "X-Digsight-Client": "digsight-web",
      },
    )
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 415)
    self.assertEqual(payload["error"]["type"], "unsupported_media_type")

  def test_gateway_routes_patch_delete_and_import_mutations_through_state_store(self):
    class FakeStateStore:
      def __init__(self):
        self.persist_values = []

      def update(self, mutator, *, persist=None):
        self.persist_values.append(persist)
        mutator({"controller": {}})

    class FakeRouter:
      def persistent_state(self, _state):
        return {"vehicles": []}

      def handle_json(self, method, path, body, state):
        return response.success({
          "method": method,
          "path": path,
          "body": body.decode("utf-8"),
        }), 200

      def import_config_bytes(self, format_name, file_name, body, state, options=None):
        return response.success({
          "format": format_name,
          "file_name": file_name,
          "size": len(body),
          "options": options or {},
        }), 200

    original_context = gateway_main.GATEWAY_CONTEXT
    fake_store = FakeStateStore()
    try:
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=fake_store,
        vehicle_store=None,
        api_router=FakeRouter(),
        started_at=0,
      )

      status, body = self.request("PATCH", "/api/controller/settings", b'{"track_mode":"ho"}', JSON_CLIENT_HEADERS)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["method"], "PATCH")
      self.assertEqual(payload["data"]["path"], "/api/controller/settings")

      status, body = self.request("DELETE", "/api/categories/category-1", headers=CLIENT_HEADERS)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["method"], "DELETE")
      self.assertEqual(payload["data"]["path"], "/api/categories/category-1")

      status, body = self.post(
        "/api/import/config",
        b"layout-bytes",
        {
          **IMPORT_CLIENT_HEADERS,
          "X-Import-Format": "z21_layout_config",
          "X-File-Name": "layout.z21",
          "X-Import-Options": '{"track_mode":"ho"}',
        },
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"], {
        "format": "z21_layout_config",
        "file_name": "layout.z21",
        "size": 12,
        "options": {"track_mode": "ho"},
      })

      status, body = self.post(
        "/api/import/config",
        b"layout-bytes",
        {**IMPORT_CLIENT_HEADERS, "X-Import-Format": "z21_layout_config", "X-Import-Options": "[]"},
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "invalid_import_options")

      status, body = self.post("/api/import/config", b"layout-bytes", {**IMPORT_CLIENT_HEADERS, "X-File-Name": "layout.z21"})
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 400)
      self.assertEqual(payload["error"]["type"], "missing_import_format")

      status, body = self.post("/api/import/z21", b"z21-bytes", {**IMPORT_CLIENT_HEADERS, "X-File-Name": "sample.z21"})
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 404)
      self.assertEqual(payload["error"]["type"], "not_found")
      self.assertEqual([persist({}) for persist in fake_store.persist_values], [{"vehicles": []}] * 3)
    finally:
      gateway_main.GATEWAY_CONTEXT = original_context

  def test_controller_settings_apply_to_device_uses_hardware_lock_after_body_read(self):
    class FakeStateStore:
      def __init__(self):
        self.update_called = False
        self.load_snapshot_called = False

      def load_snapshot(self):
        self.load_snapshot_called = True
        return {
          "controller": {
            "runtime_revision": 7,
          }
        }

      def update(self, mutator, *, persist=None):
        self.update_called = True
        mutator({"controller": {}})

    class FakeRouter:
      def persistent_state(self, _state):
        return {"vehicles": []}

      def __init__(self):
        self.expected_revision = None
        self.body = None

      def handle_json(self, method, path, body, state):
        self.expected_revision = state.get("_expected_controller_runtime_revision")
        self.body = body
        return response.success({
          "method": method,
          "path": path,
          "expected_revision": self.expected_revision,
        }), 200

    original_context = gateway_main.GATEWAY_CONTEXT
    fake_store = FakeStateStore()
    fake_router = FakeRouter()
    try:
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=fake_store,
        vehicle_store=None,
        api_router=fake_router,
        started_at=0,
      )

      status, body = self.request(
        "PATCH",
        "/api/controller/settings",
        b'{"apply_to_device":true,"track_profiles":{"ho":{"current_limit_ma":4000}}}',
        JSON_CLIENT_HEADERS,
      )
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertEqual(payload["data"]["expected_revision"], 7)
      self.assertTrue(fake_store.load_snapshot_called)
      self.assertFalse(fake_store.update_called)
      self.assertEqual(fake_router.body, b'{"apply_to_device":true,"track_profiles":{"ho":{"current_limit_ma":4000}}}')
    finally:
      gateway_main.GATEWAY_CONTEXT = original_context

  def test_cv_read_all_cancel_is_not_blocked_by_long_read_all_request(self):
    class FakeStateStore:
      def __init__(self):
        self.update_called = False

      def load(self):
        return {"controller": {}}

      def update(self, mutator, *, persist=None):
        self.update_called = True
        raise AssertionError("cv read-all routes must not hold the global state update lock")

    class FakeRouter:
      def persistent_state(self, _state):
        return {}

      def __init__(self):
        self.read_all_started = threading.Event()
        self.release_read_all = threading.Event()

      def handle_json(self, method, path, body, state):
        if path == "/api/cv/read-all":
          self.read_all_started.set()
          self.release_read_all.wait(2)
          return response.success({"path": path, "finished": True}), 200
        if path == "/api/cv/read-all/cancel":
          return response.success({"path": path, "cancelled": True}), 200
        return response.failure("unexpected_route", "Unexpected route", path), 500

    original_context = gateway_main.GATEWAY_CONTEXT
    fake_store = FakeStateStore()
    fake_router = FakeRouter()
    read_all_result = {}

    def run_read_all():
      read_all_result["status"], read_all_result["body"] = self.post(
        "/api/cv/read-all",
        b'{"session_id":"session-lock-test","cv_numbers":[1,2]}',
        JSON_CLIENT_HEADERS,
      )

    try:
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=fake_store,
        vehicle_store=None,
        api_router=fake_router,
        started_at=0,
      )
      thread = threading.Thread(target=run_read_all, daemon=True)
      thread.start()
      self.assertTrue(fake_router.read_all_started.wait(1), "read-all route did not start")

      started = time.monotonic()
      status, body = self.post(
        "/api/cv/read-all/cancel",
        b'{"session_id":"session-lock-test"}',
        JSON_CLIENT_HEADERS,
      )
      elapsed = time.monotonic() - started
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["data"]["cancelled"])
      self.assertLess(elapsed, 0.5)
      self.assertFalse(fake_store.update_called)
    finally:
      fake_router.release_read_all.set()
      if "thread" in locals():
        thread.join(1)
      gateway_main.GATEWAY_CONTEXT = original_context

  def test_cv_read_all_blocks_other_hardware_session_until_finished(self):
    class FakeStateStore:
      def load_snapshot(self):
        return {"controller": {"runtime_revision": 3}, "vehicles": [], "functions": [], "categories": [], "consists": [], "imports": []}

      def load(self):
        return self.load_snapshot()

      def save_after_hardware(self, state, *, expected_controller_revision=None):
        return state

    class FakeRouter:
      def persistent_state(self, _state):
        return {}

      def __init__(self):
        self.read_all_started = threading.Event()
        self.release_read_all = threading.Event()
        self.track_power_entered = threading.Event()

      def handle_json(self, method, path, body, state):
        if path == "/api/cv/read-all":
          self.read_all_started.set()
          self.release_read_all.wait(2)
          return response.success({"path": path, "finished": True}), 200
        if path == "/api/track-power":
          self.track_power_entered.set()
          state["_pending_persistent_state"] = state
          return response.success({"path": path, "finished": True}), 200
        return response.failure("unexpected_route", "Unexpected route", path), 500

    original_context = gateway_main.GATEWAY_CONTEXT
    fake_router = FakeRouter()
    read_all_result = {}
    track_result = {}

    def run_read_all():
      read_all_result["status"], read_all_result["body"] = self.post(
        "/api/cv/read-all",
        b'{"session_id":"session-hardware-lock-test","cv_numbers":[1,2]}',
        JSON_CLIENT_HEADERS,
      )

    def run_track_power():
      track_result["status"], track_result["body"] = self.post(
        "/api/track-power",
        b'{"powered":true}',
        JSON_CLIENT_HEADERS,
      )

    try:
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=FakeStateStore(),
        vehicle_store=None,
        api_router=fake_router,
        started_at=0,
      )
      read_thread = threading.Thread(target=run_read_all, daemon=True)
      read_thread.start()
      self.assertTrue(fake_router.read_all_started.wait(1), "read-all route did not start")

      track_thread = threading.Thread(target=run_track_power, daemon=True)
      track_thread.start()
      time.sleep(0.2)
      self.assertFalse(fake_router.track_power_entered.is_set(), "track-power entered while read-all was active")

      fake_router.release_read_all.set()
      read_thread.join(1)
      track_thread.join(1)
      self.assertEqual(read_all_result["status"], 200)
      self.assertEqual(track_result["status"], 200)
      self.assertTrue(fake_router.track_power_entered.is_set())
    finally:
      fake_router.release_read_all.set()
      for thread in (locals().get("read_thread"), locals().get("track_thread")):
        if thread:
          thread.join(1)
      gateway_main.GATEWAY_CONTEXT = original_context

  def test_hardware_mutation_does_not_block_regular_state_update(self):
    class FakeStateStore:
      def __init__(self):
        self.lock = threading.Lock()
        self.update_paths = []

      def load_snapshot(self):
        return {"controller": {}, "vehicles": [], "functions": [], "categories": [], "consists": [], "imports": []}

      def load(self):
        return self.load_snapshot()

      def update(self, mutator, *, persist=None):
        with self.lock:
          state = self.load_snapshot()
          result = mutator(state)
          return result

    class FakeRouter:
      def __init__(self):
        self.track_started = threading.Event()
        self.release_track = threading.Event()

      def persistent_state(self, state):
        return state

      def handle_json(self, method, path, body, state):
        if path == "/api/track-power":
          self.track_started.set()
          self.release_track.wait(2)
          return response.success({"path": path, "finished": True}), 200
        if path == "/api/vehicles":
          return response.success({"path": path, "created": True}), 200
        return response.failure("unexpected_route", "Unexpected route", path), 500

    original_context = gateway_main.GATEWAY_CONTEXT
    fake_store = FakeStateStore()
    fake_router = FakeRouter()
    track_result = {}

    def run_track_power():
      track_result["status"], track_result["body"] = self.post(
        "/api/track-power",
        b'{"powered":true}',
        JSON_CLIENT_HEADERS,
      )

    try:
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=fake_store,
        vehicle_store=None,
        api_router=fake_router,
        started_at=0,
      )
      thread = threading.Thread(target=run_track_power, daemon=True)
      thread.start()
      self.assertTrue(fake_router.track_started.wait(1), "track-power route did not start")

      started = time.monotonic()
      status, body = self.post("/api/vehicles", b'{"name":"test","address":3}', JSON_CLIENT_HEADERS)
      elapsed = time.monotonic() - started
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 200)
      self.assertTrue(payload["data"]["created"])
      self.assertLess(elapsed, 0.5)
    finally:
      fake_router.release_track.set()
      if "thread" in locals():
        thread.join(1)
      gateway_main.GATEWAY_CONTEXT = original_context

  def test_hardware_mutation_returns_conflict_when_runtime_changes_before_save(self):
    class FakeStateStore:
      def load_snapshot(self):
        return {"controller": {"runtime_revision": 0}, "vehicles": [], "functions": [], "categories": [], "consists": [], "imports": []}

      def save_after_hardware(self, state, *, expected_controller_revision=None):
        raise ValueError("controller runtime changed during hardware operation")

    class FakeRouter:
      def persistent_state(self, state):
        return state

      def handle_json(self, method, path, body, state):
        state["_pending_persistent_state"] = {
          "controller": {"runtime_revision": 0, "last_probe_ok": True},
          "vehicles": [],
          "functions": [],
          "categories": [],
          "consists": [],
          "imports": [],
        }
        return response.success({"path": path}), 200

    original_context = gateway_main.GATEWAY_CONTEXT
    try:
      gateway_main.GATEWAY_CONTEXT = SimpleNamespace(
        project_root=gateway_main.PROJECT_ROOT,
        state_store=FakeStateStore(),
        vehicle_store=None,
        api_router=FakeRouter(),
        started_at=0,
      )
      status, body = self.post("/api/track-power", b'{"powered":true}', JSON_CLIENT_HEADERS)
      payload = json.loads(body.decode("utf-8"))
      self.assertEqual(status, 409)
      self.assertEqual(payload["error"]["type"], "controller_runtime_changed")
    finally:
      gateway_main.GATEWAY_CONTEXT = original_context


if __name__ == "__main__":
  unittest.main()

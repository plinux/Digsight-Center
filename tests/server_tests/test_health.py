import json
import importlib.util
import inspect
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import server.main as gateway_main
from server.main import add_no_store_headers, build_health_payload, parse_gateway_args


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESS_HELPER_PATH = PROJECT_ROOT / "scripts" / "digsight_web_process.py"


def load_process_helper():
  spec = importlib.util.spec_from_file_location("digsight_web_process", PROCESS_HELPER_PATH)
  module = importlib.util.module_from_spec(spec)
  spec.loader.exec_module(module)
  return module


class HealthTest(unittest.TestCase):
  def test_health_payload_identifies_gateway(self):
    payload = build_health_payload(started_at=0, now=2.5, python_version="3.12.0 test")
    self.assertEqual(payload["name"], "Digsight-Center")
    self.assertEqual(payload["uptime_seconds"], 2.5)
    self.assertEqual(payload["python"], "3.12.0")

  def test_static_gateway_disables_browser_cache(self):
    sent_headers = []

    class FakeHandler:
      def send_header(self, name, value):
        sent_headers.append((name, value))

    add_no_store_headers(FakeHandler())
    self.assertIn(("Cache-Control", "no-store, max-age=0"), sent_headers)
    self.assertIn(("Pragma", "no-cache"), sent_headers)
    self.assertIn(("Expires", "0"), sent_headers)

  def test_gateway_defaults_to_lan_accessible_host(self):
    args = parse_gateway_args([])
    self.assertEqual(args.host, "0.0.0.0")
    self.assertEqual(args.port, 8765)

  def test_gateway_host_can_still_be_overridden(self):
    args = parse_gateway_args(["--host", "127.0.0.1", "--port", "9000"])
    self.assertEqual(args.host, "127.0.0.1")
    self.assertEqual(args.port, 9000)

  def test_gateway_trusted_host_args_are_repeatable(self):
    args = parse_gateway_args(["--host", "::", "--trusted-host", "layout.local", "--trusted-host", "digsight.local"])
    self.assertEqual(args.host, "::")
    self.assertEqual(args.trusted_host, ["layout.local", "digsight.local"])

  def test_create_gateway_context_accepts_custom_paths(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      context = gateway_main.create_gateway_context(root)
      self.assertEqual(context.project_root, root)
      self.assertTrue((root / "data" / "vehicles.sqlite3").exists())
      self.assertIsNotNone(context.api_router)

  def test_gateway_uses_ipv6_server_for_ipv6_host(self):
    server_class = gateway_main.server_class_for_host("::")
    self.assertEqual(server_class.address_family, gateway_main.socket.AF_INET6)

  def test_gateway_configures_trusted_dns_hosts(self):
    original = set(gateway_main.TRUSTED_DNS_HOSTS)
    try:
      gateway_main.configure_trusted_dns_hosts(["layout.local", " DIGSIGHT.local "])
      self.assertEqual(gateway_main.TRUSTED_DNS_HOSTS, {"localhost", "layout.local", "digsight.local"})
    finally:
      gateway_main.TRUSTED_DNS_HOSTS.clear()
      gateway_main.TRUSTED_DNS_HOSTS.update(original)

  def test_ipv6_server_can_bind_when_platform_supports_ipv6(self):
    if not gateway_main.socket.has_ipv6:
      self.skipTest("IPv6 is not available on this platform")
    server_class = gateway_main.server_class_for_host("::1")
    server = server_class(("::1", 0), gateway_main.DigsightHandler)
    try:
      self.assertEqual(server.address_family, gateway_main.socket.AF_INET6)
      self.assertGreater(server.server_address[1], 0)
    finally:
      server.server_close()

  def test_start_web_script_uses_lan_accessible_host(self):
    script = PROJECT_ROOT / "scripts" / "start_web.sh"
    self.assertTrue(script.exists())
    content = script.read_text(encoding="utf-8")
    self.assertIn('WEB_HOST="0.0.0.0"', content)
    self.assertIn('WEB_PORT="8765"', content)
    self.assertIn("-H|--host)", content)
    self.assertIn("-P|--port)", content)
    self.assertIn("--trusted-host)", content)
    self.assertIn("--python)", content)
    self.assertNotIn("DIGSIGHT_WEB_HOST", content)
    self.assertNotIn("DIGSIGHT_WEB_PORT", content)
    self.assertNotIn("PYTHON_BIN", content)
    self.assertNotIn("${PYTHON_BIN:-", content)
    self.assertNotIn("/opt/" + "homebrew/bin/python3", content)
    self.assertIn('"server.main"', content)
    self.assertIn('"--trusted-host"', content)
    self.assertIn('"PYTHONPATH"', content)
    self.assertIn('"packages" / "train-dcc" / "src"', content)
    self.assertIn('"packages" / "digsight-dxdcnet" / "src"', content)

  def test_public_document_entry_files_exist(self):
    self.assertTrue((PROJECT_ROOT / "README.md").is_file())
    self.assertTrue((PROJECT_ROOT / "manual" / "MANUAL.html").is_file())

  def test_gateway_static_controller_config_allowlist_is_registry_driven(self):
    source = inspect.getsource(gateway_main)
    self.assertIn("def static_public_files(", source)
    self.assertIn("registry.descriptors()", source)
    self.assertNotIn("Digsight_D9000", source)
    self.assertIn("/config/controllers/Digsight_D9000.json", gateway_main.static_public_files())

  def test_start_web_script_starts_gateway_as_detached_background_process(self):
    content = (PROJECT_ROOT / "scripts" / "start_web.sh").read_text(encoding="utf-8")
    self.assertIn("PID_FILE=", content)
    self.assertIn("LOG_FILE=", content)
    self.assertIn("digsight_web_process.py", content)
    self.assertIn('"project_root"', content)
    self.assertIn('"command"', content)
    self.assertIn("subprocess.Popen", content)
    self.assertIn("start_new_session=True", content)
    self.assertNotIn("def read_pid_record", content)
    self.assertNotIn("def gateway_process_matches", content)
    self.assertNotIn('exec "${PYTHON_CMD}" -m server.main', content)

  def test_stop_web_script_stops_gateway_from_pid_file(self):
    script = PROJECT_ROOT / "scripts" / "stop_web.sh"
    self.assertTrue(script.exists())
    content = script.read_text(encoding="utf-8")
    self.assertIn("PID_FILE=", content)
    self.assertIn("digsight_web_process.py", content)
    self.assertIn("--python)", content)
    self.assertNotIn("python3 - \"${PID_FILE}\"", content)
    self.assertNotIn("def read_pid_record", content)
    self.assertNotIn("def gateway_process_matches", content)
    self.assertIn("Refusing to stop PID", content)
    self.assertIn("kill", content)
    self.assertIn("rm -f", content)

  def test_pid_helper_rejects_digit_only_pidfile(self):
    helper = load_process_helper()
    with tempfile.TemporaryDirectory() as temp_dir:
      pid_file = Path(temp_dir) / "gateway.pid"
      pid_file.write_text("999999\n", encoding="utf-8")

      status, pid, detail = helper.classify_pid_file(
        pid_file,
        PROJECT_ROOT,
        process_exists=lambda _pid: False,
      )

    self.assertEqual(status, "invalid")
    self.assertEqual(pid, 0)
    self.assertIn("JSON", detail)

  def test_pid_helper_refuses_mismatched_live_process(self):
    helper = load_process_helper()
    with tempfile.TemporaryDirectory() as temp_dir:
      pid_file = Path(temp_dir) / "gateway.pid"
      pid_file.write_text(
        json.dumps({"pid": 123, "project_root": str(PROJECT_ROOT), "command": ["python3", "-m", "server.main"]}),
        encoding="utf-8",
      )

      status, pid, detail = helper.classify_pid_file(
        pid_file,
        PROJECT_ROOT,
        process_exists=lambda _pid: True,
        command_reader=lambda _pid: "python3 unrelated.py",
        cwd_reader=lambda _pid: str(PROJECT_ROOT),
      )

    self.assertEqual(status, "mismatch")
    self.assertEqual(pid, 123)
    self.assertIn("unrelated.py", detail)

  def test_start_web_script_checks_python_version(self):
    content = (PROJECT_ROOT / "scripts" / "start_web.sh").read_text(encoding="utf-8")
    self.assertIn("sys.version_info", content)
    self.assertIn("Python 3.10", content)
    self.assertIn("Use --python", content)

  def test_gateway_main_constructs_server_and_prints_lan_hint(self):
    calls = []

    class FakeServer:
      def __init__(self, address, handler_class):
        calls.append(("server", address, handler_class.__name__))

      def serve_forever(self):
        calls.append(("serve_forever",))
        raise RuntimeError("stop test server")

    original_parse = gateway_main.parse_gateway_args
    original_server = gateway_main.ThreadingHTTPServer
    original_chdir = gateway_main.os.chdir
    original_create_context = gateway_main.create_gateway_context
    original_context = gateway_main.GATEWAY_CONTEXT
    try:
      gateway_main.parse_gateway_args = lambda: SimpleNamespace(host="0.0.0.0", port=8765)
      gateway_main.ThreadingHTTPServer = FakeServer
      gateway_main.os.chdir = lambda path: calls.append(("chdir", str(path)))
      gateway_main.GATEWAY_CONTEXT = None
      gateway_main.create_gateway_context = lambda project_root: SimpleNamespace(
        project_root=project_root,
        state_store=None,
        vehicle_store=None,
        api_router=None,
        started_at=0,
      )
      with self.assertRaisesRegex(RuntimeError, "stop test server"):
        gateway_main.main()
    finally:
      gateway_main.parse_gateway_args = original_parse
      gateway_main.ThreadingHTTPServer = original_server
      gateway_main.os.chdir = original_chdir
      gateway_main.create_gateway_context = original_create_context
      gateway_main.GATEWAY_CONTEXT = original_context

    self.assertEqual(calls[0], ("chdir", str(PROJECT_ROOT)))
    self.assertEqual(calls[1], ("server", ("0.0.0.0", 8765), "DigsightHandler"))
    self.assertEqual(calls[2], ("serve_forever",))


if __name__ == "__main__":
  unittest.main()

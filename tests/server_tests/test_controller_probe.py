import json
import unittest

import server.controller_probe as probe_module
from server.api import ApiRouter
from server.app_state import default_state
from server.controller_probe import ProbeResult, probe_ip, probe_ip_with_runner
from tests.server_tests.controller_test_env import (
  controller_ip_payload,
  controller_test_ip,
  ping_command,
  require_configured_controller_ip,
)


class ControllerProbeTest(unittest.TestCase):
  def test_probe_ip_with_runner_reports_success(self):
    def runner(_cmd):
      return 0, "ok", ""

    result = probe_ip_with_runner(controller_test_ip(), runner)
    self.assertEqual(result, ProbeResult(ok=True, detail="ok"))

  def test_probe_ip_with_runner_reports_failure(self):
    def runner(_cmd):
      return 1, "", "timeout"

    result = probe_ip_with_runner(controller_test_ip(), runner)
    self.assertFalse(result.ok)
    self.assertEqual(result.detail, "timeout")

  def test_probe_ip_uses_system_runner_without_direct_network_side_effect(self):
    original_runner = probe_module._subprocess_runner
    calls = []
    try:
      def fake_runner(command):
        calls.append(command)
        return 0, "reachable", ""

      probe_module._subprocess_runner = fake_runner
      result = probe_ip(controller_test_ip())
    finally:
      probe_module._subprocess_runner = original_runner

    self.assertEqual(result, ProbeResult(ok=True, detail="reachable"))
    self.assertEqual(calls, [ping_command()])

  def test_subprocess_runner_returns_process_output(self):
    class CompletedProcess:
      returncode = 1
      stdout = ""
      stderr = "packet loss"

    original_run = probe_module.subprocess.run
    try:
      def fake_run(command, capture_output, check, text, timeout):
        self.assertEqual(command, ping_command())
        self.assertTrue(capture_output)
        self.assertFalse(check)
        self.assertTrue(text)
        self.assertEqual(timeout, 4)
        return CompletedProcess()

      probe_module.subprocess.run = fake_run
      self.assertEqual(
        probe_module._subprocess_runner(ping_command()),
        (1, "", "packet loss"),
      )
    finally:
      probe_module.subprocess.run = original_run

  def test_controller_probe_api_updates_state(self):
    state = default_state()
    router = ApiRouter(None, probe_runner=lambda _cmd: (0, "reachable", ""))
    body, status = router.handle_json("POST", "/api/controller/probe", controller_ip_payload(), state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 200)
    self.assertTrue(payload["data"]["reachable"])
    self.assertTrue(state["controller"]["last_probe_ok"])

  def test_controller_probe_rejects_invalid_ip(self):
    state = default_state()
    router = ApiRouter(None, probe_runner=lambda _cmd: (0, "reachable", ""))
    body, status = router.handle_json("POST", "/api/controller/probe", b'{"ip":"bad"}', state)
    payload = json.loads(body.decode("utf-8"))
    self.assertEqual(status, 400)
    self.assertEqual(payload["error"]["type"], "invalid_controller_ip")

  def test_optional_real_controller_probe_uses_local_config_file(self):
    controller_ip = require_configured_controller_ip(self)
    result = probe_ip(controller_ip)
    self.assertTrue(result.ok, result.detail)


if __name__ == "__main__":
  unittest.main()

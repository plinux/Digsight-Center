from pathlib import Path
import threading
import time
import unittest

from digsight_dxdcnet.session import DXDCNetSessionManager
from server.controller_sessions import ControllerSessionRegistry, default_controller_session_registry
from tests.server_tests.controller_test_env import controller_test_ip


class ConcurrentDetectingTransport:
  def __init__(self):
    self.active = 0
    self.max_active = 0
    self.concurrent_bind_conflicts = 0
    self.bind_calls = []
    self.lock = threading.Lock()

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None):
    with self.lock:
      self.bind_calls.append(local_port)
      self.active += 1
      self.max_active = max(self.max_active, self.active)
      if self.active > 1:
        self.concurrent_bind_conflicts += 1
    time.sleep(0.02)
    with self.lock:
      self.active -= 1
    return [payload]


class DXDCNetSessionManagerTest(unittest.TestCase):
  def controller(self, **overrides):
    controller = {
      "kind": "digsight_controller",
      "protocol": "DXDCNet",
      "ip": controller_test_ip(),
      "udp_port": 12000,
      "local_udp_port": 6667,
      "udp_checksum_algorithm": "xor",
    }
    controller.update(overrides)
    return controller

  def test_default_session_registry_creates_dxdcnet_session(self):
    registry = default_controller_session_registry()
    session = registry.session_for_controller("digsight_controller", "DXDCNet", self.controller())

    self.assertIsInstance(session, DXDCNetSessionManager)
    self.assertIs(session, registry.session_for_controller("digsight_controller", "dxdcnet", self.controller()))

  def test_default_session_registry_keeps_dxdcnet_factory_in_adapter(self):
    source = Path("server/controller_sessions.py").read_text(encoding="utf-8")

    self.assertNotIn("digsight_dxdcnet", source)
    self.assertNotIn("DXDCNetSessionManager", source)

  def test_session_registry_scopes_sessions_by_controller_endpoint(self):
    registry = ControllerSessionRegistry()
    contexts = []

    def factory(_transport, context):
      contexts.append(context)
      return object()

    registry.register("digsight_controller", "DXDCNet", factory)
    first = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(ip="192.0.2.11"),
      endpoint_identity=(("ip", "192.0.2.11"), ("transport.udp_port", "12000")),
    )
    same = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(ip="192.0.2.11"),
      endpoint_identity=(("ip", "192.0.2.11"), ("transport.udp_port", "12000")),
    )
    different_ip = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(ip="192.0.2.12"),
      endpoint_identity=(("ip", "192.0.2.12"), ("transport.udp_port", "12000")),
    )
    different_port = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(ip="192.0.2.11", udp_port=13000),
      endpoint_identity=(("ip", "192.0.2.11"), ("transport.udp_port", "13000")),
    )

    self.assertIs(first, same)
    self.assertIsNot(first, different_ip)
    self.assertIsNot(first, different_port)
    self.assertEqual(len(contexts), 3)
    self.assertEqual(contexts[0].protocol, "DXDCNet")
    self.assertEqual(contexts[0].controller_kind, "digsight_controller")
    self.assertEqual(contexts[0].endpoint_identity, (("ip", "192.0.2.11"), ("transport.udp_port", "12000")))
    self.assertFalse(hasattr(contexts[0], "udp_port"))
    self.assertFalse(hasattr(contexts[0], "local_udp_port"))
    self.assertFalse(hasattr(contexts[0], "udp_checksum_algorithm"))

  def test_session_registry_scopes_sessions_by_controller_settings(self):
    registry = ControllerSessionRegistry()
    registry.register("digsight_controller", "DXDCNet", lambda _transport, _context: object())

    first = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(settings={"auth_token": "one"}),
    )
    same = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(settings={"auth_token": "one"}),
    )
    different_settings = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(settings={"auth_token": "two"}),
    )

    self.assertIs(first, same)
    self.assertIsNot(first, different_settings)

  def test_session_registry_scopes_factories_by_controller_kind_and_protocol(self):
    registry = ControllerSessionRegistry()
    registry.register("digsight_controller", "DXDCNet", lambda _transport, _context: "digsight-session")
    registry.register("future_dxdcnet_controller", "DXDCNet", lambda _transport, _context: "future-session")

    digsight_session = registry.session_for_controller(
      "digsight_controller",
      "DXDCNet",
      self.controller(kind="digsight_controller"),
    )
    future_session = registry.session_for_controller(
      "future_dxdcnet_controller",
      "DXDCNet",
      self.controller(kind="future_dxdcnet_controller"),
    )

    self.assertEqual(digsight_session, "digsight-session")
    self.assertEqual(future_session, "future-session")

  def test_session_registry_rejects_unregistered_protocol(self):
    registry = ControllerSessionRegistry()
    registry.register("digsight_controller", "DXDCNet", lambda _transport, _context: object())

    with self.assertRaisesRegex(ValueError, "Unsupported controller session: digsight_controller/ECoS"):
      registry.session_for_controller("digsight_controller", "ECoS", self.controller(protocol="ECoS"))

  def test_session_manager_requires_transport(self):
    manager = DXDCNetSessionManager()
    with self.assertRaisesRegex(ValueError, "transport is not configured"):
      manager.exchange(controller_test_ip(), 12000, b"\x10", local_port=6667)

  def test_session_manager_serializes_exchange_for_fixed_local_port(self):
    transport = ConcurrentDetectingTransport()
    manager = DXDCNetSessionManager(transport)
    start = threading.Event()
    errors = []

    def worker():
      start.wait(1)
      try:
        manager.exchange(controller_test_ip(), 12000, b"\x10", local_port=6667)
      except Exception as exc:  # pragma: no cover - test failure path
        errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for thread in threads:
      thread.start()
    start.set()
    for thread in threads:
      thread.join(1)

    self.assertEqual(errors, [])
    self.assertEqual(transport.bind_calls, [6667, 6667])
    self.assertEqual(transport.concurrent_bind_conflicts, 0)
    self.assertEqual(transport.max_active, 1)


if __name__ == "__main__":
  unittest.main()

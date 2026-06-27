import threading
import time
import unittest

from digsight_dxdcnet.session import DXDCNetSessionManager
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

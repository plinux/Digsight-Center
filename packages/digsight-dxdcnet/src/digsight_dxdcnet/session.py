"""Serialized DXDCNet hardware I/O session management."""

import threading


class DXDCNetSessionManager:
  def __init__(self, default_transport=None):
    self.default_transport = default_transport
    self._exchange_lock = threading.Lock()

  def exchange(self, host, port, payload, local_port=0, max_packets=32, stop_when=None, transport=None):
    active_transport = transport or self.default_transport
    if active_transport is None:
      raise ValueError("DXDCNet transport is not configured")
    with self._exchange_lock:
      return active_transport.exchange(
        host,
        port,
        payload,
        local_port=local_port,
        max_packets=max_packets,
        stop_when=stop_when,
      )

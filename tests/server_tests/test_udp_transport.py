import socket
import threading
import unittest

from digsight_dxdcnet.udp_transport import UDPTransport


def run_udp_echo_server(port_holder, ready_event, stop_event):
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind(("127.0.0.1", 0))
  port_holder.append(sock.getsockname()[1])
  sock.settimeout(0.1)
  ready_event.set()
  while not stop_event.is_set():
    try:
      data, address = sock.recvfrom(4096)
    except socket.timeout:
      continue
    sock.sendto(data, address)
  sock.close()


def run_udp_sequence_server(port_holder, ready_event, response_packets, stop_event):
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind(("127.0.0.1", 0))
  port_holder.append(sock.getsockname()[1])
  sock.settimeout(0.1)
  ready_event.set()
  while not stop_event.is_set():
    try:
      _data, address = sock.recvfrom(4096)
    except socket.timeout:
      continue
    for packet in response_packets:
      sock.sendto(packet, address)
  sock.close()


def run_udp_spoof_then_response_server(port_holder, ready_event, spoof_packets, response_packets, stop_event):
  sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
  sock.bind(("127.0.0.1", 0))
  port_holder.append(sock.getsockname()[1])
  sock.settimeout(0.1)
  ready_event.set()
  while not stop_event.is_set():
    try:
      _data, address = sock.recvfrom(4096)
    except socket.timeout:
      continue
    spoof_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
      for packet in spoof_packets:
        spoof_sock.sendto(packet, address)
    finally:
      spoof_sock.close()
    for packet in response_packets:
      sock.sendto(packet, address)
  sock.close()


class UdpTransportTest(unittest.TestCase):
  def test_round_trip_with_echo_server(self):
    port_holder = []
    ready = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(target=run_udp_echo_server, args=(port_holder, ready, stop), daemon=True)
    thread.start()
    ready.wait(1)
    try:
      transport = UDPTransport(timeout_seconds=0.2, retries=0)
      response = transport.request("127.0.0.1", port_holder[0], b"abc")
      self.assertEqual(response, b"abc")
    finally:
      stop.set()
      thread.join(1)

  def test_request_ignores_packet_from_unexpected_source_port(self):
    port_holder = []
    ready = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(
      target=run_udp_spoof_then_response_server,
      args=(port_holder, ready, [b"spoof"], [b"real"], stop),
      daemon=True,
    )
    thread.start()
    ready.wait(1)
    try:
      transport = UDPTransport(timeout_seconds=0.2, retries=0)
      response = transport.request("127.0.0.1", port_holder[0], b"abc")
      self.assertEqual(response, b"real")
    finally:
      stop.set()
      thread.join(1)

  def test_timeout_raises_timeout_error(self):
    transport = UDPTransport(timeout_seconds=0.05, retries=0)
    with self.assertRaises(TimeoutError):
      transport.request("127.0.0.1", 9, b"abc")

  def test_refuses_unconfigured_port(self):
    transport = UDPTransport(timeout_seconds=0.05, retries=0)
    with self.assertRaises(ValueError):
      transport.request("127.0.0.1", 0, b"abc")

  def test_request_rejects_port_above_udp_range(self):
    transport = UDPTransport(timeout_seconds=0.05, retries=0)
    with self.assertRaises(ValueError):
      transport.request("127.0.0.1", 65536, b"abc")

  def test_exchange_collects_packets_until_stop_condition(self):
    port_holder = []
    ready = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(
      target=run_udp_sequence_server,
      args=(port_holder, ready, [b"status", b"done", b"ignored"], stop),
      daemon=True,
    )
    thread.start()
    ready.wait(1)
    try:
      transport = UDPTransport(timeout_seconds=0.2, retries=0)
      responses = transport.exchange(
        "127.0.0.1",
        port_holder[0],
        b"request",
        stop_when=lambda packet: packet == b"done",
      )
      self.assertEqual(responses, [b"status", b"done"])
    finally:
      stop.set()
      thread.join(1)

  def test_exchange_ignores_packets_from_unexpected_source_port(self):
    port_holder = []
    ready = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(
      target=run_udp_spoof_then_response_server,
      args=(port_holder, ready, [b"spoof-1", b"spoof-2"], [b"status", b"done"], stop),
      daemon=True,
    )
    thread.start()
    ready.wait(1)
    try:
      transport = UDPTransport(timeout_seconds=0.2, retries=0)
      responses = transport.exchange(
        "127.0.0.1",
        port_holder[0],
        b"request",
        stop_when=lambda packet: packet == b"done",
      )
      self.assertEqual(responses, [b"status", b"done"])
    finally:
      stop.set()
      thread.join(1)

  def test_exchange_rejects_invalid_ports_without_sending(self):
    transport = UDPTransport(timeout_seconds=0.05, retries=0)
    with self.assertRaises(ValueError):
      transport.exchange("127.0.0.1", 0, b"abc")
    with self.assertRaises(ValueError):
      transport.exchange("127.0.0.1", 12000, b"abc", local_port=-1)
    with self.assertRaises(ValueError):
      transport.exchange("127.0.0.1", 65536, b"abc")
    with self.assertRaises(ValueError):
      transport.exchange("127.0.0.1", 12000, b"abc", local_port=65536)

  def test_exchange_returns_packets_received_before_timeout(self):
    port_holder = []
    ready = threading.Event()
    stop = threading.Event()
    thread = threading.Thread(
      target=run_udp_sequence_server,
      args=(port_holder, ready, [b"only-packet"], stop),
      daemon=True,
    )
    thread.start()
    ready.wait(1)
    try:
      transport = UDPTransport(timeout_seconds=0.05, retries=0)
      self.assertEqual(transport.exchange("127.0.0.1", port_holder[0], b"request"), [b"only-packet"])
    finally:
      stop.set()
      thread.join(1)


if __name__ == "__main__":
  unittest.main()

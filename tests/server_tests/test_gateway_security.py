import json
from pathlib import Path
import socket
import threading
import time
import unittest
from urllib.request import Request
from urllib.error import HTTPError
from urllib.request import urlopen

from server import response
import server.main as gateway_main
from server.main import DigsightHandler, is_public_static_path
from http.server import ThreadingHTTPServer

CLIENT_HEADERS = {"X-Digsight-Client": "digsight-web"}
JSON_CLIENT_HEADERS = {"Content-Type": "application/json", **CLIENT_HEADERS}
IMPORT_CLIENT_HEADERS = {"X-Digsight-Client": "digsight-web"}



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

  def test_head_static_server_allows_public_manual(self):
    status, headers = self.head("/manual/MANUAL.html")
    self.assertEqual(status, 200)
    self.assertIn("text/html", headers.get("Content-Type", ""))

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

if __name__ == "__main__":
  unittest.main()

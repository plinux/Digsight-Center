import json
import unittest

from server import models
from server.api import ApiRouter
from server.app_state import default_state


class CapabilitiesApiTest(unittest.TestCase):
  def test_capabilities_payload_exposes_controller_and_import_descriptors(self):
    router = ApiRouter(None)
    body, status = router.handle_json(
      "GET",
      "/api/capabilities",
      b"",
      default_state(),
    )

    self.assertEqual(status, 200)
    payload = json.loads(body)
    self.assertTrue(payload["ok"])
    data = payload["data"]
    self.assertEqual(data["default_controller_kind"], "digsight_controller")
    self.assertEqual(data["default_import_format"], "z21_layout_config")
    self.assertEqual([item["kind"] for item in data["controllers"]], ["digsight_controller"])
    self.assertEqual([item["format"] for item in data["import_formats"]], ["z21_layout_config"])
    self.assertEqual(data["controllers"][0]["kind"], "digsight_controller")
    self.assertEqual(data["controllers"][0]["label"], "动芯 DXDCNet")
    self.assertEqual(data["controllers"][0]["default_ip"], models.CONTROLLER_DEFAULT_IP)
    self.assertTrue(data["controllers"][0]["capabilities"]["track_power"])
    self.assertEqual(data["controllers"][0]["transport_defaults"], {
      "udp_port": 12000,
      "local_udp_port": 6667,
      "checksum_algorithm": "xor",
      "checksum_algorithms": ["xor"],
      "allow_zero_local_udp_port": False,
    })
    self.assertEqual(data["import_formats"][0]["format"], "z21_layout_config")
    self.assertIn(".z21", data["import_formats"][0]["extensions"])


if __name__ == "__main__":
  unittest.main()

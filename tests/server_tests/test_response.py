import json
import unittest

from server import response


class ResponseTest(unittest.TestCase):
  def test_success_payload_uses_common_shape(self):
    payload = json.loads(response.success({"value": 1}).decode("utf-8"))
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["data"]["value"], 1)
    self.assertIsNone(payload["error"])
    self.assertIn("debug", payload)

  def test_failure_payload_uses_common_shape(self):
    payload = json.loads(response.failure("bad_request", "请求无效", "detail").decode("utf-8"))
    self.assertFalse(payload["ok"])
    self.assertIsNone(payload["data"])
    self.assertEqual(payload["error"]["type"], "bad_request")
    self.assertEqual(payload["error"]["message"], "请求无效")
    self.assertEqual(payload["error"]["detail"], "detail")


if __name__ == "__main__":
  unittest.main()

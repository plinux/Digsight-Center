import unittest

from server.app_state import default_state


class ControllerKindStateTest(unittest.TestCase):
  def test_default_controller_kind_is_digsight_controller(self):
    state = default_state()
    self.assertEqual(state["controller"]["kind"], "digsight_controller")
    self.assertIn("settings", state["controller"])


if __name__ == "__main__":
  unittest.main()

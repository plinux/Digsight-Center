import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.server_tests import controller_test_env
from server import models


class ControllerTestEnvTest(unittest.TestCase):
  def test_configured_controller_ip_prefers_test_env_var(self):
    with patch.dict(os.environ, {"DIGSIGHT_TEST_D9000_IP": "192.0.2.88"}, clear=False):
      self.assertEqual(controller_test_env.configured_controller_ip(), "192.0.2.88")

  def test_configured_controller_ip_reads_selected_controller_config_file(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      config_path = Path(temp_dir) / "app-state.json"
      controller_config_dir = Path(temp_dir) / "config" / "controllers"
      controller_config_dir.mkdir(parents=True)
      config_path.write_text(json.dumps({
        "controller": {
          "kind": "digsight_controller",
        },
      }), encoding="utf-8")
      (controller_config_dir / models.CONTROLLER_CONFIG_FILES["digsight_controller"]).write_text(json.dumps({
        "ip": "192.0.2.44",
      }), encoding="utf-8")

      with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(controller_test_env, "DEFAULT_RUNTIME_CONFIG_PATH", config_path),
        patch.object(controller_test_env, "DEFAULT_CONTROLLER_CONFIG_DIR", controller_config_dir),
      ):
        self.assertEqual(controller_test_env.configured_controller_ip(), "192.0.2.44")

  def test_configured_controller_ip_treats_default_placeholder_as_missing(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      config_path = Path(temp_dir) / "app-state.json"
      controller_config_dir = Path(temp_dir) / "config" / "controllers"
      controller_config_dir.mkdir(parents=True)
      config_path.write_text(json.dumps({
        "controller": {
          "kind": "digsight_controller",
        },
      }), encoding="utf-8")
      (controller_config_dir / models.CONTROLLER_CONFIG_FILES["digsight_controller"]).write_text(json.dumps({
        "ip": "0.0.0.0",
      }), encoding="utf-8")

      with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(controller_test_env, "DEFAULT_RUNTIME_CONFIG_PATH", config_path),
        patch.object(controller_test_env, "DEFAULT_CONTROLLER_CONFIG_DIR", controller_config_dir),
      ):
        self.assertIsNone(controller_test_env.configured_controller_ip())

  def test_configured_controller_ip_missing_controller_config_file_is_missing(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      config_path = Path(temp_dir) / "missing-app-state.json"
      controller_config_dir = Path(temp_dir) / "config" / "controllers"

      with (
        patch.dict(os.environ, {}, clear=True),
        patch.object(controller_test_env, "DEFAULT_RUNTIME_CONFIG_PATH", config_path),
        patch.object(controller_test_env, "DEFAULT_CONTROLLER_CONFIG_DIR", controller_config_dir),
      ):
        self.assertIsNone(controller_test_env.configured_controller_ip())


if __name__ == "__main__":
  unittest.main()

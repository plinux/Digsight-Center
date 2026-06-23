import os
import tempfile
import unittest
from pathlib import Path

from server.importers.base import ConfigImportRequest
from server.importers.z21 import Z21ConfigImporter


class OptionalExternalInputTest(unittest.TestCase):
  def _import_z21_from_env(self, env_name: str, logical_file_name: str):
    path_value = os.environ.get(env_name)
    if not path_value:
      self.skipTest(f"set {env_name} to validate a local Z21 export")
    path = Path(path_value)
    self.assertTrue(path.exists(), f"{env_name} does not exist: {path}")
    self.assertEqual(path.suffix.lower(), ".z21")
    with tempfile.TemporaryDirectory() as temp_dir:
      result = Z21ConfigImporter(Path(temp_dir) / "vehicle-images").import_bytes(
        ConfigImportRequest(
          format="z21_layout_config",
          file_name=logical_file_name,
          content=path.read_bytes(),
        )
      )
    self.assertGreaterEqual(result.summary["vehicles_imported"], 0)
    self.assertGreaterEqual(result.summary["functions_imported"], 0)
    return result

  def test_optional_external_ho_z21_file_can_be_provided_by_environment(self):
    result = self._import_z21_from_env("DIGSIGHT_TEST_Z21_HO_FILE", "HO.z21")
    self.assertEqual(result.summary["track_mode"], "ho")

  def test_optional_external_n_z21_file_can_be_provided_by_environment(self):
    result = self._import_z21_from_env("DIGSIGHT_TEST_Z21_N_FILE", "N.z21")
    self.assertEqual(result.summary["track_mode"], "n")


if __name__ == "__main__":
  unittest.main()

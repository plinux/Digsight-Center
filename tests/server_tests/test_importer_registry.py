import unittest

from server.importers.base import ConfigImportRequest, ConfigImportResult, ImportFormatDescriptor
from server.importers.z21 import Z21ConfigImporter


class ImporterContractTest(unittest.TestCase):
  def test_import_request_carries_format_file_name_and_bytes(self):
    request = ConfigImportRequest(format="z21_layout_config", file_name="HO.z21", content=b"abc", options={"track_mode": "ho"})
    self.assertEqual(request.format, "z21_layout_config")
    self.assertEqual(request.file_name, "HO.z21")
    self.assertEqual(request.content, b"abc")
    self.assertEqual(request.options["track_mode"], "ho")

  def test_import_result_has_normalized_collections(self):
    result = ConfigImportResult(
      format="z21_layout_config",
      vehicles=[{"id": "v1"}],
      functions=[],
      categories=[],
      consists=[],
      images=[],
      summary={"vehicles_imported": 1},
      warnings=[],
      errors=[],
    )
    self.assertEqual(result.format, "z21_layout_config")
    self.assertEqual(result.vehicles[0]["id"], "v1")
    self.assertEqual(result.summary["vehicles_imported"], 1)

  def test_format_descriptor_names_user_visible_format(self):
    descriptor = ImportFormatDescriptor(format="z21_layout_config", label="Z21 .z21", extensions=[".z21"])
    self.assertEqual(descriptor.format, "z21_layout_config")
    self.assertEqual(descriptor.extensions, [".z21"])


class Z21ConfigImporterTest(unittest.TestCase):
  def test_z21_descriptor_is_user_visible(self):
    importer = Z21ConfigImporter(image_dir="/tmp/digsight-images")
    self.assertEqual(importer.descriptor.format, "z21_layout_config")
    self.assertIn(".z21", importer.descriptor.extensions)

  def test_z21_importer_rejects_non_zip_bytes_with_format_error(self):
    importer = Z21ConfigImporter(image_dir="/tmp/digsight-images")
    request = ConfigImportRequest(format="z21_layout_config", file_name="bad.z21", content=b"not a zip")
    with self.assertRaises(ValueError) as caught:
      importer.import_bytes(request)
    self.assertIn("Z21", str(caught.exception))


if __name__ == "__main__":
  unittest.main()

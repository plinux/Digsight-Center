import unittest
from unittest.mock import patch
import tempfile
from pathlib import Path

from server.importers.base import ConfigImportRequest, ConfigImportResult, ImportFormatDescriptor, ImportSource
from server.importers.registry import ImportRegistry
from server.importers.z21 import Z21ConfigImporter
from server.importers.z21_parser import Z21Importer
from tests.server_tests.z21_fixture_builder import write_minimal_z21_archive


class AlphaConfigImporter:
  descriptor = ImportFormatDescriptor(
    format="alpha_layout_config",
    label="Alpha Layout Config",
    extensions=[".alpha"],
  )

  def import_bytes(self, request):
    raise NotImplementedError


class UnsafePublicFileImporter:
  descriptor = ImportFormatDescriptor(
    format="unsafe_public_file_layout_config",
    label="Unsafe Public File Layout Config",
    extensions=[".unsafe"],
    public_files=["/server/api.py"],
  )

  def import_bytes(self, request):
    raise NotImplementedError


class GenericPublicFileImporter:
  descriptor = ImportFormatDescriptor(
    format="generic_public_file_layout_config",
    label="Generic Public File Layout Config",
    extensions=[".generic"],
    public_files=["/config/importers/generic-public.json"],
  )

  def import_bytes(self, request):
    raise NotImplementedError


class UnsafeFunctionIconMappingImporter:
  descriptor = ImportFormatDescriptor(
    format="unsafe_mapping_layout_config",
    label="Unsafe Mapping Layout Config",
    extensions=[".unsafe"],
    function_icon_mapping_files=["/config/importers/not-a-function-map.json"],
  )

  def import_bytes(self, request):
    raise NotImplementedError


class TraversalMappingImporter:
  descriptor = ImportFormatDescriptor(
    format="traversal_mapping_layout_config",
    label="Traversal Mapping Layout Config",
    extensions=[".traversal"],
    function_icon_mapping_files=["/config/function-icon-mappings/../private.json"],
  )

  def import_bytes(self, request):
    raise NotImplementedError


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
      source=ImportSource(format="z21_layout_config", key="z21", label="Z21 .z21"),
      vehicles=[{"id": "v1"}],
      functions=[],
      categories=[],
      consists=[],
      summary={"vehicles_imported": 1},
      warnings=[],
      errors=[],
    )
    self.assertEqual(result.format, "z21_layout_config")
    self.assertEqual(result.vehicles[0]["id"], "v1")
    self.assertEqual(result.summary["vehicles_imported"], 1)
    self.assertEqual(result.replace_scope, {})
    self.assertFalse(hasattr(result, "images"))
    self.assertEqual(result.source_mappings, {})

  def test_format_descriptor_names_user_visible_format(self):
    descriptor = ImportFormatDescriptor(format="z21_layout_config", label="Z21 .z21", extensions=[".z21"])
    self.assertEqual(descriptor.format, "z21_layout_config")
    self.assertEqual(descriptor.extensions, [".z21"])


class Z21ConfigImporterTest(unittest.TestCase):
  def test_z21_descriptor_is_user_visible(self):
    importer = Z21ConfigImporter(image_dir="/tmp/digsight-images")
    self.assertEqual(importer.descriptor.format, "z21_layout_config")
    self.assertIn(".z21", importer.descriptor.extensions)
    self.assertEqual(importer.descriptor.public_files, ["/config/function-icon-mappings/z21.json"])
    self.assertEqual(importer.descriptor.function_icon_mapping_files, ["/config/function-icon-mappings/z21.json"])

  def test_z21_importer_rejects_non_zip_bytes_with_format_error(self):
    importer = Z21ConfigImporter(image_dir="/tmp/digsight-images")
    request = ConfigImportRequest(format="z21_layout_config", file_name="bad.z21", content=b"not a zip")
    with self.assertRaises(ValueError) as caught:
      importer.import_bytes(request)
    self.assertIn("Z21", str(caught.exception))

  def test_z21_importer_wraps_expected_input_errors(self):
    importer = Z21ConfigImporter(image_dir="/tmp/digsight-images")
    request = ConfigImportRequest(format="z21_layout_config", file_name="bad.z21", content=b"bad content")
    with patch("server.importers.z21.Z21Importer.import_file", side_effect=ValueError("bad z21")):
      with self.assertRaises(ValueError) as caught:
        importer.import_bytes(request)
    self.assertEqual(str(caught.exception), "Z21 configuration import failed: bad z21")

  def test_z21_importer_preserves_unexpected_errors(self):
    importer = Z21ConfigImporter(image_dir="/tmp/digsight-images")
    request = ConfigImportRequest(format="z21_layout_config", file_name="bad.z21", content=b"bad content")
    with patch("server.importers.z21.Z21Importer.import_file", side_effect=RuntimeError("boom")):
      with self.assertRaises(RuntimeError) as caught:
        importer.import_bytes(request)
    self.assertEqual(str(caught.exception), "boom")

  def test_z21_importer_rejects_vehicle_image_with_png_name_but_wrong_signature(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      z21_path = self._write_minimal_z21(root, image_bytes=b"not a png")

      with self.assertRaises(ValueError) as caught:
        Z21Importer(root / "images").import_file(z21_path)

      self.assertIn("file content does not match PNG", str(caught.exception))
      self.assertFalse((root / "images" / "z21-ho-vehicle-1.png").exists())

  def test_z21_importer_accepts_vehicle_image_with_png_signature(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      root = Path(temp_dir)
      z21_path = self._write_minimal_z21(root, image_bytes=b"\x89PNG\r\n\x1a\nminimal")

      result = Z21Importer(root / "images").import_file(z21_path)

      self.assertEqual(result.vehicles[0]["image_path"], "/data/vehicle-images/z21-ho-vehicle-1.png")
      self.assertTrue((root / "images" / "z21-ho-vehicle-1.png").exists())

  def _write_minimal_z21(self, root: Path, image_bytes: bytes) -> Path:
    return write_minimal_z21_archive(
      root,
      sqlite_member="Loco.sqlite",
      vehicles=[{
        "id": 1,
        "position": 1,
        "image_name": "loco.png",
        "name": "测试车",
        "address": 3,
        "type": 0,
      }],
      image_files={"loco.png": image_bytes},
    )


class ImportRegistryTest(unittest.TestCase):
  def test_default_format_is_explicit_not_registration_order(self):
    registry = ImportRegistry(default_format="z21_layout_config")
    registry.register(AlphaConfigImporter())
    registry.register(Z21ConfigImporter(image_dir="/tmp/digsight-images"))

    self.assertEqual(registry.default_format, "z21_layout_config")

  def test_registry_descriptors_keep_default_first_then_stable_label_order(self):
    registry = ImportRegistry(default_format="z21_layout_config")
    registry.register(Z21ConfigImporter(image_dir="/tmp/digsight-images"))
    registry.register(AlphaConfigImporter())

    formats = [descriptor["format"] for descriptor in registry.descriptors()]
    self.assertEqual(formats, [
      "z21_layout_config",
      "alpha_layout_config",
    ])

    descriptors = registry.descriptors()
    z21_descriptor = next(descriptor for descriptor in descriptors if descriptor["format"] == "z21_layout_config")
    self.assertEqual(z21_descriptor["function_icon_mapping_files"], ["/config/function-icon-mappings/z21.json"])

  def test_default_format_requires_explicit_default(self):
    registry = ImportRegistry()
    registry.register(Z21ConfigImporter(image_dir="/tmp/digsight-images"))

    with self.assertRaises(ValueError) as caught:
      _ = registry.default_format
    self.assertEqual(str(caught.exception), "Default import format is not configured")

  def test_registry_rejects_importer_public_file_outside_allowed_prefixes(self):
    registry = ImportRegistry()
    registry.register(UnsafePublicFileImporter())

    with self.assertRaises(ValueError):
      registry.descriptors()

  def test_registry_allows_generic_importer_public_files_under_importer_config_prefix(self):
    registry = ImportRegistry()
    registry.register(GenericPublicFileImporter())

    descriptor = registry.descriptors()[0]

    self.assertEqual(descriptor["public_files"], ["/config/importers/generic-public.json"])

  def test_registry_keeps_function_icon_mapping_files_on_mapping_prefix(self):
    registry = ImportRegistry()
    registry.register(UnsafeFunctionIconMappingImporter())

    with self.assertRaises(ValueError):
      registry.descriptors()

  def test_registry_rejects_importer_function_icon_mapping_traversal(self):
    registry = ImportRegistry()
    registry.register(TraversalMappingImporter())

    with self.assertRaises(ValueError):
      registry.descriptors()

if __name__ == "__main__":
  unittest.main()

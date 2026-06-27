import unittest
from pathlib import Path

import digsight_dxdcnet


class PackageApiNamingTests(unittest.TestCase):
  def test_dxdcnet_exports_pep8_acronym_class_names(self):
    expected_names = (
      "DXDCNetFrame",
      "DXDCNetSessionManager",
      "UDPTransport",
      "XORChecksumAlgorithm",
      "CVReadPlan",
      "CVWritePlan",
      "ProgrammerResponseClassification",
    )

    for name in expected_names:
      with self.subTest(name=name):
        self.assertTrue(hasattr(digsight_dxdcnet, name))
        self.assertIn(name, digsight_dxdcnet.__all__)

  def test_dxdcnet_does_not_export_legacy_class_names(self):
    legacy_names = (
      "DxdcnetFrame",
      "DxdcnetSessionManager",
      "UdpTransport",
      "XorChecksumAlgorithm",
      "CvReadPlan",
      "CvWritePlan",
    )

    for name in legacy_names:
      with self.subTest(name=name):
        self.assertFalse(hasattr(digsight_dxdcnet, name))
        self.assertNotIn(name, digsight_dxdcnet.__all__)

  def test_user_api_docs_use_python_field_names(self):
    doc_path = Path("packages/digsight-dxdcnet/USER_API.md")
    content = doc_path.read_text(encoding="utf-8")

    self.assertNotIn("paramAddress", content)
    self.assertIn("param_address", content)

    for name in ("DxdcnetFrame", "DxdcnetSessionManager", "UdpTransport", "XorChecksumAlgorithm", "CvReadPlan", "CvWritePlan"):
      with self.subTest(name=name):
        self.assertNotIn(name, content)


if __name__ == "__main__":
  unittest.main()

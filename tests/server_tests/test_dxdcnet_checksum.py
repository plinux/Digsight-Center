import unittest
from pathlib import Path

from digsight_dxdcnet.checksum import NoChecksumAlgorithm, XORChecksumAlgorithm, checksum_from_name


class DXDCNetChecksumTest(unittest.TestCase):
  def test_unknown_checksum_refuses_real_encode(self):
    with self.assertRaises(ValueError):
      NoChecksumAlgorithm().compute(bytes.fromhex("15 01 22 00 00"))

  def test_xor_checksum_computes_over_frame_body(self):
    self.assertEqual(XORChecksumAlgorithm().compute(bytes.fromhex("15 01 22 00 00")), 0x36)

  def test_checksum_factory_rejects_unconfirmed_names(self):
    with self.assertRaises(ValueError):
      checksum_from_name("crc8")

  def test_checksum_factory_keeps_unconfirmed_default_safe(self):
    algorithm = checksum_from_name("")
    self.assertIsInstance(algorithm, NoChecksumAlgorithm)
    with self.assertRaises(ValueError):
      algorithm.compute(bytes.fromhex("15 01 22 00 00"))

  def test_public_api_docs_do_not_recommend_none_checksum_name(self):
    user_api = Path("packages/digsight-dxdcnet/USER_API.md").read_text(encoding="utf-8")
    checksum_section = user_api[user_api.index("### `NoChecksumAlgorithm`"):]
    self.assertNotIn('"none"', checksum_section)
    self.assertIn('"unconfirmed"', checksum_section)

  def test_checksum_factory_accepts_xor_name_case_insensitively(self):
    algorithm = checksum_from_name(" XOR ")
    self.assertIsInstance(algorithm, XORChecksumAlgorithm)
    self.assertEqual(algorithm.compute(bytes([0x01, 0x02, 0x03])), 0x00)


if __name__ == "__main__":
  unittest.main()

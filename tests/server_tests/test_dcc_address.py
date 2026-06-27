import unittest

from train_dcc.address import build_vehicle_address_writes, decode_vehicle_address


class DccAddressTest(unittest.TestCase):
  def test_decodes_short_address_from_cv1_when_cv29_bit5_clear(self):
    self.assertEqual(decode_vehicle_address(cv29=0x06, cv1=12), {"address": 12, "address_type": "short"})

  def test_decodes_long_address_from_cv17_cv18_when_cv29_bit5_set(self):
    self.assertEqual(decode_vehicle_address(cv29=0x26, cv17=0xC3, cv18=0xE8), {"address": 1000, "address_type": "long"})

  def test_builds_short_address_writes_and_clears_cv29_bit5(self):
    self.assertEqual(build_vehicle_address_writes(12, cv29=0x26), {
      "address": 12,
      "address_type": "short",
      "writes": [
        {"cv": 1, "value": 12},
        {"cv": 29, "value": 0x06},
      ],
    })

  def test_builds_long_address_writes_and_sets_cv29_bit5(self):
    self.assertEqual(build_vehicle_address_writes(9999, cv29=0x06), {
      "address": 9999,
      "address_type": "long",
      "writes": [
        {"cv": 17, "value": 0xE7},
        {"cv": 18, "value": 0x0F},
        {"cv": 29, "value": 0x26},
      ],
    })

  def test_rejects_short_address_without_cv1(self):
    with self.assertRaisesRegex(ValueError, "CV1 is required"):
      decode_vehicle_address(cv29=0x06)

  def test_rejects_short_address_with_bit7_or_zero_address(self):
    with self.assertRaisesRegex(ValueError, "bit7"):
      decode_vehicle_address(cv29=0x06, cv1=0x83)
    with self.assertRaisesRegex(ValueError, "short address 0"):
      decode_vehicle_address(cv29=0x06, cv1=0)

  def test_rejects_long_address_with_missing_or_invalid_cvs(self):
    with self.assertRaisesRegex(ValueError, "CV17 and CV18"):
      decode_vehicle_address(cv29=0x26, cv17=0xC0)
    with self.assertRaisesRegex(ValueError, "marker bits"):
      decode_vehicle_address(cv29=0x26, cv17=0x80, cv18=1)
    with self.assertRaisesRegex(ValueError, "long address 0"):
      decode_vehicle_address(cv29=0x26, cv17=0xC0, cv18=0)

  def test_rejects_invalid_address_writes(self):
    with self.assertRaisesRegex(ValueError, "positive"):
      build_vehicle_address_writes(0, cv29=0x06)
    with self.assertRaisesRegex(ValueError, "1..10239"):
      build_vehicle_address_writes(10240, cv29=0x06)


if __name__ == "__main__":
  unittest.main()

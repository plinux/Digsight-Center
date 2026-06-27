import unittest

from train_dcc.packets import (
  build_service_mode_cv_verify_packet,
  build_service_mode_cv_write_packet,
  dcc_xor,
)


class DccPacketsTest(unittest.TestCase):
  def test_dcc_xor_uses_all_packet_bytes(self):
    self.assertEqual(dcc_xor([0x74, 0x00, 0x03]), 0x77)

  def test_build_service_mode_cv_verify_packet_for_cv1(self):
    packet = build_service_mode_cv_verify_packet(1, 3)
    self.assertEqual(packet, bytes([0x74, 0x00, 0x03, 0x77]))

  def test_build_service_mode_cv_write_packet_for_cv1(self):
    packet = build_service_mode_cv_write_packet(1, 3)
    self.assertEqual(packet, bytes([0x7C, 0x00, 0x03, 0x7F]))

  def test_build_service_mode_packet_rejects_invalid_value(self):
    with self.assertRaises(ValueError):
      build_service_mode_cv_write_packet(1, 256)


if __name__ == "__main__":
  unittest.main()

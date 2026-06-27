import unittest

from digsight_dxdcnet.frames import DXDCNetFrame, build_udp_frame, decode_udp_frame, encode_udp_frame


class DXDCNetFrameTest(unittest.TestCase):
  def test_decodes_header_checksum_and_preserves_command_high_bit(self):
    raw = bytes.fromhex("ff ff 06 00 85 1e 16 8b")
    frame = decode_udp_frame(raw)
    self.assertEqual(frame.device_type, 0x0)
    self.assertEqual(frame.length, 0x6)
    self.assertEqual(frame.source_id, 0x00)
    self.assertEqual(frame.command, 0x85)
    self.assertTrue(frame.checksum_valid)
    self.assertEqual(frame.warnings, [])

  def test_round_trip_without_checksum_claim(self):
    frame = DXDCNetFrame(
      device_type=0x1,
      length=0x5,
      source_id=0x01,
      command=0x10,
      payload=b"\x03\x00\x81\x02",
      checksum=0,
    )
    raw = encode_udp_frame(frame)
    self.assertEqual(raw[:2], b"\xff\xff")
    self.assertEqual(decode_udp_frame(raw).command, 0x10)

  def test_builds_official_status_request_vector(self):
    raw = build_udp_frame(device_type=0x1, source_id=0, command=0x22, payload=b"\x00\x00")
    self.assertEqual(raw, bytes.fromhex("ff ff 16 00 22 00 00 34"))

  def test_rejects_non_dxdcnet_header(self):
    with self.assertRaises(ValueError):
      decode_udp_frame(bytes.fromhex("00 ff 15 01 10 00"))

  def test_rejects_short_dxdcnet_frame(self):
    with self.assertRaisesRegex(ValueError, "shorter than 6 bytes"):
      decode_udp_frame(bytes.fromhex("ff ff 15 01 10"))

  def test_build_udp_frame_rejects_payload_that_exceeds_four_bit_length(self):
    with self.assertRaisesRegex(ValueError, "too long"):
      build_udp_frame(device_type=0x1, source_id=1, command=0x10, payload=bytes(range(12)))

  def test_build_udp_frame_rejects_out_of_range_header_fields(self):
    cases = [
      ("device_type", {"device_type": 0x10, "source_id": 0x01, "command": 0x10}),
      ("source_id", {"device_type": 0x01, "source_id": 0x80, "command": 0x10}),
      ("command", {"device_type": 0x01, "source_id": 0x01, "command": 0x100}),
    ]
    for field_name, kwargs in cases:
      with self.subTest(field_name=field_name):
        with self.assertRaisesRegex(ValueError, field_name):
          build_udp_frame(payload=b"", **kwargs)

  def test_build_udp_frame_accepts_header_field_upper_bounds(self):
    raw = build_udp_frame(device_type=0x0F, source_id=0x7F, command=0xFF, payload=b"")
    frame = decode_udp_frame(raw)
    self.assertEqual(frame.device_type, 0x0F)
    self.assertEqual(frame.source_id, 0x7F)
    self.assertEqual(frame.command, 0xFF)


if __name__ == "__main__":
  unittest.main()

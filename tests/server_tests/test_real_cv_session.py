import unittest

from digsight_dxdcnet.constants import (
  CMD_PROGRAM_TRACK_ACK,
  CMD_PROGRAM_TRACK_STANDARD,
  CMD_PROGRAM_TRACK_VALUE,
  PROGRAMMER_ACK_ACK,
  PROGRAMMER_MODE_DIRECT_READ,
  PROGRAMMER_OP_ACCESSORY,
  PROGRAMMER_OP_MAIN_LOCO_POM,
)
from digsight_dxdcnet.frames import DXDCNetFrame, build_udp_frame, decode_udp_frame
from digsight_dxdcnet.matchers import (
  build_programmer_ack_matcher,
  build_programmer_value_matcher,
  build_raw_frame_matcher,
  first_matching_frame,
)
from digsight_dxdcnet.programming_track import CVReadPlan, CVWritePlan
from digsight_dxdcnet.programmer import (
  build_cv_read_frame,
  build_cv_write_frame,
  build_programmer_frame,
  parse_programmer_ack,
  parse_programmer_value,
)


class RealCvSessionTest(unittest.TestCase):
  def test_cv_read_plan_uses_official_programmer_direct_read_packet(self):
    plan = CVReadPlan(cv_number=1)
    self.assertEqual(plan.request_frame(client_id=1), build_cv_read_frame(1, client_id=1))
    self.assertEqual(plan.request_frame(client_id=1), bytes.fromhex("ff ff 17 01 14 80 00 00 82"))

  def test_cv_write_plan_uses_official_programmer_direct_write_packet(self):
    plan = CVWritePlan(cv_number=1, value=3)
    self.assertEqual(plan.request_frame(client_id=1), build_cv_write_frame(1, 3, client_id=1))
    self.assertEqual(plan.request_frame(client_id=1), bytes.fromhex("ff ff 17 01 14 e0 00 03 e1"))

  def test_main_track_pom_cv_read_frame_includes_vehicle_address(self):
    self.assertEqual(
      build_cv_read_frame(8, client_id=1, op=PROGRAMMER_OP_MAIN_LOCO_POM, pom_address=1000),
      bytes.fromhex("ff ff 19 01 14 98 07 00 e8 03 78"),
    )

  def test_programmer_frame_rejects_invalid_register_and_pom_arguments(self):
    with self.assertRaisesRegex(ValueError, "0..1023"):
      build_programmer_frame(client_id=1, mode=PROGRAMMER_MODE_DIRECT_READ, op=0, register=-1, value=0)
    with self.assertRaisesRegex(ValueError, "requires pom_address"):
      build_programmer_frame(
        client_id=1,
        mode=PROGRAMMER_MODE_DIRECT_READ,
        op=PROGRAMMER_OP_MAIN_LOCO_POM,
        register=0,
        value=0,
      )
    with self.assertRaisesRegex(ValueError, "1..9999"):
      build_programmer_frame(
        client_id=1,
        mode=PROGRAMMER_MODE_DIRECT_READ,
        op=PROGRAMMER_OP_MAIN_LOCO_POM,
        register=0,
        value=0,
        pom_address=10000,
      )
    with self.assertRaisesRegex(ValueError, "only valid"):
      build_programmer_frame(
        client_id=1,
        mode=PROGRAMMER_MODE_DIRECT_READ,
        op=PROGRAMMER_OP_ACCESSORY,
        register=0,
        value=0,
        pom_address=3,
      )

  def test_programmer_frame_rejects_out_of_range_protocol_bytes(self):
    invalid_fields = [
      ("client_id", {"client_id": 128, "mode": PROGRAMMER_MODE_DIRECT_READ, "op": 0, "register": 0, "value": 0}, "client_id"),
      ("mode", {"client_id": 1, "mode": 8, "op": 0, "register": 0, "value": 0}, "mode"),
      ("op", {"client_id": 1, "mode": PROGRAMMER_MODE_DIRECT_READ, "op": 8, "register": 0, "value": 0}, "op"),
      ("value", {"client_id": 1, "mode": PROGRAMMER_MODE_DIRECT_READ, "op": 0, "register": 0, "value": 256}, "value"),
    ]
    for _field, kwargs, error_text in invalid_fields:
      with self.subTest(error_text=error_text):
        with self.assertRaisesRegex(ValueError, error_text):
          build_programmer_frame(**kwargs)

  def test_main_track_pom_value_response_includes_vehicle_address(self):
    raw = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=bytes([0x80, 0x07, 0x56, 0x01, 0x01, 0xE8, 0x03]),
    )
    value = parse_programmer_value(decode_udp_frame(raw))
    self.assertEqual(value.cv_number, 8)
    self.assertEqual(value.value, 0x56)
    self.assertEqual(value.pom_address, 1000)

  def test_parse_programmer_value_response(self):
    raw = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=bytes([0x80, 0x07, 0x91, 0x01, 0x01]),
    )
    value = parse_programmer_value(decode_udp_frame(raw))
    self.assertEqual(value.mode, PROGRAMMER_MODE_DIRECT_READ)
    self.assertEqual(value.cv_number, 8)
    self.assertEqual(value.value, 0x91)
    self.assertEqual(value.device_id, 1)

  def test_parse_programmer_ack_response(self):
    raw = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]),
    )
    ack = parse_programmer_ack(decode_udp_frame(raw))
    self.assertEqual(ack.ack_mode, PROGRAMMER_ACK_ACK)
    self.assertEqual(ack.ack_name, "ack")
    self.assertEqual(ack.device_id, 1)

  def test_response_matchers_are_available_from_package(self):
    value_raw = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=bytes([0x80, 0x00, 0x03, 0x01, 0x01]),
    )
    ack_raw = build_udp_frame(
      device_type=0,
      source_id=0,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]),
    )
    frame = decode_udp_frame(value_raw)

    self.assertIs(first_matching_frame([frame], CMD_PROGRAM_TRACK_VALUE), frame)
    self.assertTrue(build_raw_frame_matcher(CMD_PROGRAM_TRACK_VALUE)(value_raw))
    self.assertTrue(build_programmer_value_matcher(client_id=1, cv_number=1)(value_raw))
    self.assertTrue(build_programmer_ack_matcher(client_id=1)(ack_raw))
    self.assertFalse(build_programmer_value_matcher(client_id=2, cv_number=1)(value_raw))

  def test_parse_programmer_ack_rejects_wrong_command_or_short_payload(self):
    wrong_command = DXDCNetFrame(0, 0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "not a programmer ACK"):
      parse_programmer_ack(wrong_command)
    short_payload = DXDCNetFrame(0, 0, 0, CMD_PROGRAM_TRACK_ACK, bytes([PROGRAMMER_ACK_ACK, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "ack mode"):
      parse_programmer_ack(short_payload)

  def test_parse_programmer_value_rejects_wrong_command_or_short_payload(self):
    wrong_command = DXDCNetFrame(0, 0, 0, CMD_PROGRAM_TRACK_STANDARD, bytes([0x80, 0x07, 0x56, 0x01, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "not a programmer value"):
      parse_programmer_value(wrong_command)
    short_payload = DXDCNetFrame(0, 0, 0, CMD_PROGRAM_TRACK_VALUE, bytes([0x80, 0x07, 0x56, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "mode, register"):
      parse_programmer_value(short_payload)


if __name__ == "__main__":
  unittest.main()

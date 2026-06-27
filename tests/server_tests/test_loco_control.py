import unittest

from digsight_dxdcnet.constants import CMD_LOCO_CONTROL_ACK, CMD_LOCO_FUNCTION, CMD_LOCO_SPEED, SPEED_MODE_128
from digsight_dxdcnet.frames import DXDCNetFrame, build_udp_frame, decode_udp_frame
from digsight_dxdcnet.loco_control import (
  build_loco_control_request_frame,
  build_loco_function_frame,
  build_loco_function_frames,
  build_loco_speed_frame,
  decode_loco_function_states,
  direction_bit,
  function_group_for_number,
  function_numbers_for_group,
  normalize_function_states,
  parse_loco_control_ack,
  parse_loco_function_feedback,
  parse_loco_speed_feedback,
  validate_loco_address,
  validate_loco_speed,
  validate_speed_mode,
)


class LocoControlProtocolTest(unittest.TestCase):
  def test_build_loco_speed_frame_uses_dxdcnet_0x10(self):
    self.assertEqual(
      build_loco_speed_frame(address=3, speed=10, direction="forward", speed_mode=SPEED_MODE_128, client_id=1),
      bytes.fromhex("ff ff 18 01 10 03 00 8a 02 82"),
    )

  def test_build_loco_speed_frame_marks_long_dcc_address(self):
    self.assertEqual(
      build_loco_speed_frame(address=4945, speed=10, direction="forward", speed_mode=SPEED_MODE_128, client_id=1),
      bytes.fromhex("ff ff 18 01 10 51 93 8a 02 43"),
    )

  def test_build_loco_speed_frame_marks_128_as_long_dcc_address(self):
    self.assertEqual(
      build_loco_speed_frame(address=128, speed=10, direction="forward", speed_mode=SPEED_MODE_128, client_id=1),
      bytes.fromhex("ff ff 18 01 10 80 80 8a 02 81"),
    )

  def test_build_loco_stop_frame_sets_speed_zero(self):
    self.assertEqual(
      build_loco_speed_frame(address=3, speed=0, direction="reverse", speed_mode=SPEED_MODE_128, client_id=1),
      bytes.fromhex("ff ff 18 01 10 03 00 00 02 08"),
    )

  def test_loco_speed_inputs_reject_values_that_can_target_invalid_dcc_states(self):
    for address in (0, 10000):
      with self.subTest(address=address):
        with self.assertRaisesRegex(ValueError, "1..9999"):
          validate_loco_address(address)
    for speed in (-1, 127):
      with self.subTest(speed=speed):
        with self.assertRaisesRegex(ValueError, "0..126"):
          validate_loco_speed(speed)
    for speed_mode in (-1, 8):
      with self.subTest(speed_mode=speed_mode):
        with self.assertRaisesRegex(ValueError, "0..7"):
          validate_speed_mode(speed_mode)
    with self.assertRaisesRegex(ValueError, "forward or reverse"):
      direction_bit("left")

  def test_build_loco_function_frame_encodes_f0_to_f9_group(self):
    self.assertEqual(
      build_loco_function_frame(address=3, function_states={0: True, 2: True, 4: True, 5: True}, client_id=1),
      bytes.fromhex("ff ff 18 01 11 03 00 1a 01 10"),
    )

  def test_build_loco_function_frame_marks_long_dcc_address(self):
    self.assertEqual(
      build_loco_function_frame(address=4945, function_states={0: True}, client_id=1),
      bytes.fromhex("ff ff 18 01 11 51 93 10 00 da"),
    )

  def test_build_loco_function_frame_encodes_f13_to_f20_group(self):
    self.assertEqual(
      build_loco_function_frame(address=4945, function_states={13: True}, client_id=1, function_number=13),
      bytes.fromhex("ff ff 18 01 11 51 93 40 01 8b"),
    )

  def test_build_loco_function_frame_encodes_f21_to_f28_group(self):
    self.assertEqual(
      build_loco_function_frame(address=3, function_states={28: True}, client_id=1, function_number=28),
      bytes.fromhex("ff ff 18 01 11 03 00 80 80 0b"),
    )

  def test_build_loco_function_frame_encodes_f29_to_f36_group(self):
    self.assertEqual(
      build_loco_function_frame(address=3, function_states={29: True}, client_id=1, function_number=29),
      bytes.fromhex("ff ff 18 01 11 03 00 98 01 92"),
    )

  def test_build_loco_function_frame_encodes_high_function_groups(self):
    expectations = [
      (37, 0x99, bytes.fromhex("ff ff 18 01 11 03 00 99 01 93")),
      (45, 0x9A, bytes.fromhex("ff ff 18 01 11 03 00 9a 01 90")),
      (53, 0x9B, bytes.fromhex("ff ff 18 01 11 03 00 9b 01 91")),
      (61, 0x9C, bytes.fromhex("ff ff 18 01 11 03 00 9c 01 96")),
    ]
    for function_number, group_code, expected_frame in expectations:
      with self.subTest(function_number=function_number):
        self.assertEqual(function_group_for_number(function_number), group_code)
        self.assertEqual(
          build_loco_function_frame(address=3, function_states={function_number: True}, client_id=1, function_number=function_number),
          expected_frame,
        )

  def test_loco_function_helpers_ignore_out_of_range_state_keys_but_reject_targeted_out_of_range_group(self):
    self.assertEqual(normalize_function_states({-1: True, 0: True, 69: True}), {0: True})
    self.assertEqual(function_numbers_for_group(0x00), list(range(0, 13)))
    with self.assertRaisesRegex(ValueError, "F0..F68"):
      function_group_for_number(69)
    with self.assertRaisesRegex(ValueError, "unsupported function group"):
      function_numbers_for_group(0xFE)

  def test_normalize_function_states_rejects_non_boolean_values(self):
    with self.assertRaisesRegex(ValueError, "boolean"):
      normalize_function_states({0: "false"})

  def test_build_loco_function_frames_can_emit_multiple_changed_groups(self):
    self.assertEqual(
      build_loco_function_frames(address=3, function_states={0: True, 13: True}, client_id=1),
      [
        bytes.fromhex("ff ff 18 01 11 03 00 10 00 1b"),
        bytes.fromhex("ff ff 18 01 11 03 00 40 01 4a"),
      ],
    )

  def test_parse_loco_speed_feedback(self):
    frame = decode_udp_frame(build_udp_frame(0, 0, CMD_LOCO_SPEED + 0x08, bytes([3, 0, 0x8A, 0x02])))
    feedback = parse_loco_speed_feedback(frame)
    self.assertEqual(feedback["address"], 3)
    self.assertEqual(feedback["speed"], 10)
    self.assertEqual(feedback["direction"], "forward")

  def test_parse_loco_speed_feedback_decodes_long_dcc_address(self):
    frame = decode_udp_frame(build_udp_frame(0, 0, CMD_LOCO_SPEED + 0x08, bytes([0x51, 0x93, 0x8A, 0x02])))
    feedback = parse_loco_speed_feedback(frame)
    self.assertEqual(feedback["address"], 4945)
    self.assertEqual(feedback["speed"], 10)
    self.assertEqual(feedback["direction"], "forward")

  def test_parse_loco_speed_feedback_rejects_wrong_command_or_short_payload(self):
    wrong_command = DXDCNetFrame(0, 0, 0, CMD_LOCO_FUNCTION, bytes([3, 0, 0x8A, 0x02]), 0)
    with self.assertRaisesRegex(ValueError, "not a loco speed"):
      parse_loco_speed_feedback(wrong_command)
    short_payload = DXDCNetFrame(0, 0, 0, CMD_LOCO_SPEED + 0x08, bytes([3, 0, 0x8A]), 0)
    with self.assertRaisesRegex(ValueError, "address, speed and mode"):
      parse_loco_speed_feedback(short_payload)

  def test_parse_loco_function_feedback(self):
    frame = decode_udp_frame(build_udp_frame(0, 0, CMD_LOCO_FUNCTION + 0x08, bytes([3, 0, 0x1A, 0x01])))
    feedback = parse_loco_function_feedback(frame)
    self.assertTrue(feedback["function_states"]["0"])
    self.assertTrue(feedback["function_states"]["2"])
    self.assertTrue(feedback["function_states"]["4"])
    self.assertTrue(feedback["function_states"]["5"])

  def test_parse_loco_function_feedback_decodes_f13_to_f20_group(self):
    frame = decode_udp_frame(build_udp_frame(0, 0, CMD_LOCO_FUNCTION + 0x08, bytes([0x51, 0x93, 0x40, 0x01])))
    feedback = parse_loco_function_feedback(frame)
    self.assertEqual(feedback["address"], 4945)
    self.assertTrue(feedback["function_states"]["13"])
    self.assertFalse(feedback["function_states"]["20"])

  def test_decode_loco_function_states_for_high_group(self):
    states = decode_loco_function_states(0x9C, 0x81)
    self.assertTrue(states["61"])
    self.assertTrue(states["68"])
    self.assertFalse(states["62"])

  def test_parse_loco_function_feedback_rejects_wrong_command_or_short_payload(self):
    wrong_command = DXDCNetFrame(0, 0, 0, CMD_LOCO_SPEED, bytes([3, 0, 0x1A, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "not a loco function"):
      parse_loco_function_feedback(wrong_command)
    short_payload = DXDCNetFrame(0, 0, 0, CMD_LOCO_FUNCTION + 0x08, bytes([3, 0, 0x1A]), 0)
    with self.assertRaisesRegex(ValueError, "address and function bits"):
      parse_loco_function_feedback(short_payload)

  def test_build_loco_control_request_marks_long_dcc_address(self):
    self.assertEqual(
      build_loco_control_request_frame(address=4945, client_id=1),
      bytes.fromhex("ff ff 16 01 04 51 93 d1"),
    )

  def test_parse_loco_control_ack_decodes_granted_throttle(self):
    frame = decode_udp_frame(build_udp_frame(0, 0, CMD_LOCO_CONTROL_ACK, bytes([0x51, 0x93, 0x01, 0x01])))
    feedback = parse_loco_control_ack(frame)
    self.assertEqual(feedback["address"], 4945)
    self.assertEqual(feedback["granted_device_type"], 1)
    self.assertEqual(feedback["granted_id"], 1)
    self.assertTrue(feedback["granted"])

  def test_parse_loco_control_ack_rejects_wrong_command_or_short_payload(self):
    wrong_command = DXDCNetFrame(0, 0, 0, CMD_LOCO_FUNCTION, bytes([0x51, 0x93, 0x01, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "not a loco control ACK"):
      parse_loco_control_ack(wrong_command)
    short_payload = DXDCNetFrame(0, 0, 0, CMD_LOCO_CONTROL_ACK, bytes([0x51, 0x93, 0x01]), 0)
    with self.assertRaisesRegex(ValueError, "address, device type"):
      parse_loco_control_ack(short_payload)


if __name__ == "__main__":
  unittest.main()

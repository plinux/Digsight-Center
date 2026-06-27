import unittest

from digsight_dxdcnet.constants import CMD_PROGRAM_TRACK_ACK, CMD_PROGRAM_TRACK_VALUE, PROGRAMMER_ACK_ACK, PROGRAMMER_ACK_BUSY
from digsight_dxdcnet.frames import DXDCNetFrame
from digsight_dxdcnet.programmer_responses import (
  classify_programmer_responses,
  programmer_ack_category,
  should_retry_busy_ack,
)


class ProgrammerResponseClassificationTest(unittest.TestCase):
  def test_malformed_programmer_value_is_warning_not_exception(self):
    frame = DXDCNetFrame(
      device_type=7,
      length=5,
      source_id=1,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=b"\x00",
      checksum=0,
      checksum_valid=True,
      warnings=[],
    )

    result = classify_programmer_responses([frame], client_id=1, cv_number=7)

    self.assertIsNone(result.value)
    self.assertIsNone(result.ack)
    self.assertEqual(len(result.parse_warnings), 1)
    self.assertEqual(result.parse_warnings[0]["type"], "programmer_value_parse_error")

  def test_malformed_programmer_ack_is_warning_not_exception(self):
    frame = DXDCNetFrame(
      device_type=7,
      length=5,
      source_id=1,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=b"\x00",
      checksum=0,
      checksum_valid=True,
      warnings=[],
    )

    result = classify_programmer_responses([frame], client_id=1, cv_number=7)

    self.assertIsNone(result.value)
    self.assertIsNone(result.ack)
    self.assertEqual(result.parse_warnings[0]["type"], "programmer_ack_parse_error")

  def test_matching_value_and_ack_are_classified(self):
    value_frame = DXDCNetFrame(
      device_type=7,
      length=10,
      source_id=1,
      command=CMD_PROGRAM_TRACK_VALUE,
      payload=bytes([0x00, 0x06, 0x56, 0x01, 0x01]),
      checksum=0,
      checksum_valid=True,
      warnings=[],
    )
    ack_frame = DXDCNetFrame(
      device_type=7,
      length=8,
      source_id=1,
      command=CMD_PROGRAM_TRACK_ACK,
      payload=bytes([PROGRAMMER_ACK_ACK, 0x01, 0x01]),
      checksum=0,
      checksum_valid=True,
      warnings=[],
    )

    result = classify_programmer_responses([value_frame, ack_frame], client_id=1, cv_number=7)

    self.assertEqual(result.value.value, 0x56)
    self.assertEqual(result.value.cv_number, 7)
    self.assertEqual(result.ack.ack_mode, PROGRAMMER_ACK_ACK)
    self.assertEqual(result.parse_warnings, [])

  def test_ack_category_and_busy_retry(self):
    self.assertEqual(programmer_ack_category(PROGRAMMER_ACK_BUSY), "busy")
    self.assertEqual(programmer_ack_category(PROGRAMMER_ACK_ACK), "ack")
    self.assertTrue(should_retry_busy_ack(PROGRAMMER_ACK_BUSY, attempt=0, retry_count=1))
    self.assertFalse(should_retry_busy_ack(PROGRAMMER_ACK_BUSY, attempt=1, retry_count=1))


if __name__ == "__main__":
  unittest.main()

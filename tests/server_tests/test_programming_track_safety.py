import unittest

from digsight_dxdcnet.programming_track import ProgrammingTrackSafety, ProgrammingTrackStatus


class ProgrammingTrackSafetyTest(unittest.TestCase):
  def test_allows_safe_n_dcc_programming_track(self):
    status = ProgrammingTrackStatus(
      track_mode="n",
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=60,
      output_value=0x78,
      current_limit_ma=200,
    )
    safety = ProgrammingTrackSafety()
    safety.validate(status)

  def test_rejects_dc_mode(self):
    status = ProgrammingTrackStatus(
      track_mode="dc",
      dcc_mode=False,
      programming_track_busy=False,
      programming_track_current_ma=60,
      output_value=0x78,
      current_limit_ma=200,
    )
    with self.assertRaises(ValueError):
      ProgrammingTrackSafety().validate(status)

  def test_rejects_programming_track_limit_above_service_mode_limit(self):
    status = ProgrammingTrackStatus(
      track_mode="n",
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=60,
      output_value=0x78,
      current_limit_ma=2000,
    )
    with self.assertRaisesRegex(ValueError, "编程轨限流超过 250 mA"):
      ProgrammingTrackSafety().validate(status)

  def test_allows_controller_status_when_programming_track_limit_is_not_reported(self):
    status = ProgrammingTrackStatus(
      track_mode="n",
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=0,
      output_value=0x78,
      current_limit_ma=0,
      current_limit_confirmed=False,
    )
    ProgrammingTrackSafety().validate(status)

  def test_rejects_idle_programming_track_over_current(self):
    status = ProgrammingTrackStatus(
      track_mode="n",
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=260,
      output_value=0x78,
      current_limit_ma=200,
    )
    with self.assertRaises(ValueError):
      ProgrammingTrackSafety().validate(status)


if __name__ == "__main__":
  unittest.main()

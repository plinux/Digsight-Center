import unittest

from digsight_dxdcnet.device_commands import (
  build_mac_request_frame,
  build_parameter_read_frame,
  build_parameter_write_frame,
  build_read_parameter_payload,
  build_request_device_status_payload,
  build_write_parameter_payload,
  build_status_request_frame,
  build_track_output_frame,
  build_track_output_payload,
  build_version_request_frame,
)
from digsight_dxdcnet.device_status import (
  format_app_version,
  parse_booster_status,
  parse_command_station_status,
  parse_mac_response,
  parse_parameter_response,
  parse_version_response,
)


class ControllerInfoRealCommandTest(unittest.TestCase):
  def test_build_request_command_station_status_payload(self):
    self.assertEqual(build_request_device_status_payload(target_type=0x0, target_id=0x00), bytes([0x00, 0x00]))

  def test_build_status_request_frame_uses_official_app_client_id(self):
    frame = build_status_request_frame(client_id=1, target_type=0x0, target_id=0x00)
    self.assertEqual(frame, bytes.fromhex("ff ff 16 01 22 00 00 35"))

  def test_build_version_request_frame(self):
    frame = build_version_request_frame(client_id=1, target_type=0x0, target_id=0x00)
    self.assertEqual(frame, bytes.fromhex("ff ff 16 01 84 00 00 93"))

  def test_build_mac_request_frame(self):
    frame = build_mac_request_frame(client_id=1, target_type=0x0, target_id=0x01)
    self.assertEqual(frame, bytes.fromhex("ff ff 16 01 0b 00 01 1d"))

  def test_build_read_n_current_parameter_payload(self):
    self.assertEqual(build_read_parameter_payload(target_type=0x0, target_id=0x00, param_address=0x81), bytes([0x00, 0x00, 0x81]))

  def test_build_read_n_current_parameter_frame(self):
    frame = build_parameter_read_frame(client_id=1, target_type=0x0, target_id=0x00, param_address=0x81)
    self.assertEqual(frame, bytes.fromhex("ff ff 17 01 41 00 00 81 d6"))

  def test_build_write_ho_current_parameter_frame(self):
    self.assertEqual(
      build_write_parameter_payload(target_type=0x0, target_id=0x00, param_address=0x82, value=0x64),
      bytes([0x00, 0x00, 0x82, 0x64]),
    )
    frame = build_parameter_write_frame(client_id=1, target_type=0x0, target_id=0x00, param_address=0x82, value=0x64)
    self.assertEqual(frame, bytes.fromhex("ff ff 18 01 40 00 00 82 64 bf"))

  def test_device_command_builders_reject_out_of_range_protocol_fields(self):
    invalid_calls = [
      (build_request_device_status_payload, {"target_type": 0x10, "target_id": 0}, "target_type"),
      (build_request_device_status_payload, {"target_type": 0, "target_id": 0x80}, "target_id"),
      (build_track_output_payload, {"target_id": 0x80, "powered": True, "output_value": 0}, "target_id"),
      (build_track_output_payload, {"target_id": 1, "powered": True, "output_value": 0x100}, "output_value"),
      (build_read_parameter_payload, {"target_type": 0x10, "target_id": 0, "param_address": 0x81}, "target_type"),
      (build_read_parameter_payload, {"target_type": 0, "target_id": 0x80, "param_address": 0x81}, "target_id"),
      (build_read_parameter_payload, {"target_type": 0, "target_id": 0, "param_address": 0x100}, "param_address"),
      (build_write_parameter_payload, {"target_type": 0, "target_id": 0, "param_address": 0x82, "value": 0x100}, "value"),
    ]
    for builder, kwargs, error_text in invalid_calls:
      with self.subTest(builder=builder.__name__, error_text=error_text):
        with self.assertRaisesRegex(ValueError, error_text):
          builder(**kwargs)

  def test_build_track_output_payloads_for_dcc_and_dc(self):
    self.assertEqual(build_track_output_payload(1, True, 0x78, dcc_mode=True), bytes.fromhex("01 90 78"))
    self.assertEqual(build_track_output_payload(1, True, 0x78, dcc_mode=False), bytes.fromhex("01 f0 78"))
    self.assertEqual(build_track_output_payload(1, False, 0x78, dcc_mode=True), bytes.fromhex("01 10 00"))
    self.assertEqual(build_track_output_payload(1, False, 0x78, dcc_mode=False), bytes.fromhex("01 70 00"))
    self.assertEqual(build_track_output_payload(1, True, 0x78, dcc_mode=True, auto_report=False), bytes.fromhex("01 80 78"))

  def test_build_track_output_frames_for_all_modes(self):
    self.assertEqual(build_track_output_frame(1, 1, True, 0x78, dcc_mode=True), bytes.fromhex("ff ff 17 01 20 01 90 78 df"))
    self.assertEqual(build_track_output_frame(1, 1, True, 0xA0, dcc_mode=True), bytes.fromhex("ff ff 17 01 20 01 90 a0 07"))
    self.assertEqual(build_track_output_frame(1, 1, True, 0xB4, dcc_mode=True), bytes.fromhex("ff ff 17 01 20 01 90 b4 13"))
    self.assertEqual(build_track_output_frame(1, 1, True, 0x78, dcc_mode=False), bytes.fromhex("ff ff 17 01 20 01 f0 78 bf"))
    self.assertEqual(
      build_track_output_frame(1, 1, True, 0x78, dcc_mode=False, dc_direction_positive=True),
      bytes.fromhex("ff ff 17 01 20 01 f0 78 bf"),
    )
    self.assertEqual(
      build_track_output_frame(1, 1, True, 0x78, dcc_mode=False, dc_direction_positive=False),
      bytes.fromhex("ff ff 17 01 20 01 d0 78 9f"),
    )
    self.assertEqual(
      build_track_output_frame(1, 1, False, 0x00, dcc_mode=False, dc_direction_positive=False),
      bytes.fromhex("ff ff 17 01 20 01 50 00 67"),
    )

  def test_build_track_output_off_frames(self):
    self.assertEqual(build_track_output_frame(1, 1, False, 0x00, dcc_mode=True), bytes.fromhex("ff ff 17 01 20 01 10 00 27"))
    self.assertEqual(build_track_output_frame(1, 1, False, 0x00, dcc_mode=False), bytes.fromhex("ff ff 17 01 20 01 70 00 47"))

  def test_parse_command_station_status(self):
    status = parse_command_station_status(bytes([120, 10, 115, 3, 0x00]))
    self.assertEqual(status["bus_voltage_raw"], 120)
    self.assertEqual(status["bus_current_raw"], 10)
    self.assertEqual(status["programming_track_voltage_raw"], 115)
    self.assertEqual(status["programming_track_current_raw"], 3)
    self.assertEqual(status["programming_track_busy"], False)

  def test_parse_command_station_status_rejects_short_payload(self):
    with self.assertRaisesRegex(ValueError, "at least 5 bytes"):
      parse_command_station_status(bytes([120, 10, 115, 3]))

  def test_parse_v3_booster_status(self):
    status = parse_booster_status(bytes([0x78, 0x78, 0x01, 0x22, 0x00, 0x00, 0x90]))
    self.assertEqual(status["set_voltage_raw"], 0x78)
    self.assertEqual(status["output_voltage_v"], 12.0)
    self.assertEqual(status["output_current_a"], 0.1)
    self.assertEqual(status["temperature_c"], 34)
    self.assertEqual(status["power_on"], True)
    self.assertEqual(status["dcc_mode"], True)
    self.assertEqual(status["short_circuit"], False)

  def test_parse_v3_booster_status_maps_current_alarm_to_short_circuit(self):
    status = parse_booster_status(bytes([0x78, 0x78, 0x03, 0x22, 0x00, 0x00, 0x91]))
    self.assertEqual(status["power_on"], True)
    self.assertEqual(status["current_alarm"], True)
    self.assertEqual(status["short_circuit"], True)

  def test_parse_booster_status_rejects_short_payload(self):
    with self.assertRaisesRegex(ValueError, "at least 7 bytes"):
      parse_booster_status(bytes([0x78, 0x78, 0x01, 0x22, 0x00, 0x00]))

  def test_parse_parameter_response(self):
    result = parse_parameter_response(bytes([0x81, 10]))
    self.assertEqual(result["param_address"], 0x81)
    self.assertEqual(result["value"], 10)
    self.assertEqual(result["current_limit_ma"], 400)

  def test_parse_parameter_response_only_marks_known_current_limit_addresses(self):
    result = parse_parameter_response(bytes([0x90, 10]))
    self.assertEqual(result["param_address"], 0x90)
    self.assertEqual(result["value"], 10)
    self.assertNotIn("current_limit_ma", result)

  def test_parse_parameter_response_rejects_short_payload(self):
    with self.assertRaisesRegex(ValueError, "address and value"):
      parse_parameter_response(bytes([0x81]))

  def test_parse_version_response(self):
    result = parse_version_response(bytes([0x1E, 0x16]))
    self.assertEqual(result["hardware_version_raw"], 0x1E)
    self.assertEqual(result["software_version_raw"], 0x16)
    self.assertEqual(result["hardware_version"], "30")
    self.assertEqual(result["software_version"], "22")
    self.assertEqual(result["app_version"], "3.0.2.2")

  def test_parse_version_response_rejects_short_payload(self):
    with self.assertRaisesRegex(ValueError, "hardware and software"):
      parse_version_response(bytes([0x1E]))

  def test_format_app_version_matches_official_android_display(self):
    self.assertEqual(format_app_version(30, 19), "3.0.1.9")

  def test_parse_mac_response_uses_android_app_byte_order(self):
    result = parse_mac_response(bytes([0x00, 0x34, 0x35, 0x38, 0x31, 0x1B, 0x6B]))
    self.assertEqual(result["address_type"], 0)
    self.assertEqual(result["app_order_hex"], "6B1B31383534")

  def test_parse_mac_response_rejects_short_payload(self):
    with self.assertRaisesRegex(ValueError, "6 bytes"):
      parse_mac_response(bytes([0x00, 0x34, 0x35]))


if __name__ == "__main__":
  unittest.main()

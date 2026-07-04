import unittest
import socket
import threading

from z21_lan import (
  DEFAULT_Z21_PORT,
  LAN_GET_COMMON_SETTINGS,
  LAN_GET_LOCO_MODE,
  LAN_GET_HWINFO,
  LAN_GET_MMDCC_SETTINGS,
  LAN_GET_SERIAL_NUMBER,
  LAN_SET_COMMON_SETTINGS,
  LAN_SET_LOCO_MODE,
  LAN_SET_MMDCC_SETTINGS,
  LAN_SYSTEMSTATE_DATACHANGED,
  LAN_SYSTEMSTATE_GETDATA,
  LAN_X,
  Z21SessionManager,
  Z21UDPTransport,
  build_get_hwinfo,
  build_get_common_settings,
  build_get_loco_mode,
  build_get_mmdcc_settings,
  build_get_serial_number,
  build_set_mmdcc_settings,
  build_set_common_settings,
  build_set_loco_mode,
  build_get_system_state,
  build_lan_x_payload,
  build_x_cv_pom_read_byte,
  build_x_cv_pom_write_byte,
  build_x_cv_read_direct,
  build_x_cv_write_direct,
  build_x_set_track_power_off,
  build_x_set_track_power_on,
  build_x_get_firmware_version,
  build_x_get_loco_info,
  build_x_set_loco_drive,
  build_x_set_loco_drive_128,
  build_x_set_loco_function,
  decode_datasets,
  encode_dataset,
  hardware_type_label,
  parse_loco_info,
  parse_broadcast_flags,
  parse_common_settings,
  parse_cv_result,
  parse_hwinfo,
  parse_mmdcc_settings,
  parse_serial_number,
  parse_system_state,
  parse_xbus_ack,
  xbus_xor,
)


class Z21LanProtocolTest(unittest.TestCase):
  def test_encode_and_decode_multiple_datasets(self):
    datagram = encode_dataset(LAN_GET_SERIAL_NUMBER, b"\x01\x02\x03\x04") + encode_dataset(LAN_GET_HWINFO, b"12345678")
    datasets = decode_datasets(datagram)

    self.assertEqual(len(datasets), 2)
    self.assertEqual(datasets[0].data_len, 8)
    self.assertEqual(datasets[0].header, LAN_GET_SERIAL_NUMBER)
    self.assertEqual(datasets[0].payload, b"\x01\x02\x03\x04")
    self.assertEqual(datasets[0].to_bytes(), encode_dataset(LAN_GET_SERIAL_NUMBER, b"\x01\x02\x03\x04"))

  def test_decode_rejects_truncated_dataset(self):
    with self.assertRaises(ValueError):
      decode_datasets(b"\x08\x00\x10\x00\x01")
    with self.assertRaises(ValueError):
      decode_datasets(b"\x03\x00\x10\x00")

  def test_read_only_command_builders_use_little_endian_headers(self):
    self.assertEqual(DEFAULT_Z21_PORT, 21105)
    self.assertEqual(LAN_SYSTEMSTATE_DATACHANGED, 0x0084)
    self.assertEqual(LAN_SYSTEMSTATE_GETDATA, 0x0085)
    self.assertEqual(build_get_serial_number(), b"\x04\x00\x10\x00")
    self.assertEqual(build_get_hwinfo(), b"\x04\x00\x1a\x00")
    self.assertEqual(build_get_system_state(), b"\x04\x00\x85\x00")

  def test_mmdcc_settings_builder_and_parser(self):
    settings = parse_mmdcc_settings(bytes.fromhex("19 06 07 01 05 14 88 13 10 27 32 80 80 3e 80 3e"))

    self.assertEqual(LAN_GET_MMDCC_SETTINGS, 0x0016)
    self.assertEqual(LAN_SET_MMDCC_SETTINGS, 0x0017)
    self.assertEqual(settings.startup_reset_packet_count, 25)
    self.assertEqual(settings.continue_reset_packet_count, 6)
    self.assertEqual(settings.program_packet_count, 7)
    self.assertEqual(settings.external_short_circuit_limit, 5000)
    self.assertEqual(settings.internal_short_circuit_limit, 10000)
    self.assertEqual(settings.programming_ack_current, 50)
    self.assertEqual(settings.mmdcc_flags, 0x80)
    self.assertEqual(settings.output_voltage_mv, 16000)
    self.assertEqual(settings.programming_voltage_mv, 16000)
    self.assertEqual(settings.to_debug_dict()["output_voltage_v"], 16.0)
    self.assertEqual(settings.to_payload(), bytes.fromhex("19 06 07 01 05 14 88 13 10 27 32 80 80 3e 80 3e"))
    self.assertEqual(build_get_mmdcc_settings(), bytes.fromhex("04 00 16 00"))
    self.assertEqual(
      build_set_mmdcc_settings(settings.with_voltages(output_voltage_mv=15000, programming_voltage_mv=17000)),
      bytes.fromhex("14 00 17 00 19 06 07 01 05 14 88 13 10 27 32 80 98 3a 68 42"),
    )
    with self.assertRaises(ValueError):
      parse_mmdcc_settings(b"\x00" * 15)

  def test_common_settings_builder_and_parser(self):
    settings = parse_common_settings(bytes.fromhex("01 00 00 03 01 00 03 00 00 00"))

    self.assertEqual(LAN_GET_COMMON_SETTINGS, 0x0012)
    self.assertEqual(LAN_SET_COMMON_SETTINGS, 0x0013)
    self.assertTrue(settings.enable_railcom)
    self.assertEqual(settings.programming_type, 3)
    self.assertEqual(settings.enable_loconet_current_source, 1)
    self.assertEqual(settings.loconet_mode, 3)
    self.assertEqual(settings.to_payload(), bytes.fromhex("01 00 00 03 01 00 03 00 00 00"))
    self.assertEqual(settings.to_debug_dict()["payload_hex"], "01 00 00 03 01 00 03 00 00 00")
    self.assertEqual(build_get_common_settings(), bytes.fromhex("04 00 12 00"))
    self.assertEqual(
      build_set_common_settings(settings.with_railcom(False)),
      bytes.fromhex("0e 00 13 00 00 00 00 03 01 00 03 00 00 00"),
    )
    with self.assertRaises(ValueError):
      parse_common_settings(b"\x00" * 9)

  def test_lan_x_firmware_command_appends_xbus_checksum(self):
    self.assertEqual(xbus_xor([0xF1, 0x0A]), 0xFB)
    self.assertEqual(build_lan_x_payload(0xF1, 0x0A), b"\xf1\x0a\xfb")
    dataset = decode_datasets(build_x_get_firmware_version())[0]
    self.assertEqual(dataset.header, LAN_X)
    self.assertEqual(dataset.payload, b"\xf1\x0a\xfb")

  def test_lan_x_track_power_commands_match_official_vectors(self):
    self.assertEqual(build_x_set_track_power_off(), b"\x07\x00\x40\x00\x21\x80\xa1")
    self.assertEqual(build_x_set_track_power_on(), b"\x07\x00\x40\x00\x21\x81\xa0")

  def test_lan_x_loco_control_commands_match_official_vectors(self):
    self.assertEqual(
      build_x_get_loco_info(3),
      bytes.fromhex("09 00 40 00 e3 f0 00 03 10"),
    )
    self.assertEqual(
      build_x_get_loco_info(4945),
      bytes.fromhex("09 00 40 00 e3 f0 d3 51 91"),
    )
    self.assertEqual(LAN_GET_LOCO_MODE, 0x0060)
    self.assertEqual(LAN_SET_LOCO_MODE, 0x0061)
    self.assertEqual(build_get_loco_mode(3), bytes.fromhex("06 00 60 00 00 03"))
    self.assertEqual(build_set_loco_mode(3, "dcc"), bytes.fromhex("07 00 61 00 00 03 00"))
    self.assertEqual(build_set_loco_mode(3, "motorola"), bytes.fromhex("07 00 61 00 00 03 01"))
    self.assertEqual(
      build_x_set_loco_drive_128(3, speed=42, direction="forward"),
      bytes.fromhex("0a 00 40 00 e4 13 00 03 aa 5e"),
    )
    self.assertEqual(
      build_x_set_loco_drive(3, speed=10, direction="forward", speed_steps=28),
      bytes.fromhex("0a 00 40 00 e4 12 00 03 8a 7f"),
    )
    self.assertEqual(
      build_x_set_loco_drive(3, speed=10, direction="reverse", speed_steps=14),
      bytes.fromhex("0a 00 40 00 e4 10 00 03 0a fd"),
    )
    self.assertEqual(
      build_x_set_loco_function(3, 9, True),
      bytes.fromhex("0a 00 40 00 e4 f8 00 03 49 56"),
    )

  def test_lan_x_cv_commands_match_official_vectors(self):
    self.assertEqual(
      build_x_cv_read_direct(7),
      bytes.fromhex("09 00 40 00 23 11 00 06 34"),
    )
    self.assertEqual(
      build_x_cv_write_direct(8, 8),
      bytes.fromhex("0a 00 40 00 24 12 00 07 08 39"),
    )
    self.assertEqual(
      build_x_cv_pom_read_byte(3, 7),
      bytes.fromhex("0c 00 40 00 e6 30 00 03 e4 06 00 37"),
    )
    self.assertEqual(
      build_x_cv_pom_write_byte(4945, 266, 64),
      bytes.fromhex("0c 00 40 00 e6 30 d3 51 ed 09 40 f0"),
    )

  def test_parse_basic_payloads(self):
    self.assertEqual(parse_serial_number((1234).to_bytes(4, "little")), {
      "serial_number": 1234,
      "serial_number_hex": "000004d2",
    })
    hwinfo = parse_hwinfo((0x00000211).to_bytes(4, "little") + (0x00010402).to_bytes(4, "little"))
    self.assertEqual(hwinfo["hardware_type_label"], "Z21 XL Series 10870")
    self.assertEqual(hwinfo["hardware_type_hex"], "0x00000211")
    self.assertEqual(hwinfo["firmware_version_hex"], "0x00010402")
    self.assertEqual(hardware_type_label(0xDEADBEEF), "Unknown Z21 hardware")
    self.assertEqual(parse_broadcast_flags((0x01020304).to_bytes(4, "little"))["broadcast_flags_hex"], "0x01020304")

  def test_parse_system_state_units_and_flags(self):
    payload = b"".join([
      (321).to_bytes(2, "little"),
      (12).to_bytes(2, "little"),
      (300).to_bytes(2, "little"),
      (27).to_bytes(2, "little", signed=True),
      (18000).to_bytes(2, "little"),
      (5000).to_bytes(2, "little"),
      bytes([0x07, 0x09]),
    ])
    state = parse_system_state(payload)

    self.assertEqual(state["main_track_current_ma"], 321)
    self.assertEqual(state["programming_track_current_ma"], 12)
    self.assertEqual(state["filtered_main_track_current_ma"], 300)
    self.assertEqual(state["temperature_c"], 27)
    self.assertEqual(state["supply_voltage_v"], 18.0)
    self.assertEqual(state["vcc_voltage_v"], 5.0)
    self.assertTrue(state["emergency_stop"])
    self.assertTrue(state["track_voltage_off"])
    self.assertTrue(state["short_circuit"])
    self.assertTrue(state["temperature_too_high"])
    self.assertTrue(state["internal_short"])

  def test_parse_cv_result_and_nack_payloads(self):
    result = parse_cv_result(bytes.fromhex("64 14 00 06 56 20"))
    self.assertEqual(result.cv_number, 7)
    self.assertEqual(result.value, 86)
    self.assertEqual(result.to_debug_dict()["cv"], 7)

    ack = parse_xbus_ack(bytes.fromhex("61 13 72"))
    self.assertEqual(ack.ack_mode, "no_ack")
    self.assertEqual(ack.ack_name, "LAN_X_CV_NACK")

  def test_parse_loco_info_uses_variable_payload_length(self):
    payload_without_checksum = bytes.fromhex("ef 00 03 04 aa 11 10 00 00 01")
    loco_info = parse_loco_info(build_lan_x_payload(*payload_without_checksum))

    self.assertEqual(loco_info.address, 3)
    self.assertEqual(loco_info.speed_steps, 128)
    self.assertEqual(loco_info.speed, 42)
    self.assertEqual(loco_info.direction, "forward")
    self.assertTrue(loco_info.functions[0])
    self.assertTrue(loco_info.functions[1])
    self.assertTrue(loco_info.functions[9])
    self.assertTrue(loco_info.functions[29])

  def test_session_manager_uses_injected_transport(self):
    class FakeTransport:
      def __init__(self):
        self.calls = []

      def exchange(self, host, port, payload, *, local_port=0, max_packets=8, stop_when=None):
        self.calls.append((host, port, payload, local_port, max_packets, stop_when))
        return [encode_dataset(LAN_GET_SERIAL_NUMBER, (7).to_bytes(4, "little"))]

    fake = FakeTransport()
    manager = Z21SessionManager(fake)
    responses = manager.exchange("192.168.0.111", 21105, build_get_serial_number(), local_port=0, max_packets=1)

    self.assertEqual(parse_serial_number(decode_datasets(responses[0])[0].payload)["serial_number"], 7)
    self.assertEqual(fake.calls[0][:5], ("192.168.0.111", 21105, build_get_serial_number(), 0, 1))

  def test_udp_transport_accepts_response_from_expected_source_port(self):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server_port = server.getsockname()[1]

    def responder():
      try:
        _request, client = server.recvfrom(4096)
        server.sendto(encode_dataset(LAN_GET_SERIAL_NUMBER, (42).to_bytes(4, "little")), client)
      finally:
        server.close()

    thread = threading.Thread(target=responder)
    thread.start()
    responses = Z21UDPTransport(timeout_seconds=0.2).exchange("127.0.0.1", server_port, build_get_serial_number())
    thread.join(timeout=1.0)

    self.assertEqual(parse_serial_number(decode_datasets(responses[0])[0].payload)["serial_number"], 42)

  def test_udp_transport_ignores_response_from_unexpected_source_port(self):
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server_port = server.getsockname()[1]

    def responder():
      try:
        _request, client = server.recvfrom(4096)
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as wrong_source:
          wrong_source.sendto(encode_dataset(LAN_GET_SERIAL_NUMBER, (99).to_bytes(4, "little")), client)
      finally:
        server.close()

    thread = threading.Thread(target=responder)
    thread.start()
    with self.assertRaises(TimeoutError):
      Z21UDPTransport(timeout_seconds=0.1).exchange("127.0.0.1", server_port, build_get_serial_number())
    thread.join(timeout=1.0)


if __name__ == "__main__":
  unittest.main()

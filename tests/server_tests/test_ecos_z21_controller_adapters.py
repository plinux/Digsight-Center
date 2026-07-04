import unittest

from z21_lan import (
  LAN_GET_BROADCASTFLAGS,
  LAN_GET_COMMON_SETTINGS,
  LAN_GET_HWINFO,
  LAN_SET_LOCO_MODE,
  LAN_SET_COMMON_SETTINGS,
  LAN_GET_MMDCC_SETTINGS,
  LAN_GET_SERIAL_NUMBER,
  LAN_SET_MMDCC_SETTINGS,
  LAN_X,
  LAN_SYSTEMSTATE_DATACHANGED,
  encode_dataset,
  xbus_xor,
)

from server import models
from server.controllers.base import (
  ControllerInfoReadRequest,
  CvCommandRequest,
  LocoControlGrantRequest,
  LocoFunctionRequest,
  LocoSpeedRequest,
  TrackOutputRequest,
)
from server.controllers.ecos import ECoSCvAck, ECoSCvValue, ECoSControllerAdapter, ECoSProgrammingTrackStatus
from server.controllers.z21 import Z21ProgrammingTrackStatus, Z21_XL_PROFILE, Z21LanControllerAdapter
import server.controllers.z21 as z21_module


class FakeECoSTransport:
  def __init__(self):
    self.calls = []
    self.created = False

  def exchange(self, host, port, commands, *, timeout_seconds=None, expected_replies=1, expected_events=0):
    self.calls.append((host, port, commands, timeout_seconds, expected_replies, expected_events))
    command_list = list(commands if isinstance(commands, (list, tuple)) else [commands])
    first_command = command_list[0]
    if first_command == "set(1, go)":
      return "\n".join([
        "<REPLY set(1, go)>",
        "1 status[GO]",
        "<END 0 (OK)>",
        "<REPLY get(1, status)>",
        "1 status[GO]",
        "<END 0 (OK)>",
      ])
    if first_command == "set(1, stop)":
      return "\n".join([
        "<REPLY set(1, stop)>",
        "1 status[STOP]",
        "<END 0 (OK)>",
        "<REPLY get(1, status)>",
        "1 status[STOP]",
        "<END 0 (OK)>",
      ])
    if first_command == "queryObjects(10, addr, name, protocol)":
      loco_lines = ['1001 addr[3] name["Test"] protocol[DCC128]']
      if self.created:
        loco_lines.append('1002 addr[4945] name["Digsight 4945"] protocol[DCC128]')
      return "\n".join([
        "<REPLY queryObjects(10, addr, name, protocol)>",
        *loco_lines,
        "<END 0 (OK)>",
      ])
    if first_command.startswith("create(10,"):
      self.created = True
      return "\n".join([
        f"<REPLY {first_command}>",
        "<END 0 (OK)>",
      ])
    if first_command == "request(1001, control)":
      return "\n".join([
        "<REPLY request(1001, control)>",
        "<END 0 (OK)>",
        f"<REPLY {command_list[1]}>",
        "<END 0 (OK)>",
        "<REPLY release(1001, control)>",
        "<END 0 (OK)>",
      ])
    if first_command == "request(5, view)":
      return "\n".join([
        "<REPLY request(5, view)>",
        "<END 0 (OK)>",
        f"<REPLY {command_list[1]}>",
        "<END 0 (OK)>",
        "<EVENT 5>",
        "5 state[OK] cv[7,86]",
        "<END 0 (OK)>",
        "<REPLY release(5, view)>",
        "<END 0 (OK)>",
      ])
    if first_command == "queryObjects(27, name)":
      return "\n".join([
        "<REPLY queryObjects(27, name)>",
        '65000 name["System booster"]',
        '65001 name["Ext. Booster Ctl"]',
        "<END 0 (OK)>",
      ])
    if first_command == "request(65000, view)":
      return "\n".join([
        "<REPLY request(65000, view)>",
        "<END 0 (OK)>",
        "<REPLY get(65000, name, status, current, voltage, temperature, limit)>",
        '65000 name["System booster"] status[GO] current[123,0] voltage[12989] temperature[49] limit[4000]',
        "<END 0 (OK)>",
        "<REPLY release(65000, view)>",
        "<END 0 (OK)>",
      ])
    if first_command == "request(65000, control)":
      return "\n".join([
        "<REPLY request(65000, control)>",
        "<END 0 (OK)>",
        f"<REPLY {command_list[1]}>",
        "<END 0 (OK)>",
        "<REPLY get(65000, limit)>",
        "65000 limit[3500]",
        "<END 0 (OK)>",
        "<REPLY release(65000, control)>",
        "<END 0 (OK)>",
      ])
    return "\n".join([
      "<REPLY request(1, view)>",
      "1 status[GO]",
      "<END 0 (OK)>",
      "<REPLY get(1, commandstationtype, protocolversion, hardwareversion, applicationversion, applicationversionsuffix, railcom, railcomplus, status)>",
      "1 commandstationtype[ECoS2] protocolversion[1.1] hardwareversion[50220] applicationversion[4.2.11] applicationversionsuffix[] railcom[1] railcomplus[0] status[GO]",
      "<END 0 (OK)>",
    ])


class FakeZ21Transport:
  def __init__(self):
    self.calls = []
    self.mmdcc_settings_payload = bytes.fromhex("19 06 07 01 05 14 88 13 10 27 32 80 80 3e 80 3e")
    self.common_settings_payload = bytes.fromhex("01 00 00 03 01 00 03 00 00 00")

  def exchange(self, host, port, payload, *, local_port=0, max_packets=8, stop_when=None, timeout_seconds=None):
    self.calls.append((host, port, payload, local_port, max_packets, stop_when))
    if payload == b"\x04\x00\x10\x00":
      return [encode_dataset(LAN_GET_SERIAL_NUMBER, (1234).to_bytes(4, "little"))]
    if payload == b"\x04\x00\x1a\x00":
      return [encode_dataset(LAN_GET_HWINFO, (0x00000211).to_bytes(4, "little") + (0x00010402).to_bytes(4, "little"))]
    if payload == b"\x04\x00\x51\x00":
      return [encode_dataset(LAN_GET_BROADCASTFLAGS, (0x00000001).to_bytes(4, "little"))]
    if payload == b"\x04\x00\x16\x00":
      return [encode_dataset(LAN_GET_MMDCC_SETTINGS, self.mmdcc_settings_payload)]
    if payload == b"\x04\x00\x12\x00":
      return [encode_dataset(LAN_GET_COMMON_SETTINGS, self.common_settings_payload)]
    if len(payload) == 20 and payload[:4] == b"\x14\x00\x17\x00":
      self.mmdcc_settings_payload = payload[4:]
      return [encode_dataset(LAN_SET_MMDCC_SETTINGS)]
    if len(payload) == 14 and payload[:4] == b"\x0e\x00\x13\x00":
      self.common_settings_payload = payload[4:]
      return [encode_dataset(LAN_SET_COMMON_SETTINGS)]
    if len(payload) == 7 and payload[:4] == b"\x07\x00\x61\x00":
      return [encode_dataset(LAN_SET_LOCO_MODE)]
    if payload == b"\x04\x00\x85\x00":
      state_payload = b"".join([
        (321).to_bytes(2, "little"),
        (12).to_bytes(2, "little"),
        (300).to_bytes(2, "little"),
        (27).to_bytes(2, "little", signed=True),
        (18000).to_bytes(2, "little"),
        (16000).to_bytes(2, "little"),
        bytes([0x00, 0x00]),
      ])
      return [encode_dataset(LAN_SYSTEMSTATE_DATACHANGED, state_payload)]
    if payload == b"\x07\x00\x40\x00\x21\x80\xa1":
      state_payload = b"".join([
        (0).to_bytes(2, "little"),
        (0).to_bytes(2, "little"),
        (0).to_bytes(2, "little"),
        (25).to_bytes(2, "little", signed=True),
        (18000).to_bytes(2, "little"),
        (16000).to_bytes(2, "little"),
        bytes([0x02, 0x00]),
      ])
      responses = [
        encode_dataset(LAN_X, b"\x61\x00\x61"),
        encode_dataset(LAN_SYSTEMSTATE_DATACHANGED, state_payload),
      ]
      if stop_when:
        self.stop_results = [stop_when(raw) for raw in responses]
      return responses
    if payload == b"\x07\x00\x40\x00\x21\x81\xa0":
      state_payload = b"".join([
        (11).to_bytes(2, "little"),
        (0).to_bytes(2, "little"),
        (11).to_bytes(2, "little"),
        (25).to_bytes(2, "little", signed=True),
        (18000).to_bytes(2, "little"),
        (16000).to_bytes(2, "little"),
        bytes([0x00, 0x00]),
      ])
      responses = [
        encode_dataset(LAN_X, b"\x61\x01\x60"),
        encode_dataset(LAN_SYSTEMSTATE_DATACHANGED, state_payload),
      ]
      if stop_when:
        self.stop_results = [stop_when(raw) for raw in responses]
      return responses
    if len(payload) >= 6 and payload[:4] == b"\x09\x00\x40\x00" and payload[4:6] == b"\x23\x11":
      return [encode_dataset(LAN_X, _xbus_payload(0x64, 0x14, 0x00, 0x06, 0x56))]
    if len(payload) >= 6 and payload[:4] == b"\x0a\x00\x40\x00" and payload[4:6] == b"\x24\x12":
      return [encode_dataset(LAN_X, _xbus_payload(0x64, 0x14, 0x00, 0x06, 0x56))]
    if len(payload) >= 9 and payload[:4] == b"\x0c\x00\x40\x00" and payload[4:6] == b"\xe6\x30" and payload[8] == 0xE4:
      return [encode_dataset(LAN_X, _xbus_payload(0x64, 0x14, 0x00, 0x06, 0x56))]
    if len(payload) >= 9 and payload[:4] == b"\x0c\x00\x40\x00" and payload[4:6] == b"\xe6\x30" and payload[8] == 0xEC:
      raise TimeoutError("Z21 POM byte write has no reply")
    if len(payload) >= 6 and payload[4:6] == b"\xe3\xf0":
      address = ((payload[6] & 0x3F) << 8) | payload[7]
      return [encode_dataset(LAN_X, _loco_info_payload(address, 42))]
    if len(payload) >= 6 and payload[4:6] == b"\xe4\xf8":
      return [encode_dataset(LAN_X, _xbus_payload(0xEF, 0x00, 0x03, 0x04, 0xAA, 0x10, 0x10, 0x00, 0x00))]
    if len(payload) >= 6 and payload[4] == 0xE4 and payload[5] in {0x10, 0x12, 0x13}:
      return [encode_dataset(LAN_X, _loco_info_payload(3, 42))]
    return [encode_dataset(0x0040, b"\xf3\x0a\x04")]


class FakeZ21MissingSystemStateTransport(FakeZ21Transport):
  def exchange(self, host, port, payload, *, local_port=0, max_packets=8, stop_when=None, timeout_seconds=None):
    if payload == b"\x04\x00\x85\x00":
      raise TimeoutError("system state timeout")
    return super().exchange(
      host,
      port,
      payload,
      local_port=local_port,
      max_packets=max_packets,
      stop_when=stop_when,
      timeout_seconds=timeout_seconds,
    )


class FakeZ21TimeoutAwareTransport(FakeZ21Transport):
  def __init__(self):
    super().__init__()
    self.timeout_values = []

  def exchange(self, host, port, payload, *, local_port=0, max_packets=8, stop_when=None, timeout_seconds=None):
    self.timeout_values.append(timeout_seconds)
    return super().exchange(
      host,
      port,
      payload,
      local_port=local_port,
      max_packets=max_packets,
      stop_when=stop_when,
      timeout_seconds=timeout_seconds,
    )


class FakeZ21TrackPowerPollTransport(FakeZ21Transport):
  def __init__(self):
    super().__init__()
    self.powered = True

  def exchange(self, host, port, payload, *, local_port=0, max_packets=8, stop_when=None, timeout_seconds=None):
    self.calls.append((host, port, payload, local_port, max_packets, stop_when))
    if payload == b"\x07\x00\x40\x00\x21\x80\xa1":
      self.powered = False
      raise TimeoutError("track power command has no direct reply")
    if payload == b"\x07\x00\x40\x00\x21\x81\xa0":
      self.powered = True
      raise TimeoutError("track power command has no direct reply")
    if payload == b"\x04\x00\x85\x00":
      state_payload = b"".join([
        (0).to_bytes(2, "little"),
        (0).to_bytes(2, "little"),
        (0).to_bytes(2, "little"),
        (25).to_bytes(2, "little", signed=True),
        (18000).to_bytes(2, "little"),
        (16000).to_bytes(2, "little"),
        bytes([0x00 if self.powered else 0x02, 0x00]),
      ])
      return [encode_dataset(LAN_SYSTEMSTATE_DATACHANGED, state_payload)]
    return super().exchange(
      host,
      port,
      payload,
      local_port=local_port,
      max_packets=max_packets,
      stop_when=stop_when,
      timeout_seconds=timeout_seconds,
    )


def _xbus_payload(*body_values: int) -> bytes:
  body = bytes(body_values)
  return body + bytes([xbus_xor(body)])


def _loco_info_payload(address: int, speed: int) -> bytes:
  high = ((int(address) >> 8) & 0x3F) | (0xC0 if int(address) > 127 else 0x00)
  low = int(address) & 0xFF
  speed_byte = 0x80 | int(speed)
  return _xbus_payload(0xEF, high, low, 0x04, speed_byte, 0x10, 0x00, 0x00, 0x00)


class ECoSAndZ21ControllerReadInfoTest(unittest.TestCase):
  def test_ecos_read_info_updates_controller_state_and_control_capabilities(self):
    adapter = ECoSControllerAdapter()
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.10",
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "controller_info_status_timeout_seconds": 0.25,
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    session = adapter.create_session_manager(transport=FakeECoSTransport())

    result = adapter.read_controller_info(session, controller, ControllerInfoReadRequest("ho", 0))
    parsed = adapter.parse_controller_info(controller, ControllerInfoReadRequest("ho", 0), result)

    self.assertEqual(result.collected["basic_info"]["hardwareversion"], "50220")
    self.assertEqual(result.collected["boosters"][0]["object_id"], 65000)
    self.assertEqual(result.collected["booster_monitor"]["limit"], "4000")
    self.assertEqual(controller["device_info"]["commandstationtype"], "ECoS2")
    self.assertEqual(controller["booster_status"]["source"], "ecos_booster_65000")
    self.assertEqual(controller["booster_status"]["booster_object_id"], 65000)
    self.assertEqual(controller["booster_status"]["limit_ma"], 4000)
    self.assertEqual(controller["booster_status"]["main_track_current_ma"], 123)
    self.assertEqual(controller["booster_status"]["output_voltage_v"], 12.989)
    self.assertEqual(controller["telemetry"]["track_current_a"], 0.123)
    self.assertEqual(controller["telemetry"]["track_voltage_v"], 12.989)
    self.assertEqual(controller["telemetry"]["temperature_c"], 49)
    self.assertAlmostEqual(controller["telemetry"]["track_power_w"], 1.597647)
    self.assertTrue(controller["booster_status"]["power_on"])
    self.assertEqual(controller["programming_track_status"]["source"], "ecos_booster_65000")
    self.assertEqual(controller["programming_track_status"]["track_mode"], models.TRACK_MODE_HO)
    self.assertTrue(parsed["safe_for_cv"])
    self.assertTrue(adapter.capabilities.track_power)
    self.assertTrue(adapter.capabilities.cv_programming)
    self.assertTrue(adapter.capabilities.loco_control)
    self.assertTrue(adapter.capabilities.controller_settings)
    command_batches = [call[2] for call in session.transport.calls]
    self.assertIn(["queryObjects(27, name)"], command_batches)
    self.assertIn([
      "request(65000, view)",
      "get(65000, name, status, current, voltage, temperature, limit)",
      "release(65000, view)",
    ], command_batches)

  def test_ecos_profiles_use_current_limit_without_voltage_fields(self):
    adapter = ECoSControllerAdapter()

    for mode in (models.TRACK_MODE_N, models.TRACK_MODE_HO, models.TRACK_MODE_G):
      profile = adapter.default_track_profiles[mode]
      self.assertEqual(profile["target_current_limit_ma"], 4000)
      self.assertEqual(profile["max_target_current_limit_ma"], 6000)
      self.assertEqual(profile["current_step_ma"], 100)
      self.assertNotIn("target_voltage_v", profile)
      self.assertNotIn("min_target_voltage_v", profile)
      self.assertNotIn("max_target_voltage_v", profile)
    self.assertFalse(adapter.default_track_profiles[models.TRACK_MODE_DC]["enabled"])

  def test_ecos_adapter_runtime_contract_helpers_are_protocol_specific(self):
    adapter = ECoSControllerAdapter()
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.10",
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "device_info": {},
    }
    adapter.apply_transport_runtime(controller)

    self.assertEqual(adapter.endpoint_identity(controller), (
      ("transport", "tcp"),
      ("ip", "192.0.2.10"),
      ("tcp_port", "15471"),
    ))
    self.assertEqual(adapter.session_identity(controller), ())
    self.assertEqual(adapter.runtime_readiness_warnings(controller), [])
    self.assertEqual(adapter.loco_control_readiness_warnings(controller), [])
    self.assertEqual(adapter.status_not_ready_message(), "控制器通信参数尚未确认")
    self.assertEqual(adapter.readiness_warning_detail(["controller_ip_unconfigured"]), "控制器 IP 尚未配置")
    self.assertEqual(adapter.readiness_warning_detail(["tcp_port_unconfirmed"]), "控制器 TCP 端口未确认")
    self.assertEqual(adapter.readiness_warning_detail(["controller_ip_unconfigured", "tcp_port_unconfirmed"]), "控制器 TCP 端口未确认")
    self.assertEqual(adapter.readiness_warning_detail(["other"]), "控制器通信端点尚未确认")
    self.assertEqual(adapter.controller_client_id(controller), 0)
    self.assertIsNone(adapter.programming_track_status(controller))
    self.assertFalse(adapter.is_booster_status_confirmed(controller))
    controller["booster_status"] = {"source": "ecos_object_1"}
    self.assertTrue(adapter.is_booster_status_confirmed(controller))

    unconfigured = {"ip": "0.0.0.0", "tcp_port": 0}
    self.assertEqual(adapter.runtime_readiness_warnings(unconfigured), ["controller_ip_unconfigured", "tcp_port_unconfirmed"])

  def test_ecos_track_power_loco_and_cv_commands_use_text_protocol(self):
    adapter = ECoSControllerAdapter()
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.10",
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeECoSTransport()
    session = adapter.create_session_manager(transport=transport)

    power = adapter.send_track_output_request(session, controller, TrackOutputRequest(True, models.TRACK_MODE_HO, 0))
    grant = adapter.request_loco_control_grant(session, controller, LocoControlGrantRequest(4945, 0))
    speed = adapter.send_loco_speed_request(session, controller, LocoSpeedRequest(3, 42, "forward", 0))
    speed_dcc28 = adapter.send_loco_speed_request(session, controller, LocoSpeedRequest(
      3,
      126,
      "forward",
      0,
      control_protocol="dcc",
      speed_steps=28,
    ))
    function = adapter.send_loco_function_request(session, controller, LocoFunctionRequest(3, {"9": True}, 9, 0))
    cv_read = adapter.read_cv_request(session, controller, CvCommandRequest(7, 0))
    cv_write = adapter.write_cv_request(session, controller, CvCommandRequest(7, 0, value=86))

    self.assertTrue(power.booster_status["power_on"])
    self.assertEqual(grant.feedback["object_id"], 1002)
    self.assertEqual(speed.feedback["speed"], 42)
    self.assertEqual(speed_dcc28.feedback["command_speed"], 28)
    self.assertEqual(speed_dcc28.feedback["ecos_loco_protocol"], "DCC28")
    self.assertEqual(function.feedback["function_number"], 9)
    self.assertEqual(adapter.classify_cv_responses(cv_read.frames, client_id=0, cv_number=7).value.value, 86)
    self.assertEqual(adapter.classify_cv_responses(cv_write.frames, client_id=0, cv_number=7).ack.ack_mode, "ack")
    command_batches = [call[2] for call in transport.calls]
    self.assertIn(["set(1, go)", "get(1, status)"], command_batches)
    self.assertIn(["request(5, view)", "set(5, mode[readdccdirect], cv[7])", "release(5, view)"], command_batches)
    self.assertIn(["request(1001, control)", "set(1001, speedstep[42], dir[0])", "release(1001, control)"], command_batches)
    self.assertIn(["request(1001, control)", "set(1001, speedstep[28], dir[0])", "release(1001, control)"], command_batches)

  def test_ecos_track_profile_settings_write_booster_current_limit(self):
    adapter = ECoSControllerAdapter()
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.10",
      "transport": {"kind": "tcp", "tcp_port": 15471},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeECoSTransport()
    session = adapter.create_session_manager(transport=transport)

    results = adapter.apply_track_profile_parameters(
      session,
      controller,
      {
        "ho": {"target_current_limit_ma": 3500},
      },
      ["ho"],
    )

    self.assertEqual(results, [{
      "mode": "ho",
      "setting": "ecos_booster_current_limit",
      "booster_object_id": 65000,
      "target_current_limit_ma": 3500,
      "readback_current_limit_ma": 3500,
      "write_request_hex": "72 65 71 75 65 73 74 28 36 35 30 30 30 2c 20 63 6f 6e 74 72 6f 6c 29\n73 65 74 28 36 35 30 30 30 2c 20 6c 69 6d 69 74 5b 33 35 30 30 5d 29\n67 65 74 28 36 35 30 30 30 2c 20 6c 69 6d 69 74 29\n72 65 6c 65 61 73 65 28 36 35 30 30 30 2c 20 63 6f 6e 74 72 6f 6c 29",
    }])
    self.assertEqual(controller["booster_status"]["limit_ma"], 3500)
    self.assertEqual(controller["track_profiles"]["ho"]["target_current_limit_ma"], 3500)
    self.assertIn([
      "request(65000, control)",
      "set(65000, limit[3500])",
      "get(65000, limit)",
      "release(65000, control)",
    ], [call[2] for call in transport.calls])

  def test_ecos_cv_helpers_and_programming_track_safety_are_adapter_owned(self):
    adapter = ECoSControllerAdapter()
    value = ECoSCvValue(7, 86)
    ack = ECoSCvAck("ack", "ECOS_PROGRAMMER_SUCCESS", "ok")

    self.assertEqual(value.to_debug_dict()["value"], 86)
    self.assertEqual(ack.to_debug_dict()["ack_mode"], "ack")
    self.assertEqual(adapter.cv_ack_category(ack), "ack")
    self.assertFalse(adapter.should_retry_cv_write_ack(ack, attempt=0, retry_count=5))
    self.assertFalse(adapter.is_main_track_cv_read_no_ack(ack))
    self.assertEqual(adapter.cv_ack_debug(ack)["ack"], "ECOS_PROGRAMMER_SUCCESS")
    adapter.validate_programming_track_safety(ECoSProgrammingTrackStatus(
      track_mode=models.TRACK_MODE_HO,
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=0,
      output_value=0,
      current_limit_ma=0,
    ))
    with self.assertRaises(ValueError):
      adapter.validate_programming_track_safety(ECoSProgrammingTrackStatus(
        track_mode=models.TRACK_MODE_DC,
        dcc_mode=False,
        programming_track_busy=False,
        programming_track_current_ma=0,
        output_value=0,
        current_limit_ma=0,
      ))

  def test_z21_read_info_updates_controller_state_from_system_state(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeZ21Transport()
    session = adapter.create_session_manager(transport=transport)

    result = adapter.read_controller_info(session, controller, ControllerInfoReadRequest(models.TRACK_MODE_G, 0))
    parsed = adapter.parse_controller_info(controller, ControllerInfoReadRequest(models.TRACK_MODE_G, 0), result)

    self.assertEqual(result.warnings, [])
    self.assertEqual(controller["device_info"]["hardware_type_label"], "Z21 XL Series 10870")
    self.assertEqual(controller["device_info"]["serial_number"], 1234)
    self.assertEqual(controller["booster_status"]["source"], "z21_system_state")
    self.assertEqual(controller["booster_status"]["main_track_current_ma"], 321)
    self.assertEqual(controller["booster_status"]["filtered_main_track_current_ma"], 300)
    self.assertEqual(controller["booster_status"]["supply_voltage_v"], 18.0)
    self.assertEqual(controller["booster_status"]["output_voltage_v"], 16.0)
    self.assertEqual(controller["telemetry"]["track_voltage_v"], 16.0)
    self.assertEqual(controller["telemetry"]["track_current_a"], 0.321)
    self.assertEqual(controller["telemetry"]["track_power_w"], 5.136)
    self.assertTrue(adapter.is_booster_status_confirmed(controller))
    self.assertEqual(controller["programming_track_status"]["source"], "z21_system_state")
    self.assertEqual(controller["programming_track_status"]["track_mode"], models.TRACK_MODE_G)
    self.assertEqual(controller["programming_track_status"]["programming_track_current_ma"], 12)
    self.assertTrue(parsed["safe_for_cv"])

  def test_z21_track_power_request_uses_official_lan_x_and_system_state_readback(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeZ21Transport()
    session = adapter.create_session_manager(transport=transport)

    off = adapter.send_track_output_request(
      session,
      controller,
      TrackOutputRequest(False, models.TRACK_MODE_HO, 0),
    )
    on = adapter.send_track_output_request(
      session,
      controller,
      TrackOutputRequest(True, models.TRACK_MODE_HO, 0),
    )

    self.assertEqual(off.request_hex, "07 00 40 00 21 80 a1")
    self.assertFalse(off.booster_status["power_on"])
    self.assertEqual(on.request_hex, "07 00 40 00 21 81 a0")
    self.assertTrue(on.booster_status["power_on"])
    self.assertEqual(transport.stop_results, [False, True])

  def test_z21_loco_and_cv_commands_use_lan_x_messages(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeZ21Transport()
    session = adapter.create_session_manager(transport=transport)

    cv_read = adapter.read_cv_request(session, controller, CvCommandRequest(7, 0))
    cv_write = adapter.write_cv_request(session, controller, CvCommandRequest(7, 0, value=86))
    pom_read = adapter.read_cv_request(session, controller, CvCommandRequest(7, 0, pom_address=3))
    pom_write = adapter.write_cv_request(session, controller, CvCommandRequest(7, 0, value=86, pom_address=3))
    speed = adapter.send_loco_speed_request(session, controller, LocoSpeedRequest(3, 42, "forward", 0))
    speed_dcc28 = adapter.send_loco_speed_request(session, controller, LocoSpeedRequest(
      3,
      126,
      "forward",
      0,
      control_protocol="dcc",
      speed_steps=28,
    ))
    function = adapter.send_loco_function_request(session, controller, LocoFunctionRequest(3, {"9": True}, 9, 0))

    self.assertEqual(adapter.classify_cv_responses(cv_read.frames, client_id=0, cv_number=7).value.value, 86)
    self.assertEqual(adapter.classify_cv_responses(cv_write.frames, client_id=0, cv_number=7).ack.ack_name, "LAN_X_CV_RESULT")
    self.assertEqual(adapter.classify_cv_responses(pom_read.frames, client_id=0, cv_number=7, pom_address=3).value.pom_address, 3)
    self.assertEqual(adapter.classify_cv_responses(pom_write.frames, client_id=0, cv_number=7, pom_address=3).ack.ack_name, "LAN_X_CV_POM_WRITE_BYTE_SENT")
    self.assertEqual(speed.feedback["speed"], 42)
    self.assertEqual(speed_dcc28.extra["command_speed"], 28)
    self.assertTrue(function.feedback["functions"][9])
    payloads = [call[2] for call in transport.calls]
    self.assertIn(bytes.fromhex("07 00 61 00 00 03 00"), payloads)
    self.assertIn(bytes.fromhex("09 00 40 00 23 11 00 06 34"), payloads)
    self.assertIn(bytes.fromhex("0a 00 40 00 e4 12 00 03 9c 69"), payloads)
    self.assertIn(bytes.fromhex("0a 00 40 00 e4 f8 00 03 49 56"), payloads)

  def test_z21_cv_read_uses_configured_timeout(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
      "cv_timeout_seconds": 2.5,
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeZ21TimeoutAwareTransport()
    session = adapter.create_session_manager(transport=transport)

    adapter.read_cv_request(session, controller, CvCommandRequest(8, 0))
    adapter.read_cv_request(session, controller, CvCommandRequest(7, 0, timeout_seconds=3.5))

    self.assertEqual(transport.timeout_values[-2:], [2.5, 3.5])

  def test_z21_cv_helpers_grant_and_matchers_are_adapter_owned(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    session = adapter.create_session_manager(transport=FakeZ21Transport())
    ack = adapter.classify_cv_responses(
      [encode_dataset(LAN_X, _xbus_payload(0x61, 0x13))],
      client_id=0,
      cv_number=7,
    ).ack

    grant = adapter.request_loco_control_grant(session, controller, LocoControlGrantRequest(3, 0))

    self.assertEqual(adapter.cv_ack_category(ack), "rejected")
    self.assertFalse(adapter.should_retry_cv_write_ack(ack, attempt=0, retry_count=5))
    self.assertTrue(adapter.is_main_track_cv_read_no_ack(ack))
    self.assertEqual(adapter.cv_ack_debug(ack)["ack"], "LAN_X_CV_NACK")
    self.assertTrue(grant.feedback["grant_not_required"])
    adapter.validate_programming_track_safety(Z21ProgrammingTrackStatus(
      track_mode=models.TRACK_MODE_G,
      dcc_mode=True,
      programming_track_busy=False,
      programming_track_current_ma=0,
      output_value=0,
      current_limit_ma=0,
    ))
    with self.assertRaises(ValueError):
      adapter.validate_programming_track_safety(Z21ProgrammingTrackStatus(
        track_mode=models.TRACK_MODE_HO,
        dcc_mode=True,
        programming_track_busy=True,
        programming_track_current_ma=0,
        output_value=0,
        current_limit_ma=0,
      ))
    self.assertTrue(z21_module._z21_cv_response_matcher()(encode_dataset(LAN_X, _xbus_payload(0x64, 0x14, 0x00, 0x06, 0x56))))
    self.assertFalse(z21_module._z21_cv_response_matcher()(encode_dataset(0x0040, b"\x00")))
    self.assertTrue(z21_module._z21_loco_info_matcher(3)(encode_dataset(LAN_X, _loco_info_payload(3, 42))))
    self.assertFalse(z21_module._z21_loco_info_matcher(4)(encode_dataset(LAN_X, _loco_info_payload(3, 42))))

  def test_z21_track_profile_settings_write_mmdcc_voltage_and_read_back(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeZ21Transport()
    session = adapter.create_session_manager(transport=transport)

    results = adapter.apply_track_profile_parameters(
      session,
      controller,
      {
        "ho": {"target_voltage_v": 15.0},
        "g": {"target_voltage_v": 17.0},
      },
      ["ho", "g"],
    )

    self.assertEqual([result["mode"] for result in results], ["ho", "g"])
    self.assertEqual(results[0]["output_voltage_mv"], 15000)
    self.assertEqual(results[0]["programming_voltage_mv"], 16000)
    self.assertEqual(results[1]["output_voltage_mv"], 17000)
    self.assertEqual(results[1]["programming_voltage_mv"], 16000)
    self.assertEqual(controller["booster_status"]["output_voltage_v"], 17.0)
    self.assertEqual(controller["telemetry"]["track_voltage_v"], 17.0)
    payloads = [call[2] for call in transport.calls]
    self.assertEqual(payloads, [
      bytes.fromhex("04 00 16 00"),
      bytes.fromhex("14 00 17 00 19 06 07 01 05 14 88 13 10 27 32 80 98 3a 80 3e"),
      bytes.fromhex("04 00 16 00"),
      bytes.fromhex("14 00 17 00 19 06 07 01 05 14 88 13 10 27 32 80 68 42 80 3e"),
      bytes.fromhex("04 00 16 00"),
    ])

  def test_z21_track_power_polls_system_state_when_command_has_no_direct_reply(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    transport = FakeZ21TrackPowerPollTransport()
    session = adapter.create_session_manager(transport=transport)

    off = adapter.send_track_output_request(
      session,
      controller,
      TrackOutputRequest(False, models.TRACK_MODE_HO, 0),
    )
    on = adapter.send_track_output_request(
      session,
      controller,
      TrackOutputRequest(True, models.TRACK_MODE_HO, 0),
    )

    self.assertFalse(off.booster_status["power_on"])
    self.assertEqual(off.debug["warnings"], ["track_power_command_timeout:track power command has no direct reply"])
    self.assertTrue(on.booster_status["power_on"])
    self.assertEqual(on.debug["warnings"], ["track_power_command_timeout:track power command has no direct reply"])
    self.assertEqual([call[2] for call in transport.calls], [
      b"\x07\x00\x40\x00\x21\x80\xa1",
      b"\x04\x00\x85\x00",
      b"\x07\x00\x40\x00\x21\x81\xa0",
      b"\x04\x00\x85\x00",
    ])

  def test_z21_read_info_missing_system_state_clears_old_booster_status(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "telemetry": {},
      "device_info": {},
      "booster_status": {"source": "z21_system_state", "power_on": True},
      "safety_snapshot": {},
    }
    adapter.apply_transport_runtime(controller)
    session = adapter.create_session_manager(transport=FakeZ21MissingSystemStateTransport())

    result = adapter.read_controller_info(session, controller, ControllerInfoReadRequest(models.TRACK_MODE_G, 0))
    parsed = adapter.parse_controller_info(controller, ControllerInfoReadRequest(models.TRACK_MODE_G, 0), result)

    self.assertIn("system_state_timeout", result.warnings)
    self.assertFalse(controller["controller_reachable"])
    self.assertNotIn("booster_status", controller)
    self.assertNotIn("programming_track_status", controller)
    self.assertFalse(adapter.is_booster_status_confirmed(controller))
    self.assertFalse(controller["safety_snapshot"]["booster_status_fresh"])
    self.assertFalse(parsed["safe_for_cv"])
    self.assertIn("programming_track_status_unconfirmed", parsed["warnings"])

  def test_z21_adapter_runtime_contract_helpers_are_protocol_specific(self):
    adapter = Z21LanControllerAdapter(Z21_XL_PROFILE)
    controller = {
      "kind": adapter.kind,
      "ip": "192.0.2.21",
      "transport": {"kind": "udp", "udp_port": 21105, "local_udp_port": 0},
      "device_info": {},
    }
    adapter.apply_transport_runtime(controller)

    self.assertEqual(adapter.endpoint_identity(controller), (
      ("transport", "udp"),
      ("ip", "192.0.2.21"),
      ("udp_port", "21105"),
      ("local_udp_port", ""),
    ))
    self.assertEqual(adapter.session_identity(controller), ())
    self.assertEqual(adapter.runtime_readiness_warnings(controller), [])
    self.assertEqual(adapter.loco_control_readiness_warnings(controller), [])
    self.assertEqual(adapter.status_not_ready_message(), "控制器通信参数尚未确认")
    self.assertEqual(adapter.readiness_warning_detail(["controller_ip_unconfigured"]), "控制器 IP 尚未配置")
    self.assertEqual(adapter.readiness_warning_detail(["udp_port_unconfirmed"]), "控制器 UDP 端口未确认")
    self.assertEqual(adapter.readiness_warning_detail(["controller_ip_unconfigured", "udp_port_unconfirmed"]), "控制器 UDP 端口未确认")
    self.assertEqual(adapter.readiness_warning_detail(["other"]), "控制器通信端点尚未确认")
    self.assertEqual(adapter.controller_client_id(controller), 0)
    self.assertIsNone(adapter.programming_track_status(controller))
    self.assertFalse(adapter.is_booster_status_confirmed(controller))
    controller["booster_status"] = {"source": "z21_system_state"}
    self.assertTrue(adapter.is_booster_status_confirmed(controller))

    unconfigured = {"ip": "0.0.0.0", "udp_port": 0}
    self.assertEqual(adapter.runtime_readiness_warnings(unconfigured), ["controller_ip_unconfigured", "udp_port_unconfirmed"])


if __name__ == "__main__":
  unittest.main()

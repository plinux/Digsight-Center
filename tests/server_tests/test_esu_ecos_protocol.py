import unittest
import socket

from esu_ecos import (
  BASIC_INFO_FIELDS,
  DEFAULT_ECOS_PORT,
  ECoSSessionManager,
  BOOSTER_MANAGER_OBJECT_ID,
  BOOSTER_MONITOR_FIELDS,
  SYSTEM_BOOSTER_OBJECT_ID,
  build_booster_current_limit_write_commands,
  build_booster_monitor_commands,
  build_booster_query_command,
  build_create_loco_command,
  build_basic_info_commands,
  build_get_command,
  build_loco_function_command,
  build_loco_query_command,
  build_loco_speed_command,
  build_programmer_cv_read_commands,
  build_programmer_cv_write_commands,
  build_power_command,
  build_request_command,
  build_railcom_command,
  build_railcomplus_command,
  build_release_command,
  build_set_command,
  ecos_loco_protocol_name,
  parse_booster_monitor_info,
  parse_booster_query_results,
  parse_loco_query_results,
  parse_basic_info,
  parse_blocks,
  parse_object_options,
  parse_programmer_event,
)
from esu_ecos.transport import _read_until_expected_blocks


class ECoSProtocolTest(unittest.TestCase):
  def test_build_basic_info_commands_read_object_one(self):
    self.assertEqual(DEFAULT_ECOS_PORT, 15471)
    self.assertEqual(build_request_command(1, "view"), "request(1, view)")
    self.assertEqual(build_release_command(1, "view"), "release(1, view)")
    self.assertEqual(build_get_command(1, ("status", "protocolversion")), "get(1, status, protocolversion)")
    self.assertEqual(build_set_command(1, ("go",)), "set(1, go)")
    self.assertEqual(build_basic_info_commands(), [
      "request(1, view)",
      f"get(1, {', '.join(BASIC_INFO_FIELDS)})",
    ])

  def test_request_command_rejects_unknown_permission(self):
    with self.assertRaises(ValueError):
      build_request_command(1, "write")
    with self.assertRaises(ValueError):
      build_release_command(1, "write")

  def test_build_power_loco_and_programmer_commands(self):
    self.assertEqual(build_power_command(True), "set(1, go)")
    self.assertEqual(build_power_command(False), "set(1, stop)")
    self.assertEqual(build_railcom_command(True), "set(1, railcom[1])")
    self.assertEqual(build_railcom_command(False), "set(1, railcom[0])")
    self.assertEqual(build_railcomplus_command(True), "set(1, railcomplus[1])")
    self.assertEqual(build_railcomplus_command(False), "set(1, railcomplus[0])")
    self.assertEqual(build_loco_query_command(), "queryObjects(10, addr, name, protocol)")
    self.assertEqual(
      build_create_loco_command(3, "Digsight 3"),
      'create(10, addr[3], name["Digsight 3"], protocol[DCC128], append)',
    )
    self.assertEqual(ecos_loco_protocol_name("dcc", 14), "DCC14")
    self.assertEqual(ecos_loco_protocol_name("dcc", 28), "DCC28")
    self.assertEqual(ecos_loco_protocol_name("dcc", 128), "DCC128")
    self.assertEqual(ecos_loco_protocol_name("motorola", 1), "MM14")
    self.assertEqual(ecos_loco_protocol_name("motorola", 2), "MM27")
    self.assertEqual(ecos_loco_protocol_name("motorola", 28), "MM28")
    self.assertEqual(ecos_loco_protocol_name("m4", 128), "M4")
    self.assertEqual(
      build_create_loco_command(3, "MM 3", ecos_loco_protocol_name("motorola", 28)),
      'create(10, addr[3], name["MM 3"], protocol[MM28], append)',
    )
    self.assertEqual(build_loco_speed_command(1001, 42), "set(1001, speedstep[42])")
    self.assertEqual(build_loco_speed_command(1001, 0, direction="reverse"), "set(1001, speedstep[0], dir[1])")
    self.assertEqual(build_loco_function_command(1001, 9, True), "set(1001, func[9,1])")
    self.assertEqual(build_programmer_cv_read_commands(7), ["request(5, view)", "set(5, mode[readdccdirect], cv[7])"])
    self.assertEqual(build_programmer_cv_write_commands(8, 8), ["request(5, view)", "set(5, mode[writedccdirect], cv[8,8])"])

  def test_build_booster_monitor_and_limit_commands(self):
    self.assertEqual(BOOSTER_MANAGER_OBJECT_ID, 27)
    self.assertEqual(SYSTEM_BOOSTER_OBJECT_ID, 65000)
    self.assertEqual(build_booster_query_command(), "queryObjects(27, name)")
    self.assertEqual(
      build_booster_monitor_commands(65000),
      [
        "request(65000, view)",
        f"get(65000, {', '.join(BOOSTER_MONITOR_FIELDS)})",
        "release(65000, view)",
      ],
    )
    self.assertEqual(
      build_booster_current_limit_write_commands(65000, 4000),
      [
        "request(65000, control)",
        "set(65000, limit[4000])",
        "get(65000, limit)",
        "release(65000, control)",
      ],
    )
    with self.assertRaises(ValueError):
      build_booster_current_limit_write_commands(65000, 999)
    with self.assertRaises(ValueError):
      build_booster_current_limit_write_commands(65000, 6001)

  def test_parse_reply_and_event_blocks(self):
    text = "\n".join([
      "<EVENT 1>",
      "1 status[GO]",
      "<END 0 (OK)>",
      "<REPLY get(1, status)>",
      "1 status[STOP]",
      "<END 0 (OK)>",
    ])
    blocks = parse_blocks(text)
    self.assertEqual([block.kind for block in blocks], ["EVENT", "REPLY"])
    self.assertEqual(blocks[1].command, "get(1, status)")
    self.assertTrue(blocks[1].ok)

  def test_parse_object_options_handles_quoted_and_multi_value_options(self):
    object_id, options = parse_object_options('100 name["BR ""218"""] func[7,1] status[GO]')
    self.assertEqual(object_id, 100)
    self.assertEqual(options["name"], 'BR "218"')
    self.assertEqual(options["func"], ["7", "1"])
    self.assertEqual(options["status"], "GO")

  def test_parse_basic_info_extracts_get_object_fields(self):
    text = "\n".join([
      "<REPLY request(1, view)>",
      "1 status[GO]",
      "<END 0 (OK)>",
      "<REPLY get(1, commandstationtype, protocolversion, hardwareversion, applicationversion, applicationversionsuffix, railcom, railcomplus, status)>",
      "1 commandstationtype[ECoS2] protocolversion[1.1] hardwareversion[50220] applicationversion[4.2.11] applicationversionsuffix[] railcom[1] railcomplus[0] status[GO]",
      "<END 0 (OK)>",
    ])
    info = parse_basic_info(text)
    self.assertEqual(info["commandstationtype"], "ECoS2")
    self.assertEqual(info["protocolversion"], "1.1")
    self.assertEqual(info["hardwareversion"], "50220")
    self.assertEqual(info["applicationversion"], "4.2.11")
    self.assertEqual(info["railcom"], "1")
    self.assertEqual(info["status"], "GO")

  def test_parse_basic_info_merges_multiline_object_fields(self):
    text = "\n".join([
      "<REPLY get(1, commandstationtype, protocolversion, hardwareversion, applicationversion, applicationversionsuffix, railcom, railcomplus, status)>",
      '1 commandstationtype["ECoS2"]',
      "1 protocolversion[0.5]",
      "1 hardwareversion[2.5]",
      "1 applicationversion[4.3.3]",
      '1 applicationversionsuffix[""]',
      "1 railcom[1]",
      "1 railcomplus[1]",
      "1 status[STOP]",
      "<END 0 (OK)>",
    ])

    info = parse_basic_info(text)

    self.assertEqual(info["commandstationtype"], "ECoS2")
    self.assertEqual(info["protocolversion"], "0.5")
    self.assertEqual(info["hardwareversion"], "2.5")
    self.assertEqual(info["applicationversion"], "4.3.3")
    self.assertEqual(info["applicationversionsuffix"], "")
    self.assertEqual(info["railcom"], "1")
    self.assertEqual(info["railcomplus"], "1")
    self.assertEqual(info["status"], "STOP")

  def test_parse_booster_query_and_monitor_info(self):
    text = "\n".join([
      "<REPLY queryObjects(27, name)>",
      '65000 name["System booster"]',
      '65001 name["Ext. Booster Ctl"]',
      "<END 0 (OK)>",
      "<REPLY request(65000, view)>",
      "<END 0 (OK)>",
      "<REPLY get(65000, name, status, current, voltage, temperature, limit)>",
      '65000 name["System booster"] status[STOP] current[123,0] voltage[12989] temperature[49] limit[4000]',
      "<END 0 (OK)>",
      "<REPLY release(65000, view)>",
      "<END 0 (OK)>",
    ])
    boosters = parse_booster_query_results(text)
    monitor = parse_booster_monitor_info(text, object_id=65000)

    self.assertEqual(boosters, [
      {"object_id": 65000, "name": "System booster"},
      {"object_id": 65001, "name": "Ext. Booster Ctl"},
    ])
    self.assertEqual(monitor["object_id"], 65000)
    self.assertEqual(monitor["name"], "System booster")
    self.assertEqual(monitor["status"], "STOP")
    self.assertEqual(monitor["current"], ["123", "0"])
    self.assertEqual(monitor["voltage"], "12989")
    self.assertEqual(monitor["temperature"], "49")
    self.assertEqual(monitor["limit"], "4000")

  def test_parse_loco_query_results_and_programmer_event(self):
    text = "\n".join([
      "<REPLY queryObjects(10, addr, name, protocol)>",
      '1001 addr[3] name["Test Loco"] protocol[DCC128]',
      '1002 addr[4945] name["BR494"] protocol[DCC128]',
      "<END 0 (OK)>",
      "<EVENT 5>",
      "5 state[OK] cv[7,86]",
      "<END 0 (OK)>",
    ])
    blocks = parse_blocks(text)
    locos = parse_loco_query_results(blocks, address=3)
    self.assertEqual(locos[0]["object_id"], 1001)
    self.assertEqual(locos[0]["addr"], "3")
    self.assertEqual(locos[0]["protocol"], "DCC128")

    event = parse_programmer_event(blocks)
    self.assertEqual(event.state, "OK")
    self.assertEqual(event.cv_number, 7)
    self.assertEqual(event.value, 86)
    self.assertEqual(event.to_debug_dict()["state"], "OK")

  def test_session_manager_uses_injected_transport(self):
    class FakeTransport:
      def __init__(self):
        self.calls = []

      def exchange(self, host, port, commands, *, timeout_seconds=None, expected_replies=1, expected_events=0):
        self.calls.append((host, port, commands, timeout_seconds, expected_replies, expected_events))
        return "<REPLY get(1, status)>\n1 status[GO]\n<END 0 (OK)>\n"

    fake = FakeTransport()
    manager = ECoSSessionManager(fake)
    text = manager.exchange("ecos.local", 15471, ["get(1, status)"], timeout_seconds=0.1, expected_replies=1)

    self.assertIn("status[GO]", text)
    self.assertEqual(fake.calls, [("ecos.local", 15471, ["get(1, status)"], 0.1, 1, 0)])

  def test_transport_rejects_partial_reply_before_expected_reply_count(self):
    class PartialSocket:
      def __init__(self):
        self.chunks = [
          b"<REPLY request(1, view)>\n1 status[GO]\n<END 0 (OK)>\n",
          b"",
        ]

      def recv(self, size):
        return self.chunks.pop(0)

    with self.assertRaises(TimeoutError) as context:
      _read_until_expected_blocks(PartialSocket(), 2, 0)

    self.assertIn("1 of 2 expected replies", str(context.exception))

  def test_transport_rejects_timed_out_partial_reply(self):
    class TimedOutPartialSocket:
      def __init__(self):
        self.returned = False

      def recv(self, size):
        if not self.returned:
          self.returned = True
          return b"<REPLY request(1, view)>\n"
        raise socket.timeout()

    with self.assertRaises(TimeoutError) as context:
      _read_until_expected_blocks(TimedOutPartialSocket(), 1, 0)

    self.assertEqual(str(context.exception), "ECoS TCP exchange timed out")


if __name__ == "__main__":
  unittest.main()

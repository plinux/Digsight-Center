import base64
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

from server.api import ApiRouter
from server.app_state import default_state
from server.api_support.sound_editor import SoundEditorApiSupport
from server.api_support.routes import handler_for, mutation_route_spec
from server.main import DigsightHandler
from server.sound_editor import (
  build_dxsd_package,
  load_user_sound_library,
  parse_dxsd_summary,
  parse_sound_project_summary,
  save_user_sound_library_slot,
  save_user_sound_library_sound,
  sound_chip_profiles,
  sound_library_catalog,
)
import server.sound_editor as sound_editor_module


def wav_bytes(sample_rate=44100, bits=16, channels=1, data=b"\x00\x00\x01\x00") -> bytes:
  byte_rate = sample_rate * channels * bits // 8
  block_align = channels * bits // 8
  fmt = struct.pack("<HHIIHH", 1, channels, sample_rate, byte_rate, block_align, bits)
  return (
    b"RIFF"
    + struct.pack("<I", 4 + (8 + len(fmt)) + (8 + len(data)))
    + b"WAVE"
    + b"fmt "
    + struct.pack("<I", len(fmt))
    + fmt
    + b"data"
    + struct.pack("<I", len(data))
    + data
  )


def minimal_dxsd_xml() -> bytes:
  pcm = base64.b64encode(b"\x00\x00\x01\x00\x02\x00\x03\x00").decode("ascii")
  return f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<NewDataSet>
  <Base_Info>
    <Decoder_Moudle>8004</Decoder_Moudle>
    <SoftWare_Version>37</SoftWare_Version>
    <Dealer_ID>mi8uqAK9gjU=</Dealer_ID>
    <Engine_Type>1</Engine_Type>
    <Sound_Name>Digsight</Sound_Name>
    <Sound_Mac_ID>4294967295</Sound_Mac_ID>
    <Model_ID>0</Model_ID>
    <Decoder_Name>8004</Decoder_Name>
  </Base_Info>
  <Slot_Table>
    <Slot_ID>1</Slot_ID>
    <Slot_Priority>1</Slot_Priority>
    <Slot_StartNode>0</Slot_StartNode>
    <Is_Use>true</Is_Use>
    <Start_Address>100</Start_Address>
    <Slot_Name>1 劈相机</Slot_Name>
  </Slot_Table>
  <Node_Table>
    <Node_ID>0</Node_ID>
    <Slot_ID>1</Slot_ID>
    <Node_Type>1</Node_Type>
    <File_ID>0</File_ID>
    <Node_Config>0</Node_Config>
    <Repeat_Amount>1</Repeat_Amount>
    <Sound_Volume>255</Sound_Volume>
    <Node_X>40</Node_X>
    <Node_Y>60</Node_Y>
    <Node_W>80</Node_W>
    <Node_H>60</Node_H>
    <Node_Name>入口</Node_Name>
    <Start_Address>0</Start_Address>
  </Node_Table>
  <Node_Table>
    <Node_ID>1</Node_ID>
    <Slot_ID>1</Slot_ID>
    <Node_Type>1</Node_Type>
    <File_ID>6</File_ID>
    <Node_Config>0</Node_Config>
    <Repeat_Amount>0</Repeat_Amount>
    <Sound_Volume>200</Sound_Volume>
    <Node_X>180</Node_X>
    <Node_Y>60</Node_Y>
    <Node_W>80</Node_W>
    <Node_H>60</Node_H>
    <Node_Name>播放劈相机</Node_Name>
    <Start_Address>0</Start_Address>
  </Node_Table>
  <Connector_Table>
    <Connector_ID>7</Connector_ID>
    <Connector_Type>0</Connector_Type>
    <Node_ID>0</Node_ID>
    <Node_Index_ID>1</Node_Index_ID>
    <Slot_ID>1</Slot_ID>
    <OUT_Node_ID>1</OUT_Node_ID>
    <Start_Address>0</Start_Address>
  </Connector_Table>
  <Judgment_Table>
    <Judgment_ID>8</Judgment_ID>
    <Connector_ID>7</Connector_ID>
    <Register_Type>1</Register_Type>
    <Operation_Type>128</Operation_Type>
    <Parameter_Value>65535</Parameter_Value>
  </Judgment_Table>
  <Action_Table>
    <Action_ID>9</Action_ID>
    <Connector_ID>7</Connector_ID>
    <Register_Type>30</Register_Type>
    <Operation_Config>128</Operation_Config>
    <Parameter_Value>65535</Parameter_Value>
  </Action_Table>
  <Random_CV_Table>
    <CV_Address>171</CV_Address>
    <CV_Value>1</CV_Value>
    <CV_Description>Slot1响应功能</CV_Description>
  </Random_CV_Table>
  <Random_CV_Table>
    <CV_Address>113</CV_Address>
    <CV_Value>180</CV_Value>
    <CV_Description>总音量</CV_Description>
  </Random_CV_Table>
  <SoundFile_Table>
    <File_ID>6</File_ID>
    <File_Name>劈相机.wav</File_Name>
    <File_Length>8</File_Length>
    <Start_Address>200</Start_Address>
    <File_Data>{pcm}</File_Data>
    <File_Flag>0</File_Flag>
  </SoundFile_Table>
</NewDataSet>
""".encode("utf-8")


def six_series_dxsd_with_default_slot_cv_xml() -> bytes:
  slot_rows = []
  for slot_id in range(1, 17):
    slot_rows.append(f"""  <Slot_Table>
    <Slot_ID>{slot_id}</Slot_ID>
    <Slot_Priority>{slot_id}</Slot_Priority>
    <Slot_StartNode>0</Slot_StartNode>
    <Is_Use>false</Is_Use>
    <Start_Address>{slot_id * 100}</Start_Address>
    <Slot_Name>Slot {slot_id}</Slot_Name>
  </Slot_Table>""")
  cv_rows = []
  for slot_id in range(1, 65):
    cv_rows.append(f"""  <Random_CV_Table>
    <CV_Address>{170 + slot_id}</CV_Address>
    <CV_Value>{slot_id if slot_id <= 60 else 255}</CV_Value>
    <CV_Description>Slot{slot_id}响应功能</CV_Description>
  </Random_CV_Table>""")
  return f"""<?xml version="1.0" encoding="utf-8" standalone="yes"?>
<NewDataSet>
  <Base_Info>
    <Decoder_Moudle>6008</Decoder_Moudle>
    <SoftWare_Version>37</SoftWare_Version>
    <Dealer_ID>mi8uqAK9gjU=</Dealer_ID>
    <Engine_Type>1</Engine_Type>
    <Sound_Name>6008 Test</Sound_Name>
    <Sound_Mac_ID>4294967295</Sound_Mac_ID>
    <Model_ID>0</Model_ID>
    <Decoder_Name>6008</Decoder_Name>
  </Base_Info>
{chr(10).join(slot_rows)}
{chr(10).join(cv_rows)}
</NewDataSet>
""".encode("utf-8")


def minimal_dxsp_xml(decoder_module: str = "5313") -> bytes:
  rows = []
  for slot_id in range(1, 30):
    file_id = 0 if slot_id == 1 else 255
    rows.append(f"""  <User_Sound_Table>
    <User_Type>{1 if slot_id == 1 else 0}</User_Type>
    <User_Volume>{255 if slot_id == 1 else 0}</User_Volume>
    <User_Label>1</User_Label>
    <User_Function_Name></User_Function_Name>
    <File_0>{file_id}</File_0>
    <File_1>255</File_1>
    <File_2>255</File_2>
  </User_Sound_Table>""")
  sound_payload = base64.b64encode(b"\x80\x81\x82\x83").decode("ascii")
  return f"""<?xml version="1.0" standalone="yes"?>
<NewDataSet>
  <Project_Base_Info>
    <Decoder_Moudle>{decoder_module}</Decoder_Moudle>
    <Flash_Size>33554432</Flash_Size>
    <SoftWare_Version>22</SoftWare_Version>
    <Engine_Type>0</Engine_Type>
    <Random_Interval>4</Random_Interval>
    <Sound_Config>254</Sound_Config>
    <Sound_Name>Default</Sound_Name>
    <Sound_Mac_ID>151587054</Sound_Mac_ID>
    <Model_ID>0</Model_ID>
    <Decoder_Name>动芯领域</Decoder_Name>
  </Project_Base_Info>
{chr(10).join(rows)}
  <SoundFile_Table>
    <File_ID>0</File_ID>
    <File_Name>SwitchAOn.wav</File_Name>
    <File_Length>4</File_Length>
    <File_Data>{sound_payload}</File_Data>
  </SoundFile_Table>
</NewDataSet>
""".encode("utf-8")


def dxsp_loop_xml(decoder_module: str = "5323") -> bytes:
  rows = []
  for slot_id in range(1, 29):
    if slot_id == 4:
      rows.append("""  <User_Sound_Table>
    <User_Type>2</User_Type>
    <User_Volume>180</User_Volume>
    <User_Label>1</User_Label>
    <User_Function_Name>循环风机</User_Function_Name>
    <File_0>0</File_0>
    <File_1>3</File_1>
    <File_2>4</File_2>
  </User_Sound_Table>""")
    else:
      rows.append("""  <User_Sound_Table>
    <User_Type>0</User_Type>
    <User_Volume>0</User_Volume>
    <User_Label>1</User_Label>
    <User_Function_Name></User_Function_Name>
    <File_0>255</File_0>
    <File_1>255</File_1>
    <File_2>255</File_2>
  </User_Sound_Table>""")
  sound_rows = []
  for file_id, name in [(0, "start.wav"), (3, "loop.wav"), (4, "end.wav")]:
    sound_payload = base64.b64encode(bytes([0x80 + file_id, 0x81 + file_id])).decode("ascii")
    sound_rows.append(f"""  <SoundFile_Table>
    <File_ID>{file_id}</File_ID>
    <File_Name>{name}</File_Name>
    <File_Length>2</File_Length>
    <File_Data>{sound_payload}</File_Data>
  </SoundFile_Table>""")
  return f"""<?xml version="1.0" standalone="yes"?>
<NewDataSet>
  <Project_Base_Info>
    <Decoder_Moudle>{decoder_module}</Decoder_Moudle>
    <Flash_Size>33554432</Flash_Size>
    <SoftWare_Version>25</SoftWare_Version>
    <Engine_Type>0</Engine_Type>
    <Random_Interval>4</Random_Interval>
    <Sound_Config>254</Sound_Config>
    <Sound_Name>Loop</Sound_Name>
    <Sound_Mac_ID>151587054</Sound_Mac_ID>
    <Model_ID>0</Model_ID>
    <Decoder_Name>动芯领域</Decoder_Name>
  </Project_Base_Info>
{chr(10).join(rows)}
{chr(10).join(sound_rows)}
</NewDataSet>
""".encode("utf-8")


class SoundEditorDomainTest(unittest.TestCase):
  def test_parse_dxsd_summary_preserves_graph_and_audio_metadata(self):
    summary = parse_dxsd_summary(minimal_dxsd_xml(), "sample.dxsd")

    self.assertEqual(summary["file_name"], "sample.dxsd")
    self.assertEqual(summary["base_info"]["decoder_module"], "8004")
    self.assertEqual(summary["counts"]["slots"], 1)
    self.assertEqual(summary["counts"]["nodes"], 2)
    self.assertEqual(summary["counts"]["connectors"], 1)
    self.assertEqual(summary["counts"]["judgments"], 1)
    self.assertEqual(summary["counts"]["actions"], 1)
    self.assertEqual(summary["counts"]["sound_files"], 1)
    self.assertEqual(summary["slots"][0]["slot_name"], "1 劈相机")
    self.assertEqual(summary["nodes"][1]["node_key"], "1:1")
    self.assertEqual(summary["connectors"][0]["source_node_key"], "1:0")
    self.assertEqual(summary["connectors"][0]["target_node_key"], "1:1")
    self.assertEqual(summary["connectors"][0]["judgment_count"], 1)
    self.assertEqual(summary["sound_files"][0]["content_base64"], base64.b64encode(b"\x00\x00\x01\x00\x02\x00\x03\x00").decode("ascii"))
    self.assertEqual(summary["sound_files"][0]["content_encoding"], "pcm")
    self.assertEqual(summary["sound_files"][0]["preview_format"], {"sample_rate_hz": 44100, "bits": 16, "channels": 1})
    self.assertEqual(summary["sound_files"][0]["pcm_bytes"], 8)
    self.assertGreater(summary["sound_files"][0]["duration_seconds"], 0)
    self.assertEqual(summary["function_mappings"][0]["function_key"], "F1")

  def test_parse_sound_project_summary_rejects_zip_package(self):
    with self.assertRaises(ValueError) as context:
      parse_sound_project_summary(b"PK\x03\x04zip payload", "6005_Test_V37.zip")

    self.assertIn("ZIP", str(context.exception))
    self.assertIn(".dxsd", str(context.exception))

  def test_parse_sound_project_summary_rejects_non_project_extension(self):
    with self.assertRaises(ValueError) as context:
      parse_sound_project_summary(minimal_dxsd_xml(), "sound.xml")

    self.assertIn(".dxsp", str(context.exception))

  def test_parse_dxsd_summary_accepts_f0_and_ignores_unassigned_or_invalid_slot_function_values(self):
    xml = minimal_dxsd_xml().replace(
      b"  <Node_Table>",
      """  <Slot_Table>
    <Slot_ID>2</Slot_ID>
    <Slot_Priority>2</Slot_Priority>
    <Slot_StartNode>0</Slot_StartNode>
    <Is_Use>false</Is_Use>
    <Start_Address>200</Start_Address>
    <Slot_Name>F0 Slot</Slot_Name>
  </Slot_Table>
  <Node_Table>""".encode("utf-8"),
    ).replace(
      b"  <Random_CV_Table>\n    <CV_Address>113</CV_Address>",
      """  <Random_CV_Table>
    <CV_Address>172</CV_Address>
    <CV_Value>0</CV_Value>
    <CV_Description>Slot2响应功能</CV_Description>
  </Random_CV_Table>
  <Random_CV_Table>
    <CV_Address>173</CV_Address>
    <CV_Value>255</CV_Value>
    <CV_Description>Slot3响应功能</CV_Description>
  </Random_CV_Table>
  <Random_CV_Table>
    <CV_Address>174</CV_Address>
    <CV_Value>69</CV_Value>
    <CV_Description>Slot4响应功能</CV_Description>
  </Random_CV_Table>
  <Random_CV_Table>
    <CV_Address>113</CV_Address>""".encode("utf-8"),
    )

    summary = parse_dxsd_summary(xml, "mapping.dxsd")

    self.assertEqual([entry["function_key"] for entry in summary["function_mappings"]], ["F1", "F0"])
    self.assertTrue(summary["function_mappings"][0]["is_assigned"])

  def test_parse_dxsd_summary_limits_default_slot_cv_mappings_to_existing_slots(self):
    summary = parse_dxsd_summary(six_series_dxsd_with_default_slot_cv_xml(), "6008.dxsd")

    self.assertEqual(summary["base_info"]["decoder_module"], "6008")
    self.assertEqual(summary["counts"]["slots"], 16)
    self.assertEqual(summary["counts"]["cv_entries"], 64)
    self.assertEqual([entry["slot_id"] for entry in summary["function_mappings"]], list(range(1, 17)))
    self.assertEqual(summary["function_mappings"][0]["function_key"], "F1")
    self.assertEqual(summary["function_mappings"][-1]["function_key"], "F16")

  def test_parse_dxsp_summary_maps_5313_and_5323_legacy_user_sounds_without_fake_nodes(self):
    for decoder_module in ["5313", "5323"]:
      with self.subTest(decoder_module=decoder_module):
        summary = parse_sound_project_summary(minimal_dxsp_xml(decoder_module), f"legacy-{decoder_module}.dxsp")

        self.assertEqual(summary["file_name"], f"legacy-{decoder_module}.dxsp")
        self.assertEqual(summary["project_format"], "dxsp_legacy")
        self.assertEqual(summary["base_info"]["decoder_module"], decoder_module)
        self.assertEqual(summary["base_info"]["flash_size"], 33554432)
        self.assertEqual(summary["counts"]["slots"], 28)
        self.assertEqual(summary["counts"]["nodes"], 0)
        self.assertEqual(summary["slots"][0]["legacy_file_ids"], [0])
        self.assertEqual(summary["slots"][0]["legacy_user_files"], [0, None, None])
        self.assertEqual(summary["slots"][0]["legacy_user_type"], 1)
        self.assertEqual(summary["function_mappings"][0]["function_key"], "F1")
        self.assertEqual(summary["function_mappings"][-1]["function_key"], "F28")

  def test_parse_dxsp_summary_preserves_legacy_loop_sound_segments(self):
    summary = parse_sound_project_summary(dxsp_loop_xml(), "legacy-loop.dxsp")

    loop_slot = summary["slots"][3]
    self.assertEqual(loop_slot["slot_name"], "循环风机")
    self.assertEqual(loop_slot["legacy_user_type"], 2)
    self.assertEqual(loop_slot["legacy_user_volume"], 180)
    self.assertEqual(loop_slot["legacy_user_files"], [0, 3, 4])
    self.assertEqual(loop_slot["legacy_file_ids"], [0, 3, 4])
    self.assertEqual(summary["counts"]["nodes"], 0)
    self.assertEqual({entry["file_id"] for entry in summary["sound_files"]}, {0, 3, 4})

  def test_parse_dxsd_summary_rejects_dtd_and_entity_declarations(self):
    xml = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "x">]><NewDataSet />'

    with self.assertRaises(ValueError) as context:
      parse_dxsd_summary(xml, "unsafe.dxsd")

    self.assertIn("DOCTYPE", str(context.exception))

  def test_sound_chip_profiles_mark_unverified_storage_capacity(self):
    profiles = sound_chip_profiles()
    profile_ids = {profile["chip_id"] for profile in profiles}

    self.assertIn("digsight_5313", profile_ids)
    self.assertIn("digsight_8004", profile_ids)
    for profile in profiles:
      self.assertIn("evidence_status", profile)
      if profile["storage_bytes"] is None:
        self.assertEqual(profile["evidence_status"], "needs_storage_capacity_confirmation")

  def test_sound_chip_profiles_include_60_80_capacity_and_fixed_slots(self):
    profiles = {profile["chip_id"]: profile for profile in sound_chip_profiles()}

    for chip_id in ["digsight_5313", "digsight_5323"]:
      with self.subTest(chip_id=chip_id):
        profile = profiles[chip_id]
        self.assertIsNone(profile["storage_bytes"])
        self.assertEqual(profile["fixed_slot_count"], 28)
        self.assertIn("28 个 Slot", profile["slot_count_evidence"])

    for chip_id in ["digsight_6003", "digsight_6005", "digsight_6006", "digsight_6008"]:
      with self.subTest(chip_id=chip_id):
        profile = profiles[chip_id]
        self.assertEqual(profile["storage_bits"], 64 * 1024 * 1024)
        self.assertEqual(profile["storage_bytes"], 64 * 1024 * 1024 // 8)
        self.assertEqual(profile["fixed_slot_count"], 16)
        self.assertEqual(profile["storage_unit"], "Mb")
        self.assertEqual(profile["audio_format"], {"sample_rate_hz": 44100, "bits": 12, "channels": 1})
        self.assertIn("16 个可编辑音轨", profile["slot_count_evidence"])

    for chip_id, megabits in {
      "digsight_8003": 256,
      "digsight_8004": 128,
      "digsight_8005": 256,
      "digsight_8006": 256,
      "digsight_8008": 256,
    }.items():
      with self.subTest(chip_id=chip_id):
        profile = profiles[chip_id]
        self.assertEqual(profile["storage_bits"], megabits * 1024 * 1024)
        self.assertEqual(profile["storage_bytes"], megabits * 1024 * 1024 // 8)
        self.assertEqual(profile["fixed_slot_count"], 64)
        self.assertEqual(profile["audio_format"], {"sample_rate_hz": 44100, "bits": 16, "channels": 1})
        self.assertIn("64 个可编辑音轨", profile["slot_count_evidence"])

  def test_sound_library_catalog_contains_required_categories_without_remote_assets(self):
    catalog = sound_library_catalog()
    categories = {entry["category"] for entry in catalog["sounds"]}

    self.assertIn("traction_engine", categories)
    self.assertIn("horn", categories)
    self.assertIn("rail_wheel", categories)
    self.assertIn("radio", categories)
    self.assertIn("station_announcement", categories)
    for entry in catalog["sounds"]:
      self.assertEqual(entry["asset_source"], "metadata_only")
      self.assertFalse(entry["audio_available"])

  def test_build_dxsd_package_outputs_minimal_digsight_project(self):
    sound_payload = base64.b64encode(wav_bytes()).decode("ascii")
    package = build_dxsd_package({
      "chip_id": "digsight_8004",
      "package_name": "测试音效",
      "slots": [
        {
          "slot_id": 1,
          "slot_name": "短风笛",
          "function_key": 2,
          "sound": {
            "file_name": "horn.wav",
            "content_base64": sound_payload,
          },
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertEqual(package["file_name"], "测试音效.dxsd")
    self.assertIn("<Base_Info>", xml)
    self.assertIn("<Decoder_Moudle>8004</Decoder_Moudle>", xml)
    self.assertIn("<Slot_Name>短风笛</Slot_Name>", xml)
    self.assertIn("<Node_Table>", xml)
    self.assertIn("<Connector_Table>", xml)
    self.assertIn("<SoundFile_Table>", xml)
    self.assertIn("<File_Length>4</File_Length>", xml)
    self.assertIn("<CV_Address>171</CV_Address>", xml)
    self.assertIn("<CV_Value>2</CV_Value>", xml)
    self.assertEqual(package["warnings"], [])

  def test_build_dxsd_package_preserves_connector_judgments_and_actions(self):
    sound_payload = base64.b64encode(wav_bytes()).decode("ascii")
    package = build_dxsd_package({
      "chip_id": "digsight_8004",
      "package_name": "连接判断",
      "slots": [
        {
          "slot_id": 1,
          "slot_name": "短风笛",
          "function_key": 2,
          "nodes": [
            {"node_id": 0, "node_name": "入口", "file_id": 0, "x": 40, "y": 60},
            {"node_id": 1, "node_name": "播放", "file_id": 6, "x": 180, "y": 60},
          ],
          "connectors": [
            {"connector_id": 7, "source_node_id": 0, "target_node_id": 1, "source_port_index": 2},
          ],
          "judgments": [
            {"judgment_id": 8, "connector_id": 7, "register_type": 8, "operation_type": 128, "parameter_value": 65535},
          ],
          "actions": [
            {"action_id": 9, "connector_id": 7, "register_type": 30, "operation_config": 128, "parameter_value": 1},
          ],
          "sound_files": [
            {"file_id": 6, "file_name": "horn.wav", "content_base64": sound_payload},
          ],
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertIn("<Judgment_Table>", xml)
    self.assertIn("<Judgment_ID>8</Judgment_ID>", xml)
    self.assertIn("<Register_Type>8</Register_Type>", xml)
    self.assertIn("<Operation_Type>128</Operation_Type>", xml)
    self.assertIn("<Parameter_Value>65535</Parameter_Value>", xml)
    self.assertIn("<Action_Table>", xml)
    self.assertIn("<Action_ID>9</Action_ID>", xml)
    self.assertIn("<Operation_Config>128</Operation_Config>", xml)
    self.assertEqual(package["warnings"], [])

  def test_build_dxsp_package_for_5313_uses_legacy_project_suffix_and_tables(self):
    sound_payload = base64.b64encode(wav_bytes(sample_rate=11025, bits=8, data=b"\x00\x01")).decode("ascii")
    package = build_dxsd_package({
      "chip_id": "digsight_5313",
      "package_name": "5313音效",
      "slots": [
        {
          "slot_id": 1,
          "slot_name": "短风笛",
          "function_key": 2,
          "sound": {
            "file_name": "horn.wav",
            "content_base64": sound_payload,
          },
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertEqual(package["file_name"], "5313音效.dxsp")
    self.assertIn("<Project_Base_Info>", xml)
    self.assertIn("<Decoder_Moudle>5313</Decoder_Moudle>", xml)
    self.assertIn("<User_Sound_Table>", xml)
    self.assertIn("<User_Function_Name>短风笛</User_Function_Name>", xml)
    self.assertIn("<File_0>0</File_0>", xml)
    self.assertIn("<SoundFile_Table>", xml)
    self.assertIn("<File_ID>0</File_ID>", xml)
    self.assertNotIn("<Base_Info>", xml)
    self.assertNotIn("<Slot_Table>", xml)
    self.assertIn("sound_capacity_unconfirmed", {warning["type"] for warning in package["warnings"]})

  def test_build_dxsp_package_preserves_imported_pcm_sound_files(self):
    pcm_payload = base64.b64encode(b"\x00\x01\x02").decode("ascii")
    package = build_dxsd_package({
      "chip_id": "digsight_5323",
      "package_name": "5323导入音效",
      "slots": [
        {
          "slot_id": 1,
          "slot_name": "启动音",
          "function_key": 1,
          "sound_files": [
            {
              "file_id": 0,
              "file_name": "SwitchAOn.wav",
              "content_base64": pcm_payload,
              "content_encoding": "pcm",
            },
          ],
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertEqual(package["file_name"], "5323导入音效.dxsp")
    self.assertIn("<Decoder_Moudle>5323</Decoder_Moudle>", xml)
    self.assertIn("<File_0>0</File_0>", xml)
    self.assertIn("<File_ID>0</File_ID>", xml)
    self.assertIn("<File_Length>3</File_Length>", xml)
    self.assertIn(f"<File_Data>{pcm_payload}</File_Data>", xml)
    self.assertNotIn("metadata_only_sound", {warning["type"] for warning in package["warnings"]})

  def test_build_dxsp_package_preserves_legacy_loop_type_and_three_sound_files(self):
    start_payload = base64.b64encode(b"\x80\x81").decode("ascii")
    loop_payload = base64.b64encode(b"\x82\x83").decode("ascii")
    end_payload = base64.b64encode(b"\x84\x85").decode("ascii")
    package = build_dxsd_package({
      "chip_id": "digsight_5323",
      "package_name": "5323循环音效",
      "slots": [
        {
          "slot_id": 4,
          "slot_name": "循环风机",
          "legacy_user_type": 2,
          "legacy_user_volume": 180,
          "legacy_user_files": [0, 3, 4],
          "sound_files": [
            {"file_id": 0, "file_name": "start.wav", "content_base64": start_payload, "content_encoding": "pcm"},
            {"file_id": 3, "file_name": "loop.wav", "content_base64": loop_payload, "content_encoding": "pcm"},
            {"file_id": 4, "file_name": "end.wav", "content_base64": end_payload, "content_encoding": "pcm"},
          ],
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertEqual(package["file_name"], "5323循环音效.dxsp")
    self.assertIn("<User_Function_Name>循环风机</User_Function_Name>", xml)
    self.assertIn("<User_Type>2</User_Type>", xml)
    self.assertIn("<User_Volume>180</User_Volume>", xml)
    self.assertIn("<File_0>0</File_0>", xml)
    self.assertIn("<File_1>3</File_1>", xml)
    self.assertIn("<File_2>4</File_2>", xml)
    self.assertIn("<File_ID>0</File_ID>", xml)
    self.assertIn("<File_ID>3</File_ID>", xml)
    self.assertIn("<File_ID>4</File_ID>", xml)
    self.assertNotIn("dxsp_missing_sound_file_payload", {warning["type"] for warning in package["warnings"]})

  def test_build_dxsd_package_preserves_edited_graph_payload(self):
    sound_payload = base64.b64encode(wav_bytes()).decode("ascii")

    package = build_dxsd_package({
      "chip_id": "digsight_8004",
      "package_name": "节点编辑",
      "slots": [
        {
          "slot_id": 3,
          "slot_name": "自定义流程",
          "function_key": 9,
          "nodes": [
            {"node_id": 0, "node_name": "入口", "node_type": 1, "file_id": 0, "x": 40, "y": 80, "width": 96, "height": 64},
            {"node_id": 1, "node_name": "播放 A", "node_type": 1, "file_id": 21, "x": 220, "y": 80, "width": 120, "height": 70, "sound_volume": 180, "repeat_amount": 2},
            {"node_id": 2, "node_name": "播放 B", "node_type": 1, "file_id": 0, "x": 420, "y": 120, "width": 120, "height": 70},
          ],
          "connectors": [
            {"connector_id": 31, "source_node_id": 0, "target_node_id": 1, "source_port_index": 1, "connector_type": 0},
            {"connector_id": 32, "source_node_id": 1, "target_node_id": 2, "source_port_index": 1, "connector_type": 0},
          ],
          "sound_files": [
            {"file_id": 21, "file_name": "custom.wav", "content_base64": sound_payload},
          ],
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertIn("<Slot_ID>3</Slot_ID>", xml)
    self.assertIn("<CV_Address>173</CV_Address>", xml)
    self.assertIn("<CV_Value>9</CV_Value>", xml)
    self.assertIn("<Node_ID>2</Node_ID>", xml)
    self.assertIn("<Node_Name>播放 B</Node_Name>", xml)
    self.assertIn("<Sound_Volume>180</Sound_Volume>", xml)
    self.assertIn("<Repeat_Amount>2</Repeat_Amount>", xml)
    self.assertIn("<Node_X>420</Node_X>", xml)
    self.assertIn("<Connector_ID>32</Connector_ID>", xml)
    self.assertIn("<OUT_Node_ID>2</OUT_Node_ID>", xml)
    self.assertIn("<File_ID>21</File_ID>", xml)
    self.assertIn("<File_Name>custom.wav</File_Name>", xml)
    self.assertEqual(package["warnings"], [])

  def test_build_dxsd_package_round_trips_minimal_graph_structure(self):
    sound_payload = base64.b64encode(wav_bytes()).decode("ascii")

    package = build_dxsd_package({
      "chip_id": "digsight_8004",
      "package_name": "往返验证",
      "slots": [
        {
          "slot_id": 4,
          "slot_name": "自定义鸣笛",
          "function_key": 0,
          "nodes": [
            {"node_id": 0, "node_name": "入口", "node_type": 1, "file_id": 0, "x": 40, "y": 80, "width": 96, "height": 64},
            {"node_id": 1, "node_name": "播放鸣笛", "node_type": 1, "file_id": 12, "x": 220, "y": 80, "width": 120, "height": 70, "sound_volume": 180, "repeat_amount": 2},
          ],
          "connectors": [
            {"connector_id": 33, "source_node_id": 0, "target_node_id": 1, "source_port_index": 1, "connector_type": 0},
          ],
          "sound_files": [
            {"file_id": 12, "file_name": "horn.wav", "content_base64": sound_payload},
          ],
        },
      ],
    })
    generated = base64.b64decode(package["content_base64"])
    summary = parse_dxsd_summary(generated, package["file_name"])

    self.assertEqual(summary["base_info"]["decoder_module"], "8004")
    self.assertEqual(summary["base_info"]["sound_name"], "往返验证")
    self.assertEqual(summary["slots"][0]["slot_id"], 4)
    self.assertEqual(summary["slots"][0]["slot_name"], "自定义鸣笛")
    self.assertEqual(summary["function_mappings"][0]["function_number"], 0)
    self.assertEqual(summary["nodes"][1]["node_name"], "播放鸣笛")
    self.assertEqual(summary["nodes"][1]["file_id"], 12)
    self.assertEqual(summary["connectors"][0]["source_node_key"], "4:0")
    self.assertEqual(summary["connectors"][0]["target_node_key"], "4:1")
    self.assertEqual(summary["sound_files"][0]["file_id"], 12)
    self.assertEqual(summary["sound_files"][0]["file_name"], "horn.wav")
    self.assertEqual(summary["sound_files"][0]["pcm_bytes"], 4)

  def test_build_dxsd_package_keeps_unused_fixed_slots_without_placeholder_audio(self):
    package = build_dxsd_package({
      "chip_id": "digsight_8004",
      "package_name": "固定 Slot",
      "slots": [
        {
          "slot_id": 8,
          "slot_name": "Slot 8",
          "function_key": 8,
          "is_use": False,
          "sound": {},
          "nodes": [],
          "connectors": [],
          "sound_files": [],
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertIn("<Slot_ID>8</Slot_ID>", xml)
    self.assertIn("<Is_Use>false</Is_Use>", xml)
    self.assertNotIn("<Node_Table>", xml)
    self.assertNotIn("<Connector_Table>", xml)
    self.assertNotIn("<SoundFile_Table>", xml)
    self.assertEqual(package["warnings"], [])

  def test_build_dxsd_package_uses_cv_zero_for_f0_and_255_for_unmapped_slots(self):
    package = build_dxsd_package({
      "chip_id": "digsight_8004",
      "package_name": "F0 和未映射 Slot",
      "slots": [
        {
          "slot_id": 5,
          "slot_name": "F0 Slot",
          "function_key": 0,
        },
        {
          "slot_id": 6,
          "slot_name": "未映射",
          "function_key": None,
        },
      ],
    })
    xml = base64.b64decode(package["content_base64"]).decode("utf-8")

    self.assertIn("<CV_Address>175</CV_Address>", xml)
    self.assertIn("<CV_Value>0</CV_Value>", xml)
    self.assertIn("<CV_Address>176</CV_Address>", xml)
    self.assertIn("<CV_Value>255</CV_Value>", xml)

  def test_build_dxsd_package_rejects_wrong_wav_format_for_chip(self):
    sound_payload = base64.b64encode(wav_bytes(sample_rate=22050)).decode("ascii")

    with self.assertRaises(ValueError) as context:
      build_dxsd_package({
        "chip_id": "digsight_8004",
        "package_name": "错误格式",
        "slots": [{
          "slot_id": 1,
          "slot_name": "短风笛",
          "function_key": 2,
          "sound": {
            "file_name": "horn.wav",
            "content_base64": sound_payload,
          },
        }],
      })

    self.assertIn("44100Hz / 16bit / 1声道", str(context.exception))

  def test_build_dxsd_package_rejects_wrong_bit_depth_for_chip(self):
    sound_payload = base64.b64encode(wav_bytes(bits=8, data=b"\x00\x01")).decode("ascii")

    with self.assertRaises(ValueError) as context:
      build_dxsd_package({
        "chip_id": "digsight_8004",
        "package_name": "错误位深",
        "slots": [{
          "slot_id": 1,
          "slot_name": "短风笛",
          "function_key": 2,
          "sound": {
            "file_name": "horn.wav",
            "content_base64": sound_payload,
          },
        }],
      })

    self.assertIn("44100Hz / 16bit / 1声道", str(context.exception))

  def test_build_dxsd_package_rejects_16bit_wav_for_60_series_12bit_profile(self):
    sound_payload = base64.b64encode(wav_bytes()).decode("ascii")

    with self.assertRaises(ValueError) as context:
      build_dxsd_package({
        "chip_id": "digsight_6008",
        "package_name": "错误位深",
        "slots": [{
          "slot_id": 1,
          "slot_name": "短风笛",
          "function_key": 2,
          "sound": {
            "file_name": "horn.wav",
            "content_base64": sound_payload,
          },
        }],
      })

    self.assertIn("44100Hz / 12bit / 1声道", str(context.exception))

  def test_build_dxsd_package_accepts_12bit_wav_for_60_series_profile(self):
    sound_payload = base64.b64encode(wav_bytes(bits=12, data=b"\x00\x01")).decode("ascii")

    package = build_dxsd_package({
      "chip_id": "digsight_6008",
      "package_name": "6008音效",
      "slots": [{
        "slot_id": 1,
        "slot_name": "短风笛",
        "function_key": 2,
        "sound": {
          "file_name": "horn.wav",
          "content_base64": sound_payload,
        },
      }],
    })

    self.assertEqual(package["file_name"], "6008音效.dxsd")
    self.assertEqual(package["warnings"], [])

  def test_build_dxsd_package_warns_when_capacity_is_unknown(self):
    sound_payload = base64.b64encode(wav_bytes(sample_rate=11025, bits=8, data=b"\x00\x01")).decode("ascii")

    package = build_dxsd_package({
      "chip_id": "digsight_5313",
      "package_name": "未知容量",
      "slots": [{
        "slot_id": 1,
        "slot_name": "短风笛",
        "function_key": 2,
        "sound": {
          "file_name": "horn.wav",
          "content_base64": sound_payload,
        },
      }],
    })

    self.assertIn("sound_capacity_unconfirmed", {warning["type"] for warning in package["warnings"]})

  def test_build_dxsd_package_rejects_known_capacity_overflow(self):
    profile = next(profile for profile in sound_editor_module._CHIP_PROFILES if profile["chip_id"] == "digsight_8004")
    original_storage = profile["storage_bytes"]
    profile["storage_bytes"] = 1
    try:
      sound_payload = base64.b64encode(wav_bytes()).decode("ascii")
      with self.assertRaises(ValueError) as context:
        build_dxsd_package({
          "chip_id": "digsight_8004",
          "package_name": "超容量",
          "slots": [{
            "slot_id": 1,
            "slot_name": "短风笛",
            "function_key": 2,
            "sound": {
              "file_name": "horn.wav",
              "content_base64": sound_payload,
            },
          }],
        })
    finally:
      profile["storage_bytes"] = original_storage

    self.assertIn("超过芯片容量", str(context.exception))

  def test_build_dxsd_package_allows_metadata_only_sounds_with_warning(self):
    package = build_dxsd_package({
      "chip_id": "digsight_5313",
      "package_name": "占位音效",
      "slots": [
        {
          "slot_id": 1,
          "slot_name": "主电机",
          "function_key": 1,
          "sound": {
            "library_id": "electric-main-motor-loop",
            "file_name": "主电机.wav",
          },
        },
      ],
    })

    self.assertTrue(package["warnings"])
    self.assertIn("metadata_only_sound", package["warnings"][0]["type"])


class SoundEditorApiTest(unittest.TestCase):
  def test_sound_editor_routes_are_registered(self):
    self.assertEqual(handler_for("GET", "/api/sound/chips"), "sound.chips")
    self.assertEqual(handler_for("GET", "/api/sound/library"), "sound.library")
    self.assertEqual(handler_for("POST", "/api/sound/library/sounds"), "sound.library_sound")
    self.assertEqual(handler_for("POST", "/api/sound/library/slots"), "sound.library_slot")
    self.assertEqual(handler_for("POST", "/api/sound/dxsd/import"), "sound.dxsd_import")
    self.assertEqual(handler_for("POST", "/api/sound/package"), "sound.package")
    self.assertFalse(mutation_route_spec("POST", "/api/sound/dxsd/import")["json_body"])
    self.assertGreaterEqual(mutation_route_spec("POST", "/api/sound/dxsd/import")["body_limit"], 64 * 1024 * 1024)
    self.assertGreaterEqual(mutation_route_spec("POST", "/api/sound/library/sounds")["body_limit"], 64 * 1024 * 1024)

  def test_router_returns_sound_chip_profiles(self):
    body, status = ApiRouter(None).handle_json("GET", "/api/sound/chips", b"", default_state())
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertIn("digsight_5313", {profile["chip_id"] for profile in payload["data"]})

  def test_router_returns_sound_library_catalog(self):
    body, status = ApiRouter(None).handle_json("GET", "/api/sound/library", b"", default_state())
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertIn("sounds", payload["data"])
    self.assertIn("saved_sounds", payload["data"])
    self.assertIn("slot_library", payload["data"])
    self.assertIn("horn", {entry["category"] for entry in payload["data"]["sounds"]})

  def test_sound_library_store_persists_saved_sounds_and_slots(self):
    with tempfile.TemporaryDirectory() as temp_dir:
      store_path = Path(temp_dir) / "sound-library.json"

      saved_sound = save_user_sound_library_sound({
        "sound_id": "saved-sound-horn",
        "label": "保存风笛",
        "category": "horn",
        "fileName": "horn.wav",
        "contentBase64": "AAAA",
        "audio_available": True,
      }, store_path)
      saved_slot = save_user_sound_library_slot({
        "slot_library_id": "slot-template-horn",
        "label": "短风笛 Slot",
        "category": "horn",
        "nodes": [{"slot_id": 1, "node_id": 1, "file_id": 10}],
        "connectors": [{"slot_id": 1, "connector_id": 2, "source_node_id": 1, "target_node_id": 3}],
      }, store_path)

      loaded = load_user_sound_library(store_path)
      catalog = sound_library_catalog(loaded)

      self.assertEqual(saved_sound["sound_id"], "saved-sound-horn")
      self.assertEqual(saved_slot["slot_library_id"], "slot-template-horn")
      self.assertEqual(loaded["saved_sounds"][0]["content_base64"], "AAAA")
      self.assertEqual(loaded["slot_library"]["slots"][0]["nodes"][0]["node_id"], 1)
      self.assertEqual(catalog["saved_sounds"][0]["fileName"], "horn.wav")
      self.assertEqual(catalog["slot_library"]["slots"][0]["connectors"][0]["connector_id"], 2)

  def test_sound_library_api_saves_sound_with_default_category(self):
    api = SoundEditorApiSupport()
    captured = {}

    def fake_save(sound):
      captured.update(sound)
      return {"sound_id": "saved-sound", **sound}

    with patch("server.api_support.sound_editor.save_user_sound_library_sound", fake_save):
      body, status = api.save_library_sound(json.dumps({
        "sound": {
          "label": "短风笛",
          "fileName": "horn.wav",
          "contentBase64": "AAAA",
        }
      }).encode("utf-8"))
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(captured["category"], "custom")
    self.assertEqual(payload["data"]["fileName"], "horn.wav")

  def test_sound_library_api_saves_slot_with_request_category(self):
    api = SoundEditorApiSupport()
    captured = {}

    def fake_save(slot):
      captured.update(slot)
      return {"slot_library_id": "slot-template", **slot}

    with patch("server.api_support.sound_editor.save_user_sound_library_slot", fake_save):
      body, status = api.save_library_slot(json.dumps({
        "category": "horn",
        "slot": {
          "label": "短风笛 Slot",
          "nodes": [{"slot_id": 1, "node_id": 1}],
          "connectors": [],
        }
      }).encode("utf-8"))
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(captured["category"], "horn")
    self.assertEqual(payload["data"]["slot_library_id"], "slot-template")

  def test_router_imports_dxsd_bytes(self):
    body, status = ApiRouter(None).handle_json(
      "POST",
      "/api/sound/dxsd/import",
      minimal_dxsd_xml(),
      default_state(),
    )
    payload = json.loads(body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["data"]["base_info"]["decoder_module"], "8004")

  def test_gateway_handler_imports_dxsp_bytes_with_uploaded_file_name(self):
    handler = DigsightHandler.__new__(DigsightHandler)
    handler.headers = {"X-File-Name": "legacy-5313.dxsp"}
    captured = {}
    handler._send_json = lambda status, body: captured.update({"status": status, "body": body})

    handler._handle_sound_project_import_mutation(minimal_dxsp_xml("5313"))
    payload = json.loads(captured["body"].decode("utf-8"))

    self.assertEqual(captured["status"], 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["data"]["file_name"], "legacy-5313.dxsp")
    self.assertEqual(payload["data"]["project_format"], "dxsp_legacy")

  def test_router_builds_sound_package(self):
    body = json.dumps({
      "chip_id": "digsight_8004",
      "package_name": "测试音效",
      "slots": [],
    }).encode("utf-8")

    response_body, status = ApiRouter(None).handle_json("POST", "/api/sound/package", body, default_state())
    payload = json.loads(response_body.decode("utf-8"))

    self.assertEqual(status, 200)
    self.assertTrue(payload["ok"])
    self.assertEqual(payload["data"]["mime_type"], "application/xml")


if __name__ == "__main__":
  unittest.main()

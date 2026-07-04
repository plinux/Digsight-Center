import base64
import json
import struct
import unittest

from server.api import ApiRouter
from server.app_state import default_state
from server.api_support.routes import handler_for, mutation_route_spec
from server.sound_editor import (
  build_dxsd_package,
  parse_dxsd_summary,
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
    self.assertEqual(summary["sound_files"][0]["pcm_bytes"], 8)
    self.assertGreater(summary["sound_files"][0]["duration_seconds"], 0)
    self.assertEqual(summary["function_mappings"][0]["function_key"], "F1")

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
        self.assertEqual(profile["evidence_status"], "needs_official_or_real_device_confirmation")

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
    self.assertEqual(handler_for("POST", "/api/sound/dxsd/import"), "sound.dxsd_import")
    self.assertEqual(handler_for("POST", "/api/sound/package"), "sound.package")
    self.assertFalse(mutation_route_spec("POST", "/api/sound/dxsd/import")["json_body"])
    self.assertGreaterEqual(mutation_route_spec("POST", "/api/sound/dxsd/import")["body_limit"], 64 * 1024 * 1024)

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
    self.assertIn("horn", {entry["category"] for entry in payload["data"]["sounds"]})

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

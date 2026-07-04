"""Digsight DXSD sound project parsing and package generation."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


DXSD_BODY_LIMIT_BYTES = 64 * 1024 * 1024
DEFAULT_TOTAL_VOLUME = 180
SOUND_PROJECT_MIME_TYPE = "application/xml"


_CHIP_PROFILES = [
  {
    "chip_id": "digsight_5313",
    "label": "动芯 5313 数码音效芯片",
    "decoder_module": "5313",
    "supported_decoder_modules": ["5313"],
    "interfaces": ["NEM652 8Pin", "MTC21 21Pin"],
    "dcc_speed_steps": [14, 28, 128],
    "simultaneous_sound_channels": 4,
    "speaker_impedance_ohm": "4-32",
    "storage_bytes": None,
    "evidence_status": "needs_official_or_real_device_confirmation",
    "audio_format": {"sample_rate_hz": 11025, "bits": 8, "channels": 1},
    "notes": [
      "官网说明支持声音文件刷新、F1-F28 声音控制和 4 声道混音。",
      "公开网页未确认声音存储容量，生成时不得把容量作为已验证限制。",
    ],
  },
  {
    "chip_id": "digsight_5323",
    "label": "动芯 5323 数码音效芯片",
    "decoder_module": "5323",
    "supported_decoder_modules": ["5323"],
    "interfaces": ["NEM652 8Pin", "PluX22"],
    "dcc_speed_steps": [14, 28, 128],
    "simultaneous_sound_channels": 4,
    "speaker_impedance_ohm": "4-32",
    "storage_bytes": None,
    "evidence_status": "needs_official_or_real_device_confirmation",
    "audio_format": {"sample_rate_hz": 11025, "bits": 8, "channels": 1},
    "notes": [
      "系列说明书覆盖 5313/5323，公开资料未给出可验证声音存储容量。",
    ],
  },
  {
    "chip_id": "digsight_8004",
    "label": "动芯 8004 DXSD 音效工程",
    "decoder_module": "8004",
    "supported_decoder_modules": ["8004"],
    "interfaces": ["DXSD sample evidence"],
    "dcc_speed_steps": [14, 28, 128],
    "simultaneous_sound_channels": 4,
    "speaker_impedance_ohm": None,
    "storage_bytes": None,
    "evidence_status": "needs_official_or_real_device_confirmation",
    "audio_format": {"sample_rate_hz": 44100, "bits": 16, "channels": 1},
    "notes": [
      "8004_HW2_SS7C_V37_KF.dxsd 样例显示 Base_Info.Decoder_Moudle=8004。",
      "样例音频为 base64 PCM，按 44.1kHz/16-bit/mono 估算时长。",
    ],
  },
  {
    "chip_id": "digsight_8005",
    "label": "动芯 8005 逑音音效工程",
    "decoder_module": "8005",
    "supported_decoder_modules": ["8005"],
    "interfaces": ["DXSD editor reference"],
    "dcc_speed_steps": [14, 28, 128],
    "simultaneous_sound_channels": 4,
    "speaker_impedance_ohm": None,
    "storage_bytes": None,
    "evidence_status": "needs_official_or_real_device_confirmation",
    "audio_format": {"sample_rate_hz": 44100, "bits": 16, "channels": 1},
    "notes": [
      "参考编辑器页面标题包含 Decoder 8005；公开页面未确认存储容量。",
    ],
  },
]


_SOUND_LIBRARY = [
  ("electric-main-motor-loop", "电力主音效循环", "traction_engine", "电力机车牵引电机持续声", ["电力", "主音效", "循环"]),
  ("diesel-main-engine-idle", "内燃机怠速主音效", "traction_engine", "柴油机怠速与低速运转声", ["内燃", "主音效", "怠速"]),
  ("blower-start-stop", "风机启动/停止", "traction_engine", "电力机车风机启停声", ["风机", "启动", "停止"]),
  ("air-compressor-loop", "空压机循环", "traction_engine", "空压机启动、循环和排气", ["空压机", "循环"]),
  ("short-air-horn", "短风笛", "horn", "短促风笛鸣响", ["喇叭", "短鸣"]),
  ("long-air-horn", "长风笛", "horn", "长风笛鸣响", ["喇叭", "长鸣"]),
  ("electric-whistle-short", "短电笛", "horn", "电力机车短电笛", ["电笛", "短鸣"]),
  ("electric-whistle-long", "长电笛", "horn", "电力机车长电笛", ["电笛", "长鸣"]),
  ("rail-joint-click", "轮轨接缝咔哒声", "rail_wheel", "车头压过轨缝的节奏咔哒声", ["轨缝", "咔哒"]),
  ("turnout-flange-squeal", "过道岔摩擦声", "rail_wheel", "轮缘通过道岔时的摩擦和冲击", ["道岔", "摩擦"]),
  ("curve-squeal", "过弯摩擦声", "rail_wheel", "小半径曲线轮轨尖叫", ["弯道", "摩擦"]),
  ("cab-radio-dispatch", "司机手台调度", "radio", "司机与调度的手台交流声", ["司机", "手台"]),
  ("station-departure-announcement", "车站发车广播", "station_announcement", "车站发车广播提示", ["车站", "广播"]),
  ("arrival-reminder", "车辆到站提醒", "station_announcement", "到站提示音与播报", ["到站", "提醒"]),
  ("door-close-warning", "关门提示", "station_announcement", "关门提示音和蜂鸣", ["车门", "提示"]),
]


def sound_chip_profiles() -> list[dict[str, Any]]:
  return [dict(profile) for profile in _CHIP_PROFILES]


def sound_library_catalog() -> dict[str, Any]:
  categories = [
    {"category": "traction_engine", "label": "主音效", "description": "内燃、电力、电机、风机和空压机等持续或循环声音"},
    {"category": "horn", "label": "鸣笛", "description": "风笛、电笛、长鸣、短鸣和组合鸣笛"},
    {"category": "rail_wheel", "label": "轮轨声", "description": "轨缝、道岔、曲线和轮缘摩擦声"},
    {"category": "radio", "label": "司机手台", "description": "司机、调度、车站值班交流声"},
    {"category": "station_announcement", "label": "广播与提示", "description": "车站广播、到站提醒、关门提示和客室提示音"},
  ]
  sounds = []
  for sound_id, label, category, description, tags in _SOUND_LIBRARY:
    sounds.append({
      "sound_id": sound_id,
      "label": label,
      "category": category,
      "description": description,
      "tags": tags,
      "audio_available": False,
      "asset_source": "metadata_only",
      "license": "pending_user_or_project_asset",
    })
  return {"categories": categories, "sounds": sounds}


def parse_dxsd_summary(xml_bytes: bytes, file_name: str = "sound.dxsd") -> dict[str, Any]:
  if len(xml_bytes) > DXSD_BODY_LIMIT_BYTES:
    raise ValueError(f"DXSD 文件超过 {DXSD_BODY_LIMIT_BYTES} 字节限制")
  _reject_unsafe_xml(xml_bytes)
  records = _stream_dxsd_records(xml_bytes)
  base_info = _normalize_base_info(_first(records, "Base_Info"))
  slots = [_normalize_slot(row) for row in records.get("Slot_Table", [])]
  nodes = [_normalize_node(row) for row in records.get("Node_Table", [])]
  judgments = [_normalize_judgment(row) for row in records.get("Judgment_Table", [])]
  actions = [_normalize_action(row) for row in records.get("Action_Table", [])]
  judgment_counts = _counts_by(judgments, "connector_id")
  action_counts = _counts_by(actions, "connector_id")
  connectors = [
    _normalize_connector(row, judgment_counts=judgment_counts, action_counts=action_counts)
    for row in records.get("Connector_Table", [])
  ]
  sound_files = [
    _normalize_sound_file(row, base_info.get("decoder_module", ""))
    for row in records.get("SoundFile_Table", [])
  ]
  cv_entries = [_normalize_cv(row) for row in records.get("Random_CV_Table", [])]
  function_mappings = _function_mappings(cv_entries, {slot["slot_id"]: slot for slot in slots})
  return {
    "file_name": Path(file_name or "sound.dxsd").name,
    "base_info": base_info,
    "counts": {
      "slots": len(slots),
      "nodes": len(nodes),
      "connectors": len(connectors),
      "paths": len(records.get("Connector_PathTable", [])),
      "judgments": len(judgments),
      "actions": len(actions),
      "sound_files": len(sound_files),
      "cv_entries": len(cv_entries),
    },
    "slots": slots,
    "nodes": nodes,
    "connectors": connectors,
    "judgments": judgments,
    "actions": actions,
    "sound_files": sound_files,
    "function_mappings": function_mappings,
  }


def build_dxsd_package(project: dict[str, Any]) -> dict[str, Any]:
  if not isinstance(project, dict):
    raise ValueError("sound package request must be a JSON object")
  chip = _chip_profile(str(project.get("chip_id") or "digsight_8004"))
  package_name = _safe_package_name(project.get("package_name") or "digsight-sound")
  slots = project.get("slots") or []
  if not isinstance(slots, list):
    raise ValueError("slots must be a JSON array")
  warnings = []
  xml = _build_package_xml(chip, package_name, slots, warnings)
  content = xml.encode("utf-8")
  return {
    "file_name": f"{package_name}.dxsd",
    "mime_type": SOUND_PROJECT_MIME_TYPE,
    "content_base64": base64.b64encode(content).decode("ascii"),
    "byte_length": len(content),
    "warnings": warnings,
  }


def _reject_unsafe_xml(xml_bytes: bytes) -> None:
  upper_prefix = xml_bytes[:4096].upper()
  if b"<!DOCTYPE" in upper_prefix:
    raise ValueError("DOCTYPE declarations are not allowed in DXSD XML")
  if b"<!ENTITY" in upper_prefix:
    raise ValueError("ENTITY declarations are not allowed in DXSD XML")


def _stream_dxsd_records(xml_bytes: bytes) -> dict[str, list[dict[str, str]]]:
  tables: dict[str, list[dict[str, str]]] = {}
  stack: list[str] = []
  try:
    context = ET.iterparse(BytesIO(xml_bytes), events=("start", "end"))
    for event, element in context:
      if event == "start":
        stack.append(element.tag)
        continue
      if len(stack) == 2:
        tables.setdefault(element.tag, []).append({
          child.tag: (child.text or "").strip()
          for child in list(element)
        })
        element.clear()
      stack.pop()
  except ET.ParseError as exc:
    raise ValueError(f"DXSD XML 解析失败: {exc}") from exc
  return tables


def _first(records: dict[str, list[dict[str, str]]], table_name: str) -> dict[str, str]:
  values = records.get(table_name) or []
  return values[0] if values else {}


def _normalize_base_info(row: dict[str, str]) -> dict[str, Any]:
  return {
    "decoder_module": row.get("Decoder_Moudle", ""),
    "software_version": row.get("SoftWare_Version", ""),
    "dealer_id": row.get("Dealer_ID", ""),
    "engine_type": _int(row.get("Engine_Type")),
    "sound_name": row.get("Sound_Name", ""),
    "sound_mac_id": row.get("Sound_Mac_ID", ""),
    "model_id": _int(row.get("Model_ID")),
    "decoder_name": row.get("Decoder_Name", ""),
  }


def _normalize_slot(row: dict[str, str]) -> dict[str, Any]:
  slot_id = _int(row.get("Slot_ID"))
  return {
    "slot_id": slot_id,
    "slot_priority": _int(row.get("Slot_Priority")),
    "slot_start_node": _int(row.get("Slot_StartNode")),
    "is_use": _bool(row.get("Is_Use")),
    "start_address": _int(row.get("Start_Address")),
    "slot_name": row.get("Slot_Name", ""),
  }


def _normalize_node(row: dict[str, str]) -> dict[str, Any]:
  slot_id = _int(row.get("Slot_ID"))
  node_id = _int(row.get("Node_ID"))
  return {
    "node_key": f"{slot_id}:{node_id}",
    "node_id": node_id,
    "slot_id": slot_id,
    "node_type": _int(row.get("Node_Type")),
    "file_id": _int(row.get("File_ID")),
    "node_config": _int(row.get("Node_Config")),
    "repeat_amount": _int(row.get("Repeat_Amount")),
    "sound_volume": _int(row.get("Sound_Volume")),
    "x": _float(row.get("Node_X")),
    "y": _float(row.get("Node_Y")),
    "width": _float(row.get("Node_W")),
    "height": _float(row.get("Node_H")),
    "node_name": row.get("Node_Name", ""),
    "start_address": _int(row.get("Start_Address")),
  }


def _normalize_connector(
  row: dict[str, str],
  *,
  judgment_counts: dict[int, int],
  action_counts: dict[int, int],
) -> dict[str, Any]:
  connector_id = _int(row.get("Connector_ID"))
  slot_id = _int(row.get("Slot_ID"))
  node_id = _int(row.get("Node_ID"))
  out_node_id = _int(row.get("OUT_Node_ID"))
  return {
    "connector_id": connector_id,
    "connector_type": _int(row.get("Connector_Type")),
    "slot_id": slot_id,
    "source_node_id": node_id,
    "source_node_key": f"{slot_id}:{node_id}",
    "source_port_index": _int(row.get("Node_Index_ID")),
    "target_node_id": out_node_id,
    "target_node_key": f"{slot_id}:{out_node_id}",
    "start_address": _int(row.get("Start_Address")),
    "judgment_count": judgment_counts.get(connector_id, 0),
    "action_count": action_counts.get(connector_id, 0),
  }


def _normalize_judgment(row: dict[str, str]) -> dict[str, Any]:
  return {
    "judgment_id": _int(row.get("Judgment_ID")),
    "connector_id": _int(row.get("Connector_ID")),
    "register_type": _int(row.get("Register_Type")),
    "operation_type": _int(row.get("Operation_Type")),
    "parameter_value": _int(row.get("Parameter_Value")),
  }


def _normalize_action(row: dict[str, str]) -> dict[str, Any]:
  return {
    "action_id": _int(row.get("Action_ID")),
    "connector_id": _int(row.get("Connector_ID")),
    "register_type": _int(row.get("Register_Type")),
    "operation_config": _int(row.get("Operation_Config")),
    "parameter_value": _int(row.get("Parameter_Value")),
  }


def _normalize_sound_file(row: dict[str, str], decoder_module: str) -> dict[str, Any]:
  file_data = row.get("File_Data", "")
  pcm_bytes = _base64_len(file_data)
  duration = _duration_seconds(pcm_bytes, decoder_module)
  return {
    "file_id": _int(row.get("File_ID")),
    "file_name": row.get("File_Name", ""),
    "file_length": _int(row.get("File_Length")),
    "start_address": _int(row.get("Start_Address")),
    "file_flag": _int(row.get("File_Flag")),
    "has_audio_data": bool(file_data),
    "pcm_bytes": pcm_bytes,
    "duration_seconds": duration,
  }


def _normalize_cv(row: dict[str, str]) -> dict[str, Any]:
  return {
    "cv_address": _int(row.get("CV_Address")),
    "cv_value": _int(row.get("CV_Value")),
    "description": row.get("CV_Description", ""),
  }


def _function_mappings(cv_entries: list[dict[str, Any]], slots_by_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
  mappings = []
  for entry in cv_entries:
    cv_address = entry["cv_address"]
    value = entry["cv_value"]
    if 171 <= cv_address <= 234 and value not in {0, 255}:
      slot_id = cv_address - 170
      mappings.append({
        "cv_address": cv_address,
        "slot_id": slot_id,
        "slot_name": slots_by_id.get(slot_id, {}).get("slot_name", ""),
        "function_key": f"F{value}",
        "function_number": value,
      })
  return mappings


def _build_package_xml(chip: dict[str, Any], package_name: str, slots: list[Any], warnings: list[dict[str, str]]) -> str:
  lines = [
    '<?xml version="1.0" encoding="utf-8" standalone="yes"?>',
    "<NewDataSet>",
    "  <Base_Info>",
    f"    <Decoder_Moudle>{_xml(chip['decoder_module'])}</Decoder_Moudle>",
    "    <SoftWare_Version>1</SoftWare_Version>",
    "    <Dealer_ID></Dealer_ID>",
    "    <Engine_Type>1</Engine_Type>",
    f"    <Sound_Name>{_xml(package_name)}</Sound_Name>",
    "    <Sound_Mac_ID>4294967295</Sound_Mac_ID>",
    "    <Model_ID>0</Model_ID>",
    f"    <Decoder_Name>{_xml(chip['decoder_module'])}</Decoder_Name>",
    "  </Base_Info>",
  ]
  sound_file_rows = []
  for index, raw_slot in enumerate(slots, start=1):
    if not isinstance(raw_slot, dict):
      raise ValueError("each slot must be a JSON object")
    slot_id = _bounded_int(raw_slot.get("slot_id"), index, 1, 64)
    function_key = _bounded_int(raw_slot.get("function_key"), slot_id, 0, 68)
    slot_name = str(raw_slot.get("slot_name") or f"Sound slot {slot_id}")
    file_id = index
    sound = raw_slot.get("sound") if isinstance(raw_slot.get("sound"), dict) else {}
    file_name = str(sound.get("file_name") or sound.get("label") or f"sound-{slot_id}.pcm")
    content_base64 = _clean_base64(str(sound.get("content_base64") or ""))
    file_length = _base64_len(content_base64)
    if not content_base64:
      warnings.append({
        "type": "metadata_only_sound",
        "slot_id": str(slot_id),
        "message": f"Slot {slot_id}「{slot_name}」没有实际音频数据，仅生成工程占位。",
      })
    lines.extend(_slot_xml(slot_id, slot_name))
    lines.extend(_node_xml(slot_id, 0, 0, "入口", 40, 60))
    lines.extend(_node_xml(slot_id, 1, file_id, slot_name, 180, 60))
    lines.extend(_connector_xml(slot_id, index, 0, 1))
    sound_file_rows.extend(_sound_file_xml(file_id, file_name, file_length, content_base64))
    lines.extend(_cv_xml(170 + slot_id, function_key, f"Slot{slot_id}响应功能"))
  lines.extend(_cv_xml(113, DEFAULT_TOTAL_VOLUME, "总音量"))
  lines.extend(sound_file_rows)
  lines.append("</NewDataSet>")
  return "\n".join(lines) + "\n"


def _slot_xml(slot_id: int, slot_name: str) -> list[str]:
  return [
    "  <Slot_Table>",
    f"    <Slot_ID>{slot_id}</Slot_ID>",
    f"    <Slot_Priority>{slot_id}</Slot_Priority>",
    "    <Slot_StartNode>0</Slot_StartNode>",
    "    <Is_Use>true</Is_Use>",
    "    <Start_Address>0</Start_Address>",
    f"    <Slot_Name>{_xml(slot_name)}</Slot_Name>",
    "  </Slot_Table>",
  ]


def _node_xml(slot_id: int, node_id: int, file_id: int, name: str, x: int, y: int) -> list[str]:
  return [
    "  <Node_Table>",
    f"    <Node_ID>{node_id}</Node_ID>",
    f"    <Slot_ID>{slot_id}</Slot_ID>",
    "    <Node_Type>1</Node_Type>",
    f"    <File_ID>{file_id}</File_ID>",
    "    <Node_Config>0</Node_Config>",
    "    <Repeat_Amount>1</Repeat_Amount>",
    "    <Sound_Volume>255</Sound_Volume>",
    f"    <Node_X>{x}</Node_X>",
    f"    <Node_Y>{y}</Node_Y>",
    "    <Node_W>96</Node_W>",
    "    <Node_H>64</Node_H>",
    f"    <Node_Name>{_xml(name)}</Node_Name>",
    "    <Start_Address>0</Start_Address>",
    "  </Node_Table>",
  ]


def _connector_xml(slot_id: int, connector_id: int, source_node_id: int, target_node_id: int) -> list[str]:
  return [
    "  <Connector_Table>",
    f"    <Connector_ID>{connector_id}</Connector_ID>",
    "    <Connector_Type>0</Connector_Type>",
    f"    <Node_ID>{source_node_id}</Node_ID>",
    "    <Node_Index_ID>1</Node_Index_ID>",
    f"    <Slot_ID>{slot_id}</Slot_ID>",
    f"    <OUT_Node_ID>{target_node_id}</OUT_Node_ID>",
    "    <Start_Address>0</Start_Address>",
    "  </Connector_Table>",
  ]


def _sound_file_xml(file_id: int, file_name: str, file_length: int, content_base64: str) -> list[str]:
  return [
    "  <SoundFile_Table>",
    f"    <File_ID>{file_id}</File_ID>",
    f"    <File_Name>{_xml(file_name)}</File_Name>",
    f"    <File_Length>{file_length}</File_Length>",
    "    <Start_Address>0</Start_Address>",
    f"    <File_Data>{content_base64}</File_Data>",
    "    <File_Flag>0</File_Flag>",
    "  </SoundFile_Table>",
  ]


def _cv_xml(address: int, value: int, description: str) -> list[str]:
  return [
    "  <Random_CV_Table>",
    f"    <CV_Address>{address}</CV_Address>",
    f"    <CV_Value>{value}</CV_Value>",
    f"    <CV_Description>{_xml(description)}</CV_Description>",
    "  </Random_CV_Table>",
  ]


def _chip_profile(chip_id: str) -> dict[str, Any]:
  for profile in _CHIP_PROFILES:
    if profile["chip_id"] == chip_id:
      return profile
  raise ValueError(f"unsupported sound chip profile: {chip_id}")


def _counts_by(rows: list[dict[str, Any]], field_name: str) -> dict[int, int]:
  counts: dict[int, int] = {}
  for row in rows:
    value = int(row.get(field_name, 0) or 0)
    counts[value] = counts.get(value, 0) + 1
  return counts


def _duration_seconds(pcm_bytes: int, decoder_module: str) -> float:
  fmt = _audio_format(decoder_module)
  bytes_per_second = fmt["sample_rate_hz"] * fmt["channels"] * max(1, fmt["bits"] // 8)
  if not pcm_bytes or not bytes_per_second:
    return 0.0
  return round(pcm_bytes / bytes_per_second, 6)


def _audio_format(decoder_module: str) -> dict[str, int]:
  module = str(decoder_module or "")
  for profile in _CHIP_PROFILES:
    if any(module.startswith(prefix) for prefix in profile["supported_decoder_modules"]):
      return profile["audio_format"]
  return {"sample_rate_hz": 44100, "bits": 16, "channels": 1}


def _base64_len(value: str) -> int:
  if not value:
    return 0
  try:
    return len(base64.b64decode(_clean_base64(value), validate=True))
  except ValueError:
    return 0


def _clean_base64(value: str) -> str:
  if "," in value and value.strip().startswith("data:"):
    return value.split(",", 1)[1].strip()
  return "".join(str(value or "").split())


def _safe_package_name(value: Any) -> str:
  name = str(value or "").strip() or "digsight-sound"
  for char in '/\\:*?"<>|':
    name = name.replace(char, "_")
  return name[:80] or "digsight-sound"


def _xml(value: Any) -> str:
  return escape(str(value or ""), {'"': "&quot;", "'": "&apos;"})


def _int(value: Any, default: int = 0) -> int:
  try:
    return int(float(str(value).strip()))
  except (TypeError, ValueError):
    return default


def _float(value: Any, default: float = 0.0) -> float:
  try:
    return float(str(value).strip())
  except (TypeError, ValueError):
    return default


def _bool(value: Any) -> bool:
  return str(value).strip().lower() == "true"


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
  parsed = _int(value, default)
  return max(minimum, min(maximum, parsed))

"""Digsight DXSD sound project parsing and package generation."""

from __future__ import annotations

import base64
import binascii
import json
from io import BytesIO
from pathlib import Path
from typing import Any
import uuid
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape


SOUND_PROJECT_BODY_LIMIT_BYTES = 64 * 1024 * 1024
SOUND_PROJECT_INPUT_EXTENSIONS = {".dxsd", ".dxsp"}
DEFAULT_TOTAL_VOLUME = 180
SOUND_PROJECT_MIME_TYPE = "application/xml"
LEGACY_DXSP_FLASH_SIZE = 33_554_432
LEGACY_DXSP_USER_SOUND_FILE_FIELDS = 3
UNMAPPED_SLOT_FUNCTION_CV_VALUE = 255
USER_SOUND_LIBRARY_PATH = Path("data/sound-library.json")


def _megabits_to_bits(megabits: int) -> int:
  return megabits * 1024 * 1024


def _megabits_to_bytes(megabits: int) -> int:
  return _megabits_to_bits(megabits) // 8


def _sound_chip_profile_60_80(
  model: str,
  series_label: str,
  interface_name: str,
  storage_megabits: int,
  audio_bits: int,
  fixed_slot_count: int,
  slot_count_evidence: str,
) -> dict[str, Any]:
  return {
    "chip_id": f"digsight_{model}",
    "label": f"动芯 {model} {series_label}",
    "decoder_module": model,
    "supported_decoder_modules": [model],
    "interfaces": [interface_name],
    "dcc_speed_steps": [14, 28, 128],
    "simultaneous_sound_channels": 4,
    "speaker_impedance_ohm": "4-32",
    "storage_bits": _megabits_to_bits(storage_megabits),
    "storage_bytes": _megabits_to_bytes(storage_megabits),
    "storage_unit": "Mb",
    "fixed_slot_count": fixed_slot_count,
    "slot_count_evidence": slot_count_evidence,
    "evidence_status": "official_capacity_confirmed",
    "project_extension": "dxsd",
    "audio_format": {"sample_rate_hz": 44100, "bits": audio_bits, "channels": 1},
    "notes": [
      f"60/80 系列手册确认 {model} 存储空间为 {storage_megabits}Mb。",
      f"{series_label} {model} 按当前厂商答复和产品目录固定为 {fixed_slot_count} 个可编辑 Slot。",
    ],
  }


def _sound_chip_profile_6x(model: str, interface_name: str) -> dict[str, Any]:
  return _sound_chip_profile_60_80(
    model,
    "龟趺Ⅲ",
    interface_name,
    64,
    12,
    16,
    "2026 产品目录图确认电跌/龟趺Ⅲ 6 系列支持 16 个可编辑音轨。",
  )


def _sound_chip_profile_8x(model: str, interface_name: str, storage_megabits: int) -> dict[str, Any]:
  return _sound_chip_profile_60_80(
    model,
    "逑音",
    interface_name,
    storage_megabits,
    16,
    64,
    "2026 产品目录图确认逑音 8 系列支持 64 个可编辑音轨；8004 DXSD 样例也解析出 64 个 Slot。",
  )


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
    "storage_bits": None,
    "storage_bytes": None,
    "storage_unit": "Mb",
    "fixed_slot_count": 28,
    "slot_count_evidence": "2026-07-02 厂商答复确认 5313/5323 固定 28 个 Slot。",
    "evidence_status": "needs_storage_capacity_confirmation",
    "project_extension": "dxsp",
    "legacy_software_version": "22",
    "audio_format": {"sample_rate_hz": 11025, "bits": 8, "channels": 1},
    "notes": [
      "官网说明支持声音文件刷新、F1-F28 声音控制和 4 声道混音。",
      "公开网页未确认声音存储容量，生成时不得把容量作为已验证限制。",
      "厂商已确认 5313/5323 固定 28 个 Slot。",
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
    "storage_bits": None,
    "storage_bytes": None,
    "storage_unit": "Mb",
    "fixed_slot_count": 28,
    "slot_count_evidence": "2026-07-02 厂商答复确认 5313/5323 固定 28 个 Slot。",
    "evidence_status": "needs_storage_capacity_confirmation",
    "project_extension": "dxsp",
    "legacy_software_version": "25",
    "audio_format": {"sample_rate_hz": 11025, "bits": 8, "channels": 1},
    "notes": [
      "系列说明书覆盖 5313/5323，公开资料未给出可验证声音存储容量。",
      "厂商已确认 5313/5323 固定 28 个 Slot。",
    ],
  },
  _sound_chip_profile_6x("6003", "PluX22"),
  _sound_chip_profile_6x("6005", "21MTC"),
  _sound_chip_profile_6x("6006", "NEXT18"),
  _sound_chip_profile_6x("6008", "E24"),
  _sound_chip_profile_8x("8003", "PluX22", 256),
  _sound_chip_profile_8x("8004", "NEXT18", 128),
  _sound_chip_profile_8x("8005", "21MTC", 256),
  _sound_chip_profile_8x("8006", "NEXT18", 256),
  _sound_chip_profile_8x("8008", "E24", 256),
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

_SOUND_LIBRARY_CATEGORIES = [
  {"category": "traction_engine", "label": "主音效", "description": "内燃、电力、电机、风机和空压机等持续或循环声音"},
  {"category": "horn", "label": "鸣笛", "description": "风笛、电笛、长鸣、短鸣和组合鸣笛"},
  {"category": "rail_wheel", "label": "轮轨声", "description": "轨缝、道岔、曲线和轮缘摩擦声"},
  {"category": "radio", "label": "司机手台", "description": "司机、调度、车站值班交流声"},
  {"category": "station_announcement", "label": "广播与提示", "description": "车站广播、到站提醒、关门提示和客室提示音"},
]

_SLOT_LIBRARY_CATEGORIES = [
  {"category": "power_unit", "label": "动力单元"},
  {"category": "horn", "label": "鸣笛"},
  {"category": "mechanical_unit", "label": "机械单元"},
  {"category": "running_sound", "label": "行驶音效"},
  {"category": "radio_control", "label": "联控音效"},
  {"category": "announcement", "label": "广播音效"},
]


def sound_chip_profiles() -> list[dict[str, Any]]:
  return [dict(profile) for profile in _CHIP_PROFILES]


def sound_library_catalog(user_library: dict[str, Any] | None = None) -> dict[str, Any]:
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
  library = normalized_user_sound_library(user_library or load_user_sound_library())
  return {
    "categories": [dict(category) for category in _SOUND_LIBRARY_CATEGORIES],
    "sounds": sounds,
    "saved_sounds": library["saved_sounds"],
    "slot_library": library["slot_library"],
  }


def default_user_sound_library() -> dict[str, Any]:
  return {
    "saved_sounds": [],
    "slot_library": {
      "categories": [dict(category) for category in _SLOT_LIBRARY_CATEGORIES],
      "slots": [],
    },
  }


def load_user_sound_library(store_path: Path | str = USER_SOUND_LIBRARY_PATH) -> dict[str, Any]:
  path = Path(store_path)
  if not path.exists():
    return default_user_sound_library()
  try:
    payload = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return default_user_sound_library()
  return normalized_user_sound_library(payload)


def normalized_user_sound_library(payload: dict[str, Any]) -> dict[str, Any]:
  library = default_user_sound_library()
  if not isinstance(payload, dict):
    return library
  library["saved_sounds"] = [
    _normalize_saved_sound(sound)
    for sound in payload.get("saved_sounds", [])
    if isinstance(sound, dict)
  ]
  slot_library = payload.get("slot_library", {})
  if isinstance(slot_library, dict):
    categories = slot_library.get("categories")
    if isinstance(categories, list) and categories:
      library["slot_library"]["categories"] = [
        {"category": str(category.get("category", "")), "label": str(category.get("label", ""))}
        for category in categories
        if isinstance(category, dict) and category.get("category")
      ] or library["slot_library"]["categories"]
    library["slot_library"]["slots"] = [
      _normalize_slot_library_entry(slot)
      for slot in slot_library.get("slots", [])
      if isinstance(slot, dict)
    ]
  return library


def save_user_sound_library_sound(sound: dict[str, Any], store_path: Path | str = USER_SOUND_LIBRARY_PATH) -> dict[str, Any]:
  entry = _normalize_saved_sound(sound)
  library = load_user_sound_library(store_path)
  library["saved_sounds"] = _upsert_by_key(library["saved_sounds"], entry, "sound_id")
  _write_user_sound_library(library, store_path)
  return entry


def save_user_sound_library_slot(slot: dict[str, Any], store_path: Path | str = USER_SOUND_LIBRARY_PATH) -> dict[str, Any]:
  entry = _normalize_slot_library_entry(slot)
  library = load_user_sound_library(store_path)
  library["slot_library"]["slots"] = _upsert_by_key(library["slot_library"]["slots"], entry, "slot_library_id")
  _write_user_sound_library(library, store_path)
  return entry


def _write_user_sound_library(library: dict[str, Any], store_path: Path | str) -> None:
  path = Path(store_path)
  path.parent.mkdir(parents=True, exist_ok=True)
  normalized = normalized_user_sound_library(library)
  tmp_path = path.with_suffix(path.suffix + ".tmp")
  tmp_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
  tmp_path.replace(path)


def _upsert_by_key(entries: list[dict[str, Any]], entry: dict[str, Any], key: str) -> list[dict[str, Any]]:
  entry_key = entry.get(key)
  return [current for current in entries if current.get(key) != entry_key] + [entry]


def _normalize_saved_sound(sound: dict[str, Any]) -> dict[str, Any]:
  category = str(sound.get("category") or "custom").strip() or "custom"
  file_name = str(sound.get("fileName") or sound.get("file_name") or sound.get("label") or "sound.wav")
  content_base64 = str(sound.get("contentBase64") or sound.get("content_base64") or "")
  content_encoding = str(sound.get("contentEncoding") or sound.get("content_encoding") or "")
  preview_format = sound.get("previewFormat", sound.get("preview_format"))
  pcm_bytes = int(sound.get("pcmBytes", sound.get("pcm_bytes", 0)) or 0)
  sound_id = str(sound.get("sound_id") or f"saved-sound-{uuid.uuid4().hex}")
  label = str(sound.get("label") or file_name)
  return {
    "sound_id": sound_id,
    "label": label,
    "category": category,
    "description": str(sound.get("description") or f"用户保存的音效 {file_name}"),
    "tags": [str(tag) for tag in sound.get("tags", []) if str(tag).strip()],
    "audio_available": bool(sound.get("audio_available") or content_base64),
    "asset_source": str(sound.get("asset_source") or "saved_project_sound"),
    "license": str(sound.get("license") or "user_saved_asset"),
    "fileName": file_name,
    "file_name": file_name,
    "contentBase64": content_base64,
    "content_base64": content_base64,
    "contentEncoding": content_encoding,
    "content_encoding": content_encoding,
    "previewFormat": preview_format,
    "preview_format": preview_format,
    "pcmBytes": pcm_bytes,
    "pcm_bytes": pcm_bytes,
  }


def _normalize_slot_library_entry(slot: dict[str, Any]) -> dict[str, Any]:
  category = str(slot.get("category") or "power_unit").strip() or "power_unit"
  slot_id = str(slot.get("slot_library_id") or f"slot-template-{uuid.uuid4().hex}")
  nodes = [_plain_dict(node) for node in slot.get("nodes", []) if isinstance(node, dict)]
  connectors = [_plain_dict(connector) for connector in slot.get("connectors", []) if isinstance(connector, dict)]
  sound_files = [_plain_dict(sound_file) for sound_file in slot.get("sound_files", []) if isinstance(sound_file, dict)]
  sound_file_ids = [
    int(value)
    for value in slot.get("sound_file_ids", [])
    if str(value).strip().isdigit()
  ]
  return {
    "slot_library_id": slot_id,
    "category": category,
    "label": str(slot.get("label") or "未命名 Slot"),
    "source_slot_id": int(slot.get("source_slot_id") or 0),
    "nodes": nodes,
    "connectors": connectors,
    "sound_files": sound_files,
    "sound_file_ids": sound_file_ids,
  }


def _plain_dict(value: dict[str, Any]) -> dict[str, Any]:
  return {str(key): item for key, item in value.items() if isinstance(key, str)}


def parse_sound_project_summary(project_bytes: bytes, file_name: str = "sound.dxsd") -> dict[str, Any]:
  if len(project_bytes) > SOUND_PROJECT_BODY_LIMIT_BYTES:
    raise ValueError(f"音效工程文件超过 {SOUND_PROJECT_BODY_LIMIT_BYTES} 字节限制")
  _validate_sound_project_file_name(file_name)
  if project_bytes[:4] == b"PK\x03\x04":
    raise ValueError("不支持直接导入 ZIP；官方 ZIP 只是下载容器，请先解压后选择 .dxsd 或 .dxsp 工程文件")
  return parse_dxsd_summary(project_bytes, file_name)


def parse_dxsd_summary(xml_bytes: bytes, file_name: str = "sound.dxsd") -> dict[str, Any]:
  if len(xml_bytes) > SOUND_PROJECT_BODY_LIMIT_BYTES:
    raise ValueError(f"音效工程 XML 超过 {SOUND_PROJECT_BODY_LIMIT_BYTES} 字节限制")
  _reject_unsafe_xml(xml_bytes)
  records = _stream_dxsd_records(xml_bytes)
  is_legacy_dxsp = bool(records.get("Project_Base_Info")) and not records.get("Base_Info")
  project_format = "dxsp_legacy" if is_legacy_dxsp else "dxsd"
  base_info = _normalize_base_info(_base_info_row(records))
  if is_legacy_dxsp:
    slots = _legacy_dxsp_slots(records)
    nodes = []
    connectors = []
    judgments = []
    actions = []
  else:
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
  if is_legacy_dxsp:
    function_mappings = _legacy_dxsp_function_mappings(slots)
  else:
    function_mappings = _function_mappings(cv_entries, {slot["slot_id"]: slot for slot in slots})
  return {
    "file_name": Path(file_name or "sound.dxsd").name,
    "project_format": project_format,
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
  project_extension = str(chip.get("project_extension") or "dxsd")
  if project_extension == "dxsp":
    xml = _build_dxsp_package_xml(chip, package_name, slots, warnings)
  else:
    xml = _build_package_xml(chip, package_name, slots, warnings)
  content = xml.encode("utf-8")
  return {
    "file_name": f"{package_name}.{project_extension}",
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


def _base_info_row(records: dict[str, list[dict[str, str]]]) -> dict[str, str]:
  return _first(records, "Base_Info") or _first(records, "Project_Base_Info")


def _normalize_base_info(row: dict[str, str]) -> dict[str, Any]:
  return {
    "decoder_module": row.get("Decoder_Moudle", ""),
    "flash_size": _int(row.get("Flash_Size")),
    "software_version": row.get("SoftWare_Version", ""),
    "dealer_id": row.get("Dealer_ID", ""),
    "engine_type": _int(row.get("Engine_Type")),
    "random_interval": _int(row.get("Random_Interval")),
    "sound_config": _int(row.get("Sound_Config")),
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
    "content_base64": _clean_base64(file_data),
    "content_encoding": "pcm",
    "preview_format": _audio_preview_format(decoder_module),
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
    function_number = _slot_function_number(value)
    if not (171 <= cv_address <= 234 and function_number is not None):
      continue
    slot_id = cv_address - 170
    slot = slots_by_id.get(slot_id)
    if slot is None:
      continue
    mappings.append({
      "cv_address": cv_address,
      "slot_id": slot_id,
      "slot_name": slot.get("slot_name", ""),
      "function_key": f"F{function_number}",
      "function_number": function_number,
      "is_assigned": True,
    })
  return mappings


def _slot_function_number(value: Any) -> int | None:
  number = _int(value)
  return number if 0 <= number <= 68 else None


def _legacy_dxsp_slots(records: dict[str, list[dict[str, str]]]) -> list[dict[str, Any]]:
  slots = []
  for index, row in enumerate(records.get("User_Sound_Table", [])[:28], start=1):
    user_type = _int(row.get("User_Type"))
    raw_user_files = _legacy_user_file_slots(row)
    user_files = raw_user_files if user_type else [None, None, None]
    file_ids = [file_id for file_id in user_files if file_id is not None]
    slots.append({
      "slot_id": index,
      "slot_priority": index,
      "slot_start_node": 0,
      "is_use": bool(file_ids or user_type),
      "start_address": 0,
      "slot_name": str(row.get("User_Function_Name") or f"F{index} 音效"),
      "legacy_table": "User_Sound_Table",
      "legacy_user_type": user_type,
      "legacy_user_volume": _int(row.get("User_Volume")),
      "legacy_user_label": _int(row.get("User_Label")),
      "legacy_user_files": user_files,
      "legacy_file_ids": file_ids,
    })
  return slots


def _legacy_user_file_slots(row: dict[str, str]) -> list[int | None]:
  file_slots: list[int | None] = []
  for index in range(LEGACY_DXSP_USER_SOUND_FILE_FIELDS):
    file_id = _int(row.get(f"File_{index}"), 255)
    file_slots.append(None if file_id == 255 else file_id)
  return file_slots


def _legacy_dxsp_function_mappings(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
  mappings = []
  for slot in slots:
    function_number = _slot_function_number(slot["slot_id"])
    if not function_number:
      continue
    mappings.append({
      "cv_address": 0,
      "slot_id": slot["slot_id"],
      "slot_name": slot.get("slot_name", ""),
      "function_key": f"F{function_number}",
      "function_number": function_number,
      "is_assigned": True,
      "source": "dxsp_user_sound_table",
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
  emitted_sound_file_ids: set[int] = set()
  total_audio_bytes = 0
  for index, raw_slot in enumerate(slots, start=1):
    if not isinstance(raw_slot, dict):
      raise ValueError("each slot must be a JSON object")
    slot_id = _bounded_int(raw_slot.get("slot_id"), index, 1, 64)
    function_key = _function_cv_value(raw_slot.get("function_key"))
    slot_name = str(raw_slot.get("slot_name") or f"Sound slot {slot_id}")
    sound = raw_slot.get("sound") if isinstance(raw_slot.get("sound"), dict) else {}
    raw_nodes = raw_slot.get("nodes") if isinstance(raw_slot.get("nodes"), list) else []
    raw_connectors = raw_slot.get("connectors") if isinstance(raw_slot.get("connectors"), list) else []
    raw_judgments = raw_slot.get("judgments") if isinstance(raw_slot.get("judgments"), list) else []
    raw_actions = raw_slot.get("actions") if isinstance(raw_slot.get("actions"), list) else []
    raw_sound_files = raw_slot.get("sound_files") if isinstance(raw_slot.get("sound_files"), list) else []
    has_default_sound = _slot_has_default_sound(sound)
    slot_is_use = _boolish(raw_slot.get("is_use"), bool(raw_nodes or raw_connectors or raw_sound_files or has_default_sound))
    lines.extend(_slot_xml(slot_id, slot_name, slot_is_use))
    if raw_nodes:
      for raw_node in raw_nodes:
        if not isinstance(raw_node, dict):
          continue
        lines.extend(_node_xml(
          slot_id,
          _bounded_int(raw_node.get("node_id"), 0, 0, 999),
          _bounded_int(raw_node.get("file_id"), 0, 0, 999999),
          str(raw_node.get("node_name") or f"Node {_bounded_int(raw_node.get('node_id'), 0, 0, 999)}"),
          _bounded_int(raw_node.get("x"), 40, 0, 999999),
          _bounded_int(raw_node.get("y"), 60, 0, 999999),
          node_type=_bounded_int(raw_node.get("node_type"), 1, 0, 999),
          node_config=_bounded_int(raw_node.get("node_config"), 0, 0, 999999),
          repeat_amount=_bounded_int(raw_node.get("repeat_amount"), 1, 0, 999999),
          sound_volume=_bounded_int(raw_node.get("sound_volume"), 255, 0, 255),
          width=_bounded_int(raw_node.get("width"), 96, 1, 999999),
          height=_bounded_int(raw_node.get("height"), 64, 1, 999999),
          start_address=_bounded_int(raw_node.get("start_address"), 0, 0, 999999),
        ))
      for raw_connector in raw_connectors:
        if not isinstance(raw_connector, dict):
          continue
        lines.extend(_connector_xml(
          slot_id,
          _bounded_int(raw_connector.get("connector_id"), index, 1, 999999),
          _bounded_int(raw_connector.get("source_node_id"), 0, 0, 999),
          _bounded_int(raw_connector.get("target_node_id"), 0, 0, 999),
          connector_type=_bounded_int(raw_connector.get("connector_type"), 0, 0, 999),
          source_port_index=_bounded_int(raw_connector.get("source_port_index"), 1, 0, 999),
          start_address=_bounded_int(raw_connector.get("start_address"), 0, 0, 999999),
        ))
      for raw_judgment in raw_judgments:
        if not isinstance(raw_judgment, dict):
          continue
        lines.extend(_judgment_xml(
          _bounded_int(raw_judgment.get("judgment_id"), 1, 1, 999999),
          _bounded_int(raw_judgment.get("connector_id"), 0, 1, 999999),
          register_type=_bounded_int(raw_judgment.get("register_type"), 0, 0, 255),
          operation_type=_bounded_int(raw_judgment.get("operation_type"), 0, 0, 255),
          parameter_value=_bounded_int(raw_judgment.get("parameter_value"), 0, 0, 65535),
        ))
      for raw_action in raw_actions:
        if not isinstance(raw_action, dict):
          continue
        lines.extend(_action_xml(
          _bounded_int(raw_action.get("action_id"), 1, 1, 999999),
          _bounded_int(raw_action.get("connector_id"), 0, 1, 999999),
          register_type=_bounded_int(raw_action.get("register_type"), 0, 0, 255),
          operation_config=_bounded_int(raw_action.get("operation_config"), 0, 0, 255),
          parameter_value=_bounded_int(raw_action.get("parameter_value"), 0, 0, 65535),
        ))
      for raw_sound_file in raw_sound_files:
        if not isinstance(raw_sound_file, dict):
          continue
        file_id = _bounded_int(raw_sound_file.get("file_id"), 0, 0, 999999)
        if not file_id or file_id in emitted_sound_file_ids:
          continue
        sound_payload = _sound_payload_for_slot(chip, slot_id, slot_name, raw_sound_file, warnings)
        total_audio_bytes += sound_payload["audio_bytes"]
        sound_file_rows.extend(_sound_file_xml(
          file_id,
          sound_payload["file_name"],
          sound_payload["file_length"],
          sound_payload["content_base64"],
        ))
        emitted_sound_file_ids.add(file_id)
    elif has_default_sound:
      file_id = index
      sound_payload = _sound_payload_for_slot(chip, slot_id, slot_name, sound, warnings)
      total_audio_bytes += sound_payload["audio_bytes"]
      lines.extend(_node_xml(slot_id, 0, 0, "入口", 40, 60))
      lines.extend(_node_xml(slot_id, 1, file_id, slot_name, 180, 60))
      lines.extend(_connector_xml(slot_id, index, 0, 1))
      sound_file_rows.extend(_sound_file_xml(file_id, sound_payload["file_name"], sound_payload["file_length"], sound_payload["content_base64"]))
    lines.extend(_cv_xml(170 + slot_id, function_key, f"Slot{slot_id}响应功能"))
  _validate_total_sound_size(chip, total_audio_bytes, warnings)
  lines.extend(_cv_xml(113, DEFAULT_TOTAL_VOLUME, "总音量"))
  lines.extend(sound_file_rows)
  lines.append("</NewDataSet>")
  return "\n".join(lines) + "\n"


def _build_dxsp_package_xml(chip: dict[str, Any], package_name: str, slots: list[Any], warnings: list[dict[str, str]]) -> str:
  fixed_slot_count = int(chip.get("fixed_slot_count") or 28)
  slot_map: dict[int, dict[str, Any]] = {}
  for index, raw_slot in enumerate(slots, start=1):
    if not isinstance(raw_slot, dict):
      raise ValueError("each slot must be a JSON object")
    slot_id = _bounded_int(raw_slot.get("slot_id"), index, 1, fixed_slot_count)
    slot_map[slot_id] = raw_slot

  lines = [
    '<?xml version="1.0" standalone="yes"?>',
    "<NewDataSet>",
    "  <Project_Base_Info>",
    f"    <Decoder_Moudle>{_xml(chip['decoder_module'])}</Decoder_Moudle>",
    f"    <Flash_Size>{LEGACY_DXSP_FLASH_SIZE}</Flash_Size>",
    f"    <SoftWare_Version>{_xml(chip.get('legacy_software_version') or '1')}</SoftWare_Version>",
    "    <Engine_Type>0</Engine_Type>",
    "    <Random_Interval>4</Random_Interval>",
    "    <Sound_Config>254</Sound_Config>",
    f"    <Sound_Name>{_xml(package_name)}</Sound_Name>",
    "    <Sound_Mac_ID>4294967295</Sound_Mac_ID>",
    "    <Model_ID>0</Model_ID>",
    f"    <Decoder_Name>{_xml(chip['decoder_module'])}</Decoder_Name>",
    "  </Project_Base_Info>",
  ]
  sound_file_rows: list[str] = []
  total_audio_bytes = 0
  emitted_sound_file_ids: set[int] = set()
  next_file_id = 0
  for slot_id in range(1, fixed_slot_count + 1):
    raw_slot = slot_map.get(slot_id, {})
    slot_name = str(raw_slot.get("slot_name") or f"F{slot_id} 音效")
    if raw_slot.get("nodes") or raw_slot.get("connectors"):
      warnings.append({
        "type": "dxsp_graph_not_supported",
        "slot_id": str(slot_id),
        "message": f"5313/5323 的 .dxsp 旧格式不保存节点图，Slot {slot_id} 按 User_Type 和 File_0..File_2 导出。",
      })
    user_files = _dxsp_legacy_user_files(raw_slot)
    sound_source = _slot_sound_source(raw_slot)
    if not any(file_id is not None for file_id in user_files) and sound_source:
      while next_file_id in emitted_sound_file_ids:
        next_file_id += 1
      user_files[0] = next_file_id
    user_type = _dxsp_legacy_user_type(raw_slot, user_files)
    user_volume = _dxsp_legacy_user_volume(raw_slot, user_type)
    if user_type == 0:
      user_files = [None, None, None]
    raw_sound_files = raw_slot.get("sound_files") if isinstance(raw_slot.get("sound_files"), list) else []
    sound_files_by_id = {
      _bounded_int(entry.get("file_id"), 0, 0, 999999): entry
      for entry in raw_sound_files
      if isinstance(entry, dict)
    }
    for file_id in [file_id for file_id in user_files if file_id is not None]:
      if file_id in emitted_sound_file_ids:
        continue
      sound_file_source = sound_files_by_id.get(file_id) or sound_source
      if not sound_file_source:
        warnings.append({
          "type": "dxsp_missing_sound_file_payload",
          "slot_id": str(slot_id),
          "message": f"Slot {slot_id} 引用了音频 #{file_id}，但生成请求没有携带对应音频内容。",
        })
        continue
      payload = _sound_payload_for_slot(chip, slot_id, slot_name, sound_file_source, warnings)
      if not payload["content_base64"]:
        continue
      total_audio_bytes += payload["audio_bytes"]
      sound_file_rows.extend(_dxsp_sound_file_xml(
        file_id,
        payload["file_name"],
        payload["file_length"],
        payload["content_base64"],
      ))
      emitted_sound_file_ids.add(file_id)
    lines.extend(_dxsp_user_sound_xml(slot_id, slot_name, user_type, user_volume, user_files))
  _validate_total_sound_size(chip, total_audio_bytes, warnings)
  lines.extend(sound_file_rows)
  lines.append("</NewDataSet>")
  return "\n".join(lines) + "\n"


def _validate_sound_project_file_name(file_name: str) -> None:
  suffix = Path(file_name or "").suffix.lower()
  if suffix not in SOUND_PROJECT_INPUT_EXTENSIONS:
    raise ValueError("音效工程只支持 .dxsd 或 .dxsp 文件；官方 ZIP 请先解压后再导入")


def _function_cv_value(value: Any) -> int:
  if value is None:
    return UNMAPPED_SLOT_FUNCTION_CV_VALUE
  text = str(value).strip()
  if not text:
    return UNMAPPED_SLOT_FUNCTION_CV_VALUE
  if text.lower().startswith("f"):
    text = text[1:].strip()
  number = _int(text, UNMAPPED_SLOT_FUNCTION_CV_VALUE)
  if number < 0:
    return UNMAPPED_SLOT_FUNCTION_CV_VALUE
  return min(68, number)


def _slot_sound_source(raw_slot: dict[str, Any]) -> dict[str, Any]:
  raw_sound_files = raw_slot.get("sound_files") if isinstance(raw_slot.get("sound_files"), list) else []
  for raw_sound_file in raw_sound_files:
    if isinstance(raw_sound_file, dict) and _slot_has_default_sound(raw_sound_file):
      return raw_sound_file
  sound = raw_slot.get("sound") if isinstance(raw_slot.get("sound"), dict) else {}
  return sound if _slot_has_default_sound(sound) else {}


def _dxsp_legacy_user_files(raw_slot: dict[str, Any]) -> list[int | None]:
  user_files = raw_slot.get("legacy_user_files")
  if isinstance(user_files, list):
    return _normalize_dxsp_file_slots(user_files)
  legacy_file_ids = raw_slot.get("legacy_file_ids")
  if isinstance(legacy_file_ids, list):
    return _normalize_dxsp_file_slots(legacy_file_ids)
  raw_sound_files = raw_slot.get("sound_files") if isinstance(raw_slot.get("sound_files"), list) else []
  sound_file_ids = [
    _bounded_int(entry.get("file_id"), 0, 0, 999999)
    for entry in raw_sound_files
    if isinstance(entry, dict) and _slot_has_default_sound(entry)
  ]
  return _normalize_dxsp_file_slots(sound_file_ids)


def _normalize_dxsp_file_slots(values: list[Any]) -> list[int | None]:
  normalized: list[int | None] = []
  for value in values[:LEGACY_DXSP_USER_SOUND_FILE_FIELDS]:
    if value is None or str(value).strip() == "":
      normalized.append(None)
      continue
    file_id = _bounded_int(value, 255, 0, 999999)
    normalized.append(None if file_id == 255 else file_id)
  while len(normalized) < LEGACY_DXSP_USER_SOUND_FILE_FIELDS:
    normalized.append(None)
  return normalized


def _dxsp_legacy_user_type(raw_slot: dict[str, Any], user_files: list[int | None]) -> int:
  raw_type = raw_slot.get("legacy_user_type")
  if raw_type is not None and str(raw_type).strip() != "":
    return _bounded_int(raw_type, 0, 0, 255)
  if not any(file_id is not None for file_id in user_files):
    return 0
  return 2 if any(file_id is not None for file_id in user_files[1:]) else 1


def _dxsp_legacy_user_volume(raw_slot: dict[str, Any], user_type: int) -> int:
  raw_volume = raw_slot.get("legacy_user_volume")
  default_volume = 255 if user_type else 0
  if raw_volume is None or str(raw_volume).strip() == "":
    return default_volume
  return _bounded_int(raw_volume, default_volume, 0, 255)


def _dxsp_user_sound_xml(
  slot_id: int,
  slot_name: str,
  user_type: int,
  user_volume: int,
  user_files: list[int | None],
) -> list[str]:
  file_values = _normalize_dxsp_file_slots(user_files)
  return [
    "  <User_Sound_Table>",
    f"    <User_Type>{user_type}</User_Type>",
    f"    <User_Volume>{user_volume}</User_Volume>",
    "    <User_Label>1</User_Label>",
    f"    <User_Function_Name>{_xml(slot_name)}</User_Function_Name>",
    f"    <File_0>{file_values[0] if file_values[0] is not None else 255}</File_0>",
    f"    <File_1>{file_values[1] if file_values[1] is not None else 255}</File_1>",
    f"    <File_2>{file_values[2] if file_values[2] is not None else 255}</File_2>",
    "  </User_Sound_Table>",
  ]


def _dxsp_sound_file_xml(file_id: int, file_name: str, file_length: int, content_base64: str) -> list[str]:
  return [
    "  <SoundFile_Table>",
    f"    <File_ID>{file_id}</File_ID>",
    f"    <File_Name>{_xml(file_name)}</File_Name>",
    f"    <File_Length>{file_length}</File_Length>",
    f"    <File_Data>{content_base64}</File_Data>",
    "  </SoundFile_Table>",
  ]


def _slot_xml(slot_id: int, slot_name: str, is_use: bool = True) -> list[str]:
  return [
    "  <Slot_Table>",
    f"    <Slot_ID>{slot_id}</Slot_ID>",
    f"    <Slot_Priority>{slot_id}</Slot_Priority>",
    "    <Slot_StartNode>0</Slot_StartNode>",
    f"    <Is_Use>{str(bool(is_use)).lower()}</Is_Use>",
    "    <Start_Address>0</Start_Address>",
    f"    <Slot_Name>{_xml(slot_name)}</Slot_Name>",
    "  </Slot_Table>",
  ]


def _node_xml(
  slot_id: int,
  node_id: int,
  file_id: int,
  name: str,
  x: int,
  y: int,
  *,
  node_type: int = 1,
  node_config: int = 0,
  repeat_amount: int = 1,
  sound_volume: int = 255,
  width: int = 96,
  height: int = 64,
  start_address: int = 0,
) -> list[str]:
  return [
    "  <Node_Table>",
    f"    <Node_ID>{node_id}</Node_ID>",
    f"    <Slot_ID>{slot_id}</Slot_ID>",
    f"    <Node_Type>{node_type}</Node_Type>",
    f"    <File_ID>{file_id}</File_ID>",
    f"    <Node_Config>{node_config}</Node_Config>",
    f"    <Repeat_Amount>{repeat_amount}</Repeat_Amount>",
    f"    <Sound_Volume>{sound_volume}</Sound_Volume>",
    f"    <Node_X>{x}</Node_X>",
    f"    <Node_Y>{y}</Node_Y>",
    f"    <Node_W>{width}</Node_W>",
    f"    <Node_H>{height}</Node_H>",
    f"    <Node_Name>{_xml(name)}</Node_Name>",
    f"    <Start_Address>{start_address}</Start_Address>",
    "  </Node_Table>",
  ]


def _connector_xml(
  slot_id: int,
  connector_id: int,
  source_node_id: int,
  target_node_id: int,
  *,
  connector_type: int = 0,
  source_port_index: int = 1,
  start_address: int = 0,
) -> list[str]:
  return [
    "  <Connector_Table>",
    f"    <Connector_ID>{connector_id}</Connector_ID>",
    f"    <Connector_Type>{connector_type}</Connector_Type>",
    f"    <Node_ID>{source_node_id}</Node_ID>",
    f"    <Node_Index_ID>{source_port_index}</Node_Index_ID>",
    f"    <Slot_ID>{slot_id}</Slot_ID>",
    f"    <OUT_Node_ID>{target_node_id}</OUT_Node_ID>",
    f"    <Start_Address>{start_address}</Start_Address>",
    "  </Connector_Table>",
  ]


def _judgment_xml(
  judgment_id: int,
  connector_id: int,
  *,
  register_type: int = 0,
  operation_type: int = 0,
  parameter_value: int = 0,
) -> list[str]:
  return [
    "  <Judgment_Table>",
    f"    <Judgment_ID>{judgment_id}</Judgment_ID>",
    f"    <Connector_ID>{connector_id}</Connector_ID>",
    f"    <Register_Type>{register_type}</Register_Type>",
    f"    <Operation_Type>{operation_type}</Operation_Type>",
    f"    <Parameter_Value>{parameter_value}</Parameter_Value>",
    "  </Judgment_Table>",
  ]


def _action_xml(
  action_id: int,
  connector_id: int,
  *,
  register_type: int = 0,
  operation_config: int = 0,
  parameter_value: int = 0,
) -> list[str]:
  return [
    "  <Action_Table>",
    f"    <Action_ID>{action_id}</Action_ID>",
    f"    <Connector_ID>{connector_id}</Connector_ID>",
    f"    <Register_Type>{register_type}</Register_Type>",
    f"    <Operation_Config>{operation_config}</Operation_Config>",
    f"    <Parameter_Value>{parameter_value}</Parameter_Value>",
    "  </Action_Table>",
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


def _sound_payload_for_slot(
  chip: dict[str, Any],
  slot_id: int,
  slot_name: str,
  sound: dict[str, Any],
  warnings: list[dict[str, str]],
) -> dict[str, Any]:
  file_name = str(sound.get("file_name") or sound.get("label") or f"sound-{slot_id}.wav")
  content_base64 = _clean_base64(str(sound.get("content_base64") or ""))
  content_encoding = str(sound.get("content_encoding") or sound.get("contentEncoding") or "").strip().lower()
  if not content_base64:
    warnings.append({
      "type": "metadata_only_sound",
      "slot_id": str(slot_id),
      "message": f"Slot {slot_id}「{slot_name}」没有实际音频数据，仅生成工程占位。",
    })
    return {
      "file_name": file_name,
      "file_length": 0,
      "content_base64": "",
      "audio_bytes": 0,
    }
  if content_encoding == "pcm":
    pcm_bytes = _decode_base64_bytes(content_base64)
    return {
      "file_name": file_name,
      "file_length": len(pcm_bytes),
      "content_base64": content_base64,
      "audio_bytes": len(pcm_bytes),
    }
  if not file_name.lower().endswith(".wav"):
    raise ValueError(f"Slot {slot_id}「{slot_name}」的音效文件必须是 WAV 格式")
  wav_bytes = _decode_base64_bytes(content_base64)
  metadata = _wav_metadata(wav_bytes)
  _validate_wav_for_chip(metadata, chip, slot_id, slot_name)
  data_start = metadata["data_offset"]
  data_end = data_start + metadata["data_bytes"]
  return {
    "file_name": file_name,
    "file_length": metadata["data_bytes"],
    "content_base64": base64.b64encode(wav_bytes[data_start:data_end]).decode("ascii"),
    "audio_bytes": metadata["data_bytes"],
  }


def _decode_base64_bytes(value: str) -> bytes:
  try:
    return base64.b64decode(_clean_base64(value), validate=True)
  except (ValueError, binascii.Error) as exc:
    raise ValueError("WAV 音频数据不是有效的 base64") from exc


def _wav_metadata(wav_bytes: bytes) -> dict[str, int]:
  if len(wav_bytes) < 44 or wav_bytes[:4] != b"RIFF" or wav_bytes[8:12] != b"WAVE":
    raise ValueError("音效文件必须是 WAV 格式")
  offset = 12
  fmt: dict[str, int] | None = None
  data_offset = 0
  data_bytes = 0
  while offset + 8 <= len(wav_bytes):
    chunk_id = wav_bytes[offset:offset + 4]
    chunk_size = int.from_bytes(wav_bytes[offset + 4:offset + 8], "little")
    chunk_data = offset + 8
    if chunk_data + chunk_size > len(wav_bytes):
      raise ValueError("WAV 文件结构不完整")
    if chunk_id == b"fmt ":
      if chunk_size < 16:
        raise ValueError("WAV fmt chunk 不完整")
      fmt = {
        "audio_format": int.from_bytes(wav_bytes[chunk_data:chunk_data + 2], "little"),
        "channels": int.from_bytes(wav_bytes[chunk_data + 2:chunk_data + 4], "little"),
        "sample_rate_hz": int.from_bytes(wav_bytes[chunk_data + 4:chunk_data + 8], "little"),
        "bits": int.from_bytes(wav_bytes[chunk_data + 14:chunk_data + 16], "little"),
      }
    elif chunk_id == b"data":
      data_offset = chunk_data
      data_bytes = chunk_size
    offset = chunk_data + chunk_size + (chunk_size % 2)
  if not fmt or not data_bytes:
    raise ValueError("WAV 文件缺少 fmt 或 data chunk")
  if fmt["audio_format"] != 1:
    raise ValueError("仅支持 PCM WAV 音频")
  return {
    **fmt,
    "data_offset": data_offset,
    "data_bytes": data_bytes,
  }


def _validate_wav_for_chip(metadata: dict[str, int], chip: dict[str, Any], slot_id: int, slot_name: str) -> None:
  expected = chip["audio_format"]
  if (
    metadata["sample_rate_hz"] != expected["sample_rate_hz"]
    or metadata["bits"] != expected["bits"]
    or metadata["channels"] != expected["channels"]
  ):
    raise ValueError(
      f"Slot {slot_id}「{slot_name}」WAV 格式必须是 "
      f"{expected['sample_rate_hz']}Hz / {expected['bits']}bit / {expected['channels']}声道"
    )


def _validate_total_sound_size(chip: dict[str, Any], total_audio_bytes: int, warnings: list[dict[str, str]]) -> None:
  if not total_audio_bytes:
    return
  storage_bytes = chip.get("storage_bytes")
  if storage_bytes is None:
    warnings.append({
      "type": "sound_capacity_unconfirmed",
      "chip_id": str(chip.get("chip_id", "")),
      "message": "当前芯片公开资料未确认音效存储容量，请用官方工具或实物验证容量。",
    })
    return
  if total_audio_bytes > int(storage_bytes):
    raise ValueError(
      f"音效数据 {total_audio_bytes} 字节超过芯片容量 {int(storage_bytes)} 字节"
    )


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


def _audio_preview_format(decoder_module: str) -> dict[str, int]:
  audio_format = _audio_format(decoder_module)
  preview_bits = 8 if int(audio_format.get("bits", 16)) <= 8 else 16
  return {
    "sample_rate_hz": int(audio_format.get("sample_rate_hz", 44100)),
    "bits": preview_bits,
    "channels": int(audio_format.get("channels", 1)),
  }


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


def _boolish(value: Any, default: bool) -> bool:
  if value is None:
    return default
  if isinstance(value, bool):
    return value
  if isinstance(value, (int, float)):
    return bool(value)
  text = str(value).strip().lower()
  if text in {"true", "1", "yes", "y"}:
    return True
  if text in {"false", "0", "no", "n", ""}:
    return False
  return default


def _slot_has_default_sound(sound: dict[str, Any]) -> bool:
  return any(str(sound.get(field_name) or "").strip() for field_name in [
    "content_base64",
    "contentBase64",
    "library_id",
    "libraryId",
    "file_name",
    "fileName",
    "label",
  ])


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
  parsed = _int(value, default)
  return max(minimum, min(maximum, parsed))

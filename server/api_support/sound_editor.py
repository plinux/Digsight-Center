"""API support for Digsight sound editor workflows."""

from server import response
from server.api_support import http_helpers
from server.sound_editor import (
  build_dxsd_package,
  parse_sound_project_summary,
  save_user_sound_library_slot,
  save_user_sound_library_sound,
  sound_chip_profiles,
  sound_library_catalog,
)


class SoundEditorApiSupport:
  def list_chip_profiles(self):
    return http_helpers.success(sound_chip_profiles())

  def list_library(self):
    return http_helpers.success(sound_library_catalog())

  def save_library_sound(self, body: bytes):
    try:
      request = http_helpers.json_body(body)
      sound = dict(request.get("sound") or {})
      sound["category"] = request.get("category") or sound.get("category") or "custom"
      saved = save_user_sound_library_sound(sound)
    except (TypeError, ValueError) as exc:
      return http_helpers.failure("invalid_sound_library_entry", "音效库条目无效", str(exc), status=400)
    except http_helpers.JsonBodyError as exc:
      return response.failure("invalid_json", "请求 JSON 无效", str(exc)), 400
    return http_helpers.success(saved)

  def save_library_slot(self, body: bytes):
    try:
      request = http_helpers.json_body(body)
      slot = dict(request.get("slot") or {})
      slot["category"] = request.get("category") or slot.get("category") or "power_unit"
      saved = save_user_sound_library_slot(slot)
    except (TypeError, ValueError) as exc:
      return http_helpers.failure("invalid_slot_library_entry", "Slot 库条目无效", str(exc), status=400)
    except http_helpers.JsonBodyError as exc:
      return response.failure("invalid_json", "请求 JSON 无效", str(exc)), 400
    return http_helpers.success(saved)

  def import_dxsd(self, body: bytes, file_name: str = "uploaded.dxsd"):
    try:
      summary = parse_sound_project_summary(body, file_name)
    except ValueError as exc:
      return http_helpers.failure("invalid_sound_project", "音效工程文件无效", str(exc), status=400)
    return http_helpers.success(summary)

  def build_package(self, body: bytes):
    try:
      request = http_helpers.json_body(body)
      package = build_dxsd_package(request)
    except http_helpers.JsonBodyError as exc:
      return response.failure("invalid_json", "请求 JSON 无效", str(exc)), 400
    except ValueError as exc:
      return http_helpers.failure("invalid_sound_package", "音效工程生成失败", str(exc), status=400)
    return http_helpers.success(package)

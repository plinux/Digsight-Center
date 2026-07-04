"""API support for Digsight sound editor workflows."""

from server import response
from server.api_support import http_helpers
from server.sound_editor import (
  build_dxsd_package,
  parse_dxsd_summary,
  sound_chip_profiles,
  sound_library_catalog,
)


class SoundEditorApiSupport:
  def list_chip_profiles(self):
    return http_helpers.success(sound_chip_profiles())

  def list_library(self):
    return http_helpers.success(sound_library_catalog())

  def import_dxsd(self, body: bytes):
    try:
      summary = parse_dxsd_summary(body, "uploaded.dxsd")
    except ValueError as exc:
      return http_helpers.failure("invalid_dxsd", "DXSD 文件无效", str(exc), status=400)
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

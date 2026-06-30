"""Static resource mutation API support."""

import base64
import binascii
import uuid

from server import response
from server.api_support import http_helpers
from server.image_validation import DEFAULT_MAX_VEHICLE_IMAGE_BYTES, validate_vehicle_image
from server.public_paths import VEHICLE_IMAGE_PUBLIC_PREFIX


MAX_VEHICLE_IMAGE_BYTES = DEFAULT_MAX_VEHICLE_IMAGE_BYTES


class ResourceApiSupport:
  def __init__(self, context):
    self.context = context

  def upload_vehicle_image(self, body: bytes):
    request = http_helpers.json_body(body)
    file_name = str(request.get("file_name") or "vehicle-image.png")
    raw_content = request.get("content_base64")
    if not isinstance(raw_content, str) or not raw_content.strip():
      return response.failure("invalid_vehicle_image", "车辆图片无效", "content_base64 is required"), 400
    try:
      content = base64.b64decode(raw_content, validate=True)
    except (binascii.Error, ValueError) as exc:
      return response.failure("invalid_vehicle_image", "车辆图片无效", str(exc)), 400
    try:
      extension = validate_vehicle_image(file_name, content, max_bytes=MAX_VEHICLE_IMAGE_BYTES)
    except ValueError as exc:
      return response.failure("invalid_vehicle_image", "车辆图片无效", str(exc)), 400
    try:
      self.context.image_dir.mkdir(parents=True, exist_ok=True)
      target = self.context.image_dir / f"vehicle-{uuid.uuid4().hex}{extension}"
      target.write_bytes(content)
    except OSError as exc:
      return response.failure("vehicle_image_write_failed", "车辆图片写入失败", str(exc)), 500
    return response.success({
      "image_path": f"{VEHICLE_IMAGE_PUBLIC_PREFIX}{target.name}",
      "size": len(content),
    }), 200

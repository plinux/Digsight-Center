"""Controller configuration defaults shared by runtime state and SQLite seeds."""

import copy
from typing import Any, Dict

from server import models
from server.controllers.base import (
  ControllerTransportDescriptor,
  controller_display_name,
  controller_protocol,
)
from server.controllers.registry import default_controller_registry


UNREGISTERED_CONTROLLER_TRANSPORT_DESCRIPTOR = ControllerTransportDescriptor(
  kind="unconfigured",
  defaults={},
)

CONTROLLER_CONFIG_FIELDS = {
  "display_name",
  "field_descriptions",
  "ip",
  "protocol",
  "settings",
  "transport",
  "track_profiles",
}

CONTROLLER_CONFIG_COMMON_FIELD_DESCRIPTIONS = {
  "display_name": "控制器在页面下拉菜单中显示的名称，仅用于界面展示。",
  "ip": "控制器 IP 地址；0.0.0.0 是安全占位值，真实使用前需要改成控制器实际地址。",
  "protocol": "该控制器使用的通讯协议名称；同一种协议可以被多个控制器配置复用。",
  "settings": "控制器私有设置扩展区；没有专用设置时保持空对象。",
  "transport.kind": "传输类型；具体字段由当前控制器 adapter 解释。",
  "track_profiles.<mode>.mode": "轨道输出模式标识，取 n、ho、g 或 dc。",
  "track_profiles.<mode>.name": "轨道输出模式显示名称。",
  "track_profiles.<mode>.enabled": "该模式是否可在当前控制器上选择；不支持的模式会在页面上禁用，并由后端拒绝切换。",
  "track_profiles.<mode>.output_value": "下发给控制器的轨道输出值；具体含义由当前控制器 adapter 定义，不是实时电压读数。",
  "track_profiles.<mode>.target_voltage_v": "该模式的目标/配置电压，供界面和 DC 输出换算使用；不是控制器实时回报电压。",
  "track_profiles.<mode>.min_target_voltage_v": "该模式允许配置的目标电压下限。",
  "track_profiles.<mode>.max_target_voltage_v": "该模式允许配置的目标电压上限。",
  "track_profiles.<mode>.current_param": "该模式的限流参数标识；具体取值由当前控制器 adapter 定义。",
  "track_profiles.<mode>.target_current_limit_ma": "该模式的目标/配置限流值，保存后可写入控制器；不是实时电流读数。",
  "track_profiles.<mode>.max_target_current_limit_ma": "该模式允许配置的目标限流上限。",
}


def controller_field_descriptions(adapter=None) -> Dict[str, str]:
  descriptions = dict(CONTROLLER_CONFIG_COMMON_FIELD_DESCRIPTIONS)
  descriptions.update(getattr(adapter, "field_descriptions", {}) or {})
  profile_defaults = getattr(adapter, "default_track_profiles", None)
  if isinstance(profile_defaults, dict):
    profile_keys = {
      key
      for profile in profile_defaults.values()
      if isinstance(profile, dict)
      for key in profile
    }
    for profile_key in (
      "output_value",
      "current_param",
      "target_voltage_v",
      "min_target_voltage_v",
      "max_target_voltage_v",
      "min_target_current_limit_ma",
      "target_current_limit_ma",
      "max_target_current_limit_ma",
      "current_step_ma",
    ):
      if profile_key not in profile_keys:
        descriptions.pop(f"track_profiles.<mode>.{profile_key}", None)
  return descriptions


def controller_default_config(controller_registry, controller_kind: str) -> Dict[str, Any]:
  adapter = None
  try:
    adapter = controller_registry.get(controller_kind)
    transport_descriptor = adapter.transport_descriptor
    default_ip = adapter.default_ip
    display_name = controller_display_name(adapter)
    protocol = controller_protocol(adapter)
  except ValueError:
    transport_descriptor = UNREGISTERED_CONTROLLER_TRANSPORT_DESCRIPTOR
    default_ip = models.CONTROLLER_DEFAULT_IP
    display_name = ""
    protocol = ""
  return {
    "display_name": display_name,
    "field_descriptions": controller_field_descriptions(adapter),
    "ip": default_ip,
    "protocol": protocol,
    "settings": copy.deepcopy(getattr(adapter, "default_settings", {}) or {}),
    "transport": transport_descriptor.default_config(),
    "track_profiles": getattr(adapter, "default_track_profiles", None) or models.default_track_profiles(),
  }


def controller_default_config_rows(controller_registry=None) -> list[dict]:
  registry = controller_registry or default_controller_registry()
  rows = []
  for sort_order, adapter in enumerate(registry.adapters()):
    rows.append({
      "kind": adapter.kind,
      "config_file_name": registry.config_file_name(adapter.kind),
      "config": controller_default_config(registry, adapter.kind),
      "sort_order": sort_order,
    })
  return rows

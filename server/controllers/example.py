"""Code-only example controller adapter contract.

This module is not registered by default and is not exposed to the UI. It shows
the minimum surface a future controller adapter must implement before it can be
registered in :mod:`server.controllers.registry`.
"""

from server.controllers.base import (
  ControllerCapabilities,
  ControllerTransportDescriptor,
)


class ExampleControllerAdapter:
  """Non-functional sample controller adapter for extension authors."""

  kind = "example_controller"
  label = "样例控制器"
  default_display_name = "样例控制器"
  protocol = "ExampleProtocol"
  config_file_name = "example_controller.json"
  default_ip = ""
  field_descriptions = {
    "protocol": "样例控制器使用的占位协议名称；真实控制器应改为自己的协议标识。",
    "transport.kind": "样例控制器的传输类型；真实控制器可声明 tcp、udp、serial 或其它自定义类型。",
    "transport.endpoint": "样例控制器演示用端点字段；真实控制器应在 adapter 中声明自己需要的连接参数。",
  }
  capabilities = ControllerCapabilities(
    track_power=False,
    dc_control=False,
    read_info=False,
    cv_programming=False,
    loco_control=False,
    controller_settings=False,
  )
  transport_descriptor = ControllerTransportDescriptor(
    kind="example_transport",
    defaults={"endpoint": ""},
    endpoint_required_paths=("transport.endpoint",),
  )

  def runtime_readiness_warnings(self, controller: dict) -> list[str]:
    return ["controller_runtime_not_implemented"]

  def loco_control_readiness_warnings(self, controller: dict) -> list[str]:
    return ["controller_runtime_not_implemented"]

  def status_not_ready_message(self) -> str:
    return "样例控制器未实现通信运行时"

  def controller_client_id(self, controller: dict) -> int:
    raise NotImplementedError("样例控制器未实现 client id 策略")

  def is_booster_status_confirmed(self, controller: dict) -> bool:
    return False

  def programming_track_status(self, controller: dict):
    return None

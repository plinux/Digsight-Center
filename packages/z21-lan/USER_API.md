# Z21 LAN Python API

本 package 提供 Roco/Fleischmann Z21/z21 LAN UDP 协议的基础 helper。当前公开 API 覆盖控制器信息读取、系统状态解析、Common Settings RailCom 开关、MMDCC 主轨/编程轨电压设置、轨道电源开关、DCC/Motorola 机车模式和速度/功能键、Service Mode CV 和 POM 字节读写命令。

| API | 作用 |
| --- | --- |
| `DEFAULT_Z21_PORT` | Z21 LAN 默认 UDP 端口 `21105`。 |
| `LAN_SYSTEMSTATE_DATACHANGED` | Z21 系统状态响应/广播 header `0x0084`。 |
| `LAN_SYSTEMSTATE_GETDATA` | Z21 系统状态读取请求 header `0x0085`。 |
| `Z21Dataset` | 一个已解析的 Z21 dataset，包含 `data_len`、`header` 和 `payload`。 |
| `encode_dataset(header, payload=b\"\")` | 构造 little-endian Z21 dataset。 |
| `decode_datasets(datagram)` | 从一个 UDP datagram 解析一个或多个 dataset。 |
| `build_get_serial_number()` | 构造 `LAN_GET_SERIAL_NUMBER` 请求。 |
| `build_get_hwinfo()` | 构造 `LAN_GET_HWINFO` 请求。 |
| `build_get_broadcast_flags()` | 构造 `LAN_GET_BROADCASTFLAGS` 请求。 |
| `build_get_system_state()` | 构造 `LAN_SYSTEMSTATE_GETDATA` 请求。 |
| `build_get_common_settings()` | 构造 Z21 Maintenance Tool Common Settings 读取请求 `0x0012`。 |
| `build_set_common_settings(settings)` | 构造 Z21 Maintenance Tool Common Settings 写入请求 `0x0013`，会修改控制器配置。 |
| `build_get_mmdcc_settings()` | 构造 Z21 Maintenance Tool MMDCC 设置读取请求 `0x0016`。 |
| `build_set_mmdcc_settings(settings)` | 构造 Z21 Maintenance Tool MMDCC 设置写入请求 `0x0017`，会修改控制器配置。 |
| `build_x_get_firmware_version()` | 构造 `LAN_X_GET_FIRMWARE_VERSION` 请求。 |
| `build_x_set_track_power_off()` | 构造官方 `LAN_X_SET_TRACK_POWER_OFF` 请求。 |
| `build_x_set_track_power_on()` | 构造官方 `LAN_X_SET_TRACK_POWER_ON` 请求。 |
| `build_x_get_loco_info(address)` | 构造读取机车状态的 `LAN_X_GET_LOCO_INFO` 请求。 |
| `build_get_loco_mode(address)` | 构造读取短地址机车 DCC/Motorola 模式的 `LAN_GET_LOCO_MODE` 请求。 |
| `build_set_loco_mode(address, control_protocol)` | 构造设置短地址机车 DCC/Motorola 模式的 `LAN_SET_LOCO_MODE` 请求，`control_protocol` 支持 `dcc` 或 `motorola`。 |
| `build_x_set_loco_drive(address, speed, direction, speed_steps=128)` | 构造 14/28/128 步速度/方向控制请求，按 `speed_steps` 选择 X-BUS DB0 `0x10/0x12/0x13`。 |
| `build_x_set_loco_drive_128(address, speed, direction)` | 构造 128 步速度/方向控制请求。 |
| `build_x_set_loco_function(address, function_number, enabled)` | 构造 F0-F31 功能键控制请求。 |
| `build_x_cv_read_direct(cv_number)` | 构造 Service Mode CV 字节读取请求。 |
| `build_x_cv_write_direct(cv_number, value)` | 构造 Service Mode CV 字节写入请求。 |
| `build_x_cv_pom_read_byte(address, cv_number)` | 构造主轨 POM CV 字节读取请求。 |
| `build_x_cv_pom_write_byte(address, cv_number, value)` | 构造主轨 POM CV 字节写入请求。 |
| `xbus_xor(payload)` | 计算 X-BUS/XPressNet payload XOR。 |
| `build_lan_x_payload(*bytes)` | 构造带 XOR 的 LAN_X payload。 |
| `parse_serial_number(payload)` | 解析序列号 payload。 |
| `parse_hwinfo(payload)` | 解析 hardware type 和 firmware raw。 |
| `parse_broadcast_flags(payload)` | 解析广播 flags。 |
| `parse_system_state(payload)` | 解析系统电流、温度、电压和 central state 位。 |
| `parse_common_settings(payload)` | 解析 10 字节 Common Settings payload。 |
| `Z21CommonSettings` | 保留 Common Settings payload 字段，提供 `enable_railcom`、`with_railcom()` 和 `to_payload()`。 |
| `parse_mmdcc_settings(payload)` | 解析 16 字节 MMDCC 设置 payload。 |
| `Z21MMDCCSettings` | 保留 MMDCC payload 字段，提供 `output_voltage_mv`、`programming_voltage_mv`、`with_voltages()` 和 `to_payload()`。 |
| `parse_loco_info(payload)` | 解析 `LAN_X_LOCO_INFO` 机车速度、方向和功能键状态。 |
| `parse_cv_result(payload, pom_address=None)` | 解析 `LAN_X_CV_RESULT` CV 值。 |
| `parse_xbus_ack(payload)` | 解析 CV NACK/unknown-command 类 X-BUS 回包。 |
| `synthetic_pom_write_ack()` | 为 Z21 POM 字节写入无回包语义生成显式合成 ACK。 |
| `Z21UDPTransport.exchange(...)` | 使用 UDP 发送一个请求并读取响应 datagram，可用 `timeout_seconds` 覆盖本次读取超时。 |
| `Z21SessionManager.exchange(...)` | adapter 使用的会话门面，可注入 fake transport 测试，并可向底层传递单次 `timeout_seconds`。 |

## 示例

```python
from z21_lan import build_get_hwinfo, decode_datasets, parse_hwinfo, Z21UDPTransport

responses = Z21UDPTransport().exchange("192.168.0.111", 21105, build_get_hwinfo())
for dataset in decode_datasets(responses[0]):
    if dataset.header == 0x001A:
        print(parse_hwinfo(dataset.payload))
```

```python
from z21_lan import build_x_cv_read_direct, Z21UDPTransport

# Service Mode CV 读取可能需要等待解码器 ACK；可按本次请求放宽超时。
responses = Z21UDPTransport().exchange(
    "192.168.0.111",
    21105,
    build_x_cv_read_direct(8),
    timeout_seconds=10.0,
)
```

```python
from z21_lan import build_x_set_track_power_off, Z21UDPTransport

# 会改变控制器轨道电源状态；只在确认真实设备安全时执行。
Z21UDPTransport().exchange("192.168.0.111", 21105, build_x_set_track_power_off())
```

```python
from z21_lan import build_set_loco_mode, build_x_set_loco_drive, Z21UDPTransport

# 控制短地址 3 的 DCC 28 步机车前进 10/28。
transport = Z21UDPTransport()
transport.exchange("192.168.0.111", 21105, build_set_loco_mode(3, "dcc"), timeout_seconds=0.2)
transport.exchange("192.168.0.111", 21105, build_x_set_loco_drive(3, 10, "forward", speed_steps=28))
```

```python
from z21_lan import (
    Z21UDPTransport,
    build_get_mmdcc_settings,
    build_set_mmdcc_settings,
    decode_datasets,
    parse_mmdcc_settings,
)

transport = Z21UDPTransport()
responses = transport.exchange("192.168.0.111", 21105, build_get_mmdcc_settings())
settings = None
for dataset in decode_datasets(responses[0]):
    if dataset.header == 0x0016:
        settings = parse_mmdcc_settings(dataset.payload)

# 会修改控制器主轨输出电压和编程轨电压；只在确认硬件安全且用户授权时执行。
updated = settings.with_voltages(output_voltage_mv=16000, programming_voltage_mv=16000)
transport.exchange("192.168.0.111", 21105, build_set_mmdcc_settings(updated))
```

```python
from z21_lan import (
    Z21UDPTransport,
    build_get_common_settings,
    build_set_common_settings,
    decode_datasets,
    parse_common_settings,
)

transport = Z21UDPTransport()
responses = transport.exchange("192.168.0.111", 21105, build_get_common_settings())
settings = None
for dataset in decode_datasets(responses[0]):
    if dataset.header == 0x0012:
        settings = parse_common_settings(dataset.payload)

# 会修改控制器是否生成 RailCom cutout；只在确认需要且用户授权时执行。
transport.exchange("192.168.0.111", 21105, build_set_common_settings(settings.with_railcom(True)))
```

## 协议边界

- Z21 LAN 是 UDP 二进制协议，默认端口 `21105`。
- 一个 UDP datagram 可包含多个 dataset，必须按 little-endian `DataLen` 分帧。
- 官方名为 Z21 的标准版控制器、white z21、z21 start 和 Z21 XL 属于同一 Z21 LAN 协议族；商品名只影响默认配置和能力说明，真实能力以硬件信息、固件版本、broadcast flags 和实际返回为准。
- `LAN_SYSTEMSTATE_GETDATA` 是客户端请求 header，实际系统状态数据通过 `LAN_SYSTEMSTATE_DATACHANGED` 返回；调用者不能用请求 header 匹配响应。
- `parse_system_state()` 会同时保留主轨瞬时电流 `main_track_current_ma`、主轨平滑电流 `filtered_main_track_current_ma` 和编程轨电流 `programming_track_current_ma`；界面需要稳定数值时可显示平滑电流，但不能把它当成不同输出通道。
- `parse_system_state()` 中 `supply_voltage_v` 是电源适配器/输入电压，`vcc_voltage_v` 是 Z21 内部电压，官方说明该值等同轨道输出电压；轨道电压显示和功率计算应优先使用 `vcc_voltage_v`。
- `build_x_set_track_power_on()` 和 `build_x_set_track_power_off()` 会改变 Z21 轨道电源状态；调用者必须在真实设备安全且用户授权的前提下使用，并在发送后读取 `LAN_SYSTEMSTATE_DATACHANGED` 或显式轮询 `LAN_SYSTEMSTATE_GETDATA` 确认状态。
- `build_get_loco_mode()` / `build_set_loco_mode()` 对应 Z21 LAN 的短地址机车协议模式读写。`LAN_SET_LOCO_MODE` 中 `0` 表示 DCC，`1` 表示 Motorola；Z21 文档说明长地址 `>=256` 固定为 DCC，调用方不应对长地址设置 Motorola。
- `build_x_set_loco_drive()` 只负责 X-BUS 速度/方向 dataset 编码。DCC 14/28/128 步分别使用 DB0 `0x10/0x12/0x13`；Motorola 模式需要调用方先用 `build_set_loco_mode(address, "motorola")` 设置机车模式，再选择符合控制器语义的速度步进。
- `build_get_mmdcc_settings()` / `build_set_mmdcc_settings()` 对应 Z21 Maintenance Tool 的 MMDCC 设置读写；payload 长度必须为 16 字节，其中 offset `0x0c` 是主轨输出电压 mV，offset `0x0e` 是编程轨电压 mV，均为 little-endian。写入会改变控制器持久配置，调用方必须先读取当前 payload，再只改确认过的字段，最后重新读取 `0x0016` 校验。
- `build_get_common_settings()` / `build_set_common_settings()` 对应 Z21 Maintenance Tool 的 Common Settings 读写；payload 长度必须为 10 字节，其中 offset `0x00` 是 RailCom cutout 开关，`0x01` 表示启用，`0x00` 表示关闭。写入会改变控制器持久配置，调用方必须先读取当前 payload，再只改确认过的字段，最后重新读取 `0x0012` 校验。
- `LAN_SET_BROADCASTFLAGS` 中 RailCom 相关 flags 只控制 RailCom 数据是否转发给当前 LAN 客户端，不是 RailCom cutout 开关。
- 已确认 black Z21 / 标准 Z21 可通过 MMDCC 设置修改主轨和编程轨电压；white z21 / z21 start 不支持独立硬件电压写入，调用方必须按硬件型号和能力声明决定是否开放。
- Z21 POM 字节写入协议没有标准成功回包；调用方应把 UDP 请求发送成功视为“命令已发出”，需要确认时再用 POM 读回或其它反馈机制。
- 本 package 当前不提供限流参数、道岔或反馈模块写操作；这些能力需要独立协议证据和实机验证后再开放。

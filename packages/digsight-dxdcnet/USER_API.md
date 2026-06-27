# digsight_dxdcnet 用户接口说明

`digsight_dxdcnet` 是 Digsight-Center 仓库内的动芯 DXDCNet 协议 helper package，面向需要在 Python 程序中构造、解析或收发 DXDCNet UDP 帧的使用者。当前版本覆盖 UDP 帧编解码、XOR 校验、控制器状态/参数命令、轨道输出命令、机车控制命令、Programmer CV 命令、编程轨状态校验、回包 matcher、UDP transport 和串行 session。

## 本地引用方式

在本仓库中使用时，建议从仓库根目录执行 editable install：

```bash
python3 -m pip install -e packages/digsight-dxdcnet
```

安装后即可直接：

```python
from digsight_dxdcnet.frames import build_udp_frame, decode_udp_frame
```

如果只是临时在本仓库内运行脚本，也可以显式指定源码路径：

```bash
PYTHONPATH="packages/digsight-dxdcnet/src" python3 your_script.py
```

## 命名规范

本 package 的公开 Python API 按 PEP 8 命名：

- 模块名、函数名、方法名、参数名和返回字典字段使用 `snake_case`，例如 `build_udp_frame()`、`param_address`、`current_limit_ma`。
- 类名使用 `PascalCase`，其中协议和行业常见缩写保留大写，例如 `DXDCNetFrame`、`CVReadPlan`、`UDPTransport`、`XORChecksumAlgorithm`。
- 常量使用 `UPPER_SNAKE_CASE`，例如 `CMD_TRACK_OUTPUT`、`SERVICE_MODE_CURRENT_LIMIT_MAX_MA`。
- 文档中若提到协议原始字节或外部资料字段，会明确说明它是协议字段；Python API 本身不使用 camelCase 字段。

## API 总览

| API | 模块 | 作用 | 常见用途 |
|---|---|---|---|
| `D9000_CURRENT_LIMIT_STEP_MA` 等常量 | `digsight_dxdcnet.constants` | DXDCNet 命令字、设备类型、D9000 参数和 Programmer 枚举 | 构造命令、判断回包、参数换算 |
| `DXDCNetFrame` | `digsight_dxdcnet.frames` | 表示解码后的 UDP 帧 | 调试、回包过滤、原始字段保留 |
| `build_udp_frame()` | `digsight_dxdcnet.frames` | 构造 DXDCNet UDP 帧 | 所有命令 builder 的底层封装 |
| `decode_udp_frame()` | `digsight_dxdcnet.frames` | 解析 DXDCNet UDP 帧并校验长度/XOR | 收包解析、matcher |
| `encode_udp_frame()` | `digsight_dxdcnet.frames` | 把 `DXDCNetFrame` 编回 UDP bytes | 测试和调试 |
| `calculate_udp_checksum()` | `digsight_dxdcnet.frames` | 计算 UDP XOR 校验字节 | 校验测试、调试 |
| `NoChecksumAlgorithm` / `XORChecksumAlgorithm` / `checksum_from_name()` | `digsight_dxdcnet.checksum` | 校验策略对象 | 网关 checksum 配置 |
| `build_status_request_frame()` | `digsight_dxdcnet.device_commands` | 构造 `0x22` 设备状态请求 | 读取 command station/booster 状态 |
| `build_track_output_frame()` | `digsight_dxdcnet.device_commands` | 构造 `0x20` 轨道输出控制 | N/HO/G DCC 上电、DC 输出 |
| `build_version_request_frame()` | `digsight_dxdcnet.device_commands` | 构造 `0x84` 版本请求 | 控制器信息读取 |
| `build_mac_request_frame()` | `digsight_dxdcnet.device_commands` | 构造 `0x0B` MAC 请求 | 控制器 MAC 信息读取 |
| `build_parameter_read_frame()` | `digsight_dxdcnet.device_commands` | 构造 `0x41` 参数读取 | D9000 参数读回 |
| `build_parameter_write_frame()` | `digsight_dxdcnet.device_commands` | 构造 `0x40` 参数写入 | D9000 参数写入 |
| `build_request_device_status_payload()` | `digsight_dxdcnet.device_commands` | 构造设备状态请求 payload | 自定义 UDP 帧封装 |
| `build_track_output_payload()` | `digsight_dxdcnet.device_commands` | 构造轨道输出 payload | 自定义 UDP 帧封装 |
| `build_read_parameter_payload()` / `build_write_parameter_payload()` | `digsight_dxdcnet.device_commands` | 构造参数读写 payload | 自定义 UDP 帧封装 |
| `parse_command_station_status()` | `digsight_dxdcnet.device_status` | 解析 command station `0x23` 状态 payload | 编程轨 busy/电流状态 |
| `parse_booster_status()` | `digsight_dxdcnet.device_status` | 解析 booster `0x23` 状态 payload | 轨道电压、电流、模式、告警 |
| `parse_parameter_response()` | `digsight_dxdcnet.device_status` | 解析 `0x42` 参数回包 | 参数读回校验、限流换算 |
| `parse_version_response()` / `format_app_version()` | `digsight_dxdcnet.device_status` | 解析版本回包 | 设备信息展示 |
| `parse_mac_response()` | `digsight_dxdcnet.device_status` | 解析 MAC 回包 | 设备信息展示 |
| `encode_loco_address()` / `decode_loco_address()` | `digsight_dxdcnet.loco_control` | DXDCNet 机车地址低/高字节转换 | 速度/功能/控制权命令 |
| `build_loco_control_request_frame()` | `digsight_dxdcnet.loco_control` | 构造机车控制权请求 | 发起车辆控制前置请求 |
| `build_loco_speed_frame()` | `digsight_dxdcnet.loco_control` | 构造速度/方向命令 | DCC 车辆速度控制 |
| `build_loco_function_frame()` / `build_loco_function_frames()` | `digsight_dxdcnet.loco_control` | 构造单个或多个功能键命令 | F0-F31 控制 |
| `parse_loco_control_ack()` | `digsight_dxdcnet.loco_control` | 解析控制权 ACK | 控制权确认 |
| `parse_loco_speed_feedback()` | `digsight_dxdcnet.loco_control` | 解析速度回包 | 控制反馈 |
| `parse_loco_function_feedback()` | `digsight_dxdcnet.loco_control` | 解析功能键回包 | 功能反馈 |
| `ProgrammerAck` / `ProgrammerValue` | `digsight_dxdcnet.programmer` | Programmer 回包结构 | CV ACK/值读取 |
| `build_cv_read_frame()` / `build_cv_write_frame()` | `digsight_dxdcnet.programmer` | 构造官方 App V3 `0x14` CV 读写帧 | 编程轨 CV、主轨 POM CV |
| `build_programmer_frame()` | `digsight_dxdcnet.programmer` | 构造自定义 Programmer 帧 | 特殊 op/mode 测试 |
| `parse_programmer_ack()` / `parse_programmer_value()` | `digsight_dxdcnet.programmer` | 解析 `0x15`/`0x17` 回包 | CV 写入确认、CV 值读取 |
| `classify_programmer_responses()` | `digsight_dxdcnet.programmer_responses` | 集中分类 `0x15`/`0x17` 回包并收集解析 warning | CV API 需要容忍 malformed 回包时 |
| `ProgrammingTrackStatus` / `ProgrammingTrackSafety` | `digsight_dxdcnet.programming_track` | 表示并校验编程轨静态安全状态 | 发送 CV 命令前的协议级安全检查 |
| `PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED` | `digsight_dxdcnet.programming_track` | 编程轨限流未确认错误文本常量 | 上层错误归一和测试断言 |
| `CVReadPlan` / `CVWritePlan` | `digsight_dxdcnet.programming_track` | 封装 CV 读写请求帧计划 | 上层流程统一生成请求帧 |
| `first_matching_frame()` | `digsight_dxdcnet.matchers` | 从帧列表中找第一个匹配命令/设备类型的帧 | 回包筛选 |
| `build_raw_frame_matcher()` | `digsight_dxdcnet.matchers` | 构造可传给 session 的原始回包 matcher | `exchange(stop_when=...)` |
| `build_programmer_value_matcher()` | `digsight_dxdcnet.matchers` | 构造 CV 值回包 matcher | CV 读取 session 停止条件 |
| `build_programmer_ack_matcher()` | `digsight_dxdcnet.matchers` | 构造 CV ACK 回包 matcher | CV 写入 session 停止条件 |
| `UDPTransport` | `digsight_dxdcnet.udp_transport` | 标准库 UDP transport | 真实设备 UDP 收发 |
| `DXDCNetSessionManager` | `digsight_dxdcnet.session` | 串行化硬件 I/O session | 固定本地 UDP 端口 `6667` 的互斥交换 |

## 公开模块

- `digsight_dxdcnet.constants`：DXDCNet 命令字、设备类型、状态位、Programmer op/mode/ACK 和 D9000 参数常量。
- `digsight_dxdcnet.frames`：DXDCNet UDP 帧编解码、长度字段和 XOR 校验。
- `digsight_dxdcnet.checksum`：校验策略对象。
- `digsight_dxdcnet.device_commands`：控制器状态、版本、MAC、参数和轨道输出命令构造。
- `digsight_dxdcnet.device_status`：状态、版本、MAC 和参数回包解析。
- `digsight_dxdcnet.loco_control`：机车控制权、速度、方向、功能键命令和回包解析。
- `digsight_dxdcnet.programmer`：官方 App V3 兼容的 `0x14` Programmer CV 读写命令和 `0x15`/`0x17` 回包解析。
- `digsight_dxdcnet.programmer_responses`：Programmer value/ACK 回包集中分类、匹配和 malformed payload warning 收集。
- `digsight_dxdcnet.programming_track`：编程轨状态结构、静态安全校验和 CV 请求计划。
- `digsight_dxdcnet.matchers`：可复用回包 matcher。
- `digsight_dxdcnet.udp_transport`：标准库 UDP transport。
- `digsight_dxdcnet.session`：串行化硬件 I/O session，避免同一 UDP 本地端口并发交换。
- `digsight_dxdcnet.api` / `digsight_dxdcnet`：公开 API re-export，适合普通调用方直接导入。

## API 详细说明

### 常量：`digsight_dxdcnet.constants`

常量模块提供已实现命令和参数的数字值，例如：

- 设备类型：`DEVICE_TYPE_COMMAND_STATION`、`DEVICE_TYPE_THROTTLE`、`DEVICE_TYPE_BOOSTER`、`DEVICE_TYPE_SPECIAL`。
- 命令字：`CMD_TRACK_OUTPUT`、`CMD_DEVICE_STATUS`、`CMD_PARAMETER_SET`、`CMD_PARAMETER_READ`、`CMD_PARAMETER_VALUE`、`CMD_LOCO_SPEED`、`CMD_LOCO_FUNCTION`、`CMD_PROGRAM_TRACK_STANDARD`。
- D9000 参数：`D9000_CURRENT_LIMIT_STEP_MA`。
- Programmer 枚举：`PROGRAMMER_OP_MAIN_LOCO_POM`、`PROGRAMMER_MODE_DIRECT_READ`、`PROGRAMMER_MODE_DIRECT_WRITE`、`PROGRAMMER_ACK_ACK` 等。

### `DXDCNetFrame`

`DXDCNetFrame` 是解码后的 UDP 帧结构，保留 `device_type`、`source_id`、`command`、`payload`、`checksum` 和 `checksum_valid`。可使用 `to_debug_dict()` 输出适合日志和 API debug 的原始字段。

### `build_udp_frame(device_type, source_id, command, payload=b"") -> bytes`

构造 DXDCNet UDP 帧。`device_type` 必须在 `0..0x0F`，`source_id` 必须在 `0..0x7F`，`command` 必须在 `0..0xFF`。payload 受协议 4 bit length 字段限制；过长、字段超范围或 payload 字节非法时抛出 `ValueError`。该函数不会静默截断调用方传入的协议字段。

### `decode_udp_frame(raw: bytes) -> DXDCNetFrame`

解析 DXDCNet UDP 帧，校验帧头、长度字段和 XOR。返回的 `DXDCNetFrame.checksum_valid` 表示校验结果；帧头/长度结构不合法时抛出 `ValueError`。

### `encode_udp_frame(frame: DXDCNetFrame) -> bytes`

把 `DXDCNetFrame` 编码回 UDP bytes，适合 round-trip 测试和调试。

### `calculate_udp_checksum(frame_bytes: bytes) -> int`

计算 DXDCNet UDP XOR 校验字节。输入通常是不含最终校验字节的完整帧前缀。

### `NoChecksumAlgorithm` / `XORChecksumAlgorithm` / `checksum_from_name(name)`

校验策略对象。`checksum_from_name("xor")` 返回 XOR 校验策略；`""` 或 `"unconfirmed"` 返回未确认校验策略，调用 `compute()` 时会抛出 `ValueError`，避免把未知校验算法用于真实编码。

### `build_status_request_frame(client_id, target_type, target_id) -> bytes`

构造 `0x22` 设备状态请求帧。常见目标包括 command station `DEVICE_TYPE_COMMAND_STATION, 0` 和 booster `DEVICE_TYPE_BOOSTER, 1`。`target_type` 必须在 `0..0x0F`，`target_id` 必须在 `0..0x7F`；越界时抛出 `ValueError`，不会静默截断。

### `build_track_output_frame(client_id, target_id, powered, output_value, dcc_mode=True, dc_direction_positive=True) -> bytes`

构造 `0x20` 轨道输出命令。`dcc_mode=True` 用于 N/HO/G DCC 输出；`dcc_mode=False` 用于 DC 输出，此时 `dc_direction_positive` 会写入 DC 方向位。

`target_id` 必须在 `0..0x7F`，`output_value` 必须在 `0..0xFF`；越界时抛出 `ValueError`，不会用掩码改写调用方输入。该函数只构造字节，不代表真实轨道可以直接上电。调用方必须确认负载、轨道模式、安全门和用户授权。

### `build_version_request_frame(client_id, target_type, target_id) -> bytes`

构造 `0x84` 版本请求帧。用于读取 command station、core 或 booster/wireless 版本信息。

### `build_mac_request_frame(client_id, target_type, target_id) -> bytes`

构造 `0x0B` MAC 请求帧。回包应使用 `parse_mac_response()` 解析。

### `build_parameter_read_frame(client_id, target_type, target_id, param_address) -> bytes`

构造 `0x41` 参数读取帧。D9000 N/HO/G/DC 限流参数地址分别为 `0x81/0x82/0x83/0x84`。`target_type` 必须在 `0..0x0F`，`target_id` 必须在 `0..0x7F`，`param_address` 必须在 `0..0xFF`。

### `build_parameter_write_frame(client_id, target_type, target_id, param_address, value) -> bytes`

构造 `0x40` 参数写入帧。`value` 必须在 `0..0xFF`；其它目标字段范围同 `build_parameter_read_frame()`。调用方必须在写入后再发送 `0x41` 并解析 `0x42`，确认 `param_address` 和 `value` 一致。

### `build_request_device_status_payload()` / `build_track_output_payload()` / `build_read_parameter_payload()` / `build_write_parameter_payload()`

这些函数只构造对应命令的 payload，不追加 DXDCNet UDP 帧头、长度或 XOR。它们执行与完整 frame builder 相同的字段范围校验，适合调用方需要自行选择 `device_type`、`source_id`、`command` 并用 `build_udp_frame()` 组装完整帧的高级场景。普通调用优先使用上面的 `build_*_frame()` 函数。

### `parse_command_station_status(payload: bytes) -> dict`

解析 command station `0x23` payload，返回总线电压/电流原始值、编程轨电压/电流原始值、编程轨 busy 状态等字段。

### `parse_booster_status(payload: bytes) -> dict`

解析 booster `0x23` payload，返回 `set_voltage_raw`、`output_voltage_v`、`output_current_a`、`temperature_c`、`power_on`、`dcc_mode`、`dc_direction_positive` 和告警位。

### `parse_parameter_response(payload: bytes) -> dict`

解析 `0x42` 参数回包，返回 `param_address` 和原始 `value`。如果参数地址是 `0x81/0x82/0x83/0x84`，会同时返回按 `40 mA` 步进换算的 `current_limit_ma`。

### `parse_version_response(payload: bytes) -> dict` 与 `format_app_version(hardware_raw, software_raw) -> str`

解析版本 payload，返回硬件/软件原始值、字符串值和 App 风格版本号。

### `parse_mac_response(payload: bytes) -> dict`

解析 MAC payload，返回地址类型、原始字节、App 展示顺序字节和十六进制字符串。

### `encode_loco_address(address: int) -> tuple[int, int]` 与 `decode_loco_address(low: int, high: int) -> int`

在 DXDCNet 机车地址的低/高字节表达和整数地址之间转换。当前地址范围按 `1..9999` 校验。

### `build_loco_control_request_frame(client_id, address, request_control=True) -> bytes`

构造机车控制权请求或释放帧。控制权 ACK 使用 `parse_loco_control_ack()` 解析。

### `build_loco_speed_frame(client_id, address, speed, forward=True, speed_mode=SPEED_MODE_128) -> bytes`

构造 DCC 机车速度/方向命令。速度允许 `0..126`，`forward` 表示方向，`speed_mode` 当前常用 `SPEED_MODE_128`。

### `build_loco_function_frame(client_id, address, function_number, active) -> bytes`

构造单个功能键命令。`function_number` 通常为 `0..31`；`active` 表示开/关。

### `build_loco_function_frames(client_id, address, function_states) -> list[bytes]`

批量构造功能键命令。`function_states` 可由上层按功能键号和状态组织，返回多个 frame。

### `parse_loco_control_ack(frame: DXDCNetFrame) -> dict`

解析机车控制权 ACK。命令字、payload 长度或字段不合法时抛出 `ValueError`。
Digsight-Center 应用层会先发送 `0x04` 控制权请求；若收到 `0x07` 且 `granted_id=0` 或授权目标不是当前 throttle，则拒绝继续控制。若短超时内未收到 `0x07`，按已验证参考程序的容错策略继续发送后续速度或功能命令，并在响应中保留 `control_feedback: null` 便于追踪。

### `parse_loco_speed_feedback(frame: DXDCNetFrame) -> dict`

解析速度反馈，返回地址、速度、方向和速度模式等字段。

### `parse_loco_function_feedback(frame: DXDCNetFrame) -> dict`

解析功能键反馈，返回地址、功能键号和状态。

### `ProgrammerAck` 与 `ProgrammerValue`

`ProgrammerAck` 表示 `0x15` ACK 回包，包含 `ack_mode`、`ack_name`、`device_type` 和 `device_id`。`ProgrammerValue` 表示 `0x17` CV 值回包，包含 `mode`、`register`、`cv_number`、`value`、`device_type`、`device_id` 和可选 `pom_address`。

### `build_cv_read_frame(cv_number, client_id=1, op=PROGRAMMER_OP_NORMAL, pom_address=None) -> bytes`

构造官方 App V3 兼容的 `0x14` CV 读取帧。默认是编程轨 direct read；主轨机车 POM 读取使用 `op=PROGRAMMER_OP_MAIN_LOCO_POM` 并提供 `pom_address`。`cv_number` 必须在 `1..1024`，`client_id` 必须在 `0..0x7F`，`op` 必须在 `0..0x07`。

### `build_cv_write_frame(cv_number, value, client_id=1, op=PROGRAMMER_OP_NORMAL, pom_address=None) -> bytes`

构造官方 App V3 兼容的 `0x14` CV 写入帧。默认是编程轨 direct write；主轨机车 POM 写入使用 `op=PROGRAMMER_OP_MAIN_LOCO_POM` 并提供 `pom_address`。`value` 必须在 `0..0xFF`；越界时抛出 `ValueError`，不会按 1 字节掩码截断。

### `build_programmer_frame(client_id, mode, op, register, value, pom_address=None) -> bytes`

底层 Programmer frame 构造函数，适合需要指定 mode/op/register/value 的测试或高级调用。`client_id` 必须在 `0..0x7F`，`mode/op` 必须在 `0..0x07`，`register` 必须在 `0..1023`，`value` 必须在 `0..0xFF`。POM op 必须提供 `pom_address`，非 POM op 不允许提供 `pom_address`。

### `parse_programmer_ack(frame: DXDCNetFrame) -> ProgrammerAck`

解析 `0x15` ACK 回包。错误命令字或 payload 太短时抛出 `ValueError`。

### `parse_programmer_value(frame: DXDCNetFrame) -> ProgrammerValue`

解析 `0x17` CV 值回包。错误命令字、payload 太短或字段不合法时抛出 `ValueError`。

### `classify_programmer_responses(frames, *, client_id, cv_number, pom_address=None) -> ProgrammerResponseClassification`

遍历已解码的 DXDCNet 回包，查找匹配当前手柄 `client_id`、CV 编号和可选 POM 地址的 `ProgrammerValue`，同时查找匹配手柄的 `ProgrammerAck`。返回对象包含：

- `value` / `value_frame`：匹配的 CV 值和原始帧；没有匹配值时为 `None`。
- `ack` / `ack_frame`：匹配的 ACK 和原始帧；没有匹配 ACK 时为 `None`。
- `parse_warnings`：无法解析的 `0x15` 或 `0x17` 回包列表，每项包含 `type`、`detail` 和 `frame` 调试信息。

该函数不会因为单个 malformed programmer 回包抛出异常。上层可以先检查 `value` 或 `ack`，如果二者都为空且 `parse_warnings` 非空，再把它转换为结构化错误。

### `ProgrammingTrackStatus`

编程轨安全状态结构，字段包括 `track_mode`、`dcc_mode`、`programming_track_busy`、`programming_track_current_ma`、`output_value`、`current_limit_ma` 和 `current_limit_confirmed`。

### `ProgrammingTrackSafety.validate(status: ProgrammingTrackStatus) -> None`

执行可复用的编程轨静态安全校验：轨道模式必须是 N/HO/G DCC、编程轨不能 busy、已确认的编程轨限流不能超过 `250 mA`、空闲电流不能超过当前项目使用的安全阈值。失败时抛出 `ValueError`。

该 helper 只做协议状态层面的静态校验；缓存时效性、用户交互确认和真实设备测试边界仍由上层应用负责。

### `PROGRAMMING_TRACK_CURRENT_LIMIT_UNCONFIRMED`

编程轨限流未确认错误文本常量。`ProgrammingTrackSafety.validate()` 只有在 `current_limit_confirmed=True` 且 `current_limit_ma<=0` 时会使用它；若上层控制器没有提供独立编程轨限流字段，可以把 `current_limit_confirmed=False` 作为“无法确认该字段”的状态传入，并依赖编程轨 busy、DCC 模式和空闲电流等其它安全条件。

### `CVReadPlan` 与 `CVWritePlan`

封装 CV 读取/写入请求帧计划。`request_frame(client_id=1)` 返回对应的 `build_cv_read_frame()` 或 `build_cv_write_frame()` 结果。

### `first_matching_frame(frames, command, device_type=None)`

从已解码的 `DXDCNetFrame` 列表中查找第一个命令字和可选设备类型匹配的帧；找不到返回 `None`。

### `build_raw_frame_matcher(command, device_type=None) -> Callable[[bytes], bool]`

构造原始 bytes matcher：解析 UDP 帧、校验 XOR、匹配命令字和可选设备类型。适合传给 `DXDCNetSessionManager.exchange(..., stop_when=...)`。

### `build_programmer_value_matcher(client_id, cv_number, pom_address=None) -> Callable[[bytes], bool]`

构造 CV 值回包 matcher：匹配 `0x17`、client id、CV 编号和可选 POM 地址。

### `build_programmer_ack_matcher(client_id) -> Callable[[bytes], bool]`

构造 CV ACK 回包 matcher：匹配 `0x15` 和 client id。

### `UDPTransport`

标准库 UDP transport，负责向指定 host/port/local_port 发送 bytes 并收集回包。调用方需要配置超时和重试。`request()` 和 `exchange()` 只接受来自请求目标 host 解析出的 IPv4 地址、且来源端口等于目标端口的 UDP 回包；其它来源的 UDP 包会被忽略，直到收到匹配回包或超时。

### `DXDCNetSessionManager.exchange(host, port, request_frame, local_port=0, max_packets=32, stop_when=None)`

串行化硬件 I/O session，避免同一 UDP 本地端口并发交换。`stop_when` 可传入 `digsight_dxdcnet.matchers` 中的 matcher。

## 最小示例

### 构造并解析状态请求帧

```python
from digsight_dxdcnet.constants import DEVICE_TYPE_COMMAND_STATION
from digsight_dxdcnet.device_commands import build_status_request_frame
from digsight_dxdcnet.frames import decode_udp_frame

request = build_status_request_frame(client_id=1, target_type=DEVICE_TYPE_COMMAND_STATION, target_id=0)
frame = decode_udp_frame(request)
assert frame.checksum_valid
print(frame.to_debug_dict())
```

### 构造 HO DCC 轨道通电帧

```python
from digsight_dxdcnet.device_commands import build_track_output_frame

frame = build_track_output_frame(client_id=1, target_id=1, powered=True, output_value=0xA0, dcc_mode=True)
print(frame.hex(" "))
```

`dc_direction_positive` 只在 `dcc_mode=False` 的 DC 轨道输出中生效，用于设置 DXDCNet 轨道输出方向位；它不是 DCC 车辆方向命令，也不涉及车辆地址或 Function。

注意：该示例只构造字节，不代表可以直接对真实轨道上电。真实设备调用必须确认负载、模式、安全门和用户授权。

### 构造 D9000 参数写入帧

```python
from digsight_dxdcnet.device_commands import build_parameter_read_frame, build_parameter_write_frame

# HO 限流参数地址 0x82，原始值 0x64 表示 4000 mA（40 mA 步进）。
write_frame = build_parameter_write_frame(client_id=1, target_type=0, target_id=0, param_address=0x82, value=0x64)
readback_frame = build_parameter_read_frame(client_id=1, target_type=0, target_id=0, param_address=0x82)
print(write_frame.hex(" "))
print(readback_frame.hex(" "))
```

真实设备调用方必须在写入后读取 `0x42` 参数回包并核对 `param_address,value`，不要只根据 `0x40` 写入帧发送成功判断参数已经生效。

### CV 读取命令和 matcher

```python
from digsight_dxdcnet.matchers import build_programmer_value_matcher
from digsight_dxdcnet.programmer import build_cv_read_frame

request = build_cv_read_frame(29, client_id=1)
stop_when = build_programmer_value_matcher(client_id=1, cv_number=29)
print(request.hex(" "))
```

### UDP transport 与 session

```python
from digsight_dxdcnet.session import DXDCNetSessionManager
from digsight_dxdcnet.udp_transport import UDPTransport

transport = UDPTransport(timeout_seconds=0.4, retries=0)
session = DXDCNetSessionManager(transport)
responses = session.exchange("192.0.2.10", 12000, b"...", local_port=6667, max_packets=8)
```

`DXDCNetSessionManager` 会串行化 `exchange()`，适合固定本地 UDP 端口 `6667` 的硬件交换。调用方仍需判断回包命令字、源设备、校验和是否匹配当前请求。

## 参数范围与异常

- `build_udp_frame()` 的 payload 受 DXDCNet 4 bit length 字段限制，过长会抛出 `ValueError`。
- 机车地址当前允许 `1..9999`，速度允许 `0..126`。
- POM 地址允许 `1..9999`，且只在 main-track POM op 中可用。
- D9000 N/HO/G/DC 限流参数地址分别为 `0x81/0x82/0x83/0x84`，当前实测按 `40 mA` 步进换算，参数原始值必须能落在 `0x01..0xFF`。
- 解析函数收到错误命令字、payload 太短或字段不合法时抛出 `ValueError`。

## 协议证据边界

当前实现按 Digsight-Center 已验证路径处理 DXDCNet UDP XOR 校验、官方 Android App V3 的 Programmer `0x14` CV 读写、`0x20` 轨道输出、`0x23` 状态回包和机车 `0x04/0x07/0x10/0x11` 控制链路。若厂商文档、旧 Demo、官方 App 或实机抓包存在冲突，应以实机抓包和真实回包为最高优先级。

## 真实设备风险

本 package 是协议 helper，不替调用方做完整真实设备安全决策。调用方必须在发送轨道通电、速度、方向、功能键、CV 写入或地址写入前完成模式检查、编程轨隔离、限流检查、目标地址确认和用户授权。

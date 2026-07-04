# ESU ECoS Python API

本 package 提供 ESU ECoS/ECoS2 PC Interface 的基础 helper。当前公开 API 覆盖控制器信息读取、System booster 查询/监控/限流写入、轨道电源开关、RailCom/RailComPlus 开关、DCC/Motorola/M4 机车对象查询/创建、机车速度/功能键控制，以及 Service Mode CV 直接读写。

| API | 作用 |
| --- | --- |
| `DEFAULT_ECOS_PORT` | ECoS PC Interface 默认 TCP 端口 `15471`。 |
| `BASIC_INFO_FIELDS` | 基础对象 `1` 的控制器信息字段列表。 |
| `BOOSTER_MANAGER_OBJECT_ID` | Booster manager 对象 ID，当前为 `27`。 |
| `SYSTEM_BOOSTER_OBJECT_ID` | 已验证的 System booster 对象 ID，当前为 `65000`；调用方仍应优先使用 `queryObjects(27, name)` 的结果。 |
| `BOOSTER_MONITOR_FIELDS` | System booster 监控字段列表：`name/status/current/voltage/temperature/limit`。 |
| `build_request_command(object_id, permission)` | 构造 `request(objectId, view/control)` 命令。 |
| `build_release_command(object_id, permission)` | 构造 `release(objectId, view/control)` 命令。 |
| `build_get_command(object_id, fields)` | 构造 `get(objectId, field...)` 命令。 |
| `build_set_command(object_id, options)` | 构造通用 `set(objectId, option...)` 命令。 |
| `build_power_command(powered)` | 构造 `set(1, go|stop)` 轨道电源命令。 |
| `build_railcom_command(enabled)` | 构造基础对象 `1` 的 `set(1, railcom[0|1])` 命令。 |
| `build_railcomplus_command(enabled)` | 构造基础对象 `1` 的 `set(1, railcomplus[0|1])` 命令。 |
| `build_basic_info_commands()` | 构造读取基础对象信息的命令列表。 |
| `build_booster_query_command()` | 构造通过 Booster manager 查询 booster 对象的命令。 |
| `build_booster_monitor_commands(object_id)` | 构造读取 booster `name/status/current/voltage/temperature/limit` 的命令序列。 |
| `build_booster_current_limit_write_commands(object_id, current_limit_ma)` | 构造写入并读回 booster `limit[mA]` 的命令序列。 |
| `build_loco_query_command()` | 构造通过对象 10 查询 DCC 机车对象的命令。 |
| `build_create_loco_command(address, name, protocol='DCC128')` | 构造在对象 10 中创建 DCC 机车对象的命令。 |
| `ecos_loco_protocol_name(control_protocol, speed_steps)` | 把本项目通用车辆协议和速度步进映射为 ECoS 机车对象协议名，例如 `DCC128`、`MM28` 或 `M4`。 |
| `build_loco_speed_command(object_id, speed, direction=None)` | 构造机车对象速度/方向命令。 |
| `build_loco_function_command(object_id, function_number, enabled)` | 构造 F0-F31 功能键命令。 |
| `build_programmer_cv_read_commands(cv_number)` | 构造 programmer object 5 的 direct CV 读取命令序列。 |
| `build_programmer_cv_write_commands(cv_number, value)` | 构造 programmer object 5 的 direct CV 写入命令序列。 |
| `parse_blocks(text)` | 解析 `<REPLY>`/`<EVENT>` 块，保留原始中间行和 `<END>` 状态。 |
| `parse_object_options(line)` | 解析对象行中的 `option[value]` 字段。 |
| `parse_basic_info(text_or_blocks)` | 从基础对象读取结果中提取控制器信息字段。 |
| `parse_booster_query_results(text_or_blocks)` | 从 Booster manager 查询结果中提取 booster 对象列表。 |
| `parse_booster_monitor_info(text_or_blocks, object_id=None)` | 从 booster 监控读取结果中提取指定 booster 的字段。 |
| `parse_loco_query_results(text_or_blocks, address=None)` | 从对象 10 查询结果中提取机车对象。 |
| `parse_programmer_event(text_or_blocks)` | 从 object 5 EVENT 中提取 CV 编程状态和值。 |
| `ECoSTCPTransport.exchange(...)` | 使用 TCP 文本协议发送命令并读取回复文本。 |
| `ECoSSessionManager.exchange(...)` | adapter 使用的会话门面，可注入 fake transport 测试。 |

## 示例

```python
from esu_ecos import build_basic_info_commands, parse_basic_info, ECoSTCPTransport

commands = build_basic_info_commands()
text = ECoSTCPTransport().exchange("192.168.1.50", 15471, commands, expected_replies=2)
info = parse_basic_info(text)
print(info["protocolversion"])
```

```python
from esu_ecos import (
    ECoSTCPTransport,
    build_booster_query_command,
    build_booster_monitor_commands,
    parse_booster_monitor_info,
    parse_booster_query_results,
)

transport = ECoSTCPTransport()
query_text = transport.exchange("192.168.1.50", 15471, [build_booster_query_command()])
boosters = parse_booster_query_results(query_text)
system_booster = next((item for item in boosters if item.get("name") == "System booster"), boosters[0])
commands = build_booster_monitor_commands(system_booster["object_id"])
monitor_text = transport.exchange("192.168.1.50", 15471, commands, expected_replies=len(commands))
monitor = parse_booster_monitor_info(monitor_text, object_id=system_booster["object_id"])
print(monitor["current"], monitor["voltage"], monitor["limit"])
```

```python
from esu_ecos import build_loco_speed_command, build_request_command, build_release_command, ECoSTCPTransport

commands = [
    build_request_command(1001, "control"),
    build_loco_speed_command(1001, 42, direction="forward"),
    build_release_command(1001, "control"),
]
ECoSTCPTransport().exchange("192.168.1.50", 15471, commands, expected_replies=3)
```

```python
from esu_ecos import build_create_loco_command, ecos_loco_protocol_name

# 创建 Motorola 28 步机车对象时，先把通用车辆字段映射为 ECoS 协议名。
protocol = ecos_loco_protocol_name("motorola", 28)
command = build_create_loco_command(3, "MM 3", protocol)
assert command == 'create(10, addr[3], name["MM 3"], protocol[MM28], append)'
```

```python
from esu_ecos import build_railcom_command, build_railcomplus_command

# ECoS 关闭 RailCom 时会联动关闭 RailComPlus；恢复两者时先开 RailCom，再开 RailComPlus。
commands = [
    build_railcom_command(True),
    build_railcomplus_command(True),
]
assert commands == ["set(1, railcom[1])", "set(1, railcomplus[1])"]
```

## 协议边界

- ECoS PC Interface 是 TCP 文本协议，默认端口 `15471`。
- 50200、50210、50220 共用同一 PC Interface 协议族；兼容性应根据控制器回包字段和错误码判断，不应按型号硬编码协议分支。
- 基础对象 `1` 支持 `railcom[0|1]` 和 `railcomplus[0|1]`。实机验证显示关闭 `railcom` 会联动关闭 `railcomplus`；重新开启 `railcom` 不会自动恢复 `railcomplus`，需要再发送 `railcomplus[1]`。
- CV 直接读写通过 programmer object `5` 返回 `<EVENT 5>`；调用者必须读取 EVENT，不能只看 `set(5, ...)` 的 `<REPLY>`。
- `ecos_loco_protocol_name()` 当前支持 `dcc/14 -> DCC14`、`dcc/28 -> DCC28`、`dcc/128 -> DCC128`、`motorola/1 -> MM14`、`motorola/2 -> MM27`、`motorola/28 -> MM28` 和 `m4/128 -> M4`。未列出的组合会抛出 `ValueError`，调用方不应猜测 ECoS 协议字符串。
- System booster 监控通过 Booster manager object `27` 查找；当前实机确认 System booster 常见对象 ID 为 `65000`，但调用方应保留查询路径。
- `limit[mA]` 写入会改变真实控制器的 booster 限流值，必须先 `request(object, control)`，写入后 `get(object, limit)` 读回校验，再 `release(object, control)`。
- ECoS 输出电压由硬件电源设置；本 package 不提供 PC Interface 电压写入 helper。ESU 用户手册中的 “Delaying Short Circuit Detection” 属于控制器设备菜单配置项，当前公开 API 未确认 PC Interface 对应字段，因此本 package 也不提供短路检测延迟写入 helper。
- `set(1, go|stop)`、机车速度、功能键和 CV 写入都会改变真实设备状态；真实设备上必须得到用户明确授权。

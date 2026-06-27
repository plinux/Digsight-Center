# train_dcc 用户接口说明

`train_dcc` 是 Digsight-Center 仓库内的 DCC 协议 helper package，面向需要在 Python 程序中构造或解析 DCC 基础数据的使用者。当前版本覆盖 CV 范围校验、DCC 车辆地址 CV 解析/写入计划，以及 direct-mode service-mode CV packet 构造。

## 本地引用方式

在本仓库中使用时，建议从仓库根目录执行 editable install：

```bash
python3 -m pip install -e packages/train-dcc
```

安装后即可直接：

```python
from train_dcc import dcc_xor, validate_cv_number
```

如果只是临时在本仓库内运行脚本，也可以显式指定源码路径：

```bash
PYTHONPATH="packages/train-dcc/src" python3 your_script.py
```

## 命名规范

本 package 的公开 Python API 按 PEP 8 命名：

- 模块名、函数名、方法名、参数名和返回字典字段使用 `snake_case`，例如 `validate_cv_number()`、`address_type`。
- 类名使用 `PascalCase`，其中 DCC、CV 等行业常见缩写保留大写。
- 常量使用 `UPPER_SNAKE_CASE`。
- 文档中若提到协议原始字段，会明确说明它是协议字段；Python API 本身不使用 camelCase 字段。

## API 总览

| API | 模块 | 作用 | 常见用途 |
|---|---|---|---|
| `validate_cv_number()` | `train_dcc.cv` | 校验 DCC CV 编号是否在 `1..1024` | HTTP/API 入参校验、CV 读写前置检查 |
| `validate_cv_byte()` | `train_dcc.cv` | 校验 CV 字节值是否在 `0..255` | CV 写入值、CV1/CV17/CV18/CV29 解码前检查 |
| `validate_loco_address()` | `train_dcc.address` | 校验本项目车辆控制使用的 DCC 车辆地址是否在 `1..9999` | 车辆速度、方向、功能键控制前置检查 |
| `validate_loco_speed_128()` | `train_dcc.address` | 校验 128 级速度命令是否在 `0..126` | 车辆速度控制前置检查 |
| `decode_vehicle_address()` | `train_dcc.address` | 根据 CV29/CV1/CV17/CV18 解析当前车辆地址 | 地址读取、芯片信息展示 |
| `build_vehicle_address_writes()` | `train_dcc.address` | 生成短地址或长地址的 CV 写入计划 | 地址修改流程 |
| `dcc_xor()` | `train_dcc.packets` | 计算 DCC packet XOR 校验字节 | 字节级 packet 构造和测试 |
| `build_service_mode_cv_verify_packet()` | `train_dcc.packets` | 构造 direct-mode service-mode CV verify packet | DCC 标准 packet 测试向量 |
| `build_service_mode_cv_write_packet()` | `train_dcc.packets` | 构造 direct-mode service-mode CV write packet | DCC 标准 packet 测试向量 |

## 公开模块

- `train_dcc.cv`：CV 编号和值范围校验。
- `train_dcc.address`：DCC 车辆短地址/长地址相关 CV 解析和写入计划。
- `train_dcc.packets`：DCC packet XOR 和 service-mode direct CV packet 构造。
- `train_dcc.api` / `train_dcc`：公开 API re-export，适合普通调用方直接导入。

## API 详细说明

### `validate_cv_number(cv_number: int) -> int`

校验 DCC CV 编号。允许范围为 `1..1024`，参数可转为整数；超出范围或无法转换时抛出 `ValueError`。

```python
from train_dcc import validate_cv_number

cv = validate_cv_number(29)
```

### `validate_cv_byte(value: int) -> int`

校验 CV 字节值。允许范围为 `0..255`，参数可转为整数；超出范围或无法转换时抛出 `ValueError`。

```python
from train_dcc import validate_cv_byte

cv29 = validate_cv_byte(0x20)
```

### `validate_loco_address(value) -> int`

校验车辆控制入口使用的 DCC 车辆地址。允许范围为 `1..9999`，参数可转为整数；超出范围或无法转换时抛出 `ValueError`。

```python
from train_dcc import validate_loco_address

address = validate_loco_address(3)
```

### `validate_loco_speed_128(value) -> int`

校验 128 级车辆速度命令。允许范围为 `0..126`，其中 `0` 表示停止；超出范围或无法转换时抛出 `ValueError`。

```python
from train_dcc import validate_loco_speed_128

speed = validate_loco_speed_128(10)
```

### `decode_vehicle_address(cv29, cv1=None, cv17=None, cv18=None) -> dict`

根据 CV29 bit 5 判断当前使用短地址还是长地址，并返回：

```python
{"address": 2041, "address_type": "long"}
```

短地址需要提供 `cv1`；长地址需要提供 `cv17` 和 `cv18`。CV17 长地址标记位不合法、地址为 0 或 CV 值超出字节范围时抛出 `ValueError`。

```python
from train_dcc import decode_vehicle_address

short_address = decode_vehicle_address(cv29=0, cv1=3)
long_address = decode_vehicle_address(cv29=0x20, cv17=0xC7, cv18=0xF9)
```

### `build_vehicle_address_writes(address: int, cv29: int) -> dict`

生成修改 DCC 车辆地址所需的 CV 写入计划。地址 `1..127` 使用短地址；地址 `128..10239` 使用长地址。

返回示例：

```python
{
  "address": 2041,
  "address_type": "long",
  "writes": [
    {"cv": 17, "value": 0xC7},
    {"cv": 18, "value": 0xF9},
    {"cv": 29, "value": 0x20},
  ],
}
```

调用示例：

```python
from train_dcc import build_vehicle_address_writes

plan = build_vehicle_address_writes(2041, cv29=0)
for item in plan["writes"]:
  print(item["cv"], item["value"])
```

### `dcc_xor(packet_bytes: Iterable[int]) -> int`

计算 DCC packet error-detection XOR 字节。每个输入字节必须在 `0..255`；非法字节会抛出 `ValueError`。

```python
from train_dcc import dcc_xor

checksum = dcc_xor([0x78, 0xEC, 0x1D])
```

### `build_service_mode_cv_verify_packet(cv_number: int, value: int) -> bytes`

构造 direct-mode service-mode CV verify packet，返回已追加 XOR 的 packet bytes。`cv_number` 按 `1..1024` 校验，`value` 按 `0..255` 校验。

```python
from train_dcc import build_service_mode_cv_verify_packet

packet = build_service_mode_cv_verify_packet(29, 0x20)
print(packet.hex(" "))
```

### `build_service_mode_cv_write_packet(cv_number: int, value: int) -> bytes`

构造 direct-mode service-mode CV write packet，返回已追加 XOR 的 packet bytes。`cv_number` 按 `1..1024` 校验，`value` 按 `0..255` 校验。

```python
from train_dcc import build_service_mode_cv_write_packet

packet = build_service_mode_cv_write_packet(29, 0x20)
print(packet.hex(" "))
```

## 协议边界

`train_dcc` 只处理 DCC 层数据，不负责轨道供电、编程轨限流、主轨 POM 目标确认、UDP/CAN 发送或动芯控制器 DXDCNet 封装。真实设备操作必须由上层程序完成隔离、限流、地址确认和用户授权。

当前 package 不是完整 DCC 标准实现；未覆盖的内容包括移动解码器速度/功能完整 packet、附件解码器 packet、RailCom、SUSI/Train Bus 和厂商私有 CV。

# Digsight-Center

Digsight-Center 是一个本地运行的 Web 控制界面，用于通过浏览器管理车辆数据并控制模型铁路控制器。前端使用纯 HTML5、CSS 和原生 JavaScript；本地 Python 网关负责同源 HTTP API、配置导入、本地状态保存和控制器通讯。当前内置 Z21 配置导入和动芯 拾Pro 控制器支持；动芯控制器当前使用 DXDCNet 协议，架构上预留其它配置格式、控制器类型和控制器协议的扩展接口。

详细操作手册见 [manual/MANUAL.html](manual/MANUAL.html)。启动网关后，也可以访问 `http://127.0.0.1:8765/manual/MANUAL.html`。

## 免责声明

本软件不是动芯官方开发的软件，而是模型铁路爱好者开发的本地控制工具。作者已经在自己的模型上测试过 DCC 控制效果，但依然不能保证在任何控制器、解码器、车辆、轨道供电或网络环境下都能正常工作。使用本程序产生的任何后果由使用者自行承担，作者不承担责任。

## 主要功能

- 控制器状态：维护控制器类型和 IP，读取控制器状态、遥测和轨道输出参数。
- 轨道电源：按 N/HO/G/DC 模式执行通电和断电，并通过 Booster 状态回包确认。
- 车辆管理：通过配置导入接口导入当前支持的 Z21 `.z21` 车辆配置文件，管理车辆、图片、分类、功能键和编组；支持缩略视图选择、多选批量删除，以及一键清空全部车辆数据和车辆图片。
- 车辆控制：N/HO/G 使用左右双控制台独立控制车辆，每个控制台可在详细列表和缩略车辆选择之间切换；DC 模式切换为独立电压、方向和急停面板。
- CV 编程：在 N/HO/G DCC 模式下读取芯片信息，读取或写入 CV，读取或写入车辆地址，支持编程轨和主轨目标。
- 控制器设置：查看控制器信息，读取并写入动芯 N/HO/G/DC 限流参数；写入后会读回校验。
- 本地协议包：`train_dcc` 和 `digsight_dxdcnet` 可作为本地 Python package 被其它程序引用。

## 环境要求

- Python 3.10 或更高版本。
- 浏览器：Microsoft Edge、Chrome、Safari 或其它现代浏览器。
- 不需要前端构建步骤；项目默认不依赖外部 CDN。

## 安装

克隆或进入项目目录后即可运行启动脚本。若要让其它 Python 程序直接 import 本项目拆分出的协议包，可以按需执行：

```bash
python3 -m pip install -e packages/train-dcc
python3 -m pip install -e packages/digsight-dxdcnet
```

两个 package 的公开接口说明分别见：

- [packages/train-dcc/USER_API.md](packages/train-dcc/USER_API.md)
- [packages/digsight-dxdcnet/USER_API.md](packages/digsight-dxdcnet/USER_API.md)

## 启动

推荐使用启动脚本，默认监听所有网卡，允许同一局域网内设备访问。脚本会把网关拉起到后台，关闭终端窗口不会停止服务：

```bash
./scripts/start_web.sh
```

如果系统默认的 `python3` 不符合版本要求，可以直接指定其它 Python 3.10+ 解释器：

```bash
./scripts/start_web.sh --python python3.11
```

首次启动且本地车辆库为空时，网关会为 N、HO、G 三种比例分别创建地址 `3`、地址 `4` 两台测试车，以及一个 `3+4` 重联控制车。它们只用于初始化，不包含任何导入配置数据；后续可在页面中删除、批量删除、清空车辆库或重新导入配置。

也可以直接运行 Python 入口，请使用 Python 3.10+ 解释器。若没有执行上面的 editable install，需要临时指定本地 package 源码路径：

```bash
PYTHONPATH="packages/train-dcc/src:packages/digsight-dxdcnet/src" python3.10 -m server.main
```

本机访问：

```text
http://127.0.0.1:8765/
```

局域网内其它设备访问：

```text
http://<运行本项目的主机局域网 IP>:8765/
```

如需限制为仅本机访问：

```bash
./scripts/start_web.sh -H 127.0.0.1
```

如需修改监听端口：

```bash
./scripts/start_web.sh -P 8877
```

监听地址和端口可以同时指定：

```bash
./scripts/start_web.sh -H 0.0.0.0 -P 8765
```

`-H 0.0.0.0` 表示监听全部 IPv4 网卡；如需监听 IPv6，可使用 `--host ::` 或具体 IPv6 地址：

```bash
./scripts/start_web.sh --host :: --port 8765
```

网关会拒绝未信任 DNS Host 发起的状态变更请求。通过 IP 地址访问不需要额外参数；如果确实需要通过局域网域名或 mDNS 名称访问，启动时显式加入可信 Host：

```bash
./scripts/start_web.sh -H 0.0.0.0 -P 8765 --trusted-host layout.local
```

健康检查：

```bash
curl http://127.0.0.1:8765/api/health
```

启动日志和 PID 文件默认写入：

```text
data/digsight-center-web.log
data/digsight-center-web.pid
```

## 安全说明

默认监听 `0.0.0.0` 时，同一局域网内设备可以打开页面。网关面向可信局域网使用，用户界面不要求输入操作令牌；服务端会拒绝明显跨站的状态变更请求，并要求 JSON 状态变更接口使用 `application/json`。打开页面后应先连接或读取控制器状态，再手动执行轨道通电。危险或不可逆操作使用普通确认提示，后端仍执行模式、状态、安全快照和参数范围等服务端安全门。配置导入、车辆图片和 JSON API 都有请求体大小限制，超限会返回结构化错误。

## 可手动修改的配置

修改配置文件前建议先停止网关，避免页面操作和手工编辑同时写入同一个文件。所有配置文件都必须保持合法 JSON；修改后重新打开页面或重新读取相关数据即可生效。

如果当前控制器配置 JSON 损坏，页面会在状态栏报错，详情中提示手工修复该文件，或点击顶部“重置”恢复默认值。点击“重置”前会先弹出确认框，并逐项列出本次会重置的文件；确认后只会重置当前选择控制器的配置文件。只有全局运行态文件也被检测为损坏时，确认框和重置结果中才会同时包含 `data/app-state.json`。

常用配置路径：

- `data/app-state.json`：运行态状态，保存当前选择的控制器类型、轨道模式、CV 编程目标和遥测缓存；不保存具体控制器 IP。
- `config/controllers/Digsight_D9000.json`：动芯 D9000/拾Pro 控制器运行态配置。首次启动时如果文件不存在，网关会从 `data/vehicles.sqlite3` 中的控制器默认配置生成它；公开仓库不跟踪该 JSON 文件。它保存控制器显示名称、使用协议、控制器 IP、UDP 目标端口、本地 UDP 端口、校验算法、轨道输出参数和控制器私有设置。页面顶部控制器下拉框显示 `display_name`，IP 输入框读取和写入这个文件；公开默认 IP 为 `0.0.0.0`。当前已知的 D9000 默认通信参数为目标 UDP `12000`、本地 UDP `6667`、校验算法 `xor`；如果手工改错，可以按下面示例改回，或在页面点击“重置”重新生成当前控制器配置。
- `config/cv/manufacturers.json`：CV8 厂家 ID 到厂家名称的列表。
- `config/cv/profile-map.json`：CV8 厂家 ID 到厂商 profile 文件名的映射。
- `config/cv/standard.json`：标准 CV 名称和 CV 范围说明。
- `config/cv/profiles/*.json`：厂商专用 CV 名称、复位方法和厂商说明。

当前控制器选择示例：

```json
{
  "controller": {
    "kind": "digsight_controller",
    "track_mode": "n",
    "programming_target": "programming_track"
  }
}
```

动芯 D9000/拾Pro 控制器配置示例：

```json
{
  "display_name": "动芯 拾Pro",
  "ip": "<controller-ip>",
  "protocol": "DXDCNet",
  "settings": {},
  "transport": {
    "kind": "udp",
    "udp_port": 12000,
    "local_udp_port": 6667,
    "udp_checksum_algorithm": "xor"
  }
}
```

每种控制器使用自己的运行态配置文件。控制器显示名、协议、IP、transport 端口和校验算法都从该文件读取；后续如果厂商固件改变默认端口，优先手工修改对应控制器配置文件，不需要改代码。同一种协议可以被多个控制器配置复用，例如后续多个控制器都可声明使用 `DXDCNet` 或其它协议。

## 二次开发扩展

项目内保留了代码级样例，验证通用架构可以接入多种控制器和多种配置导入格式，也供后续开发者参考：

- `server/controllers/example.py`：样例控制器 adapter。它演示控制器 `kind`、`protocol`、配置文件名、能力声明、transport descriptor、endpoint readiness、配置字段说明和 readiness 钩子应该放在哪里。
- `server/importers/example.py`：样例配置导入 adapter。它演示导入格式 descriptor、扩展名、分类合并策略和把外部字节解析成规范化车辆/功能键/分类/编组/来源摘要的返回边界。

这两个样例都不会注册到默认 registry，也不会出现在前端控制器或导入格式下拉框中。新增真实控制器或导入格式时，应复制样例的接口形态创建独立 adapter，再显式注册到对应 registry，并补充专用测试和文档；不要把某个协议或某种导入格式写进通用 HTTP API 或前端主流程。

CV 厂家名称配置示例：

```json
{
  "known_ids": {
    "86": "Wekomm Engineering, GmbH",
    "250": "自定义厂家"
  },
  "unassigned_notes": {
    "8": "未分配厂家 ID 8；8 常见为写入 CV8 的复位值"
  }
}
```

CV profile 映射示例：

```json
{
  "manufacturer_profiles": {
    "86": "okdcc",
    "250": "my-decoder"
  }
}
```

厂商 profile 文件放在 `config/cv/profiles/my-decoder.json`，文件名主干要和 `profile-map.json` 中的值一致。要让“读取已知CV”自动读取某个 CV，必须把该 CV 写进 `cv_definitions`；`cv_ranges` 只用于给完整扫描或自定义读取补充显示含义。

详细字段说明见 [manual/MANUAL.html](manual/MANUAL.html) 的“可编辑配置文件”章节。

## 停止

使用停止脚本关闭后台网关：

```bash
./scripts/stop_web.sh
```

如果直接运行带 `PYTHONPATH` 的 `python3.10 -m server.main`，它仍然是前台进程，按 `Ctrl-C` 停止。

## 测试

使用 Python 3.10+ 解释器执行测试；下面用 `python3` 表示已经满足版本要求的解释器。如果系统默认 `python3` 低于 3.10，请替换为 `python3.10`、`python3.11` 或其它符合要求的命令。测试可以直接使用仓库内的本地协议 package，不需要先执行 editable install；运行测试前把项目根目录和两个 package 的 `src` 目录加入 `PYTHONPATH` 即可。

```bash
python3 -m pip install -r requirements-dev.txt
export PYTHONPATH="$PWD:$PWD/packages/train-dcc/src:$PWD/packages/digsight-dxdcnet/src${PYTHONPATH:+:$PYTHONPATH}"
python3 -m unittest discover -s tests -v
python3 scripts/check_coverage.py
for file in assets/js/*.js; do node --check "$file" || exit 1; done
python3 -m compileall server tests packages
```

默认单元测试使用 mock 和仓库内 `tests/fixtures/` 数据，不需要真实控制器或本机私有文件。真实控制器 IP 不写入公开测试或文档；需要在自己的环境中验证真实控制器探测测试时，使用测试专用环境变量，不需要修改运行态控制器配置文件：

```bash
export DIGSIGHT_TEST_D9000_IP="<controller-ip>"
python3 -m unittest tests.server_tests.test_controller_probe -v
```

`DIGSIGHT_TEST_D9000_IP` 只被测试帮助模块读取，不影响页面运行时配置。未设置该变量时，真实硬件测试会跳过。需要额外使用本地 Z21 导出文件做导入回归时，再通过环境变量传入：

```bash
export DIGSIGHT_TEST_Z21_HO_FILE="<ho-z21-file-path>"
export DIGSIGHT_TEST_Z21_N_FILE="<n-z21-file-path>"
python3 -m unittest tests.server_tests.test_optional_external_inputs -v
```

如果要向本项目贡献代码，测试覆盖率必须满足：函数覆盖率 100%、行覆盖率 90%、分支覆盖率 80%。

# Digsight-Center

Digsight-Center 是一个本地运行的 Web 控制界面，用于通过浏览器管理车辆数据、编辑 DCC 音效工程并控制模型铁路控制器。前端使用纯 HTML5、CSS 和原生 JavaScript；本地 Python 网关负责同源 HTTP API、配置导入、音效工程解析、本地状态保存和控制器通讯。当前内置 Z21 配置导入、动芯 DCC 音效工程解析、动芯 拾Pro 控制器支持、ESU ECoS 50200 系列控制器支持和 Z21 LAN 控制器支持；动芯控制器当前使用 DXDCNet 协议，架构上预留其它配置格式、控制器类型、音效芯片和控制器协议的扩展接口。

详细操作手册见 [manual/MANUAL.html](manual/MANUAL.html)。启动网关后，也可以访问 `http://127.0.0.1:8765/manual/MANUAL.html`。

## 免责声明

本软件不是动芯官方开发的软件，而是模型铁路爱好者开发的本地控制工具。作者已经在自己的模型上测试过 DCC 控制效果，但依然不能保证在任何控制器、解码器、车辆、轨道供电或网络环境下都能正常工作。使用本程序产生的任何后果由使用者自行承担，作者不承担责任。

## 主要功能

- 控制器状态：维护控制器类型和各控制器独立 IP，读取控制器状态与遥测；支持控制器设置的 adapter 可把轨道输出参数和 RailCom 等私有设置写入控制器，尚未实现硬件写入的 adapter 仍可保存本地目标电压，不同控制器可显示不同的信息表。顶部控制器状态栏会固定在窗口上方，页面滚动时仍能看到状态摘要和错误详情入口。
- 轨道电源：当前动芯 拾Pro 支持按 N/HO/G/DC 模式执行通电和断电，并通过 Booster 状态回包确认；Z21 系列支持官方 LAN_X 轨道通断电命令，并通过系统状态读回确认；ESU ECoS 使用 PC Interface 的 `set(1, go/stop)` 控制轨道电源。
- 车辆管理：通过配置导入接口导入当前支持的 Z21 `.z21` 车辆配置文件，管理车辆、图片、分类、功能键和编组；支持缩略视图选择、多选批量删除，以及一键清空全部车辆数据和车辆图片。
- 音效编辑：导入动芯 `.dxsd` 或 5313/5323 旧 `.dxsp` 音效工程，查看并编辑 Slot、节点、连接、音频文件和功能键 CV 映射摘要；官方下载 `.zip` 只是下载容器，需要先解压出 `.dxsd` 或 `.dxsp` 后再导入。音效编辑不跟随当前选择的控制器，用户通过页面上的“芯片”下拉框选择目标芯片 profile；导入后会根据工程中的芯片型号自动选择对应 profile。60 系 6003/6005/6006/6008 音效空间按 64Mb 计算并固定 16 个 Slot，音频按 44100Hz、12bit、单声道校验；8 系 8004 按 128Mb 计算，8003/8005/8006/8008 按 256Mb 计算并固定 64 个 Slot，音频按 44100Hz、16bit、单声道校验；5313/5323 固定 28 个 Slot 但容量仍未确认；旧 `.dxsp` 没有节点图，页面在右侧 Slot 属性中编辑播放方式、音量和 File_0/File_1/File_2，循环发声对应启动段、循环段、结束段，不会伪造节点和连接。页面显示总空间、已用空间和剩余空间，统一按小写 bit/Mb 显示；固定 Slot 按芯片型号预创建，不提供新增或删除 Slot 入口，但可清空当前 Slot 的全部节点和连接；切换到 Slot 更少或容量更小的芯片时会提示裁剪和容量风险，确认后会删除目标芯片不支持的 Slot。每个 Slot 行可直接输入映射的 DCC 功能键，留空表示未映射，0 表示 F0，1-68 对应 F1-F68；60 系样例里的 CV 默认表可能包含 Slot17-Slot60 默认值，但界面只显示实际存在的 Slot；导出 `.dxsd` 时未映射写 255，F0 写 0。节点图固定在窗口内，支持缩放、滚轮缩放、拖拽平移、横纵滚动条、拖动节点、拖拽调整节点大小、拖拽连接端点、添加节点和添加连接；Slot 列表和右侧属性栏可以拖动调宽。只选中 Slot 且未选中具体节点或连接时，右侧属性栏会显示 Slot 属性，以及默认折叠的“Slot 内节点”“Slot 内连接”两个栏目；展开后可逐项查看和编辑。点击画布上的具体节点后，属性栏只显示该节点属性；点击连接后，属性栏只显示该连接属性。节点图可切换到框选模式，框选后右键复制、粘贴或删除选中的节点和连接。当前音效包文件可查看引用位置、按列排序、按 bit 查看大小、试听、暂停、继续播放、删除未引用文件、一键删除所有未使用音效、替换音效或把音效入库到音效库分类；属性面板中当前节点引用的音效也可试听，未选中具体节点时可在“Slot 内节点”的展开项中试听对应节点音效。底部库拆分为音效库和 Slot 库，入库后的 WAV 和 Slot 结构会落到运行态 `data/sound-library.json`，刷新页面后仍可继续使用；当前 Slot 可入库到动力单元、鸣笛、机械单元、行驶音效、联控音效或广播音效分类，后续可应用到当前 Slot。导入工程内的裸 PCM 音频会在试听时临时包装成浏览器可播放的 WAV，不改变工程导出使用的原始音频数据。上传音频只接受 WAV，并按目标芯片 profile 校验采样率、位深、声道数和已知容量；导出前会按当前芯片容量拦截超容量工程，提示先删除音效；关闭或刷新页面前如果存在未导出的音效编辑，浏览器会提示确认。导出时按芯片系列生成可刷写工具识别的工程后缀：60/80 系列为 `.dxsd`，5313/5323 为 `.dxsp`；本项目只生成本地工程文件，不直接向真实芯片刷写。
- 车辆控制：N/HO/G 使用左右双控制台独立控制车辆，每个控制台可在详细列表和缩略车辆选择之间切换；车辆可保存控制协议和速度级，Z21/ECoS 会按 DCC、Motorola 或 M4 等组合组装控制器命令，动芯只允许已验证的 DCC 128 路径；DC 模式仅动芯控制器可选，会切换为独立电压、方向和急停面板。
- CV 编程：在 N/HO/G DCC 模式下读取芯片信息，读取或写入 CV，读取或写入车辆地址，支持编程轨和主轨目标；Z21 支持 Service Mode 和主轨 POM byte 读写，ECoS 当前支持编程轨 direct CV 读写。
- 控制器设置：查看控制器信息，读取并写入动芯 N/HO/G/DC 限流参数和 RailCom 开关；写入后会读回校验。Z21 标准版和 Z21 XL 在本地保存 N/HO/G 主轨目标电压，切换到相应比例时通过 MMDCC 写入该比例主轨电压；编程轨电压是独立固定设置，默认 16V，同步写入并读回校验；z21 start 只保存本地目标电压。ESU ECoS 输出电压由硬件电源决定，页面不显示电压配置；N/HO/G 轨道输出参数显示并写入 System booster 的限流值，默认 4000mA，并保存本地短路检测延迟设置。所有控制器的轨道输出参数区域都提供“重置”按钮，按数据库默认值恢复当前控制器可编辑参数。Z21/ECoS 不支持 DC 模式，轨道输出参数中不显示 DC 项；Z21 支持 RailCom 开关写入，ECoS 支持 RailCom 和 RailComPlus 开关写入，关闭 RailCom 会同步关闭 RailComPlus。
- 本地协议包：`train_dcc`、`digsight_dxdcnet`、`esu_ecos` 和 `z21_lan` 可作为本地 Python package 被其它程序引用。

## 环境要求

- Python 3.10 或更高版本。
- 浏览器：Microsoft Edge、Chrome、Safari 或其它现代浏览器。
- 不需要前端构建步骤；项目默认不依赖外部 CDN。

## 安装

克隆或进入项目目录后即可运行启动脚本。若要让其它 Python 程序直接 import 本项目拆分出的协议包，可以按需执行：

```bash
python3 -m pip install -e packages/train-dcc
python3 -m pip install -e packages/digsight-dxdcnet
python3 -m pip install -e packages/esu-ecos
python3 -m pip install -e packages/z21-lan
```

四个本地协议 package 的公开接口说明分别见：

- [packages/train-dcc/USER_API.md](packages/train-dcc/USER_API.md)
- [packages/digsight-dxdcnet/USER_API.md](packages/digsight-dxdcnet/USER_API.md)
- [packages/esu-ecos/USER_API.md](packages/esu-ecos/USER_API.md)
- [packages/z21-lan/USER_API.md](packages/z21-lan/USER_API.md)

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
PYTHONPATH="packages/train-dcc/src:packages/digsight-dxdcnet/src:packages/esu-ecos/src:packages/z21-lan/src" python3.10 -m server.main
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

默认监听 `0.0.0.0` 时，同一局域网内设备可以打开页面。网关面向可信局域网使用，用户界面不要求输入操作令牌；服务端会拒绝明显跨站的状态变更请求，并要求 JSON 状态变更接口使用 `application/json`。打开页面后应先连接或读取控制器状态，再手动执行轨道通电。危险或不可逆操作使用普通确认提示，后端仍执行模式、状态、安全快照和参数范围等服务端安全门。配置导入、音效工程导入、车辆图片和 JSON API 都有请求体大小限制，超限会返回结构化错误。音效编辑不依赖当前控制器选择，只解析 `.dxsd` 和 `.dxsp` 音效工程；官方 zip 需要先解压后再导入其中的工程文件。上传音频必须是 WAV，生成时会按页面选择的目标芯片校验格式和已知容量；已确认容量的芯片会作为生成门禁，固定 Slot 中未使用的位置不会生成占位音频；导出时 60/80 系列生成 `.dxsd`，5313/5323 生成 `.dxsp`。该页面不发送控制器通讯或芯片刷写命令。

## 可手动修改的配置

修改配置文件前建议先停止网关，避免页面操作和手工编辑同时写入同一个文件。所有配置文件都必须保持合法 JSON；修改后重新打开页面或重新读取相关数据即可生效。

如果当前控制器配置 JSON 损坏，页面会在状态栏报错，详情中提示手工修复该文件，或点击顶部“重置”恢复默认值。点击“重置”前会先弹出确认框，并逐项列出本次会重置的文件；确认后只会重置当前选择控制器的配置文件。只有全局运行态文件也被检测为损坏时，确认框和重置结果中才会同时包含 `data/app-state.json`。

常用配置路径：

- `data/app-state.json`：运行态状态，保存当前选择的控制器类型、轨道模式、CV 编程目标和遥测缓存；不保存具体控制器 IP。
- `config/controllers/Digsight_D9000.json`：动芯 D9000/拾Pro 控制器运行态配置。首次启动时如果文件不存在，网关会从 `data/vehicles.sqlite3` 中的控制器默认配置生成它；公开仓库不跟踪该 JSON 文件。它保存控制器显示名称、使用协议、控制器 IP、UDP 目标端口、本地 UDP 端口、校验算法、轨道输出参数和控制器私有设置，例如 `settings.railcom_enabled`。页面顶部控制器下拉框显示 `display_name`，IP 输入框读取和写入这个文件；公开默认 IP 为 `0.0.0.0`。当前已知的 D9000 默认通信参数为目标 UDP `12000`、本地 UDP `6667`、校验算法 `xor`；如果手工改错，可以按下面示例改回，或在页面点击“重置”重新生成当前控制器配置。
- `config/controllers/ESU_ECoS_50200.json`：ESU ECoS 50200/50210/50220 共用的运行态配置，使用 `ECoS` 协议和 TCP `15471` 端口；当前开放控制器信息、轨道通断电、数码车辆速度/方向/功能键、编程轨 direct CV 读写、System booster 限流写入、RailCom 和 RailComPlus 开关写入，不支持 DC 模式。ECoS 输出电压由硬件电源设置，页面只把电压作为控制器信息中的只读遥测显示；轨道输出参数只显示 N/HO/G 的限流输入，默认 4000mA；短路检测延迟保存为本地配置，默认 0ms，页面提示不同 Booster 类型的建议值。关闭 RailCom 会同步关闭 RailComPlus；单独开启 RailComPlus 时页面会同时启用 RailCom。
- `config/controllers/Z21.json`、`config/controllers/Z21_Start.json`、`config/controllers/Z21_XL.json`：Z21 LAN 控制器运行态配置，使用 UDP `21105` 端口；当前开放控制器信息读取、轨道通断电、数码车辆速度/方向/功能键、Service Mode CV、主轨 POM byte 读写和 RailCom 开关写入，不支持 DC 模式，电流/限流配置项不显示。`Z21.json` 对应官方名为 Z21 的标准版控制器，也就是常说的黑盒版本；Z21 标准版和 Z21 XL 保存 N/HO/G 主轨目标电压时只更新本地目标值，切换到对应比例时会通过 MMDCC 写入该比例主轨输出电压，同时写入独立的编程轨电压并读回校验；z21 start 按官方工具能力说明只保存本地目标电压。N/HO/G 主轨目标电压和编程轨电压默认均为 16V。
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

每种控制器使用自己的运行态配置文件。控制器显示名、协议、IP、transport 端口和校验算法都从该文件读取；后续如果厂商固件改变默认端口，优先手工修改对应控制器配置文件，不需要改代码。同一种协议可以被多个控制器配置复用，例如 ESU ECoS 50200、50210 和 50220 使用同一个 `ECoS` 配置和协议。

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

使用 Python 3.10+ 解释器执行测试；下面用 `python3` 表示已经满足版本要求的解释器。如果系统默认 `python3` 低于 3.10，请替换为 `python3.10`、`python3.11` 或其它符合要求的命令。测试可以直接使用仓库内的本地协议 package，不需要先执行 editable install；运行测试前把项目根目录和四个 package 的 `src` 目录加入 `PYTHONPATH` 即可。

```bash
python3 -m pip install -r requirements-dev.txt
export PYTHONPATH="$PWD:$PWD/packages/train-dcc/src:$PWD/packages/digsight-dxdcnet/src:$PWD/packages/esu-ecos/src:$PWD/packages/z21-lan/src${PYTHONPATH:+:$PYTHONPATH}"
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

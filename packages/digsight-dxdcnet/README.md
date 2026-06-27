# digsight-dxdcnet

`digsight-dxdcnet` 是 Digsight-Center 项目拆出的动芯 DXDCNet 协议辅助包，供其它 Python 程序独立安装和引用。

## 安装

在仓库根目录执行：

```bash
python3 -m pip install packages/digsight-dxdcnet
```

## 引用

```python
from digsight_dxdcnet import build_track_output_frame, decode_udp_frame
```

完整用户接口说明见 [USER_API.md](USER_API.md)。

真实 UDP 收发请使用 `UDPTransport` 或 `DXDCNetSessionManager`；回包来源校验、超时和串行化规则见用户接口说明。

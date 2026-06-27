# train-dcc

`train-dcc` 是 Digsight-Center 项目拆出的 DCC 协议辅助包，供其它 Python 程序独立安装和引用。

## 安装

在仓库根目录执行：

```bash
python3 -m pip install packages/train-dcc
```

## 引用

```python
from train_dcc import build_service_mode_cv_write_packet, build_vehicle_address_writes
```

完整用户接口说明见 [USER_API.md](USER_API.md)。

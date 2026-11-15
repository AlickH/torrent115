# Torrent115 Native FPK

Torrent115 的 fnOS Native 进程版打包工程：不依赖 Docker，使用商店依赖 `python312` 运行。

## 结构

```
fnos-native/
├── manifest              # install_dep_apps=python312，统一网关入口
├── config/               # package 用户 / 数据目录声明
├── cmd/                  # 生命周期：venv 初始化、gunicorn 启停
├── app/ui/config         # iframe + gatewayPrefix + gatewaySocket
├── app/server/           # 构建时放入 Python 代码、static、wheelhouse
├── wizard/install        # 管理员账号/密码
├── wheelhouse/{x86,arm}  # 离线 Python 依赖
└── build.sh
```

## 构建

```bash
# x86
bash fnos-native/build.sh 0.12.1 x86

# arm64
bash fnos-native/build.sh 0.12.1 arm
```

产物：`artifacts/release/Torrent115-native-<版本>-<arch>.fpk`

wheelhouse 需要提前准备：

```bash
python3 -m pip download -r requirements-native.txt --only-binary=:all: \
  --platform manylinux2014_x86_64 --python-version 312 --implementation cp --abi cp312 \
  -d fnos-native/wheelhouse/x86

python3 -m pip download -r requirements-native.txt --only-binary=:all: \
  --platform manylinux2014_aarch64 --python-version 312 --implementation cp --abi cp312 \
  -d fnos-native/wheelhouse/arm
```

## 安装与运行

1. 应用中心手动安装 fpk（需要先安装商店依赖 Python 3.12）；
2. 安装向导设置管理员账号密码；
3. 应用中心启动后通过 `/app/torrent115` 网关访问；
4. 数据目录：`/vol1/@appdata/torrent115`；
5. 升级时保留数据，venv 会按新 wheelhouse 重装依赖。

## 与 Docker 版的区别

- 无 Docker、无宿主机 systemd 服务；
- package 用户运行，不申请 root；
- 使用统一网关，不暴露端口；
- aria2/Transmission 移动文件由进程在授权目录内直接执行；
- 默认不依赖 fnOS 下载中心 socket。

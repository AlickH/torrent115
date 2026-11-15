# Torrent115 fnOS FPK

飞牛 fnOS 的 Docker 类应用包工程，生成带离线镜像的 `.fpk`，安装后由应用中心管理启停。

## 构建

在 fnOS NAS 上执行（需要本机已有 `torrent115:latest` 镜像）：

```bash
bash fnos/build.sh 0.1.0
# 产物：artifacts/release/Torrent115-0.1.0.fpk
```

构建脚本会：

1. 把 `torrent115:latest` 打成 `torrent115:<版本>` 并导出为 `app/docker/torrent115-image.tar.gz`；
2. 写入 `cmd/offline-image.env`（镜像标签/架构/ID/SHA）；
3. 在 compose 中加 `pull_policy: never`，安装时从包内导入镜像；
4. 调用 `fnpack build` 生成 fpk。

## 安装

```bash
appcenter-cli install-fpk artifacts/release/Torrent115-0.1.0.fpk
```

或在「应用中心 → 手动安装」选择 fpk。

安装后会创建：

- 应用目录：`/var/apps/torrent115`
- 数据目录：`/vol1/@appdata/torrent115/data`（映射到容器 `/data`）
- 桌面入口：`Torrent115`，端口 `8099`

## 数据迁移（从 docker compose 部署切换）

```bash
appcenter-cli stop torrent115
cp -a /vol1/1000/TorrentTo115/data/config.json \
      /vol1/1000/TorrentTo115/data/auto_state.json \
      /vol1/@appdata/torrent115/data/
appcenter-cli start torrent115
```

## 升级

1. 更新镜像并重新构建 fpk（版本号递增）；
2. 使用升级脚本（会先备份数据）：

```bash
bash fnos/upgrade.sh artifacts/release/Torrent115-0.2.0.fpk
```

也可以从应用中心「手动安装」覆盖升级。

> 注意：当前 fnOS 的 `appcenter-cli install-fpk` 在应用已安装时不会执行升级，只会提示 `is installed`；脚本通过「备份数据 → 卸载 → 安装 → 恢复数据 → 启动」完成升级。

## 已知限制

- 默认使用 host 网络，`manifest` 中 `checkport=false`；
- 本地下载器（fnOS 下载中心 qBittorrent）默认未挂载 socket，需要手动修改 `app/docker/docker-compose.yaml` 并重新打包；
- 目前仅构建 x86 架构包（`platform=x86`），ARM 设备需要自行准备 arm64 镜像。

## 宿主机脚本代理（aria2/Transmission 移动文件）

qBittorrent 通过 API 移动；aria2/Transmission 没有移动 API，App 会把移动请求写入
`/vol1/@appdata/torrent115/data/hooks/pending/`，由宿主机代理脚本执行。

安装：

```bash
bash fnos/install-agent.sh
```

代理只允许移动 `/vol1/` 下的路径，执行完成后写回 `hooks/done/`，App 再删除下载器任务。

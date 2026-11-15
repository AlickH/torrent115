# Torrent115 Native FPK 计划

目标：把 Torrent115 从 Docker 类 FPK 改为 Native 进程类 FPK，满足 fnOS 应用商店发布要求。

## 设计决策

- [x] 运行时使用商店依赖 `python312`（`install_dep_apps=python312`）
- [x] 不依赖 Docker
- [x] 不安装任何宿主机 systemd 服务 / 不修改系统目录
- [x] 应用以 package 用户运行
- [x] 使用统一网关（`gatewayPrefix` + `gatewaySocket`），不暴露端口
- [x] 配置/状态放 `TRIM_PKGVAR`，代码放 `TRIM_APPDEST`
- [x] Python 依赖打包为离线 wheelhouse，安装时建 venv，不联网
- [x] 默认不启用 qBittorrent socket，本地下载器由用户配置 WebUI 等方式
- [x] aria2/Transmission 移动文件改由 Native 进程直接执行（在授权目录内）
- [x] x86 / arm64 双架构包

## 阶段 1：工程骨架

- [x] 创建 `fnos-native/` 工程目录
- [x] `manifest`：appname、version、install_dep_apps=python312、网关入口
- [x] `config/privilege`：run-as package
- [x] `config/resource`：数据目录声明
- [x] `app/ui/config`：iframe + gatewayPrefix + gatewaySocket
- [x] `cmd/main`：start/stop/status（gunicorn + unix socket）
- [x] `cmd/install_callback` / `upgrade_callback`：创建 venv 并离线安装依赖
- [x] `wizard/install`：管理员账号/密码
- [ ] 图标

## 阶段 2：应用适配

- [x] `app.py` 抽出 `start_runtime()`，供 WSGI 和开发模式共用
- [x] 新增 `wsgi.py`，gunicorn 入口
- [x] `DATA_DIR` 改为 `TRIM_PKGVAR/data`
- [ ] 静态目录按安装目录读取
- [ ] 默认配置调整：bitmagnet 默认关闭、本地下载器默认不依赖 socket
- [ ] 首次启动使用向导设置的管理员账号密码
- [ ] 移除 Docker 专有逻辑（volume、qbt socket 挂载假设）

## 阶段 3：依赖打包

- [x] `requirements-native.txt`
- [x] `fnos-native/build-wheelhouse.sh`（x86/arm）
- [ ] 验证 Flask/requests/requests-unixsocket/gunicorn/psycopg2/Brotli wheel
- [ ] 安装时 venv 创建与离线安装脚本

## 阶段 4：构建与安装测试

- [x] `fnos-native/build.sh` 生成 x86 fpk
- [x] 卸载 Docker 版，安装 Native 版
- [x] 验证应用中心状态、桌面入口、统一网关访问
- [x] 验证登录、搜索、追剧、设置、数据迁移
- [x] 验证升级流程与数据保留
- [x] 生成 arm64 包

## 阶段 5：商店发布准备

- [ ] 应用名称/简介/分类/标签
- [ ] 图标 64/256
- [ ] 截图
- [ ] 隐私说明与使用条款
- [ ] LICENSE
- [ ] 移除 host agent、Docker 相关文档
- [ ] x86/arm 双包与版本策略
- [ ] GitHub Release 附件

## 回滚方案

- [ ] 保留 Docker 版 fpk 与 compose 文件
- [ ] 数据目录 `/vol1/@appdata/torrent115/data` 在卸载前后备份
- [ ] Native 版异常时可重新安装 Docker 版并恢复数据

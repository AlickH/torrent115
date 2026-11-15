# Torrent115

磁力搜索 → 115 云下载 → 追剧自动转存的轻量 Web 应用。

Flask 后端 + Ant Design 5 / React 前端，部署在 fnOS NAS 上，通过 115 云下载把搜索结果转存到网盘，并支持按日历自动追剧。

## 功能

- 多来源磁力搜索：PanSou（115 分享/磁力）、TPB(apibay)、Nyaa、动漫花园、BTSearch、EZTV、knaben、therarbg、bitmagnet
- 搜索词自动解析（TMDB / IMDb），中文标题自动翻译成英文再查
- 结果按来源分 tab、去重、合并展示，支持复制磁力和一键发送到 115 云下载
- 追剧/电影自动转存：
  - Trakt 日历 + TMDB 回退
  - 多预设（清晰度、编码、体积、种子数、严格匹配、离线等待超时等）
  - AI 排序、自定义源优先级、种子分档、体积偏好
  - 串行检查、失败/停滞自动重试、已完成记录
- 115 云下载：
  - 磁力/分享链接转存
  - 云下载任务进度、停滞检测、自动换候选
  - 转存完成后自动触发 Drivemby 刷新
- 本地下载器联动（可选）：
  - 同时把磁力加入 fnOS 下载中心（qBittorrent）
  - 115 与本地谁先完成就保留谁，另一边自动清理
  - 本地完成后自动移动到 `Downloads/Done`
- 115 扫码登录、Cookie 管理、账号密码修改
- 移动端自适应、深色模式

## 技术栈

- 后端：Python 3.12 / Flask
- 前端：React 18 + Vite + Ant Design 5
- 部署：Docker（host 网络）
- 数据：`data/config.json`、`data/auto_state.json`

## 快速开始

### 1. 构建前端

```bash
cd web
npm install
npm run build
cd ..
rm -rf static && cp -r web/dist static
```

### 2. 构建并启动

```bash
docker build -t torrent115:latest .
docker compose up -d
```

访问 `http://<NAS-IP>:8099`，默认账号 `admin / admin`，首次登录后请立即修改。

也可以直接用 Docker Compose 构建：

```bash
docker compose up -d --build
```

### 3. 配置

在页面「设置」里配置：

- 115 Cookie（支持扫码登录）
- TMDB API Key（搜索解析、追剧日历）
- Trakt Client ID / OAuth（追剧日历，可选）
- PanSou / bitmagnet 地址
- 出站代理（可选，用于访问 TMDB/Trakt/部分源）

配置文件位于 `data/config.json`，其中包含 Cookie、Token 等敏感信息，不会提交到仓库。

## 目录结构

```
.
├── app.py              # 应用入口、鉴权、监控循环、静态资源
├── routes.py           # API 路由
├── config.py           # 配置默认值/读写
├── search.py           # 多源搜索、TMDB/IMDb 解析
├── tracker.py          # 追剧自动转存、日历、重试、清理
├── p115.py             # 115 API、任务、文件链
├── net.py              # HTTP 请求（代理优先）
├── drivemby.py         # Drivemby 通知与刷新
├── localtorrent.py     # 本地 qBittorrent 客户端（可选）
├── web/                # 前端源码（React + Vite）
├── static/             # 前端构建产物
├── Dockerfile
└── docker-compose.yml
```

## 可选：本地下载器（fnOS 下载中心）

默认只使用 115 云下载。若 NAS 上启用了 fnOS 下载中心，可以挂载它的 qBittorrent unix socket：

```yaml
volumes:
  - ./data:/data
  - /usr/trim/var/downloadcenter/1000/qbt.sock:/run/qbt.sock
```

并从 qBittorrent 的 WebUI 密码文件读取凭据到 `data/qbt_webui_password`（详见 `localtorrent.py`）。

启用后，预设里打开「同时添加本地下载器」即可双投；115 与本地下载哪个先完成就保留哪个。

## 可选：bitmagnet 直连数据库

bitmagnet 来源默认通过 PostgreSQL 直连查询：

- 地址：`127.0.0.1:5433`
- 数据库：`bitmagnet`
- 用户/密码：`postgres / postgres`

可在 `data/config.json` 中修改 `bitmagnet_db_*`。

## 注意

- 本项目仅供个人 NAS 使用，请遵守当地法律法规和网盘服务条款；
- 115 Cookie、API Key 等敏感信息只保存在本机 `data/`，请勿提交或分享；
- 使用 host 网络是为了访问 115、tracker、本地服务；如需端口映射可自行调整。

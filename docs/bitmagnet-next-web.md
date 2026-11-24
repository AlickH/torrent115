# Bitmagnet-Next-Web 部署记录

上游项目：<https://github.com/journey-ad/Bitmagnet-Next-Web>

用来给本机的 bitmagnet 种子库提供网页搜索界面，和 fnOS 上的 bitmagnet 共用同一个 PostgreSQL。

## 部署形态

- 镜像：本地构建 `bitmagnet-next-web:patched`（上游代码 + 下列修复）
- 网络：`network_mode: host`，监听 `0.0.0.0:3000`
- 数据库：`postgres://postgres:postgres@127.0.0.1:5433/bitmagnet`
- 容器名：`bitmagnet-next-web`，`restart: unless-stopped`
- compose 文件：`/vol1/1000/Bitmagnet/docker-compose.yml`
- 源码与构建目录：`/vol1/1000/Bitmagnet/next-web-src`

访问地址：`http://<NAS 局域网 IP>:3000`

## 为什么不用官方镜像

官方镜像的依赖是按当时的版本锁定的，直接用源码重新构建会失败，且上游还存在搜索逻辑缺陷。本地构建时做了以下修改。

## 修改清单

### 1. Docker 构建

- `npm install` 增加 `--legacy-peer-deps`：`@nextui-org/react` 与锁死的 `@nextui-org/theme`/`system` 版本冲突（ERESOLVE）
- `@nextui-org/theme`、`@nextui-org/system` 由 `2.2.5`/`2.2.1` 改为 `^2.4.0`：否则 `@nextui-org/input-otp` 找不到 `inputOtp` 导出，webpack 编译失败
- 删除 `COPY --from=builder /app/.next/server ./.next/server`：standalone 产物里已经包含该目录，上游这行会导致构建报 `not found`
- 新增构建参数 `NPM_REGISTRY`，国内构建使用镜像源

### 2. 搜索逻辑（上游 issue #22）

`app/api/graphql/service.ts` 原来把可选关键词拼成 `(A OR B OR TRUE)`，整段恒真，可选关键词完全不参与过滤和排序。改为：

- 必需关键词仍然 `AND` 过滤
- 可选关键词改为相关度打分，`ORDER BY` 中优先命中词更多的结果
- 计数查询只使用必需关键词，占位符重新从 `$1` 编号（否则 PostgreSQL 报 `could not determine data type of parameter`）

效果：`matrix 1999` 前几条均为同时命中两个词的资源，而 `matrix zzzqqq` 仍然返回 `matrix` 的结果（可选词不过滤）。

### 3. 搜索分页状态（`app/search/page.tsx`）

上游用模块级变量 `cachedSearchOption` / `totalCount` 缓存「是否新搜索」，多用户或多标签页并发时会串数据，翻页还会漏掉总数导致分页器只剩 1 页。改为每次请求都带总数，去掉模块级状态。

### 4. 详情页（上游 issue #23）

`app/detail/[hash64]/page.tsx` 在接口返回空数据时会因为读取 `data.name` 抛异常，表现为「详情页有错误」。改为数据缺失时走 `notFound()`，返回 404。

## 构建与更新

```bash
cd /vol1/1000/Bitmagnet/next-web-src
docker build --build-arg NPM_REGISTRY=https://registry.npmmirror.com \
  -t bitmagnet-next-web:patched .
cd /vol1/1000/Bitmagnet
docker compose up -d bitmagnet-next-web
```

## 依赖写入

bitmagnet 容器访问 TMDB 需要走代理，`docker-compose.yml` 中已通过 `HTTP_PROXY`/`HTTPS_PROXY` 指向本机 ShellCrash，并把 `resolv.conf` 改回公共 DNS，避免 fake-ip 与 DHT 冲突。

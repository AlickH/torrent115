# 前端（React + Ant Design 5）

构建：

```bash
cd web
npm install --registry=https://registry.npmmirror.com
npm run build
rm -rf ../static && cp -r dist ../static
```

然后重新构建并启动后端容器：

```bash
cd ..
docker build --network host -t torrent115:latest .
docker compose up -d --no-build --force-recreate
```

后端 `app.py` 只负责 `/static/*` 静态文件与 `/` 首页，逻辑与之前一致。

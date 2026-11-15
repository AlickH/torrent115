#!/usr/bin/env python3
"""本地下载器客户端：qBittorrent / aria2 / Transmission。

统一接口：
  add_magnet(magnet, savepath)  添加磁力
  torrents(hashes)              查询任务（key 为 infohash）
  all()                         全部任务
  delete(hashes, delete_files)  删除任务
  set_location(hashes, path)    移动任务文件（仅 qBittorrent 支持）
"""
import json
import os
import shutil
import time
import urllib.parse
import uuid

import requests
import requests_unixsocket

SOCK = "/run/qbt.sock"
PW_FILE = "/data/qbt_webui_password"
HOOK_DIR = "/data/hooks"
USER = "admin"


class BaseClient:
    supports_move = False

    def __init__(self, cfg=None):
        self.cfg = cfg or {}
        self.ok = False

    def login(self):
        return False

    def add_magnet(self, magnet, savepath=None):
        raise NotImplementedError

    def torrents(self, hashes):
        return {}

    def all(self):
        return list(self.torrents([]).values())

    def delete(self, hashes, delete_files=False):
        return False

    def set_location(self, hashes, location):
        return False

    def add_tags(self, hashes, tags):
        return False


class LocalQbt(BaseClient):
    """qBittorrent：fnOS 下载中心 unix socket 或 WebUI TCP。"""

    supports_move = True

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.mode = self.cfg.get("local_client") or "qbt_local"
        if self.mode == "qbt_webui":
            self.session = requests.Session()
            self.base = (self.cfg.get("local_qbt_url") or "http://127.0.0.1:8080").rstrip("/")
            self.user = self.cfg.get("local_qbt_user") or USER
            self.password = self.cfg.get("local_qbt_password") or ""
        else:
            self.session = requests_unixsocket.Session()
            sock = self.cfg.get("local_qbt_sock") or SOCK
            self.base = "http+unix://" + urllib.parse.quote(sock, safe="")
            self.user = USER
            self.password = None

    def login(self):
        if self.mode != "qbt_webui":
            try:
                self.password = open(PW_FILE, encoding="utf-8").read().strip()
            except Exception:
                return False
        try:
            r = self.session.post(self.base + "/api/v2/auth/login",
                                  data={"username": self.user, "password": self.password}, timeout=10)
            self.ok = r.status_code == 200 and r.text.strip() == "Ok."
        except Exception:
            self.ok = False
        return self.ok

    def _get(self, path, **params):
        return self.session.get(self.base + path, params=params, timeout=15)

    def _post(self, path, **data):
        return self.session.post(self.base + path, data=data, timeout=15)

    def _ready(self):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")

    def add_magnet(self, magnet, savepath=None):
        self._ready()
        r = self._post("/api/v2/torrents/add", urls=magnet, savepath=savepath or "")
        if r.status_code not in (200, 201):
            raise RuntimeError(f"本地下载器添加失败: HTTP {r.status_code}")
        return True

    def _torrents(self, hashes=None):
        self._ready()
        hs = "|".join(h for h in (hashes or []) if h)
        r = self._get("/api/v2/torrents/info", hashes=hs)
        if r.status_code != 200:
            return []
        return r.json() or []

    def torrents(self, hashes):
        return {(t.get("hash") or "").lower(): t for t in self._torrents(hashes)}

    def all(self):
        return self._torrents(None)

    def set_location(self, hashes, location):
        self._ready()
        hs = "|".join(h for h in hashes if h)
        r = self._post("/api/v2/torrents/setLocation", hashes=hs, location=location)
        return r.status_code == 200

    def add_tags(self, hashes, tags):
        self._ready()
        hs = "|".join(h for h in hashes if h)
        r = self._post("/api/v2/torrents/addTags", hashes=hs, tags=tags)
        return r.status_code == 200

    def delete(self, hashes, delete_files=False):
        self._ready()
        hs = "|".join(h for h in hashes if h)
        r = self._post("/api/v2/torrents/delete", hashes=hs,
                       deleteFiles="true" if delete_files else "false")
        return r.status_code == 200


def _progress(done, total):
    try:
        return float(done) / float(total) if float(total) > 0 else 0.0
    except Exception:
        return 0.0


class Aria2Client(BaseClient):
    """aria2 JSON-RPC。"""

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.url = self.cfg.get("aria2_url") or "http://127.0.0.1:6800/jsonrpc"
        self.secret = self.cfg.get("aria2_secret") or ""

    def _rpc(self, method, params=None):
        p = ([f"token:{self.secret}"] if self.secret else []) + list(params or [])
        r = requests.post(self.url, json={"jsonrpc": "2.0", "id": "t115", "method": method, "params": p}, timeout=10)
        r.raise_for_status()
        d = r.json()
        if d.get("error"):
            raise RuntimeError(d["error"].get("message") or "aria2 RPC 错误")
        return d.get("result")

    def login(self):
        try:
            self._rpc("aria2.getVersion")
            self.ok = True
        except Exception:
            self.ok = False
        return self.ok

    def add_magnet(self, magnet, savepath=None):
        if not self.ok and not self.login():
            raise RuntimeError("aria2 未就绪")
        opts = {"dir": savepath} if savepath else {}
        self._rpc("aria2.addUri", [[magnet], opts])
        return True

    def _status(self, gid):
        return self._rpc("aria2.tellStatus", [gid, [
            "gid", "status", "totalLength", "completedLength", "downloadSpeed",
            "infoHash", "dir", "files", "bittorrent", "errorMessage",
        ]])

    def _gids(self):
        out = []
        for method in ("aria2.tellActive", "aria2.tellWaiting", "aria2.tellStopped"):
            args = [] if method == "aria2.tellActive" else [0, 1000]
            try:
                out.extend(self._rpc(method, args) or [])
            except Exception:
                pass
        return out

    def torrents(self, hashes):
        if not self.ok and not self.login():
            return {}
        wanted = {(h or "").lower() for h in (hashes or []) if h}
        out = {}
        for item in self._gids():
            gid = item.get("gid")
            if not gid:
                continue
            try:
                st = self._status(gid)
            except Exception:
                continue
            h = (st.get("infoHash") or "").lower()
            if not h or (wanted and h not in wanted):
                continue
            files = st.get("files") or []
            name = ((st.get("bittorrent") or {}).get("info") or {}).get("name") or ""
            if not name and files:
                name = (files[0].get("path") or "").split("/")[-1]
            state = st.get("status") or ""
            out[h] = {
                "hash": h,
                "name": name,
                "progress": _progress(st.get("completedLength"), st.get("totalLength")),
                "state": {"active": "downloading", "waiting": "queued",
                          "paused": "paused", "complete": "uploading",
                          "error": "error", "removed": "removed"}.get(state, state),
                "save_path": st.get("dir") or "",
                "content_path": (files[0].get("path") if files else ""),
                "size": int(st.get("totalLength") or 0),
                "tags": "",
            }
        return out

    def delete(self, hashes, delete_files=False):
        if not self.ok and not self.login():
            return False
        for h in hashes:
            for item in self._gids():
                if (item.get("infoHash") or "").lower() != (h or "").lower():
                    continue
                gid = item.get("gid")
                try:
                    self._rpc("aria2.remove", [gid])
                except Exception:
                    pass
                try:
                    self._rpc("aria2.removeDownloadResult", [gid])
                except Exception:
                    pass
        return True


class TransmissionClient(BaseClient):
    """Transmission RPC。"""

    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.url = self.cfg.get("transmission_url") or "http://127.0.0.1:9091/transmission/rpc"
        self.user = self.cfg.get("transmission_user") or ""
        self.password = self.cfg.get("transmission_password") or ""
        self.session = requests.Session()
        self.session_id = ""
        if self.user:
            self.session.auth = (self.user, self.password)

    def _post(self, payload):
        headers = {"X-Transmission-Session-Id": self.session_id} if self.session_id else {}
        r = self.session.post(self.url, json=payload, headers=headers, timeout=10)
        if r.status_code == 409:
            self.session_id = r.headers.get("X-Transmission-Session-Id", "")
            headers = {"X-Transmission-Session-Id": self.session_id}
            r = self.session.post(self.url, json=payload, headers=headers, timeout=10)
        r.raise_for_status()
        d = r.json()
        if d.get("result") != "success":
            raise RuntimeError(d.get("result") or "Transmission RPC 错误")
        return d.get("arguments") or {}

    def login(self):
        try:
            self._post({"method": "session-get"})
            self.ok = True
        except Exception:
            self.ok = False
        return self.ok

    def add_magnet(self, magnet, savepath=None):
        if not self.ok and not self.login():
            raise RuntimeError("Transmission 未就绪")
        args = {"filename": magnet}
        if savepath:
            args["download-dir"] = savepath
        self._post({"method": "torrent-add", "arguments": args})
        return True

    def torrents(self, hashes):
        if not self.ok and not self.login():
            return {}
        args = self._post({"method": "torrent-get", "arguments": {"fields": [
            "id", "name", "hashString", "percentDone", "status", "downloadDir",
            "totalSize", "rateDownload", "labels",
        ]}})
        wanted = {(h or "").lower() for h in (hashes or []) if h}
        out = {}
        for t in args.get("torrents") or []:
            h = (t.get("hashString") or "").lower()
            if not h or (wanted and h not in wanted):
                continue
            st = t.get("status")
            out[h] = {
                "hash": h,
                "name": t.get("name") or "",
                "progress": float(t.get("percentDone") or 0),
                "state": {0: "paused", 1: "checking", 2: "downloading",
                          3: "uploading", 4: "queued", 5: "queued", 6: "downloading"}.get(st, str(st)),
                "save_path": t.get("downloadDir") or "",
                "content_path": "",
                "size": int(t.get("totalSize") or 0),
                "tags": ",".join(t.get("labels") or []),
            }
        return out

    def delete(self, hashes, delete_files=False):
        if not self.ok and not self.login():
            return False
        args = self._post({"method": "torrent-get", "arguments": {"fields": ["id", "hashString"]}})
        ids = [t.get("id") for t in (args.get("torrents") or [])
               if (t.get("hashString") or "").lower() in {(h or "").lower() for h in hashes}]
        if ids:
            self._post({"method": "torrent-remove",
                        "arguments": {"ids": ids, "delete-local-data": bool(delete_files)}})
        return True


def make_client(cfg=None):
    mode = (cfg or {}).get("local_client") or "qbt_local"
    if mode == "aria2":
        return Aria2Client(cfg)
    if mode == "transmission":
        return TransmissionClient(cfg)
    return LocalQbt(cfg)


def is_completed(t):
    if not t:
        return False
    return (float(t.get("progress") or 0) >= 0.999 or
            t.get("state") in ("uploading", "stalledUP", "pausedUP", "queuedUP", "forcedUP"))


def has_progress(t):
    if not t:
        return False
    return float(t.get("progress") or 0) > 0 or is_completed(t)


def _hook_paths():
    pending = os.path.join(HOOK_DIR, "pending")
    done = os.path.join(HOOK_DIR, "done")
    os.makedirs(pending, exist_ok=True)
    os.makedirs(done, exist_ok=True)
    return pending, done


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, path)


def _submit_host_move(cfg, t):
    pending, _ = _hook_paths()
    index_path = os.path.join(HOOK_DIR, "pending.json")
    index = _load_json(index_path, {})
    h = (t.get("hash") or "").lower()
    if h in index:
        return
    src = (t.get("content_path") or "").strip()
    if not src:
        name = (t.get("name") or "").strip()
        src = os.path.join((t.get("save_path") or "").strip(), name) if name else ""
    dst = (cfg.get("local_done_path") or "").strip()
    if not src or not dst:
        return
    job_id = uuid.uuid4().hex
    job = {"id": job_id, "action": "move", "src": src, "dst": dst,
           "hash": h, "client": (cfg.get("local_client") or ""), "created": int(time.time())}
    _save_json(os.path.join(pending, job_id + ".json"), job)
    index[h] = job_id
    _save_json(index_path, index)


def _poll_host_moves(cfg, client):
    _, done = _hook_paths()
    index_path = os.path.join(HOOK_DIR, "pending.json")
    index = _load_json(index_path, {})
    for h, job_id in list(index.items()):
        result = os.path.join(done, job_id + ".json")
        if not os.path.exists(result):
            continue
        data = _load_json(result, {})
        if data.get("ok"):
            try:
                client.delete([h])
            except Exception:
                pass
            index.pop(h, None)
            _save_json(index_path, index)
            try:
                os.remove(result)
            except Exception:
                pass
        else:
            # 失败保留结果，等下一次重试前由宿主机脚本再次执行
            pass


def move_completed(cfg):
    """移动已完成的本地下载：qBittorrent 走 API，aria2/Transmission 走宿主机脚本队列。"""
    if not cfg.get("local_move_enabled"):
        return 0
    done = (cfg.get("local_done_path") or "").strip()
    if not done:
        return 0
    q = make_client(cfg)
    if not q.supports_move:
        if not q.login():
            return 0
        for t in q.all():
            if is_completed(t):
                _submit_host_move(cfg, t)
        _poll_host_moves(cfg, q)
        return 0
    if not q.login():
        return 0
    moved = 0
    for t in q.all():
        if not is_completed(t):
            continue
        tags = (t.get("tags") or "").split(",")
        if "moved" in [x.strip() for x in tags]:
            continue
        h = (t.get("hash") or "").lower()
        if not h:
            continue
        save = (t.get("save_path") or "").rstrip("/")
        if save == done.rstrip("/"):
            q.add_tags([h], "moved")
            continue
        if q.set_location([h], done):
            q.add_tags([h], "moved")
            moved += 1
    return moved

#!/usr/bin/env python3
"""内置 BT 下载器：App 内 qBittorrent-nox，通过 unix socket WebUI 管理。"""
import os
import threading
import requests
import requests_unixsocket

SOCK = os.environ.get("T115_QBT_SOCK", "/data/qbt.sock")
BASE = "http+unix://" + requests.utils.quote(SOCK, safe="")
AUTH = ("admin", "t115pass")
_s = requests.Session()
_s.mount("http+unix://", requests_unixsocket.UnixAdapter())
_lock = threading.Lock()
_logged = False


def _login():
    global _logged
    with _lock:
        if _logged:
            return True
        try:
            r = _s.post(f"{BASE}/api/v2/auth/login", data={"username": AUTH[0], "password": AUTH[1]}, timeout=10)
            _logged = r.status_code == 200 and r.text.strip() == "Ok."
        except requests.RequestException:
            _logged = False
        return _logged


def _get(path, **kw):
    if not _login():
        raise RuntimeError("qBittorrent 未就绪")
    r = _s.get(BASE + path, timeout=20, **kw)
    r.raise_for_status()
    return r.json() if r.content else None


def _post(path, **kw):
    if not _login():
        raise RuntimeError("qBittorrent 未就绪")
    r = _s.post(BASE + path, timeout=30, **kw)
    r.raise_for_status()
    return r


def add_magnet(cfg, magnet):
    path = (os.environ.get("T115_DOWNLOAD_DIR") or cfg.get("local_save_path") or "/data/downloads").strip()
    os.makedirs(path, exist_ok=True)
    category = "t115"
    _post("/api/v2/torrents/add", data={"urls": magnet, "savepath": path, "category": category})
    return True


def _map(t):
    states = {"downloading": "downloading", "stalledDL": "downloading", "metaDL": "metadata",
              "pausedDL": "paused", "queuedDL": "queued", "uploading": "seeding", "stalledUP": "seeding",
              "pausedUP": "paused", "queuedUP": "queued", "checkingDL": "checking", "checkingUP": "checking",
              "error": "error", "missingFiles": "error"}
    return {
        "hash": (t.get("hash") or "").lower(),
        "name": t.get("name") or "",
        "progress": round(float(t.get("progress") or 0) * 100, 1),
        "state": states.get(t.get("state"), t.get("state") or ""),
        "download_rate": int(t.get("dlspeed") or 0),
        "upload_rate": int(t.get("upspeed") or 0),
        "total": int(t.get("size") or 0),
        "done": int(t.get("completed") or 0),
        "seeders": int(t.get("num_seeds") or 0),
        "peers": int(t.get("num_leechs") or 0) + int(t.get("num_seeds") or 0),
        "save_path": t.get("save_path") or "",
    }


def tasks():
    data = _get("/api/v2/torrents/info") or []
    return [_map(t) for t in data]


def _hash(hash_):
    return (hash_ or "").lower()


def pause(hash_):
    _post("/api/v2/torrents/pause", data={"hashes": _hash(hash_)})
    return True


def resume(hash_):
    _post("/api/v2/torrents/resume", data={"hashes": _hash(hash_)})
    return True


def delete(hash_, delete_files=False):
    _post("/api/v2/torrents/delete", data={"hashes": _hash(hash_), "deleteFiles": "true" if delete_files else "false"})
    return True

def detail(hash_):
    h = _hash(hash_)
    props = _get(f"/api/v2/torrents/properties?hash={h}") or {}
    trackers = _get(f"/api/v2/torrents/trackers?hash={h}") or []
    peers = _get(f"/api/v2/sync/torrentPeers?hash={h}") or {}
    return {"properties": props, "trackers": trackers, "peers": peers.get("peers", {})}

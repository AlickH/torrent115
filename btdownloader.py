#!/usr/bin/env python3
"""内置 BT 下载器：通过本机 Transmission RPC 管理。"""
import os
import threading
import requests

RPC = "http://127.0.0.1:9092/transmission/rpc"
AUTH = ("t115", "t115pass")
_s = requests.Session()
_s.auth = AUTH
_sid = ""
_lock = threading.Lock()


def _call(method, arguments=None):
    global _sid
    with _lock:
        for _ in range(2):
            r = _s.post(RPC, json={"method": method, "arguments": arguments or {}}, timeout=20,
                        headers={"X-Transmission-Session-Id": _sid})
            if r.status_code == 409:
                _sid = r.headers.get("X-Transmission-Session-Id", "")
                continue
            r.raise_for_status()
            data = r.json()
            if data.get("result") != "success":
                raise RuntimeError(data.get("result") or "Transmission RPC 失败")
            return data.get("arguments") or {}
    raise RuntimeError("Transmission RPC 会话初始化失败")


def add_magnet(cfg, magnet):
    path = (os.environ.get("T115_DOWNLOAD_DIR") or cfg.get("local_save_path") or "/data/downloads").strip()
    os.makedirs(path, exist_ok=True)
    _call("torrent-add", {"filename": magnet, "download-dir": path, "paused": False})
    return True


def tasks():
    args = _call("torrent-get", {"fields": ["id", "name", "hashString", "percentDone", "status", "rateDownload",
                                             "rateUpload", "totalSize", "peersSendingToWe", "peersGettingFromUs",
                                             "downloadDir", "leftUntilDone"]})
    out = []
    states = {0: "paused", 1: "checking", 2: "checking", 3: "metadata", 4: "downloading", 5: "queued", 6: "seeding"}
    for t in args.get("torrents", []):
        out.append({
            "hash": t.get("hashString", ""),
            "id": t.get("id"),
            "name": t.get("name") or "",
            "progress": round(float(t.get("percentDone") or 0) * 100, 1),
            "state": states.get(t.get("status"), "unknown"),
            "download_rate": int(t.get("rateDownload") or 0),
            "upload_rate": int(t.get("rateUpload") or 0),
            "total": int(t.get("totalSize") or 0),
            "done": int(t.get("totalSize") or 0) - int(t.get("leftUntilDone") or 0),
            "seeders": 0, "peers": int(t.get("peersSendingToWe") or 0),
            "save_path": t.get("downloadDir") or "",
        })
    return out


def _id(hash_):
    for t in tasks():
        if t["hash"].lower() == (hash_ or "").lower():
            return t["id"]
    return None


def pause(hash_):
    i = _id(hash_)
    if i is None:
        return False
    _call("torrent-stop", {"ids": [i]})
    return True


def resume(hash_):
    i = _id(hash_)
    if i is None:
        return False
    _call("torrent-start", {"ids": [i]})
    return True


def delete(hash_, delete_files=False):
    i = _id(hash_)
    if i is None:
        return False
    _call("torrent-remove", {"ids": [i], "delete-local-data": bool(delete_files)})
    return True

#!/usr/bin/env python3
"""本地 qBittorrent（fnOS 下载中心）客户端：通过 unix socket 操作。"""
import os
import urllib.parse

import requests_unixsocket

SOCK = "/run/qbt.sock"
PW_FILE = "/data/qbt_webui_password"
USER = "admin"


class LocalQbt:
    def __init__(self):
        self.session = requests_unixsocket.Session()
        self.base = "http+unix://" + urllib.parse.quote(SOCK, safe="")
        self.ok = False

    def login(self):
        try:
            pw = open(PW_FILE, encoding="utf-8").read().strip()
        except Exception:
            return False
        try:
            r = self.session.post(self.base + "/api/v2/auth/login",
                                  data={"username": USER, "password": pw}, timeout=10)
            self.ok = r.status_code == 200 and r.text.strip() == "Ok."
        except Exception:
            self.ok = False
        return self.ok

    def _get(self, path, **params):
        return self.session.get(self.base + path, params=params, timeout=15)

    def _post(self, path, **data):
        return self.session.post(self.base + path, data=data, timeout=15)

    def add_magnet(self, magnet, savepath="/vol1/1000/Downloads"):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")
        r = self._post("/api/v2/torrents/add", urls=magnet, savepath=savepath)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"本地下载器添加失败: HTTP {r.status_code}")
        return True

    def torrents(self, hashes):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")
        hs = "|".join(h for h in hashes if h)
        r = self._get("/api/v2/torrents/info", hashes=hs)
        if r.status_code != 200:
            return {}
        out = {}
        for t in r.json() or []:
            out[(t.get("hash") or "").lower()] = t
        return out

    def all(self):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")
        r = self._get("/api/v2/torrents/info")
        if r.status_code != 200:
            return []
        return r.json() or []

    def set_location(self, hashes, location):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")
        hs = "|".join(h for h in hashes if h)
        r = self._post("/api/v2/torrents/setLocation", hashes=hs, location=location)
        return r.status_code == 200

    def add_tags(self, hashes, tags):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")
        hs = "|".join(h for h in hashes if h)
        r = self._post("/api/v2/torrents/addTags", hashes=hs, tags=tags)
        return r.status_code == 200

    def delete(self, hashes, delete_files=False):
        if not self.ok and not self.login():
            raise RuntimeError("本地下载器未就绪")
        hs = "|".join(h for h in hashes if h)
        r = self._post("/api/v2/torrents/delete", hashes=hs,
                       deleteFiles="true" if delete_files else "false")
        return r.status_code == 200


def is_completed(t):
    return bool(t) and (float(t.get("progress") or 0) >= 0.999 or
                        t.get("state") in ("uploading", "stalledUP", "pausedUP", "queuedUP", "forcedUP"))


def has_progress(t):
    if not t:
        return False
    return float(t.get("progress") or 0) > 0 or is_completed(t)


def move_completed(cfg):
    """把已完成的本地下载移动到配置的目标目录（qbt setLocation），返回移动数量。"""
    if not cfg.get("local_move_enabled"):
        return 0
    done = (cfg.get("local_done_path") or "").strip()
    if not done:
        return 0
    q = LocalQbt()
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

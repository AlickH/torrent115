#!/usr/bin/env python3
"""TorrentTo115 - 搜索磁力/种子并发送到 115 云下载（轻量单容器）."""
import base64
import gzip

try:
    import brotli
except ImportError:
    brotli = None
import hashlib
import hmac
import json
import os
import random
import re
import secrets
import string
import threading
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests
import tracker as auto_track
from flask import Flask, Response, jsonify, redirect, request, send_file, send_from_directory, session

from drivemby import auto_drivemby_refresh, notify_drivemby
from config import BASE, CONFIG_PATH, DATA_DIR, DEFAULT_CONFIG, _pwd_fingerprint, load_config, save_config
from net import UA, http_request
from search import (
    _collect, extract_infohash, bare_season, effective_query, expand_queries, resolve_title,
    search_all_sources, search_pansou, search_site, title_tokens, tmdb_get, translate_title,
)
from routes import bp
from p115 import (
    _is_dir, collect_leaves, parse_share_url, p115_add_urls, p115_children, p115_default_cid,
    p115_downpath, p115_file_chain, p115_file_info, p115_headers, p115_task_del,
    p115_task_list, p115_transfer_target, share_snap, share_transfer,
)



app = Flask(__name__, static_folder=None)
app.register_blueprint(bp)

def _auth_enabled():
    return bool(load_config().get("auth_password"))


_LOGIN_FAILS = {}
_LOGIN_LOCK = threading.Lock()
MAX_FAILS = 5
FAIL_WINDOW = 600
LOCK_TIME = 600


def _client_ip():
    xff = request.headers.get("X-Forwarded-For") or ""
    return (xff.split(",")[0].strip() or request.remote_addr or "-")


def _login_locked(ip):
    now = time.time()
    with _LOGIN_LOCK:
        rec = _LOGIN_FAILS.get(ip)
        if not rec:
            return False, 0
        rec["times"] = [t for t in rec["times"] if now - t < FAIL_WINDOW]
        if len(rec["times"]) >= MAX_FAILS:
            remain = int(LOCK_TIME - (now - rec["times"][-1]))
            if remain > 0:
                return True, remain
            rec["times"] = []
            return False, 0
        return False, 0


def _record_fail(ip):
    with _LOGIN_LOCK:
        rec = _LOGIN_FAILS.setdefault(ip, {"times": []})
        now = time.time()
        rec["times"] = [t for t in rec["times"] if now - t < FAIL_WINDOW]
        rec["times"].append(now)
        if len(rec["times"]) >= MAX_FAILS:
            rec["times"] = [now] * MAX_FAILS


def _clear_fail(ip):
    with _LOGIN_LOCK:
        _LOGIN_FAILS.pop(ip, None)


@app.before_request
def _require_login():
    if not _auth_enabled():
        return None
    if request.path in ("/login", "/favicon.ico") or request.path.startswith("/static/"):
        return None
    if session.get("auth"):
        if session.get("pv") != _pwd_fingerprint(load_config().get("auth_password")):
            session.clear()
            if request.path.startswith("/api/"):
                return jsonify({"ok": False, "error": "登录已失效，请重新登录"}), 401
            return redirect("/login")
        return None
    if request.path.startswith("/api/"):
        return jsonify({"ok": False, "error": "未登录"}), 401
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    cfg = load_config()
    if not cfg.get("auth_password"):
        return redirect("/")
    error = ""
    status = 200
    ip = _client_ip()
    if request.method == "POST":
        locked, remain = _login_locked(ip)
        if locked:
            error = "尝试次数过多，请 %d 分钟后再试" % max(1, remain // 60)
            status = 429
        else:
            user = (request.form.get("user") or "").strip()
            pwd = request.form.get("password") or ""
            if (hmac.compare_digest(user, str(cfg.get("auth_user") or ""))
                    and hmac.compare_digest(pwd, str(cfg.get("auth_password") or ""))):
                _clear_fail(ip)
                session["auth"] = True
                session["pv"] = _pwd_fingerprint(pwd)
                session.permanent = True
                return redirect("/")
            _record_fail(ip)
            locked, remain = _login_locked(ip)
            if locked:
                error = "尝试次数过多，请 %d 分钟后再试" % max(1, remain // 60)
                status = 429
            else:
                left = max(0, MAX_FAILS - len(_LOGIN_FAILS.get(ip, {}).get("times", [])))
                error = "用户名或密码错误，再错 %d 次将锁定 10 分钟" % left
    html = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1"/>
<title>登录 - 磁力搜索</title>
<style>body{margin:0;background:#0b1220;color:#e6edf7;font:14px -apple-system,"PingFang SC",sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh}
.box{background:#141d2f;border:1px solid #22304a;border-radius:14px;padding:28px;width:320px}
h1{font-size:18px;margin:0 0 18px}
input{width:100%;box-sizing:border-box;background:#0d1626;border:1px solid #22304a;color:#e6edf7;border-radius:8px;padding:10px 12px;margin-bottom:12px;font-size:14px}
button{width:100%;background:#5b8cff;color:#fff;border:0;border-radius:8px;padding:10px;font-size:14px;cursor:pointer}
.err{color:#ff8f8f;font-size:13px;min-height:18px;margin-bottom:8px}
@media (prefers-color-scheme: light){
 body{background:#f3f5fa;color:#1b2433}
 .box{background:#fff;border-color:#d9e1ef}
 input{background:#fff;border-color:#d9e1ef;color:#1b2433}
 .err{color:#c62828}
}</style></head><body>
<div class="box"><h1>🔐 登录</h1><div class="err">"""+error+"""</div>
<form method="post"><input name="user" placeholder="用户名" autofocus/><input name="password" type="password" placeholder="密码"/><button>登录</button></form>""" + ("""<div class="hint">默认账号：admin / admin（登录后请立即修改）</div>""" if (cfg.get("auth_user") == "admin" and cfg.get("auth_password") == "admin") else "") + """</div></body></html>"""
    if cfg.get("auth_user") == "admin" and cfg.get("auth_password") == "admin":
        html = html.replace('<input name="user" placeholder="用户名" autofocus/>',
                            '<input name="user" value="admin" autofocus/>')
        html = html.replace('<input name="password" type="password" placeholder="密码"/>',
                            '<input name="password" type="password" value="admin"/>')
    return Response(html, status=status, mimetype="text/html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


app.secret_key = load_config().get("secret_key") or ""
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ---------------- 115 云下载 ----------------


# ---------------- torrent -> info hash ----------------

def folder_signature(cfg, cid):
    items = p115_children(cfg, cid)
    files = [x for x in items if not _is_dir(x)]
    dirs = [x for x in items if _is_dir(x)]
    sig = [len(files), sum(int(x.get("s") or 0) for x in files), len(dirs)]
    for d in dirs[:8]:
        sub = p115_children(cfg, d.get("cid"))
        subf = [x for x in sub if not _is_dir(x)]
        sig += [len(subf), sum(int(x.get("s") or 0) for x in subf)]
    return sig


MONITOR_STATE = os.path.join(DATA_DIR, "monitor_state.json")
MONITOR_SEEN_TTL = 7 * 86400
_BOOTSTRAP_IDS = set()


def load_monitor_state():
    try:
        with open(MONITOR_STATE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"seen": {}}


def save_monitor_state(state):
    now = time.time()
    for k, v in list(state["seen"].items()):
        if now - v.get("ts", now) > MONITOR_SEEN_TTL:
            state["seen"].pop(k, None)
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = MONITOR_STATE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, MONITOR_STATE)




def monitor_tick():
    cfg = load_config()
    if not cfg.get("monitor_enabled") or not cfg.get("p115_cookie"):
        return
    cid = cfg.get("monitor_cid") or p115_default_cid(cfg)
    state = load_monitor_state()
    seen = state["seen"]
    dirs = [x for x in p115_children(cfg, cid) if _is_dir(x)]
    for d in dirs:
        key = str(d.get("cid"))
        name = d.get("n") or ""
        st = seen.get(key)
        if not st:
            boot = key in _BOOTSTRAP_IDS
            seen[key] = {"name": name, "sig": None, "stable": 0, "ts": time.time(),
                         "bootstrap": boot}
            if boot:
                continue
            print(f"[monitor] new folder detected: {name}", flush=True)
            continue
        if st.get("bootstrap") and st.get("sig") is None:
            st["sig"] = folder_signature(cfg, key)
            st["last_notify_sig"] = st["sig"]
            st["stable"] = 2
            st["last_notify_ts"] = time.time()
            st["bootstrap"] = False
            continue
        sig = folder_signature(cfg, key)
        if st.get("sig") == sig:
            st["stable"] = st.get("stable", 0) + 1
        else:
            st["stable"] = 0
            st["sig"] = sig
        last = st.get("last_notify_ts") or 0
        if last and time.time() - last > 6 * 3600:
            continue
        if st["stable"] >= 2 and sig != st.get("last_notify_sig") and time.time() - last >= 300:
            if not cfg.get("drivemby_enabled", True):
                save_monitor_state(state)
                continue
            ok = notify_drivemby(cfg, name, key)
            if ok:
                st["last_notify_ts"] = time.time()
                st["last_notify_sig"] = sig
                print(f"[monitor] notified {name}: {ok}", flush=True)
                auto_track.log(f"[monitor] Drivemby 已刷新: {name}")
    save_monitor_state(state)


def monitor_loop():
    try:
        cfg = load_config()
        cid = cfg.get("monitor_cid") or p115_default_cid(cfg)
        for x in p115_children(cfg, cid):
            if _is_dir(x):
                _BOOTSTRAP_IDS.add(str(x.get("cid")))
        print(f"[monitor] started, {len(_BOOTSTRAP_IDS)} existing folders marked known", flush=True)
    except Exception as e:
        print(f"[monitor] bootstrap ERROR {e}", flush=True)
    while True:
        try:
            monitor_tick()
        except Exception as e:
            print(f"[monitor] ERROR {e}", flush=True)
        try:
            interval = max(10, int(load_config().get("monitor_interval") or 60))
        except Exception:
            interval = 60
        time.sleep(interval)


# ---------------- routes ----------------

QR_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


STATIC_DIR = os.path.join(BASE, "static")


_BR_CACHE = {}


@app.after_request
def _zip_response(resp):
    try:
        if resp.direct_passthrough:
            resp.direct_passthrough = False
        if resp.headers.get("Content-Encoding") or resp.status_code != 200:
            return resp
        ae = request.headers.get("Accept-Encoding") or ""
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if not any(t in ctype for t in ("text/", "javascript", "json", "svg", "xml")):
            return resp
        data = resp.get_data()
        if len(data) < 1024:
            return resp
        if brotli is not None and "br" in ae:
            key = (request.path, len(data))
            comp = _BR_CACHE.get(key)
            if comp is None:
                comp = brotli.compress(data, quality=5)
                if len(_BR_CACHE) < 50:
                    _BR_CACHE[key] = comp
            resp.set_data(comp)
            resp.headers["Content-Encoding"] = "br"
        elif "gzip" in ae:
            resp.set_data(gzip.compress(data, 6))
            resp.headers["Content-Encoding"] = "gzip"
        else:
            return resp
        resp.headers["Content-Length"] = str(len(resp.get_data()))
        resp.headers["Vary"] = "Accept-Encoding"
        return resp
    except Exception:
        return resp


@app.route("/")
def index():
    r = send_file(os.path.join(STATIC_DIR, "index.html"))
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return r


@app.route("/static/<path:filename>")
def static_files(filename):
    resp = send_from_directory(STATIC_DIR, filename)
    if filename.startswith("assets/"):
        resp.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        resp.headers["Cache-Control"] = "public, max-age=3600"
    return resp


if __name__ == "__main__":
    os.makedirs(DATA_DIR, exist_ok=True)
    cfg0 = load_config()
    if not cfg0.get("secret_key"):
        import secrets
        cfg0["secret_key"] = secrets.token_hex(32)
        save_config(cfg0)
        app.secret_key = cfg0["secret_key"]
    threading.Thread(target=monitor_loop, daemon=True).start()
    auto_track.configure(DATA_DIR, load_config, search_site, search_pansou,
                         p115_add_urls, share_transfer, p115_task_list, p115_task_del, auto_drivemby_refresh, search_all_sources)
    threading.Thread(target=auto_track.loop, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8099")))

#!/usr/bin/env python3
"""HTTP API 路由（Blueprint）。"""
import base64
import hashlib
import hmac
import json
import os
import random
import secrets
import re
import time
import urllib.parse

import requests
from flask import Blueprint, Response, jsonify, redirect, request, send_file, session

import tracker as auto_track
from config import DATA_DIR, DEFAULT_CONFIG, _pwd_fingerprint, load_config, public_config, save_config
from drivemby import auto_drivemby_refresh
from net import UA, http_request
from p115 import (
    _is_dir, collect_leaves, parse_share_url, p115_add_urls, p115_children,
    p115_default_cid, p115_downpath, p115_file_chain, p115_file_info, p115_headers,
    p115_task_del, p115_task_list, p115_transfer_target, share_snap, share_transfer,
)
from search import (
    _collect, bare_season, effective_query, expand_queries, extract_infohash, resolve_title,
    search_all_sources, search_pansou, search_site, title_tokens, tmdb_get, translate_title,
)

bp = Blueprint("api", __name__)

def _cache_get(key):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < _CACHE_TTL:
        return hit[1]
    return None

def _cache_put(key, payload):
    _CACHE[key] = (time.time(), payload)
    return payload

def _external_root():
    proto = request.headers.get("X-Forwarded-Proto") or request.scheme
    host = request.headers.get("X-Forwarded-Host") or request.host
    return f"{proto}://{host}"

def qr_http(url, method="GET", **kw):
    kw.setdefault("headers", {})["User-Agent"] = QR_UA
    kw.setdefault("timeout", 25)
    return requests.request(method, url, **kw)

def _cookie_from_qr(uid):
    r = qr_http("https://qrcodeapi.115.com/app/1.0/web/1.0/login/qrcode/",
                method="POST", data={"account": uid})
    jar = {k: v for k, v in r.cookies.get_dict().items()}
    try:
        body = r.json()
    except Exception:
        body = {}
    if body.get("state") in (0, False):
        return None, (body.get("message") or body.get("error") or "登录失败")
    data = body.get("data") or {}
    if isinstance(data, dict):
        for k, v in (data.items() if isinstance(data, dict) else []):
            if isinstance(v, str) and k.upper() in ("UID", "CID", "SEID", "KID", "PUID", "PSEID"):
                jar[k.upper()] = v
    if not jar:
        return None, "登录响应里没有 Cookie"
    return "; ".join(f"{k}={v}" for k, v in jar.items()), None

def _bdecode(data, i=0):
    """极小 bencode 解析，返回 (value, next_index)。字节串保持 bytes。"""
    c = data[i:i + 1]
    if c == b"i":
        j = data.index(b"e", i)
        return int(data[i + 1:j]), j + 1
    if c == b"l":
        i += 1
        out = []
        while data[i:i + 1] != b"e":
            v, i = _bdecode(data, i)
            out.append(v)
        return out, i + 1
    if c == b"d":
        i += 1
        out = {}
        while data[i:i + 1] != b"e":
            k, i = _bdecode(data, i)
            v, i = _bdecode(data, i)
            out[k] = v
        return out, i + 1
    j = data.index(b":", i)
    n = int(data[i:j])
    return data[j + 1:j + 1 + n], j + 1 + n

def torrent_infohash(raw):
    i = raw.index(b"4:info")
    start = i + len(b"4:info")
    _, end = _bdecode(raw, start)
    return hashlib.sha1(raw[start:end]).hexdigest()

def torrent_to_magnet(raw, name=None):
    ih = torrent_infohash(raw)
    dn = hashlib.md5(raw).hexdigest()
    if name:
        dn = name
    return f"magnet:?xt=urn:btih:{ih}&dn={urllib.parse.quote(dn)}"

def fetch_torrent_magnet(url):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=40)
    r.raise_for_status()
    name = urllib.parse.unquote(url.rsplit("/", 1)[-1])
    return torrent_to_magnet(r.content, name)


# ---------------- 站点抓取 ----------------

ANCHOR_RE = re.compile(r"<a\b[^>]*href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", re.I | re.S)
_RESOLVE_CACHE = {}



# ---------------- 115 分享转存 ----------------


# ---------------- 115 目录监控 -> Drivemby ----------------


_TRAKT_OAUTH = {}
_TRAKT_OAUTH_ERROR = ""



@bp.route("/api/account", methods=["POST"])
def api_account():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    old = body.get("old") or ""
    new_user = (body.get("user") or "").strip()
    new_pwd = body.get("password") or ""
    if not hmac.compare_digest(old, str(cfg.get("auth_password") or "")):
        return jsonify({"ok": False, "error": "当前密码不正确"})
    if new_user:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,32}", new_user):
            return jsonify({"ok": False, "error": "用户名需 3-32 位字母/数字/_.-"})
    if new_pwd and len(new_pwd) < 5:
        return jsonify({"ok": False, "error": "新密码至少 5 位（建议 8 位以上）"})
    if not new_user and not new_pwd:
        return jsonify({"ok": False, "error": "用户名和新密码都没填"})
    if new_user:
        cfg["auth_user"] = new_user
    if new_pwd:
        cfg["auth_password"] = new_pwd
    save_config(cfg)
    session["pv"] = _pwd_fingerprint(cfg.get("auth_password") or "")
    return jsonify({"ok": True, "auth_user": cfg["auth_user"], "is_default_auth": False})

@bp.route("/api/password", methods=["POST"])
def api_password():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    old = body.get("old") or ""
    new = body.get("new") or ""
    if not hmac.compare_digest(old, str(cfg.get("auth_password") or "")):
        return jsonify({"ok": False, "error": "当前密码不正确"})
    if len(new) < 5:
        return jsonify({"ok": False, "error": "新密码至少 5 位（建议 8 位以上）"})
    cfg["auth_password"] = new
    save_config(cfg)
    session["pv"] = _pwd_fingerprint(new)
    return jsonify({"ok": True})

@bp.route("/api/115/qr/start", methods=["POST"])
def api_qr_start():
    try:
        r = qr_http("https://qrcodeapi.115.com/api/1.0/web/1.0/token/")
        d = r.json()
        data = d.get("data") or {}
        uid = data.get("uid")
        if not uid:
            return jsonify({"ok": False, "error": d.get("message") or "获取二维码失败"})
        img = qr_http("https://qrcodeapi.115.com/api/1.0/web/1.0/qrcode",
                      params={"uid": uid}).content
        return jsonify({"ok": True, "uid": uid, "time": data.get("time"), "sign": data.get("sign"),
                        "qrcode": data.get("qrcode"),
                        "image": "data:image/png;base64," + base64.b64encode(img).decode()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@bp.route("/api/115/qr/status")
def api_qr_status():
    uid = request.args.get("uid") or ""
    tm = request.args.get("time") or ""
    sign = request.args.get("sign") or ""
    if not uid:
        return jsonify({"ok": False, "error": "缺少 uid"})
    try:
        r = qr_http("https://qrcodeapi.115.com/get/status/",
                    params={"uid": uid, "time": tm, "sign": sign})
        d = r.json()
        status = (d.get("data") or {}).get("status")
        if status != 2:
            return jsonify({"ok": True, "status": status,
                            "msg": {0: "等待扫码", 1: "已扫码，请在手机上确认",
                                    -1: "二维码已过期", -2: "已取消"}.get(status, str(status))})
        cookie_val, err = _cookie_from_qr(uid)
        if not cookie_val:
            return jsonify({"ok": False, "status": status, "error": err or "登录失败"})
        cfg = load_config()
        cfg["p115_cookie"] = cookie_val
        save_config(cfg)
        try:
            p115_downpath(cfg)
        except Exception as e:
            return jsonify({"ok": False, "status": status, "error": "Cookie 校验失败: " + str(e)})
        return jsonify({"ok": True, "status": status, "msg": "登录成功",
                        "cookie_hint": cookie_val[:6] + "..."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@bp.route("/api/secrets")
def api_secrets():
    cfg = load_config()
    name = request.args.get("name") or ""
    if name == "cookie":
        return jsonify({"ok": True, "value": cfg.get("p115_cookie") or ""})
    if name == "tmdb":
        return jsonify({"ok": True, "value": cfg.get("tmdb_api_key") or ""})
    if name == "ai":
        return jsonify({"ok": True, "value": cfg.get("ai_api_key") or ""})
    if name == "trakt":
        return jsonify({"ok": True, "value": cfg.get("trakt_token") or ""})
    if name in ("preset_ai", "preset_trakt", "ai_preset"):
        pid = request.args.get("id") or ""
        if name == "ai_preset":
            for a in (cfg.get("ai_presets") or []):
                if str(a.get("id")) == str(pid):
                    return jsonify({"ok": True, "value": a.get("api_key") or ""})
            return jsonify({"ok": True, "value": ""})
        for pr in (cfg.get("auto_presets") or []):
            if str(pr.get("id")) == str(pid):
                key = "ai_api_key" if name == "preset_ai" else "trakt_token"
                return jsonify({"ok": True, "value": pr.get(key) or ""})
        return jsonify({"ok": True, "value": ""})
    return jsonify({"ok": False, "error": "unknown secret"})

@bp.route("/api/config", methods=["GET"])
def get_config():
    return jsonify(public_config(load_config()))

@bp.route("/api/config", methods=["POST"])
def set_config():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    # 合并时保留未提交的密钥（前端拿到的是脱敏列表）
    def _merge_secret_list(key, fields):
        incoming = body.get(key)
        if not isinstance(incoming, list):
            return
        old = {str(x.get("id")): x for x in (cfg.get(key) or [])}
        merged = []
        for item in incoming:
            it = dict(item)
            for f in ("has_key", "has_ai", "has_trakt"):
                it.pop(f, None)
            prev = old.get(str(it.get("id")))
            if prev:
                for sf in fields:
                    if not it.get(sf):
                        it[sf] = prev.get(sf) or ""
            merged.append(it)
        body[key] = merged
    _merge_secret_list("ai_presets", ("api_key",))
    _merge_secret_list("auto_presets", ("ai_api_key", "trakt_token"))

    for k in ("pansou_url", "bitmagnet_url", "outbound_proxy", "p115_target_cid", "p115_transfer_cid",
              "auto_enabled", "auto_interval", "auto_days", "auto_max_episodes", "auto_strict_match", "auto_task_timeout", "auto_wait_timeout", "auto_use_local", "local_client", "local_qbt_url", "local_qbt_user", "local_qbt_password", "local_qbt_sock", "aria2_url", "aria2_secret", "transmission_url", "transmission_user", "transmission_password", "local_save_path", "local_move_enabled", "local_done_path", "auto_upload_115", "p115_upload_cid", "auto_upload_delete_local", "auto_presets", "auto_tv_preset", "auto_movie_preset", "ai_presets", "calendar_source", "auto_shows", "auto_res_order", "auto_rank_order", "auto_seed_tiers", "auto_size_big", "auto_source_order",
              "auto_max_size_gb", "auto_min_seeders", "auto_codec", "auto_dry_run",
              "ai_enabled", "ai_base_url", "ai_model", "trakt_client_id",
              "tmdb_api_key", "monitor_enabled", "monitor_interval", "monitor_cid",
              "drivemby_url", "drivemby_token", "drivemby_prefix", "drivemby_enabled"):
        if k in body:
            cfg[k] = body[k]
    if body.get("p115_cookie"):
        cfg["p115_cookie"] = body["p115_cookie"].strip()
    if body.get("ai_api_key"):
        cfg["ai_api_key"] = body["ai_api_key"].strip()
    if body.get("trakt_token"):
        cfg["trakt_token"] = body["trakt_token"].strip()
    if isinstance(body.get("sites"), dict):
        for sk, sv in body["sites"].items():
            cfg["sites"].setdefault(sk, {}).update(sv or {})
    save_config(cfg)
    return jsonify(public_config(cfg))

@bp.route("/api/115/test")
def test_115():
    cfg = load_config()
    try:
        d = p115_downpath(cfg)
        return jsonify({"ok": True, "folders": (d.get("data") or []), "default_cid": p115_default_cid(cfg)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


_CACHE = {}
_CACHE_TTL = 300

@bp.route("/api/search")
def api_search():
    cfg = load_config()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"items": [], "errors": {"all": "请输入关键词"}})
    sources = [s for s in (request.args.get("sources") or "pansou,apibay,nyaa,dmhy,btsearch,eztv,knaben,therarbg,bitmagnet").split(",") if s]
    key = ("all", q, tuple(sources))
    cached = _cache_get(key)
    if cached:
        return jsonify(cached)
    return jsonify(_cache_put(key, _collect(cfg, q, sources, True)))

@bp.route("/api/search/pansou")
def api_search_pansou():
    cfg = load_config()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"items": [], "errors": {"all": "请输入关键词"}})
    key = ("pansou", q)
    cached = _cache_get(key)
    if cached:
        return jsonify(cached)
    items, err = search_pansou(cfg, q)
    errors = {"pansou": err} if err else {}
    return jsonify(_cache_put(key, {"items": items, "errors": errors}))

@bp.route("/api/search/site")
def api_search_site():
    cfg = load_config()
    q = (request.args.get("q") or "").strip()
    source = (request.args.get("source") or "").strip()
    if not q or not source:
        return jsonify({"items": [], "errors": {source or "all": "参数缺失"}})
    expand = request.args.get("expand") in ("1", "true", "on")
    try:
        min_seeds = max(0, int(request.args.get("min_seeds") or 0))
    except Exception:
        min_seeds = 0
    key = ("site", q, source, bool(expand), min_seeds)
    cached = _cache_get(key)
    if cached:
        return jsonify(cached)
    resolved = resolve_title(cfg, q) or {}
    if expand and source in ("apibay", "therarbg", "nyaa"):
        queries = expand_queries(effective_query(q, resolved))
        items, seen = [], set()
        for qq in queries:
            got, _ = search_site(cfg, source, qq, resolved)
            for it in got:
                h = extract_infohash(it.get("url")) or it.get("url")
                if h in seen:
                    continue
                seen.add(h)
                items.append(it)
        err = None if items else "季集展开后没有结果"
    else:
        items, err = search_site(cfg, source, q, resolved)
    if min_seeds:
        items = [it for it in items if it.get("seeders") is None or int(it["seeders"]) >= min_seeds]
    payload = {"items": items, "errors": {source: err} if err else {}, "resolved": resolved}
    return jsonify(_cache_put(key, payload))

@bp.route("/api/search/sites")
def api_search_sites():
    cfg = load_config()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"items": [], "errors": {"all": "请输入关键词"}})
    sources = [s for s in (request.args.get("sources") or "apibay,nyaa,dmhy,btsearch,eztv,knaben,therarbg,bitmagnet").split(",") if s]
    key = ("sites", q, tuple(sources))
    cached = _cache_get(key)
    if cached:
        return jsonify(cached)
    return jsonify(_cache_put(key, _collect(cfg, q, sources, True)))

@bp.route("/api/trakt/oauth/start", methods=["POST"])
def api_trakt_oauth_start():
    body = request.get_json(force=True, silent=True) or {}
    client_id = (body.get("client_id") or load_config().get("trakt_client_id") or "").strip()
    if not client_id:
        return jsonify({"ok": False, "error": "请先填写 Trakt Client ID"})
    global _TRAKT_OAUTH_ERROR
    _TRAKT_OAUTH_ERROR = ""
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
    state = secrets.token_urlsafe(16)
    redirect_uri = _external_root() + "/api/trakt/callback"
    _TRAKT_OAUTH[state] = {"verifier": verifier, "client_id": client_id, "redirect_uri": redirect_uri, "ts": time.time()}
    auth = ("https://trakt.tv/oauth/authorize?response_type=code&client_id=" + urllib.parse.quote(client_id)
            + "&redirect_uri=" + urllib.parse.quote(redirect_uri, safe="")
            + "&state=" + state + "&code_challenge=" + challenge + "&code_challenge_method=S256")
    return jsonify({"ok": True, "auth_url": auth, "redirect_uri": redirect_uri})

@bp.route("/api/trakt/callback")
def api_trakt_callback():
    code = request.args.get("code") or ""
    state = request.args.get("state") or ""
    global _TRAKT_OAUTH_ERROR
    pending = _TRAKT_OAUTH.pop(state, None)
    if not code or not pending:
        _TRAKT_OAUTH_ERROR = "缺少 code 或 state 已失效（请重新点击 OAuth 获取 Token）"
        return f"<h3>Trakt 授权失败：{_TRAKT_OAUTH_ERROR}</h3>", 400
    try:
        r = http_request(load_config(), "POST", "https://api.trakt.tv/oauth/token",
                         headers={"Content-Type": "application/json"},
                         json={"code": code, "client_id": pending["client_id"],
                               "redirect_uri": pending["redirect_uri"], "code_verifier": pending["verifier"],
                               "grant_type": "authorization_code"}, timeout=30)
        d = r.json()
        token = d.get("access_token") or ""
        if not token:
            _TRAKT_OAUTH_ERROR = str(d)[:300]
            return f"<h3>Trakt 授权失败：{_TRAKT_OAUTH_ERROR}</h3>", 400
        cfg = load_config()
        cfg["trakt_client_id"] = pending["client_id"]
        cfg["trakt_token"] = token
        save_config(cfg)
        _TRAKT_OAUTH_ERROR = ""
        return "<html><body style='font-family:sans-serif;padding:40px'><h3>Trakt 授权成功 ✅</h3><p>可以关闭此页面，回到应用继续操作。</p><script>setTimeout(()=>window.close(),800)</script></body></html>"
    except Exception as e:
        _TRAKT_OAUTH_ERROR = str(e)[:300]
        return f"<h3>Trakt 授权失败：{_TRAKT_OAUTH_ERROR}</h3>", 500

@bp.route("/api/trakt/oauth/status")
def api_trakt_oauth_status():
    cfg = load_config()
    return jsonify({"ok": True, "has_token": bool(cfg.get("trakt_token")),
                    "has_client_id": bool(cfg.get("trakt_client_id")),
                    "last_error": _TRAKT_OAUTH_ERROR})

@bp.route("/api/ai/models", methods=["POST"])
def api_ai_models():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    base = (body.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    key = (body.get("api_key") or "").strip()
    if not key and body.get("id"):
        for a in (cfg.get("ai_presets") or []):
            if str(a.get("id")) == str(body.get("id")):
                key = (a.get("api_key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "缺少 API Key"})
    try:
        r = http_request(cfg, "GET", base + "/models", headers={"Authorization": "Bearer " + key}, timeout=25)
        try:
            d = r.json()
        except Exception:
            d = {}
        if r.status_code >= 400:
            msg = (d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else None
            return jsonify({"ok": False, "error": f"HTTP {r.status_code}: {msg or r.text[:160]}"})
        raw = d.get("data") or []
        models = sorted({(m.get("id") or "") for m in raw if isinstance(m, dict) and m.get("id")})
        return jsonify({"ok": True, "models": models})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:240]})

@bp.route("/api/ai/test", methods=["POST"])
def api_ai_test():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    base = (body.get("base_url") or "https://api.openai.com/v1").rstrip("/")
    model = body.get("model") or "gpt-4o-mini"
    key = (body.get("api_key") or "").strip()
    if not key and body.get("id"):
        for a in (cfg.get("ai_presets") or []):
            if str(a.get("id")) == str(body.get("id")):
                key = (a.get("api_key") or "").strip()
    if not key:
        return jsonify({"ok": False, "error": "缺少 API Key"})
    try:
        r = http_request(cfg, "POST", base + "/chat/completions",
                         headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
                         json={"model": model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 8},
                         timeout=30)
        try:
            d = r.json()
        except Exception:
            d = {}
        if r.status_code >= 400:
            msg = (d.get("error") or {}).get("message") if isinstance(d.get("error"), dict) else None
            return jsonify({"ok": False, "error": f"HTTP {r.status_code}: {msg or r.text[:160]}"})
        reply = ""
        try:
            reply = (d.get("choices") or [{}])[0].get("message", {}).get("content") or ""
        except Exception:
            reply = ""
        return jsonify({"ok": True, "reply": reply[:200], "model": model})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:240]})

@bp.route("/api/auto/status")
def api_auto_status():
    cfg = load_config()
    pub = {k: cfg.get(k) for k in ("auto_enabled", "auto_interval", "auto_days", "auto_max_episodes",
                                   "auto_strict_match", "auto_task_timeout", "auto_wait_timeout", "auto_use_local", "local_client", "local_qbt_url", "local_qbt_user", "local_qbt_password", "local_qbt_sock", "aria2_url", "aria2_secret", "transmission_url", "transmission_user", "transmission_password", "local_save_path", "local_move_enabled", "local_done_path", "auto_upload_115", "p115_upload_cid", "auto_upload_delete_local", "auto_presets", "auto_tv_preset", "auto_movie_preset",
                                   "ai_presets", "calendar_source", "auto_shows", "auto_res_order",
                                   "auto_max_size_gb", "auto_min_seeders", "auto_codec",
                                   "auto_dry_run", "ai_enabled", "ai_base_url", "ai_model", "trakt_client_id", "drivemby_enabled", "auto_rank_order", "auto_seed_tiers", "auto_size_big", "auto_source_order")}
    pub["has_trakt"] = bool(cfg.get("trakt_token"))
    pub["has_ai"] = bool(cfg.get("ai_api_key"))
    pub["has_tmdb"] = bool(cfg.get("tmdb_api_key"))
    pub["ai_presets"] = [dict({k: v for k, v in a.items() if k != "api_key"}, has_key=bool(a.get("api_key"))) for a in (cfg.get("ai_presets") or [])]
    pub.update(auto_track.status())
    return jsonify(pub)

@bp.route("/api/auto/done")
def api_auto_done():
    return jsonify({"ok": True, "items": auto_track.done_items(load_config())})

@bp.route("/api/auto/done/remove", methods=["POST"])
def api_auto_done_remove():
    body = request.get_json(force=True, silent=True) or {}
    auto_track.remove_done(body.get("keys") or [])
    return jsonify({"ok": True})

@bp.route("/api/auto/done/clear", methods=["POST"])
def api_auto_done_clear():
    auto_track.clear_done()
    return jsonify({"ok": True})

@bp.route("/api/auto/logs/clear", methods=["POST"])
def api_auto_logs_clear():
    auto_track.clear_log()
    return jsonify({"ok": True})

@bp.route("/api/auto/run", methods=["POST"])
def api_auto_run():
    body = request.get_json(force=True, silent=True) or {}
    show = body.get("show") or {}
    only = [(show.get("tmdb_id"), show.get("media_type"))] if show.get("tmdb_id") else None
    if auto_track.is_running():
        return jsonify({"ok": False, "running": True, "error": "已有任务正在运行，本次点击已跳过"})
    auto_track.start_run(dry_run=bool(body.get("dry_run", False)), only_shows=only)
    return jsonify({"ok": True, "started": True})

@bp.route("/api/tmdb/img")
def api_tmdb_img():
    path = request.args.get("path") or ""
    if not path.startswith("/"):
        return Response(status=400)
    cache_dir = os.path.join(DATA_DIR, "img_cache")
    os.makedirs(cache_dir, exist_ok=True)
    ext = os.path.splitext(path)[1] or ".jpg"
    fp = os.path.join(cache_dir, hashlib.sha1(path.encode()).hexdigest() + ext)
    headers = {"Cache-Control": "public, max-age=604800, immutable"}
    if not os.path.exists(fp):
        url = "https://image.tmdb.org/t/p/w200" + path
        try:
            r = http_request(load_config(), "GET", url, timeout=20)
            if r.status_code >= 400:
                return Response(status=502)
            with open(fp, "wb") as f:
                f.write(r.content)
        except Exception:
            return Response(status=502)
    resp = send_file(fp)
    resp.headers["Cache-Control"] = "public, max-age=604800, immutable"
    return resp

@bp.route("/api/tmdb/search")
def api_tmdb_search():
    cfg = load_config()
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"ok": True, "results": []})
    tv = (tmdb_get(cfg, "/search/tv", query=q, language="zh-CN", include_adult="false") or {}).get("results") or []
    movie = (tmdb_get(cfg, "/search/movie", query=q, language="zh-CN", include_adult="false") or {}).get("results") or []
    out, seen = [], set()
    for r in tv:
        tid = r.get("id")
        if not tid or ("tv", tid) in seen:
            continue
        seen.add(("tv", tid))
        out.append({
            "tmdb_id": tid, "media_type": "tv",
            "name": r.get("name") or r.get("original_name") or "",
            "year": (r.get("first_air_date") or "")[:4],
            "poster_path": r.get("poster_path") or "",
            "overview": (r.get("overview") or "")[:60],
            "popularity": r.get("popularity") or 0,
        })
    for r in movie:
        tid = r.get("id")
        if not tid or ("movie", tid) in seen:
            continue
        seen.add(("movie", tid))
        out.append({
            "tmdb_id": tid, "media_type": "movie",
            "name": r.get("title") or r.get("original_title") or "",
            "year": (r.get("release_date") or "")[:4],
            "poster_path": r.get("poster_path") or "",
            "overview": (r.get("overview") or "")[:60],
            "popularity": r.get("popularity") or 0,
        })
    out.sort(key=lambda x: -(x.get("popularity") or 0))
    return jsonify({"ok": True, "results": out[:12]})

@bp.route("/api/tmdb/trending")
def api_tmdb_trending():
    cfg = load_config()
    page = max(1, int(request.args.get("page") or 1))
    mdata = tmdb_get(cfg, "/movie/now_playing", language="zh-CN", region="CN", page=page) or {}
    tdata = tmdb_get(cfg, "/tv/on_the_air", language="zh-CN", page=page) or {}
    movie = mdata.get("results") or []
    tv = tdata.get("results") or []
    out = []
    for r in movie:
        if not r.get("id"):
            continue
        out.append({
            "tmdb_id": r.get("id"), "media_type": "movie",
            "name": r.get("title") or r.get("original_title") or "",
            "year": (r.get("release_date") or "")[:4],
            "poster_path": r.get("poster_path") or "",
            "overview": (r.get("overview") or "")[:100],
            "popularity": r.get("popularity") or 0,
        })
    for r in tv:
        if not r.get("id"):
            continue
        out.append({
            "tmdb_id": r.get("id"), "media_type": "tv",
            "name": r.get("name") or r.get("original_name") or "",
            "year": (r.get("first_air_date") or "")[:4],
            "poster_path": r.get("poster_path") or "",
            "overview": (r.get("overview") or "")[:100],
            "popularity": r.get("popularity") or 0,
        })
    has_more = page < max(int(mdata.get("total_pages") or 1), int(tdata.get("total_pages") or 1))
    return jsonify({"ok": True, "results": out, "page": page, "has_more": has_more})

@bp.route("/api/tmdb/tv")
def api_tmdb_tv():
    cfg = load_config()
    tid = (request.args.get("id") or "").strip()
    if not tid.isdigit():
        return jsonify({"ok": False, "error": "TMDB ID 必须是数字"})
    d = tmdb_get(cfg, f"/tv/{tid}", language="zh-CN") or {}
    if not d.get("name"):
        d2 = tmdb_get(cfg, f"/tv/{tid}", language="en-US") or {}
        d = d2 or d
    if not d.get("name"):
        return jsonify({"ok": False, "error": "TMDB 查不到该剧集"})
    return jsonify({"ok": True, "tmdb_id": int(tid), "name": d.get("name"),
                    "first_air_date": d.get("first_air_date"),
                    "poster_path": d.get("poster_path") or ""})

@bp.route("/api/115/share_check")
def api_share_check():
    cfg = load_config()
    url = (request.args.get("url") or "").strip()
    pwd = request.args.get("password") or ""
    if not url:
        return jsonify({"ok": False, "error": "缺少链接"})
    code, url_pwd = parse_share_url(url)
    if not code:
        return jsonify({"ok": False, "error": "不是 115 分享链接"})
    pwd = pwd or url_pwd
    try:
        d = share_snap(cfg, code, pwd)
    except Exception as e:
        return jsonify({"ok": True, "available": False, "reason": str(e)})
    data = d.get("data") or {}
    info = data.get("shareinfo") or {}
    listing = data.get("list") or []
    return jsonify({"ok": True, "available": True, "title": info.get("share_title"),
                    "count": len(listing), "share_state": info.get("share_state")})

@bp.route("/api/transfer115", methods=["POST"])
def api_transfer115():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    url = (body.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "缺少 115 分享链接"})
    try:
        res = share_transfer(cfg, url, body.get("password") or "")
        ok = bool(res.get("state"))
        payload = {"ok": ok, "result": res}
        if not ok:
            payload["error"] = res.get("error") or "转存失败"
            payload["errcode"] = res.get("errno")
        return jsonify(payload)
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

@bp.route("/api/add115", methods=["POST"])
def api_add115():
    cfg = load_config()
    body = request.get_json(force=True, silent=True) or {}
    urls = [u for u in (body.get("urls") or []) if u]
    if not urls:
        return jsonify({"ok": False, "error": "没有可提交的链接"})
    prepared, notes = [], []
    for u in urls:
        try:
            if u.startswith("magnet:") or u.startswith("ed2k://"):
                prepared.append(u)
            elif ".torrent" in u.lower():
                prepared.append(fetch_torrent_magnet(u))
            else:
                notes.append(f"跳过（不支持直接云下载）: {u[:60]}")
        except Exception as e:
            notes.append(f"处理失败 {u[:60]}: {e}")
    if not prepared:
        return jsonify({"ok": False, "error": "；".join(notes) or "没有可提交的磁力"})
    try:
        res = p115_add_urls(cfg, prepared)
        return jsonify({"ok": bool(res.get("state")), "result": res, "notes": notes})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "notes": notes})

@bp.route("/api/bt/tasks")
def api_bt_tasks():
    try:
        import btdownloader
        return jsonify({"ok": True, "tasks": btdownloader.tasks()})
    except Exception as e:
        return jsonify({"ok": False, "tasks": [], "error": str(e)})


@bp.route("/api/bt/add", methods=["POST"])
def api_bt_add():
    body = request.get_json(silent=True) or {}
    magnet = (body.get("magnet") or "").strip()
    if not magnet.startswith("magnet:"):
        return jsonify({"ok": False, "error": "请输入磁力链接"}), 400
    try:
        import btdownloader
        h = btdownloader.add_magnet(load_config(), magnet)
        return jsonify({"ok": True, "hash": h})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/api/bt/pause", methods=["POST"])
def api_bt_pause():
    import btdownloader
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": btdownloader.pause((body.get("hash") or "").strip())})


@bp.route("/api/bt/resume", methods=["POST"])
def api_bt_resume():
    import btdownloader
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": btdownloader.resume((body.get("hash") or "").strip())})


@bp.route("/api/bt/delete", methods=["POST"])
def api_bt_delete():
    import btdownloader
    body = request.get_json(silent=True) or {}
    return jsonify({"ok": btdownloader.delete((body.get("hash") or "").strip(), bool(body.get("files")))})

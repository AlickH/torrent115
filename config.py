#!/usr/bin/env python3
"""配置读写。"""
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", "/data")
CONFIG_PATH = os.path.join(DATA_DIR, "config.json")

DEFAULT_CONFIG = {
    "p115_cookie": "",
    "p115_target_cid": "",
    "p115_transfer_cid": "",
    "tmdb_api_key": "",
    "auth_user": "admin",
    "auth_password": "admin",
    "secret_key": "",
    "monitor_enabled": True,
    "monitor_interval": 60,
    "drivemby_url": "https://drivemby.com/api/hooks/refresh",
    "drivemby_token": "",
    "drivemby_prefix": "/云下载",
    "drivemby_enabled": True,
    "monitor_cid": "",
    "pansou_url": "http://127.0.0.1:18080",
    "bitmagnet_url": "",
    "jackett_url": "",
    "jackett_api_key": "",
    "outbound_proxy": "",
    "auto_enabled": False,
    "auto_interval": 180,
    "auto_days": 2,
    "auto_max_episodes": 10,
    "auto_task_timeout": 10,
    "auto_wait_timeout": 3,
    "auto_use_local": False,
    "local_client": "builtin",
    "local_qbt_url": "http://127.0.0.1:8080",
    "local_qbt_user": "admin",
    "local_qbt_password": "",
    "local_qbt_sock": "/downloadcenter/1000/qbt.sock",
    "aria2_url": "http://127.0.0.1:6800/jsonrpc",
    "aria2_secret": "",
    "transmission_url": "http://127.0.0.1:9091/transmission/rpc",
    "transmission_user": "",
    "transmission_password": "",
    "local_save_path": "/data/downloads",
    "local_move_enabled": True,
    "local_done_path": "/data/downloads/Done",
    "auto_upload_115": False,
    "p115_upload_cid": "",
    "auto_upload_delete_local": False,
    "bitmagnet_db_host": "127.0.0.1",
    "bitmagnet_db_port": 5433,
    "bitmagnet_db_user": "postgres",
    "bitmagnet_db_password": "postgres",
    "bitmagnet_db_name": "bitmagnet",
    "auto_strict_match": True,
    "movie_delay_days": 30,
    "auto_presets": [],
    "ai_presets": [],
    "calendar_source": "tmdb",
    "auto_tv_preset": "",
    "auto_movie_preset": "",
    "auto_shows": [],
    "auto_res_order": ["2160p", "1080p", "720p"],
    "auto_rank_order": ["shares", "seeders", "resolution", "size", "codec"],
    "auto_source_order": [],
    "auto_seed_tiers": [10, 100, 1000, 10000],
    "auto_size_big": True,
    "auto_max_size_gb": 0,
    "auto_min_seeders": 1,
    "auto_exclude_cam": True,
    "auto_codec": "",
    "auto_dry_run": True,
    "ai_enabled": False,
    "ai_base_url": "https://api.openai.com/v1",
    "ai_api_key": "",
    "ai_model": "gpt-4o-mini",
    "jev_enabled": False,
    "jev_api_key": "",
    "jev_base_url": "",
    "trakt_client_id": "",
    "trakt_token": "",
    "sites": {
        "apibay": {"enabled": True, "url": "https://apibay.org/q.php?q={q}", "kind": "json"},
        "nyaa": {"enabled": True, "url": "https://nyaa.si/?page=rss&q={q}", "kind": "rss"},
        "dmhy": {"enabled": True, "url": "https://share.dmhy.org/topics/rss/rss.xml?keyword={q}", "kind": "rss"},
        "btsearch": {"enabled": True, "url": "https://www.btsearch.love/search?keyword={q}", "kind": "js"},
        "eztv": {"enabled": True, "url": "https://eztvx.to/api/get-torrents", "kind": "eztv"},
        "knaben": {"enabled": True, "url": "https://api.knaben.org/v1", "kind": "knaben"},
        "therarbg": {"enabled": True, "url": "https://therarbg.com/get-posts/keywords:{q}/?format=json", "kind": "therarbg"},
        "bitmagnet": {"enabled": False, "url": "http://127.0.0.1:3333/graphql", "kind": "bitmagnet"},
        "jackett": {"enabled": True, "url": "http://127.0.0.1:9117", "kind": "jackett"},
    },
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    fresh = not os.path.exists(CONFIG_PATH)
    if fresh:
        user = (os.environ.get("T115_ADMIN_USER") or "").strip()
        pwd = os.environ.get("T115_ADMIN_PASSWORD") or ""
        if user:
            cfg["auth_user"] = user
        if pwd:
            cfg["auth_password"] = pwd
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                saved = json.load(f)
            for k, v in saved.items():
                if k == "sites" and isinstance(v, dict):
                    for sk, sv in v.items():
                        cfg["sites"].setdefault(sk, {}).update(sv or {})
                else:
                    cfg[k] = v
        except Exception:
            pass
    return cfg


def save_config(cfg):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_PATH)

def public_config(cfg):
    out = {k: v for k, v in cfg.items() if k not in ("p115_cookie", "tmdb_api_key", "ai_api_key", "trakt_token", "jev_api_key")}
    out["has_cookie"] = bool(cfg.get("p115_cookie"))
    out["cookie_hint"] = (cfg.get("p115_cookie") or "")[:6] + "..." if cfg.get("p115_cookie") else ""
    out["has_tmdb"] = bool(cfg.get("tmdb_api_key"))
    out["has_ai"] = bool(cfg.get("ai_api_key"))
    out["has_jev"] = bool(cfg.get("jev_api_key"))
    out["has_trakt"] = bool(cfg.get("trakt_token"))
    presets = []
    for pr in (cfg.get("auto_presets") or []):
        pr = dict(pr)
        has_ai = bool(pr.pop("ai_api_key", ""))
        has_trakt = bool(pr.pop("trakt_token", ""))
        pr["has_ai"] = has_ai
        pr["has_trakt"] = has_trakt
        presets.append(pr)
    out["auto_presets"] = presets
    ais = []
    for a in (cfg.get("ai_presets") or []):
        a = dict(a)
        has_key = bool(a.pop("api_key", ""))
        a["has_key"] = has_key
        ais.append(a)
    out["ai_presets"] = ais
    out["auth_user"] = cfg.get("auth_user") or ""
    out["is_default_auth"] = ((cfg.get("auth_user") or "admin") == "admin"
                              and (cfg.get("auth_password") or "admin") == "admin")
    return out


def _pwd_fingerprint(pwd):
    import hashlib
    return hashlib.sha256(("t115:" + (pwd or "")).encode()).hexdigest()[:16]

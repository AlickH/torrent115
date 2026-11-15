#!/usr/bin/env python3
"""115 原生上传：基于 p115sync 的秒传/OSS 上传。"""
import json
import os
import time

STATE_NAME = "upload_state.json"


def _state_path():
    return os.path.join(os.environ.get("DATA_DIR", "/data"), STATE_NAME)


def _load_state():
    try:
        with open(_state_path(), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state):
    p = _state_path()
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False)
    os.replace(tmp, p)


def upload_file(cfg, path, cid=None):
    from p115sync import P115Client, P115UploadHelper
    cookie = (cfg.get("p115_cookie") or "").strip()
    if not cookie:
        raise RuntimeError("未配置 115 Cookie")
    pid = int(cid or cfg.get("p115_upload_cid") or cfg.get("p115_target_cid") or 0)
    import httpx as _httpx
    proxy = (cfg.get("outbound_proxy") or "").strip() or None
    try:
        session = _httpx.Client(proxy=proxy, follow_redirects=True, timeout=60)
    except TypeError:
        session = _httpx.Client(proxies=proxy, follow_redirects=True, timeout=60) if proxy else None
    client = P115Client(cookie, session=session)

    # 115 上传 token 接口对 p115sync 的会话偶发 TLS EOF，用独立会话重试
    def _safe_gettoken():
        import httpx
        last = None
        for _ in range(3):
            try:
                r = httpx.get("https://uplb.115.com/3.0/gettoken.php", cookies=client.cookies, timeout=20)
                r.raise_for_status()
                raw = r.json()
                if raw.get("state"):
                    return raw
                if str(raw.get("StatusCode")) == "200":
                    data = {k: raw.get(k) for k in ("AccessKeyId", "AccessKeySecret", "SecurityToken", "Expiration")}
                    return {"state": True, "data": data}
                return raw
            except Exception as e:
                last = e
                time.sleep(1)
        raise last

    client.upload_gettoken = _safe_gettoken

    old_http_proxy = os.environ.get("HTTP_PROXY")
    old_https_proxy = os.environ.get("HTTPS_PROXY")
    if proxy:
        os.environ["HTTP_PROXY"] = proxy
        os.environ["HTTPS_PROXY"] = proxy

    # 115 部分接口偶发 SSL EOF，给客户端请求加有限重试
    _orig_request = client._request_json

    def _retry_request(method, path, **kwargs):
        last = None
        for _ in range(8):
            try:
                return _orig_request(method, path, **kwargs)
            except Exception as e:
                last = e
                msg = str(e)
                if not any(x in msg for x in ("SSL", "EOF", "timed out", "Timeout")):
                    raise
                time.sleep(1)
        raise last

    client._request_json = _retry_request
    helper = P115UploadHelper(client)
    try:
        return helper.upload_file_sample(path, pid=pid)
    finally:
        if old_http_proxy is None:
            os.environ.pop("HTTP_PROXY", None)
        else:
            os.environ["HTTP_PROXY"] = old_http_proxy
        if old_https_proxy is None:
            os.environ.pop("HTTPS_PROXY", None)
        else:
            os.environ["HTTPS_PROXY"] = old_https_proxy


def upload_completed(cfg):
    """上传本地已完成、未上传过的任务；返回本次成功数量。"""
    if not cfg.get("auto_upload_115") or not cfg.get("p115_cookie"):
        return 0
    import localtorrent
    q = localtorrent.make_client(cfg)
    if not q.login():
        return 0
    state = _load_state()
    uploaded = 0
    for t in q.all():
        if not localtorrent.is_completed(t):
            continue
        h = (t.get("hash") or "").lower()
        if not h:
            continue
        prev = state.get(h)
        if isinstance(prev, dict):
            if prev.get("ok"):
                continue
            if time.time() - int(prev.get("ts") or 0) < 600:
                continue
        elif prev:
            continue
        src = (t.get("content_path") or "").strip()
        if not src:
            name = (t.get("name") or "").strip()
            src = os.path.join((t.get("save_path") or "").strip(), name) if name else ""
        if not src or not os.path.exists(src):
            continue
        try:
            upload_file(cfg, src)
            state[h] = {"ts": int(time.time()), "ok": True}
            _save_state(state)
            uploaded += 1
            print(f"[p115upload] uploaded {src}", flush=True)
            if cfg.get("auto_upload_delete_local"):
                q.delete([h])
        except Exception as e:
            state[h] = {"ts": int(time.time()), "ok": False, "error": str(e)[:200]}
            _save_state(state)
            print(f"[p115upload] failed {src}: {e}", flush=True)
    return uploaded

#!/usr/bin/env python3
"""115 网盘/云下载/分享转存 API。"""
import re
import urllib.parse

import requests

from net import UA, http_request

VIDEO_EXT = {"mkv", "mp4", "ts", "m2ts", "iso", "avi", "mov", "wmv", "flv", "m4v", "rmvb",
             "rm", "webm", "mpg", "mpeg", "vob", "3gp", "divx", "strm", "bdmv"}



def p115_headers(cfg):
    return {"Cookie": cfg.get("p115_cookie", ""), "User-Agent": UA,
            "Referer": "https://115.com/", "Origin": "https://115.com"}

def p115_downpath(cfg):
    r = requests.get("https://webapi.115.com/offine/downpath", headers=p115_headers(cfg), timeout=25)
    r.raise_for_status()
    return r.json()

def p115_default_cid(cfg):
    if cfg.get("p115_target_cid"):
        return str(cfg["p115_target_cid"])
    data = p115_downpath(cfg).get("data") or []
    for item in data:
        if item.get("is_selected") == "1":
            return str(item.get("file_id"))
    return str(data[0].get("file_id")) if data else "0"

def p115_transfer_target(cfg):
    """转存目标：支持 CID 数字、目录名（如 云下载）、留空=根目录。"""
    raw = str(cfg.get("p115_transfer_cid") or "").strip()
    if not raw:
        return "0"
    if raw.isdigit():
        return raw
    if raw == "云下载":
        try:
            return p115_default_cid({"p115_target_cid": "", "p115_cookie": cfg.get("p115_cookie")})
        except Exception:
            pass
    r = requests.get("https://webapi.115.com/files",
                     params={"aid": 1, "cid": "0", "limit": 200, "show_dir": 1, "snap": 0},
                     headers=p115_headers(cfg), timeout=25)
    r.raise_for_status()
    data = r.json().get("data")
    for x in ((data.get("list") if isinstance(data, dict) else data) or []):
        if x.get("n") == raw:
            return str(x.get("cid"))
    raise RuntimeError(f"转存目标目录不存在：{raw}（请在设置里填目录 CID 或正确的目录名）")

def p115_task_del(cfg, hash_):
    r = http_request(cfg, "POST", "https://clouddownload.115.com/web/?ac=task_del",
                     headers=p115_headers(cfg), data={"hash": hash_}, timeout=20)
    try:
        return r.json()
    except Exception:
        return {}

def p115_task_list(cfg, rows=60):
    r = http_request(cfg, "GET", "https://clouddownload.115.com/web/?ac=task_lists&page=1&rows=%d" % rows,
                     headers=p115_headers(cfg), timeout=25)
    d = r.json()
    tasks = {}
    for t in d.get("tasks") or []:
        h = (t.get("info_hash") or "").lower()
        if h:
            tasks[h] = t
    return tasks

PUBLIC_TRACKERS = [
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.stealth.si:80/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://tracker.dler.org:6969/announce",
    "https://tracker.moeblog.cn:443/announce",
    "https://tracker.zhuqiy.com:443/announce",
    "udp://open.dstud.io:6969/announce",
    "udp://open.demonii.com:1337/announce",
    "udp://tracker.openbittorrent.com:6969/announce",
    "udp://exodus.desync.com:6969/announce",
]


def _ensure_trackers(url):
    if not (url or "").startswith("magnet:"):
        return url
    existing = set(re.findall(r"[?&]tr=([^&]+)", url))
    parts = [url]
    for t in PUBLIC_TRACKERS:
        enc = urllib.parse.quote(t, safe="")
        if enc in existing:
            continue
        parts.append("tr=" + enc)
    return "&".join(parts)


def p115_add_urls(cfg, urls, cid=None):
    if not cfg.get("p115_cookie"):
        raise RuntimeError("未配置 115 Cookie")
    cid = cid or p115_default_cid(cfg)
    form = {"wp_path_id": cid}
    for i, u in enumerate(urls):
        form[f"url[{i}]"] = _ensure_trackers(u)
    r = requests.post("https://clouddownload.115.com/web/?ac=add_task_urls",
                      data=form, headers=p115_headers(cfg), timeout=40)
    r.raise_for_status()
    return r.json()

def parse_share_url(url):
    m = re.search(r"/s/([0-9a-zA-Z]+)", url or "")
    if not m:
        raise ValueError("无法从链接中识别 115 分享码")
    code = m.group(1)
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    pwd = (qs.get("password") or qs.get("pwd") or [""])[0]
    return code, pwd

def share_snap(cfg, code, pwd):
    r = requests.get("https://webapi.115.com/share/snap",
                     params={"share_code": code, "receive_code": pwd, "cid": 0, "limit": 100, "offset": 0},
                     headers=p115_headers(cfg), timeout=25)
    r.raise_for_status()
    d = r.json()
    if not d.get("state"):
        raise RuntimeError(d.get("error") or "获取分享信息失败")
    info = (d.get("data") or {}).get("shareinfo") or {}
    if str(info.get("share_state")) not in ("1", "0") and info.get("forbid_reason"):
        raise RuntimeError("分享不可用：" + str(info.get("forbid_reason")))
    return d

def share_transfer(cfg, url, pwd="", cid=None):
    code, url_pwd = parse_share_url(url)
    pwd = pwd or url_pwd
    snap = share_snap(cfg, code, pwd)
    lst = (snap.get("data") or {}).get("list") or []
    ids = [str(it.get("cid") or it.get("fid") or "") for it in lst if (it.get("cid") or it.get("fid"))]
    if not ids:
        raise RuntimeError("分享里没有可转存的文件")
    target = cid if cid not in (None, "") else p115_transfer_target(cfg)
    data = {"share_code": code, "receive_code": pwd, "file_id": ",".join(ids), "cid": str(target)}
    r = requests.post("https://webapi.115.com/share/receive", data=data,
                      headers=p115_headers(cfg), timeout=40)
    r.raise_for_status()
    return r.json()

def p115_children(cfg, cid, limit=1000):
    r = requests.get("https://webapi.115.com/files",
                     params={"aid": 1, "cid": str(cid), "limit": limit, "show_dir": 1,
                             "snap": 0, "natsort": 0, "offset": 0},
                     headers=p115_headers(cfg), timeout=25)
    r.raise_for_status()
    d = r.json()
    data = d.get("data")
    return (data.get("list") if isinstance(data, dict) else data) or []

def collect_leaves(cfg, cid, path, out, depth=0):
    if depth > 4 or len(out) >= 12:
        return
    try:
        items = p115_children(cfg, cid)
    except Exception as e:
        print(f"[monitor] walk error {e} path={path}", flush=True)
        return
    dirs = [x for x in items if _is_dir(x)]
    if any(_is_video(x) for x in items):
        out.append(path)
        return
    for d in dirs[:20]:
        collect_leaves(cfg, d.get("cid"), path + "/" + (d.get("n") or "?"), out, depth + 1)

def p115_file_info(cfg, fid):
    r = http_request(cfg, "GET", "https://webapi.115.com/files/get_info?file_id=" + str(fid),
                     headers=p115_headers(cfg), timeout=20)
    d = r.json()
    return ((d.get("data") or [{}])[0]) or {}

def p115_file_chain(cfg, fid):
    chain, cur, guard = [], str(fid or ""), 0
    while cur and cur != "0" and guard < 12:
        info = p115_file_info(cfg, cur)
        if not info:
            break
        chain.append({"cid": str(info.get("cid") or cur), "name": info.get("n") or ""})
        cur = str(info.get("pid") or "0")
        guard += 1
    return chain

def _is_video(x):
    n = (x.get("n") or "").lower()
    return ("." in n) and n.rsplit(".", 1)[-1] in VIDEO_EXT



def _is_dir(x):
    return "fid" not in x and bool(x.get("cid"))

def p115_list_files(cfg, cid="0"):
    items = p115_children(cfg, cid)
    out = []
    for x in items:
        if x.get("cid") is not None:
            out.append({"id": str(x.get("cid")), "name": x.get("n") or "", "is_dir": True,
                        "size": 0, "mtime": x.get("t") or ""})
        else:
            out.append({"id": str(x.get("fid") or ""), "name": x.get("n") or "", "is_dir": False,
                        "size": int(x.get("s") or 0), "mtime": x.get("t") or ""})
    out.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
    return out


def p115_offline_list(cfg):
    tasks = p115_task_list(cfg, rows=100)
    out = []
    for t in tasks.values():
        out.append({
            "hash": t.get("info_hash") or "",
            "name": t.get("name") or "",
            "status": t.get("display_status") or "",
            "status_text": t.get("status_text") or "",
            "percent": float(t.get("display_percent") or 0),
            "size": int(t.get("size") or 0),
            "downloaded": int(t.get("size") or 0) * float(t.get("display_percent") or 0) / 100.0,
            "rate": int(t.get("rateDownload") or 0),
            "add_time": int(t.get("add_time") or 0),
            "file_id": str(t.get("file_id") or ""),
            "pick_code": t.get("pick_code") or "",
        })
    out.sort(key=lambda x: x["add_time"], reverse=True)
    return out

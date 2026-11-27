#!/usr/bin/env python3
"""assrt.net（伪射手）字幕接口：搜索字幕包、取单集直链。"""
import json

import net

BASE = "https://api.assrt.net/v1"


def enabled(cfg):
    return bool((cfg.get("assrt_token") or "").strip())


def _get(cfg, path, **params):
    params["token"] = (cfg.get("assrt_token") or "").strip()
    r = net.http_request(cfg, "GET", f"{BASE}{path}", params=params, timeout=20)
    return r.json()


def search(cfg, keyword, limit=15):
    """返回 [{id,title,lang,score,site,time}]，失败/无结果返回 []。"""
    keyword = (keyword or "").strip()
    if not enabled(cfg) or not keyword:
        return []
    try:
        data = _get(cfg, "/sub/search", q=keyword, cnt=limit)
    except Exception:
        return []
    subs = ((data.get("sub") or {}).get("subs")) or []
    out = []
    for s in subs:
        try:
            out.append({
                "id": int(s.get("id")),
                "title": s.get("native_name") or s.get("videoname") or "",
                "lang": (s.get("lang") or "").strip(),
                "score": s.get("vote_score"),
                "site": s.get("release_site") or "",
                "time": s.get("upload_time") or "",
            })
        except Exception:
            continue
    return out


def detail(cfg, sub_id):
    """返回 [{filename,url}]：字幕包里的文件与直链。"""
    if not enabled(cfg):
        return []
    try:
        data = _get(cfg, "/sub/detail", id=sub_id)
    except Exception:
        return []
    subs = ((data.get("sub") or {}).get("subs")) or []
    files = []
    for s in subs:
        for f in s.get("filelist") or []:
            url = (f.get("url") or "").strip()
            name = (f.get("f") or "").strip()
            if url:
                files.append({"filename": name, "url": url})
    return files


def has_chinese(item):
    lang = (item.get("lang") or "").lower()
    title = item.get("title") or ""
    return any(k in lang for k in ("简", "繁", "中", "chi", "zh")) or any(k in title for k in ("简中", "繁中", "双语", "中字"))

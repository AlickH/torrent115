#!/usr/bin/env python3
"""刮削命名：把下载目录整理成媒体库标准结构。"""
import os
import re

VIDEO_EXT = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".flv", ".webm")
NOISE = re.compile(
    r"(?i)\b(2160p|1080p|720p|480p|4k|uhd|bluray|blu-?ray|web-?dl|webrip|hdtv|remux|"
    r"hevc|h\.?264|h\.?265|x264|x265|avc|aac|ac3|dts|ddp?5\.?1|atmos|truehd|flac|"
    r"10bit|8bit|hdr|dolby|vision|proper|repack|internal|multi|dual|sub|subs|"
    r"chs|cht|简|繁|中字|国语|粤语|日语|英语)\b"
)
BRACKET = re.compile(r"[\(\[]\s*[^\)\]]*\s*[\)\]]")
GROUP_TAIL = re.compile(r"-[A-Za-z0-9_]+$")


def _clean_title(text):
    text = text.replace(".", " ").replace("_", " ")
    text = BRACKET.sub(" ", text)
    text = NOISE.sub(" ", text)
    text = GROUP_TAIL.sub("", text.strip())
    text = re.sub(r"\s{2,}", " ", text).strip(" -_.")
    return text.strip()


LEAD_GROUP = re.compile(r"^\s*(\[[^\]]*\]\s*)+")


def _normalize_title(text):
    text = _clean_title(text)
    if text and not re.search(r"[\u4e00-\u9fff]", text) and text == text.lower():
        text = " ".join(w.capitalize() for w in text.split())
    return text


def parse(name):
    """从发布名推断结构：剧集优先 SxxExx / 第N话 / - 12，否则按电影解析。"""
    base = os.path.splitext(os.path.basename(name))[0]
    ext = os.path.splitext(name)[1].lower()
    base = LEAD_GROUP.sub("", base)
    m = re.search(r"(?i)[. _-]s(\d{1,2})e(\d{1,3})", base)
    if m:
        title = _normalize_title(base[:m.start()])
        return {"kind": "tv", "title": title, "season": int(m.group(1)),
                "episode": int(m.group(2)), "ext": ext}
    m = re.search(r"第\s*(\d{1,4})\s*[集话話]", base)
    if m:
        title = _clean_title(base[:m.start()])
        return {"kind": "tv", "title": title, "season": 1, "episode": int(m.group(1)), "ext": ext}
    m = re.search(r"\s-\s(\d{1,4})(?=\s|\[|\(|$)", base)
    if m:
        ep = int(m.group(1))
        if not (1900 <= ep <= 2099):
            title = _normalize_title(base[:m.start()])
            if title:
                return {"kind": "tv", "title": title, "season": 1, "episode": ep, "ext": ext}
    m = re.search(r"[\(\[]?(19|20)\d{2}[\)\]]?", base)
    year = None
    title = base
    if m:
        year = int(re.match(r"\d{4}", m.group(0)).group(0))
        title = _normalize_title(base[:m.start()] + " " + base[m.end():])
    else:
        title = _normalize_title(base)
    return {"kind": "movie", "title": title, "year": year, "ext": ext}


def target(info):
    title = info["title"] or "Unknown"
    if info["kind"] == "tv":
        season = info.get("season") or 1
        episode = info.get("episode") or 1
        folder = os.path.join(title, f"Season {season:02d}")
        name = f"{title} - S{season:02d}E{episode:02d}{info['ext']}"
    else:
        folder = f"{title} ({info['year']})" if info.get("year") else title
        name = f"{title} ({info['year']}){info['ext']}" if info.get("year") else title + info["ext"]
    return folder, name


def plan(path):
    """对单个文件或目录生成改名计划（不落盘）。"""
    files = []
    if os.path.isdir(path):
        for root, _dirs, names in os.walk(path):
            for fn in names:
                if fn.lower().endswith(VIDEO_EXT):
                    files.append(os.path.join(root, fn))
    elif os.path.isfile(path):
        files.append(path)
    base_dir = path if os.path.isdir(path) else os.path.dirname(path)
    items = []
    for src in sorted(files):
        info = parse(src)
        folder, name = target(info)
        dst = os.path.join(base_dir, folder, name)
        items.append({"src": src, "dst": dst, "kind": info["kind"], "title": info["title"],
                      "season": info.get("season"), "episode": info.get("episode"),
                      "year": info.get("year"),
                      "action": "same" if os.path.abspath(src) == os.path.abspath(dst) else "rename"})
    return items


def apply(items):
    """按计划改名/移动；返回每项结果。"""
    results = []
    for it in items:
        src, dst = it.get("src"), it.get("dst")
        if not src or not dst or it.get("action") == "same":
            continue
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.replace(src, dst)
            results.append({"src": src, "dst": dst, "ok": True})
        except Exception as e:
            results.append({"src": src, "dst": dst, "ok": False, "error": str(e)[:160]})
    return results

def plan_cloud(cfg, cid):
    """115 目录里的视频 → 刮削结构（不落盘、不调改名）。"""
    import p115
    items = []
    for x in p115.p115_children(cfg, cid):
        name = x.get("n") or ""
        if x.get("fid") is None or not name.lower().endswith(VIDEO_EXT):
            continue
        info = parse(name)
        folder, new_name = target(info)
        parts = folder.split("/")
        items.append({"fid": str(x["fid"]), "src": name, "folder": parts[0],
                      "season": parts[1] if len(parts) > 1 else None,
                      "dst": f"{folder}/{new_name}", "kind": info["kind"],
                      "title": info["title"], "year": info.get("year"),
                      "episode": info.get("episode"),
                      "action": "same" if new_name == name else "rename"})
    return items


def apply_cloud(cfg, cid, items):
    """按计划在 115 上建目录、改名、移动。"""
    import p115
    results = []
    folders = {}
    for it in items:
        if it.get("action") == "same":
            continue
        try:
            folder = it["folder"]
            if folder not in folders:
                folders[folder] = p115.p115_mkdir(cfg, cid, folder)
            target_cid = folders[folder]
            season = it.get("season")
            if season:
                key = f"{folder}/{season}"
                if key not in folders:
                    folders[key] = p115.p115_mkdir(cfg, target_cid, season)
                target_cid = folders[key]
            name = it["dst"].rsplit("/", 1)[-1]
            if name != it["src"]:
                p115.p115_rename(cfg, it["fid"], name)
            p115.p115_move(cfg, it["fid"], target_cid)
            results.append({"fid": it["fid"], "src": it["src"], "dst": it["dst"], "ok": True})
        except Exception as e:
            results.append({"fid": it.get("fid"), "src": it.get("src"), "ok": False, "error": str(e)[:160]})
    return results


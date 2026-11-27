#!/usr/bin/env python3
"""中文字幕：先体检（有没有中字），没有再去 assrt 找，最后才 AI 翻译。"""
import json
import os
import re
import subprocess
import zipfile

import ai_client
import assrt
import net

TEXT_CODECS = ("subrip", "srt", "ass", "ssa", "mov_text", "webvtt", "text")
IMAGE_CODECS = ("hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub")
ZH_LANG = ("chi", "zho", "zh", "chs", "cht", "cn", "sc", "tc")
VIDEO_EXT = (".mkv", ".mp4", ".avi", ".ts", ".m2ts", ".mov", ".wmv", ".flv", ".webm")
CHUNK = 60

SYSTEM = """你在翻译影视字幕。输入是 JSON 数组：[{"i":序号,"t":"原文"}]，输出同样长度、同样序号的 JSON 数组：[{"i":序号,"t":"中文译文"}]。

要求：
- 只输出 JSON 数组，不要解释、不要代码块。
- 序号必须与输入一一对应，数量不能变。
- 译文要像字幕：简洁、口语、符合中文语序，单行不超过 22 个汉字（过长可断成两行，用 \\n）。
- 保留专有名词的通行译名；人名、地名首次出现按通行译法，之后保持一致。
- 不要合并相邻条目，不要吞掉语气词。
- 原文里的歌词、感叹词照译。"""


def _run(cmd, timeout=600):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def probe(video):
    """返回字幕轨列表：[{index,codec,type,lang,title}]，失败返回 []。"""
    r = _run(["ffprobe", "-v", "error", "-select_streams", "s",
              "-show_entries", "stream=index,codec_name:stream_tags=language,title",
              "-of", "json", video], timeout=60)
    if r.returncode != 0:
        return []
    try:
        streams = (json.loads(r.stdout or "{}") or {}).get("streams") or []
    except Exception:
        return []
    out = []
    for s in streams:
        codec = (s.get("codec_name") or "").lower()
        tags = s.get("tags") or {}
        if codec in IMAGE_CODECS:
            kind = "image"
        elif codec in TEXT_CODECS:
            kind = "text"
        elif codec in ("none", "") and "pgs" in codec:
            kind = "image"
        else:
            kind = "text"
        out.append({"index": int(s.get("index")), "codec": codec, "type": kind,
                    "lang": (tags.get("language") or "").lower(), "title": tags.get("title") or ""})
    return out


def is_zh_track(track):
    lang = track.get("lang") or ""
    title = track.get("title") or ""
    if any(lang.startswith(z) for z in ZH_LANG):
        return True
    return any(k in title for k in ("简", "繁", "中文", "中字", "CHS", "CHT", "chs", "cht"))


def external_subs(video):
    """同目录下的中文字幕文件（外挂），返回路径或 None。"""
    base = os.path.splitext(video)[0]
    directory = os.path.dirname(video) or "."
    name = os.path.basename(base).lower()
    try:
        entries = os.listdir(directory)
    except Exception:
        return None
    for fn in entries:
        low = fn.lower()
        if not low.endswith((".srt", ".ass", ".ssa", ".vtt")):
            continue
        if not low.startswith(name):
            continue
        if any(k in low for k in (".zh", ".chs", ".cht", ".chi", "简", "繁", "中")):
            return os.path.join(directory, fn)
    return None


def extract(video, track_index, out_srt):
    """把指定字幕轨抽成 SRT（文本轨）。"""
    r = _run(["ffmpeg", "-y", "-v", "error", "-i", video,
              "-map", f"0:{track_index}", "-c:s", "srt", out_srt])
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[:200])
    return out_srt


def _parse_srt(text):
    cues = []
    blocks = re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n"))
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        if len(lines) < 2:
            continue
        idx = None
        for i, line in enumerate(lines):
            if "-->" in line:
                idx = i
                break
        if idx is None:
            continue
        body = "\n".join(lines[idx + 1:]).strip()
        if body:
            cues.append({"timing": lines[idx].strip(), "text": body})
    return cues


def _render_srt(cues):
    parts = []
    for n, cue in enumerate(cues, 1):
        parts.append(f"{n}\n{cue['timing']}\n{cue['text']}\n")
    return "\n".join(parts)


def translate(cfg, cues, meta=None):
    """分块翻译，逐块校验条数；失败抛异常（不静默降级）。"""
    glossary = ""
    if meta:
        names = [x for x in (meta.get("names") or []) if x]
        if names:
            glossary = "术语表：" + "、".join(names[:20]) + "\n"
    out = []
    for start in range(0, len(cues), CHUNK):
        chunk = cues[start:start + CHUNK]
        payload = [{"i": i, "t": c["text"]} for i, c in enumerate(chunk)]
        prompt = glossary + "原文：\n" + json.dumps(payload, ensure_ascii=False)
        data = ai_client.chat_json(cfg, [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ], temperature=0.2)
        if not isinstance(data, list) or len(data) != len(chunk):
            raise RuntimeError(f"翻译块条数不符：期望 {len(chunk)}，得到 {len(data) if isinstance(data, list) else type(data).__name__}")
        by_index = {}
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("i"), int):
                by_index[item["i"]] = str(item.get("t") or "").strip()
        for i, cue in enumerate(chunk):
            text = by_index.get(i, "")
            if not text:
                raise RuntimeError(f"翻译块缺少第 {start + i} 条")
            out.append({"timing": cue["timing"], "text": text})
    return out


def _pick_source_track(tracks):
    """优先英文，其次任意文本轨；没有文本轨返回 None。"""
    texts = [t for t in tracks if t["type"] == "text" and not is_zh_track(t)]
    if not texts:
        return None
    for pref in ("eng", "en", "jpn", "ja"):
        for t in texts:
            if (t.get("lang") or "").startswith(pref):
                return t
    return texts[0]


def _guess_title(video):
    name = os.path.basename(video)
    name = os.path.splitext(name)[0]
    name = re.sub(r"\[[^\]]*\]", " ", name)
    name = re.sub(r"\.(?:19|20)\d{2}\..*$", "", name)
    name = name.replace(".", " ").replace("_", " ")
    return re.sub(r"\s+", " ", name).strip()


def _fetch_assrt(cfg, video, meta):
    title = (meta or {}).get("title") or _guess_title(video)
    year = (meta or {}).get("year")
    query = f"{title} {year}".strip() if year else title
    items = [it for it in assrt.search(cfg, query) if assrt.has_chinese(it)]
    if not items:
        return None, items
    items.sort(key=lambda it: (it.get("score") or 0), reverse=True)
    best = items[0]
    files = [f for f in assrt.detail(cfg, best["id"]) if f["filename"].lower().endswith((".srt", ".ass", ".ssa"))]
    if not files:
        return None, items
    return {"item": best, "files": files}, items


def _save_zip_files(cfg, files, video, workdir):
    """把 assrt 文件下到本地并改名成 <video>.zh.<ext>，返回外挂字幕路径。"""
    base = os.path.splitext(video)[0]
    saved = None
    for f in files:
        target = base + ".zh" + os.path.splitext(f["filename"])[1]
        if not target.lower().endswith((".srt", ".ass", ".ssa")):
            continue
        r = net.http_request(cfg, "GET", f["url"], timeout=60)
        tmp = os.path.join(workdir, os.path.basename(target))
        with open(tmp, "wb") as fh:
            fh.write(r.content)
        if zipfile.is_zipfile(tmp):
            with zipfile.ZipFile(tmp) as zf:
                members = [m for m in zf.namelist() if m.lower().endswith((".srt", ".ass", ".ssa"))]
                if not members:
                    os.remove(tmp)
                    continue
                with zf.open(members[0]) as src, open(target, "wb") as dst:
                    dst.write(src.read())
            os.remove(tmp)
        else:
            os.replace(tmp, target)
        saved = target
        break
    return saved


def ensure(cfg, video, meta=None, workdir="."):
    """字幕阶梯：原片中文 → 外挂 → 内封中文 → assrt → AI 翻译。

    返回 {"action": ..., "detail": ...}，action 取值：
    original-zh / external / embedded / assrt / translated / image-only / no-track / failed
    """
    if not os.path.isfile(video):
        return {"action": "failed", "detail": "文件不存在"}
    meta = meta or {}
    if str(meta.get("original_language") or "").lower() in ("zh", "cn", "zho", "chi"):
        return {"action": "original-zh", "detail": "原片就是中文作品，不翻译"}

    ext = external_subs(video)
    if ext:
        return {"action": "external", "detail": "已有中文字幕：" + os.path.basename(ext)}

    tracks = probe(video)
    if any(is_zh_track(t) for t in tracks):
        return {"action": "embedded", "detail": "内封已含中文字幕"}

    texts = [t for t in tracks if t["type"] == "text"]
    if not texts and any(t["type"] == "image" for t in tracks):
        return {"action": "image-only", "detail": "只有图形字幕（PGS/VobSub），无法翻译"}

    assrt_token = assrt.enabled(cfg)
    if assrt_token:
        found, _items = _fetch_assrt(cfg, video, meta)
        if found:
            path = _save_zip_files(cfg, found["files"], video, workdir)
            if path:
                return {"action": "assrt", "detail": "已从 assrt 下载：" + os.path.basename(path)}

    track = _pick_source_track(tracks)
    if not track:
        return {"action": "no-track", "detail": "没有可翻译的文本字幕轨"}
    if not cfg.get("ai_enabled") or not (cfg.get("ai_api_key") or "").strip():
        return {"action": "no-track", "detail": "需要翻译但没有配置 AI 模型"}

    tmp_srt = os.path.join(workdir, "src.srt")
    extract(video, track["index"], tmp_srt)
    with open(tmp_srt, encoding="utf-8", errors="ignore") as fh:
        cues = _parse_srt(fh.read())
    os.remove(tmp_srt)
    if not cues:
        return {"action": "no-track", "detail": "字幕轨为空"}
    translated = translate(cfg, cues, meta)
    target = os.path.splitext(video)[0] + ".zh.srt"
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(_render_srt(translated))
    return {"action": "translated", "detail": f"已翻译 {len(cues)} 条 → {os.path.basename(target)}"}

def _probe_cmd(url, ua):
    return ["ffprobe", "-v", "error", "-user_agent", ua, "-select_streams", "s",
            "-show_entries", "stream=index,codec_name:stream_tags=language,title",
            "-of", "json", url]


def probe_remote(cfg, pickcode, ua="Mozilla/5.0"):
    """115 云端文件：生成直链（UA 绑定）后只读头部拿字幕轨。"""
    import p115direct
    url = p115direct.download_url(cfg, pickcode, user_agent=ua)
    r = _run(_probe_cmd(url, ua), timeout=180)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[:200])
    try:
        streams = (json.loads(r.stdout or "{}") or {}).get("streams") or []
    except Exception:
        streams = []
    out = []
    for s in streams:
        codec = (s.get("codec_name") or "").lower()
        tags = s.get("tags") or {}
        out.append({"index": int(s.get("index")), "codec": codec,
                    "type": "image" if codec in IMAGE_CODECS else "text",
                    "lang": (tags.get("language") or "").lower(), "title": tags.get("title") or ""})
    return url, out


def ensure_remote(cfg, pickcode, meta=None, upload_cid=None, ua="Mozilla/5.0", workdir="/tmp"):
    """云端阶梯：内封中字 → assrt → 抽轨翻译 → 可选上传回 115。"""
    meta = meta or {}
    title = (meta.get("title") or "subtitle").replace("/", "_")
    url, tracks = probe_remote(cfg, pickcode, ua=ua)
    if any(is_zh_track(t) for t in tracks):
        return {"action": "embedded", "detail": "内封已含中文字幕"}
    texts = [t for t in tracks if t["type"] == "text"]
    if not texts and any(t["type"] == "image" for t in tracks):
        return {"action": "image-only", "detail": "只有图形字幕（PGS/VobSub），无法翻译"}

    if assrt.enabled(cfg):
        found, _items = _fetch_assrt(cfg, title, meta)
        if found:
            target_dir = os.path.dirname(url) and workdir
            fake_video = os.path.join(workdir, title + ".mkv")
            path = _save_zip_files(cfg, found["files"], fake_video, workdir)
            if path:
                uploaded = _upload(cfg, path, upload_cid)
                return {"action": "assrt", "detail": "已从 assrt 下载" + uploaded}

    track = _pick_source_track(tracks)
    if not track:
        return {"action": "no-track", "detail": "没有可翻译的文本字幕轨"}
    if not cfg.get("ai_enabled") or not (cfg.get("ai_api_key") or "").strip():
        return {"action": "no-track", "detail": "需要翻译但没有配置 AI 模型"}

    src = os.path.join(workdir, "src.srt")
    r = _run(["ffmpeg", "-y", "-v", "error", "-user_agent", ua, "-i", url,
              "-map", f"0:{track['index']}", "-c:s", "srt", src], timeout=3600)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or "").strip()[:200])
    with open(src, encoding="utf-8", errors="ignore") as fh:
        cues = _parse_srt(fh.read())
    os.remove(src)
    if not cues:
        return {"action": "no-track", "detail": "字幕轨为空"}
    translated = translate(cfg, cues, meta)
    target = os.path.join(workdir, title + ".zh.srt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(_render_srt(translated))
    uploaded = _upload(cfg, target, upload_cid)
    return {"action": "translated", "detail": f"已翻译 {len(cues)} 条{uploaded}"}


def _upload(cfg, path, cid):
    if not cid:
        return f"，本地文件：{path}"
    try:
        import p115upload
        p115upload.upload_file(cfg, path, cid)
        return "，已上传回 115"
    except Exception as e:
        return f"，上传失败：{str(e)[:80]}"

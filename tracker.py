"""自动追剧：TMDB/Trakt 日历 → 搜索 → 按偏好选种 → 转存 115."""
import json
import os
import re
import threading
import time
from datetime import date, timedelta

import requests

import localtorrent
from localtorrent import has_progress, is_completed

_LOCAL = {"client": None}


def _local_client(cfg=None):
    try:
        c = localtorrent.make_client(cfg)
        return c if c.login() else None
    except Exception:
        return None


def _local_del(h, cfg=None):
    c = _local_client(cfg)
    if c and h:
        try:
            c.delete([h])
        except Exception:
            pass

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

_STATE_LOCK = threading.RLock()
_DATA_DIR = "/data"
_DEPS = {}
_STATE = {"done": {}, "pending": {}, "last_run": 0, "log": []}
_RUN_LOCK = threading.Lock()


def configure(data_dir, get_cfg, search_site, search_pansou, add_magnets, transfer_share, check_tasks=None, del_task=None, notify_drivemby=None, search_all=None):
    global _DATA_DIR, _DEPS
    _DATA_DIR = data_dir
    _DEPS = {
        "get_cfg": get_cfg,
        "search_site": search_site,
        "search_pansou": search_pansou,
        "add_magnets": add_magnets,
        "transfer_share": transfer_share,
        "check_tasks": check_tasks,
        "del_task": del_task,
        "notify_drivemby": notify_drivemby,
        "search_all": search_all,
    }
    _load()


def _state_path():
    return os.path.join(_DATA_DIR, "auto_state.json")


def _load():
    global _STATE
    try:
        with open(_state_path(), encoding="utf-8") as f:
            d = json.load(f)
        _STATE = {"done": d.get("done") or {}, "pending": d.get("pending") or {},
                  "last_run": d.get("last_run") or 0, "log": d.get("log") or []}
    except Exception:
        _STATE = {"done": {}, "pending": {}, "last_run": 0, "log": []}


def _save():
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_state_path(), "w", encoding="utf-8") as f:
            json.dump(_STATE, f, ensure_ascii=False)
    except Exception:
        pass


def log(msg):
    with _STATE_LOCK:
        _STATE["log"].append({"ts": int(time.time()), "msg": str(msg)})
        _STATE["log"] = _STATE["log"][-300:]
        _save()


def done_items(cfg):
    shows = {}
    for s in (cfg.get("auto_shows") or []):
        shows[str(s.get("tmdb_id"))] = s.get("title") or str(s.get("tmdb_id"))
    out = []
    with _STATE_LOCK:
        for k, ts in (_STATE.get("done") or {}).items():
            m = re.match(r"^(\d+)-S(\d+)E(\d+)$", k)
            if m:
                tid, sn, en = m.group(1), int(m.group(2)), int(m.group(3))
                out.append({"key": k, "title": shows.get(tid, tid), "season": sn, "episode": en,
                            "label": f"S{sn:02d}E{en:02d}", "kind": "tv", "done_at": ts})
                continue
            m = re.match(r"^movie-(\d+)-(\d{4}-\d{2}-\d{2})$", k)
            if m:
                out.append({"key": k, "title": shows.get(m.group(1), m.group(1)), "label": m.group(2),
                            "kind": "movie", "done_at": ts})
                continue
            out.append({"key": k, "title": k, "label": "", "kind": "other", "done_at": ts})
    out.sort(key=lambda x: x.get("done_at") or 0, reverse=True)
    return out


def remove_done(keys):
    with _STATE_LOCK:
        for k in keys or []:
            (_STATE.get("done") or {}).pop(k, None)
        _save()


def clear_done():
    with _STATE_LOCK:
        _STATE["done"] = {}
        _save()


def clear_log():
    with _STATE_LOCK:
        _STATE["log"] = []
        _save()


def status():
    with _STATE_LOCK:
        return {
            "last_run": _STATE["last_run"],
            "done_count": len(_STATE["done"]),
            "pending_count": len(_STATE.get("pending") or {}),
            "pending": [{"key": k, **v} for k, v in (_STATE.get("pending") or {}).items()],
            "log": list(_STATE["log"][-80:]),
            "running": _RUN_LOCK.locked(),
        }


# ---------------- calendar ----------------

def _tmdb(cfg, path, **params):
    key = (cfg.get("tmdb_api_key") or "").strip()
    if not key:
        return None
    params["api_key"] = key
    try:
        r = requests.get("https://api.themoviedb.org/3" + path, params=params,
                         headers={"User-Agent": UA}, timeout=20)
        return r.json()
    except Exception:
        return None


def _trakt_recent(cfg, days):
    client_id = (cfg.get("trakt_client_id") or "").strip()
    token = (cfg.get("trakt_token") or "").strip()
    if not client_id or not token:
        return None
    start = (date.today() - timedelta(days=max(0, days - 1))).isoformat()
    try:
        r = requests.get(f"https://api.trakt.tv/calendars/my/shows/{start}/{days}",
                         headers={"Content-Type": "application/json",
                                  "trakt-api-version": "2", "trakt-api-key": client_id,
                                  "Authorization": "Bearer " + token}, timeout=20)
        if r.status_code != 200:
            log(f"[trakt] HTTP {r.status_code}: {r.text[:120]}")
            return []
        data = r.json() or []
        entries = []
        for day in data:
            if not isinstance(day, dict):
                continue
            if day.get("show") and day.get("episode"):
                entries.append(day)
            elif day.get("episodes"):
                entries.extend(day.get("episodes") or [])
        out = []
        for item in entries:
            show = item.get("show") or {}
            ep = item.get("episode") or {}
            tid = ((show.get("ids") or {}).get("tmdb"))
            sn = ep.get("season")
            en = ep.get("number")
            if not tid or sn is None or en is None:
                continue
            title = show.get("title") or str(tid)
            out.append({
                "key": f"{tid}-S{int(sn):02d}E{int(en):02d}",
                "tmdb_id": tid, "media_type": "tv", "show": title, "show_en": title,
                "season": int(sn), "episode": int(en),
                "title": ep.get("title") or "", "air_date": (item.get("first_aired") or "")[:10],
                "query": f"{title} S{int(sn):02d}E{int(en):02d}",
            })
        return out
    except Exception as e:
        log(f"[trakt] 请求失败: {e}")
        return []


def _preset_map(cfg):
    return {str(p.get("id")): p for p in (cfg.get("auto_presets") or [])}


def _active_preset(cfg, media_type):
    pid = cfg.get("auto_tv_preset") if media_type != "movie" else cfg.get("auto_movie_preset")
    if not pid:
        return None
    p = _preset_map(cfg).get(str(pid))
    if p and (p.get("media_type") or media_type) == media_type:
        return p
    return None


def _tmdb_recent(cfg, days, shows=None):
    shows = (cfg.get("auto_shows") if shows is None else shows) or []
    out = []
    presets = _preset_map(cfg)
    for show in shows:
        preset = presets.get(str(show.get("preset_id") or "")) or {}
        days = max(1, int(show.get("days") or preset.get("days") or cfg.get("auto_days") or 2))
        since = date.today() - timedelta(days=days - 1)
        tid = show.get("tmdb_id")
        if not tid:
            continue
        if show.get("enabled") is False:
            continue
        if (show.get("media_type") or "tv") == "movie":
            movie = _movie_recent(cfg, show)
            if movie:
                out.extend(movie)
            continue
        detail = _tmdb(cfg, f"/tv/{tid}", language="zh-CN")
        if detail is None:
            time.sleep(2)
            detail = _tmdb(cfg, f"/tv/{tid}", language="zh-CN")
        if detail is None:
            log(f"[auto] {show.get('title') or tid}：TMDB 请求失败，稍后重试")
            continue
        detail_en = _tmdb(cfg, f"/tv/{tid}", language="en-US") or {}
        name = detail.get("name") or show.get("title") or str(tid)
        show_en = detail_en.get("name") or detail_en.get("original_name") or detail.get("original_name") or name
        name_clean = re.sub(r"[（(][^）)]*[）)]", "", name).strip() or name
        try:
            alt = _tmdb(cfg, f"/tv/{tid}/alternative_titles") or {}
            for t in (alt.get("titles") or []):
                tt = (t.get("title") or "").strip()
                if tt and not re.search(r"[\u4e00-\u9fff]", tt) and len(tt) > len(show_en if re.search(r"[\u4e00-\u9fff]", show_en or "") else ""):
                    show_en = tt
                    break
        except Exception:
            pass
        if re.search(r"[\u4e00-\u9fff]", show_en or ""):
            show_en = name_clean
        seasons = [s for s in (detail.get("seasons") or []) if int(s.get("season_number") or 0) > 0]
        before = len(out)
        for s in seasons[-3:]:
            sn = int(s["season_number"])
            sd = _tmdb(cfg, f"/tv/{tid}/season/{sn}", language="zh-CN")
            if sd is None:
                log(f"[auto] {name}：TMDB 第 {sn} 季请求失败，稍后重试")
                before = -1
                continue
            for ep in sd.get("episodes") or []:
                ad = ep.get("air_date")
                if not ad:
                    continue
                try:
                    d = date.fromisoformat(ad)
                except Exception:
                    continue
                if not (since <= d <= date.today()):
                    continue
                en = int(ep.get("episode_number") or 0)
                queries = [f"{name_clean} S{sn:02d}E{en:02d}", f"{show_en} S{sn:02d}E{en:02d}"]
                if sn == 1 and en >= 50:
                    queries += [f"{show_en} {en}", f"{name_clean} {en}",
                                f"{show_en} E{en}", f"{name_clean} 第{en}集"]
                out.append({
                    "key": f"{tid}-S{sn:02d}E{en:02d}", "tmdb_id": tid, "media_type": "tv",
                    "show": name, "show_en": show_en,
                    "season": sn, "episode": en, "title": ep.get("name") or "",
                    "air_date": ad, "query": queries[0],
                    "queries": list(dict.fromkeys([q for q in queries if q.strip()])),
                })
        if before >= 0 and len(out) == before:
            log(f"[auto] {name}：最近 {days} 天没有播出的剧集")
    return out


def _movie_recent(cfg, show):
    tid = show.get("tmdb_id")
    days = max(1, int(cfg.get("auto_days") or 2))
    since = date.today() - timedelta(days=max(0, days - 1))
    detail = _tmdb(cfg, f"/movie/{tid}", language="zh-CN") or {}
    detail_en = _tmdb(cfg, f"/movie/{tid}", language="en-US") or {}
    title = detail.get("title") or show.get("title") or str(tid)
    title_en = detail_en.get("title") or detail_en.get("original_title") or title
    year = (detail.get("release_date") or detail_en.get("release_date") or "")[:4]
    rel = _tmdb(cfg, f"/movie/{tid}/release_dates") or {}
    dates = []
    for country in (rel.get("results") or []):
        for rd in (country.get("release_dates") or []):
            raw = (rd.get("release_date") or "")[:10]
            try:
                d = date.fromisoformat(raw)
            except Exception:
                continue
            dates.append((rd.get("type") or 99, d))
    # 以主发行日为准（没有则取最早的发行日期）；wishlist 从发行日起持续检查
    chosen = None
    primary = (detail.get("release_date") or detail_en.get("release_date") or "")[:10]
    try:
        chosen = date.fromisoformat(primary) if primary else None
    except Exception:
        chosen = None
    if not chosen:
        all_dates = sorted(d for (_t, d) in dates)
        chosen = all_dates[0] if all_dates else None
    if not chosen or chosen > date.today():
        return []
    q = f"{title_en} {year}".strip()
    return [{
        "key": f"movie-{tid}-{chosen.isoformat()}", "tmdb_id": tid, "media_type": "movie",
        "show": title, "show_en": title_en, "year": year, "air_date": chosen.isoformat(),
        "query": q, "queries": list(dict.fromkeys([q, f"{title} {year}".strip()])),
        "season": 0, "episode": 0, "title": "",
    }]


def recent_episodes(cfg):
    presets = _preset_map(cfg)
    shows = [x for x in (cfg.get("auto_shows") or []) if x.get("enabled") is not False]
    tv_groups = {}
    movie_shows = []
    trakt_creds = None
    for show in shows:
        if (show.get("media_type") or "tv") == "movie":
            movie_shows.append(show)
            continue
        pr = presets.get(str(show.get("preset_id") or "")) or {}
        src = (pr.get("calendar_source") or cfg.get("calendar_source") or "tmdb").lower()
        tv_groups.setdefault(src, []).append(show)
        if src == "trakt" and pr.get("trakt_client_id") and pr.get("trakt_token") and not trakt_creds:
            trakt_creds = (pr["trakt_client_id"], pr["trakt_token"])
    default_days = max(1, int(cfg.get("auto_days") or 2))
    eps = []
    tmdb_key = (cfg.get("tmdb_api_key") or "").strip()
    if tv_groups.get("tmdb"):
        if not tmdb_key:
            log("[auto] 有剧集使用 TMDB 日历，但未配置 TMDB API Key")
        else:
            eps.extend(_tmdb_recent(cfg, default_days, shows=tv_groups["tmdb"]))
    if tv_groups.get("trakt"):
        creds = trakt_creds or ((cfg.get("trakt_client_id") or "").strip(), (cfg.get("trakt_token") or "").strip())
        if not (creds[0] and creds[1]):
            log("[auto] 有剧集使用 Trakt 日历，但 Trakt Client ID / Token 未配置")
        else:
            trakt_cfg = dict(cfg, trakt_client_id=creds[0], trakt_token=creds[1])
            eff_days = {}
            for show in tv_groups["trakt"]:
                pr = presets.get(str(show.get("preset_id") or "")) or {}
                eff_days[int(show.get("tmdb_id") or 0)] = max(1, int(show.get("days") or pr.get("days") or default_days))
            max_days = max(eff_days.values())
            got = _trakt_recent(trakt_cfg, max_days) or []
            today = date.today()
            kept = []
            for e in got:
                tid = int(e.get("tmdb_id") or 0)
                if tid not in eff_days:
                    continue
                try:
                    d = date.fromisoformat((e.get("air_date") or "")[:10])
                except Exception:
                    continue
                if today - timedelta(days=eff_days[tid] - 1) <= d <= today:
                    kept.append(e)
            log(f"[auto] Trakt 日历近 {max_days} 天共 {len(got)} 条，追剧列表内 {len(kept)} 条")
            eps.extend(kept)
            # Trakt 日历里没有的剧集回退到 TMDB，避免静默跳过
            if tmdb_key:
                hit_tids = {int(e.get("tmdb_id") or 0) for e in kept}
                missing = [sh for sh in tv_groups["trakt"] if int(sh.get("tmdb_id") or 0) not in hit_tids]
                if missing:
                    for sh in missing:
                        log(f"[auto] {sh.get('title') or sh.get('tmdb_id')}：Trakt 日历中没有记录，回退 TMDB 检查")
                    eps.extend(_tmdb_recent(cfg, default_days, shows=missing))
    if movie_shows:
        if not tmdb_key:
            log("[auto] 有电影条目，但未配置 TMDB API Key")
        else:
            eps.extend(_tmdb_recent(cfg, default_days, shows=movie_shows))
    seen, out = set(), []
    for e in eps:
        if e["key"] in seen:
            continue
        seen.add(e["key"])
        out.append(e)
    return out


# ---------------- selection ----------------

_RES_ALIASES = {
    "2160p": ("2160p", "2160", "4k", "uhd"),
    "1080p": ("1080p", "1080", "fhd"),
    "720p": ("720p", "720"),
    "480p": ("480p", "480"),
}


def _res_rank(name, order):
    low = (name or "").lower()
    for i, r in enumerate(order):
        pats = _RES_ALIASES.get(r.lower(), (r.lower(),))
        if any(p in low for p in pats):
            return i
    return len(order)


def _size_gb(it):
    size = it.get("size") or 0
    return round(size / (1024 ** 3), 2) if size else 0


STOP_WORDS = {"the", "and", "for", "with", "of", "a", "an", "to", "in", "on", "part", "season"}

AUDIO_ONLY_RE = re.compile(
    r"(?<![a-z0-9])(flac|alac|dsf|dff|m4a|mp3|ost|soundtrack|soundtracks|"
    r"lossless|hires|hi-res|vinyl|vinylrip|album|320kbps|320k|vbr|v0)(?![a-z0-9])"
)
AUDIO_ONLY_CN = ("原声", "原聲", "无损", "無損", "专辑", "專輯")

CAM_RE = re.compile(
    r"(?<![a-z0-9])(cam|camrip|hdcam|hqcam|hdts|hdtc|telesync|telecine|tsrip)(?![a-z0-9])"
)
CAM_UPPER_RE = re.compile(r"(?<![A-Za-z0-9])(TS|TC)(?![A-Za-z0-9])")
CAM_CN = ("枪版", "槍版", "抢先版", "搶先版", "录屏", "錄屏")


def is_cam_release(title):
    raw = title or ""
    if CAM_RE.search(raw.lower()):
        return True
    for m in CAM_UPPER_RE.finditer(raw):
        if raw[m.end():].strip(" ._-[]()"):
            return True
    return any(w in raw for w in CAM_CN)


def is_video_release(title):
    low = (title or "").lower()
    if AUDIO_ONLY_RE.search(low):
        return False
    return not any(w in low for w in AUDIO_ONLY_CN)


def strict_match(item, episode):
    title = (item.get("title") or "").lower()
    if (episode.get("media_type") or "tv") == "movie":
        raw = f"{episode.get('show_en') or ''} {episode.get('show') or ''}"
        if re.search(r"[\u4e00-\u9fff]", raw):
            for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", raw):
                if chunk in title:
                    return True
        tokens = {t for t in re.findall(r"[a-z0-9]+", raw.lower()) if len(t) >= 3 and t not in STOP_WORDS}
        title_tokens = set(re.findall(r"[a-z0-9]+", title))
        if not tokens or len(tokens & title_tokens) < max(1, min(2, len(tokens))):
            return False
        year = episode.get("year") or ""
        if year and year not in title:
            return False
        return True
    sn, en = int(episode["season"]), int(episode["episode"])
    m = re.search(rf"(?<![a-z0-9])s0*{sn}[ ._-]?e0*{en}(?![0-9])", title)
    if not m and sn == 1 and en >= 50:
        m = re.search(rf"(?<![a-z0-9])(?:e|ep)?0*{en}(?:集)?(?![0-9])", title)
    if not m:
        return False
    prefix = title[:m.start()]  # 剧名必须出现在集号之前
    raw = f"{episode.get('show_en') or ''} {episode.get('show') or ''}"
    if re.search(r"[\u4e00-\u9fff]", raw):
        for chunk in re.findall(r"[\u4e00-\u9fff]{2,}", raw):
            if chunk in prefix:
                return True
    tokens = {t for t in re.findall(r"[a-z0-9]+", raw.lower()) if len(t) >= 3 and t not in STOP_WORDS}
    prefix_tokens = set(re.findall(r"[a-z0-9]+", prefix))
    return len(tokens & prefix_tokens) >= max(1, min(2, len(tokens)))


def rank_candidates(cfg, items, episode=None):
    order = cfg.get("auto_res_order") or ["2160p", "1080p", "720p"]
    codec = (cfg.get("auto_codec") or "").lower()
    min_seed = int(cfg.get("auto_min_seeders") or 0)
    max_gb = float(cfg.get("auto_max_size_gb") or 0)
    out = []
    strict = bool(cfg.get("auto_strict_match"))
    exclude_cam = bool(cfg.get("auto_exclude_cam", True)) and (episode or {}).get("media_type") == "movie"
    for it in items:
        if not is_video_release(it.get("title")):
            continue
        if exclude_cam and is_cam_release(it.get("title")):
            continue
        if strict and episode and it.get("kind") != "115" and not strict_match(it, episode):
            continue
        if it.get("kind") == "115":
            out.append(it)
            continue
        if (it.get("seeders") or 0) < min_seed:
            continue
        gb = _size_gb(it)
        if max_gb and gb and gb > max_gb:
            continue
        out.append(it)

    tiers = sorted(int(x) for x in (cfg.get("auto_seed_tiers") or [10, 100, 1000, 10000]) if str(x).strip())

    def seed_bucket(seeders):
        return sum(1 for t in tiers if seeders >= t)

    keys = cfg.get("auto_rank_order") or ["shares", "seeders", "resolution", "size", "codec"]
    # 补齐未配置的维度，保证排序稳定
    for k in ("shares", "seeders", "resolution", "size", "codec"):
        if k not in keys:
            keys.append(k)

    def part(key, it):
        if key == "shares":
            return 0 if it.get("kind") == "115" else 1
        if key == "seeders":
            return -seed_bucket(int(it.get("seeders") or 0))
        if key == "resolution":
            return _res_rank(it.get("title") or "", order)
        if key == "size":
            big = bool(cfg.get("auto_size_big", True))
            return -_size_gb(it) if big else _size_gb(it)
        if key == "codec":
            return 0 if (codec and codec in (it.get("title") or "").lower()) else 1
        return 0

    src_order = cfg.get("auto_source_order") or []

    def score(it):
        parts = [part(k, it) for k in keys]
        if src_order:
            src = it.get("source") or ""
            srank = src_order.index(src) if src in src_order else len(src_order)
            idx = keys.index("shares") + 1 if "shares" in keys else 0
            parts.insert(idx, srank)
        return tuple(parts)

    return sorted(out, key=score)


def ai_pick(cfg, episode, candidates):
    if not cfg.get("ai_enabled") or not cfg.get("ai_api_key") or not candidates:
        return None
    base = (cfg.get("ai_base_url") or "https://api.openai.com/v1").rstrip("/")
    model = cfg.get("ai_model") or "gpt-4o-mini"
    pref = cfg.get("auto_res_order") or ["2160p", "1080p", "720p"]
    rows = [{"index": i, "title": c.get("title", "")[:160], "kind": c.get("kind"),
             "size_gb": _size_gb(c), "seeders": c.get("seeders") or 0} for i, c in enumerate(candidates[:25])]
    prompt = (
        f"剧集：{episode['show']} S{episode['season']:02d}E{episode['episode']:02d}\n"
        f"清晰度优先级：{', '.join(pref)}\n"
        f"编码偏好：{cfg.get('auto_codec') or '不限'}；最大体积：{cfg.get('auto_max_size_gb') or '不限'}GB；"
        f"最小种子：{cfg.get('auto_min_seeders') or 0}\n"
        f"候选资源（JSON）：{json.dumps(rows, ensure_ascii=False)}\n"
        "请只返回最合适的候选 index 数字，不要解释。"
    )
    try:
        proxy = (cfg.get("outbound_proxy") or "").strip()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        r = requests.post(base + "/chat/completions",
                          headers={"Authorization": "Bearer " + cfg["ai_api_key"],
                                   "Content-Type": "application/json"},
                          json={"model": model, "temperature": 0,
                                "messages": [{"role": "user", "content": prompt}]},
                          proxies=proxies, timeout=40)
        r.raise_for_status()
        text = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\d+", text or "")
        if not m:
            return None
        idx = int(m.group(0))
        if 0 <= idx < len(candidates):
            log(f"[ai] {episode['key']} 选择候选 #{idx}: {candidates[idx].get('title','')[:80]}")
            return candidates[idx]
    except Exception as e:
        log(f"[ai] 调用失败: {e}")
    return None


# ---------------- run ----------------

def _hash_of(url):
    m = re.search(r"btih:([0-9a-fA-F]{32,40})", url or "")
    return m.group(1).lower() if m else ""


def _exists_in_tasks(task_map, ep):
    if not task_map:
        return False
    est, een = ep.get("season"), ep.get("episode")
    names = []
    for t in task_map.values():
        names.append((t.get("name") or "").lower())
    show = (ep.get("show_en") or ep.get("show") or "").lower()
    tokens = [x for x in re.findall(r"[a-z0-9]+", show) if len(x) >= 4]
    if ep.get("media_type") == "movie":
        title_tokens = [x for x in re.findall(r"[a-z0-9]+", show) if len(x) >= 4]
        return any(any(tok in n for tok in title_tokens) for n in names)
    if est is None or een is None:
        return False
    for n in names:
        m = re.search(r"s(\d{1,2})[ ._-]?e(\d{1,3})", n)
        if not m:
            continue
        if int(m.group(1)) != int(est) or int(m.group(2)) != int(een):
            continue
        if not tokens or any(tok in n for tok in tokens):
            return True
    return False


def _eff_cfg(cfg, show, presets, keypair):
    eff = dict(cfg)
    preset = presets.get(str(show.get("preset_id") or "")) or {}
    if preset and (preset.get("media_type") or "tv") != keypair[1]:
        preset = {}
    for src, dst in (("days", "auto_days"), ("res_order", "auto_res_order"),
                     ("max_size_gb", "auto_max_size_gb"), ("min_seeders", "auto_min_seeders"),
                     ("codec", "auto_codec"), ("strict_match", "auto_strict_match"),
                     ("rank_order", "auto_rank_order"), ("seed_tiers", "auto_seed_tiers"),
                     ("size_big", "auto_size_big"), ("source_order", "auto_source_order"),
                     ("wait_timeout", "auto_wait_timeout"), ("use_local", "auto_use_local"),
                     ("exclude_cam", "auto_exclude_cam")):
        v = preset.get(src)
        if v not in (None, "", []):
            eff[dst] = v
    eff["ai_enabled"] = False
    if preset.get("ai_enabled"):
        aip = {str(a.get("id")): a for a in (cfg.get("ai_presets") or [])}.get(str(preset.get("ai_preset_id") or ""))
        if aip:
            eff["ai_enabled"] = True
            eff["ai_base_url"] = aip.get("base_url") or "https://api.openai.com/v1"
            eff["ai_model"] = aip.get("model") or "gpt-4o-mini"
            eff["ai_api_key"] = aip.get("api_key") or ""
    for src, dst in (("res_order", "auto_res_order"), ("max_size_gb", "auto_max_size_gb"),
                     ("min_seeders", "auto_min_seeders"), ("codec", "auto_codec"),
                     ("strict_match", "auto_strict_match"), ("days", "auto_days")):
        v = show.get(src)
        if v not in (None, "", []):
            eff[dst] = v
    if show.get("ai_rank") is True:
        eff["ai_enabled"] = True
    elif show.get("ai_rank") is False:
        eff["ai_enabled"] = False
    return eff


def _notify_drivemby(cfg, ep, file_id=None):
    cb = _DEPS.get("notify_drivemby")
    if not cb:
        return
    try:
        ok, msg = cb(cfg, file_id)
        log(f"[auto] {ep['key']} Drivemby 刷新{'成功' if ok else '异常'}：{msg}")
    except Exception as e:
        log(f"[auto] {ep['key']} Drivemby 刷新失败：{e}")


def _label(ep):
    return f"{ep.get('show') or ''} {ep['key']}".strip()


def _process_episode(cfg, ep, eff, dry_run, excluded, timeout_min):
    queries = ep.get("queries") or [ep["query"]]
    candidates = _DEPS["search_all"](cfg, queries)
    total = len(candidates)
    ranked = rank_candidates(eff, candidates, ep)
    if excluded:
        filtered = [x for x in ranked if _hash_of(x.get("url")) not in excluded]
        if filtered:
            ranked = filtered
        else:
            log(f"[auto] {_label(ep)} 候选都尝试过了，重新枚举")
    if eff.get("auto_strict_match"):
        log(f"[auto] {_label(ep)} 候选 {total} 条，严格匹配后 {len(ranked)} 条")
    if not ranked:
        log(f"[auto] {_label(ep)} 未找到合适资源")
        return "none"
    pick = ai_pick(eff, ep, ranked) or ranked[0]
    desc = f"{pick.get('title','')[:90]} (来源={pick.get('source') or '未知'}, seeders={pick.get('seeders')}, size={_size_gb(pick)}GB)"
    if dry_run:
        log(f"[auto][演练] {_label(ep)} 将转存: {desc}")
        return "dry"
    if pick.get("kind") == "115":
        try:
            _DEPS["transfer_share"](cfg, pick["url"], pick.get("password") or "")
        except Exception as e:
            log(f"[auto] {_label(ep)} 转存失败: {e}")
            return "fail"
        with _STATE_LOCK:
            _STATE["done"][ep["key"]] = int(time.time())
            _STATE["pending"].pop(ep["key"], None)
            _save()
        log(f"[auto] {_label(ep)} 转存成功: {desc}")
        _notify_drivemby(cfg, ep)
        return "done"
    h = _hash_of(pick.get("url"))
    tried = set(excluded or [])
    if h:
        tried.add(h)
    _chk = _DEPS.get("check_tasks")
    existing = ((_chk(cfg) if _chk else {}) or {}).get(h) if h else None
    if existing:
        pct = existing.get("percentDone") or existing.get("display_percent") or 0
        with _STATE_LOCK:
            _STATE["pending"][ep["key"]] = {"hash": h, "local_hash": local_hash, "ts": int(time.time()), "last_pct": pct,
                                            "check_ts": int(time.time()), "ep": ep, "tried": sorted(tried)}
            _save()
        log(f"[auto] {_label(ep)} 该磁力任务已存在，记为下载中（{pct}%）")
        return "pending"
    try:
        _DEPS["add_magnets"](cfg, [pick["url"]])
    except Exception as e:
        log(f"[auto] {_label(ep)} 提交云下载失败: {e}")
        return "fail"
    local_hash = None
    if eff.get("auto_use_local"):
        lc = _local_client(cfg)
        if not lc:
            log(f"[auto] {_label(ep)} 本地下载器未就绪，仅使用 115")
        else:
            try:
                lc.add_magnet(pick["url"], savepath=cfg.get("local_save_path") or "/vol1/1000/Downloads")
                local_hash = h
                log(f"[auto] {_label(ep)} 已同时加入本地下载器")
            except Exception as e:
                log(f"[auto] {_label(ep)} 加入本地下载器失败: {e}")
    checker = _DEPS.get("check_tasks")
    task = None
    finished = False
    if h and checker:
        for _ in range(2):
            try:
                tasks = checker(cfg)
            except Exception:
                tasks = {}
            task = tasks.get(h)
            if task:
                st = task.get("status")
                pct = task.get("percentDone") or task.get("display_percent") or 0
                if st == 2 or pct >= 99.9:
                    finished = True
                    break
                if st in (3, 4) or "失败" in (task.get("status_text") or ""):
                    break
            time.sleep(3)
    now = int(time.time())
    if finished:
        with _STATE_LOCK:
            _STATE["done"][ep["key"]] = now
            _STATE["pending"].pop(ep["key"], None)
            _save()
        log(f"[auto] {_label(ep)} 云下载完成（已确认）: {desc}")
        _local_del(local_hash, cfg)
        _notify_drivemby(cfg, ep, (task or {}).get("file_id"))
        return "done"
    if h and task:
        pct = task.get("percentDone") or task.get("display_percent") or 0
        with _STATE_LOCK:
            _STATE["pending"][ep["key"]] = {"hash": h, "local_hash": local_hash, "ts": now, "last_pct": pct,
                                            "check_ts": now, "ep": ep, "tried": sorted(tried)}
            _save()
        log(f"[auto] {_label(ep)} 已提交，云下载中（{pct}%）: {desc}")
        return "pending"
    with _STATE_LOCK:
        _STATE["done"][ep["key"]] = now
        _save()
    log(f"[auto] {_label(ep)} 已提交（未读取到任务状态，按成功处理）: {desc}")
    return "done"


def run_once(cfg, dry_run=False, only_shows=None):
    if not _RUN_LOCK.acquire(blocking=False):
        log("[auto] 已有任务在运行，跳过")
        return
    try:
        with _STATE_LOCK:
            _STATE["last_run"] = int(time.time())
            _save()
        episodes = recent_episodes(cfg)
        cap = int(cfg.get("auto_max_episodes") or 0)
        if cap > 0:
            episodes = episodes[:cap]
            log(f"[auto] 日历共 {len(episodes)} 个条目待检查（本次最多 {cap} 个，逐条串行处理）")
        else:
            log(f"[auto] 日历共 {len(episodes)} 个条目待检查（不限量，逐条串行处理）")
        shows = {(int(x.get("tmdb_id") or 0), x.get("media_type") or "tv"): x for x in (cfg.get("auto_shows") or [])}
        presets = _preset_map(cfg)
        only = {(int(a), b or "tv") for a, b in (only_shows or [])}
        checker = _DEPS.get("check_tasks")
        deleter = _DEPS.get("del_task")
        timeout_min = max(0, int(cfg.get("auto_task_timeout") or 10))
        wait_timeout = max(0, int(cfg.get("auto_wait_timeout") or 3))
        task_map = {}
        if checker:
            try:
                task_map = checker(cfg)
            except Exception as e:
                log(f"[auto] 获取云下载任务列表失败: {e}")
        retry_eps = []
        notify_after = []
        delete_after = []
        local_delete_after = []
        local_hashes = [v.get("local_hash") for v in (_STATE.get("pending") or {}).values() if v.get("local_hash")]
        local_map = {}
        lc = _local_client(cfg) if local_hashes else None
        if lc and local_hashes:
            try:
                local_map = lc.torrents(local_hashes)
            except Exception as e:
                log(f"[auto] 查询本地下载器失败: {e}")
        with _STATE_LOCK:
            for key in list((_STATE.get("pending") or {}).keys()):
                info = _STATE["pending"].get(key) or {}
                h = info.get("hash") or ""
                ep = info.get("ep")
                tried = set(info.get("tried") or ([h] if h else []))
                t = task_map.get(h) if h else None
                lh = info.get("local_hash") or ""
                lt = local_map.get(lh) if lh else None
                if not t:
                    if lt and has_progress(lt):
                        if is_completed(lt):
                            _STATE["done"][key] = int(time.time())
                            _STATE["pending"].pop(key, None)
                            _save()
                            log(f"[auto] {key} 本地下载完成（115 任务已不存在）")
                        else:
                            log(f"[auto] {key} 本地下载中，继续等待")
                        continue
                    _STATE["pending"].pop(key, None)
                    _save()
                    log(f"[auto] {key} 云下载任务不存在，重新处理")
                    if lh:
                        local_delete_after.append(lh)
                    if ep:
                        retry_eps.append((ep, tried))
                    continue
                st = t.get("status")
                pct = t.get("percentDone") or t.get("display_percent") or 0
                if st == 2 or pct >= 99.9:
                    _STATE["done"][key] = int(time.time())
                    _STATE["pending"].pop(key, None)
                    _save()
                    log(f"[auto] {key} 云下载完成（已确认）")
                    if lh:
                        local_delete_after.append(lh)
                    notify_after.append((ep or {"key": key}, t.get("file_id")))
                elif lt and is_completed(lt):
                    _STATE["done"][key] = int(time.time())
                    _STATE["pending"].pop(key, None)
                    _save()
                    delete_after.append(h)
                    log(f"[auto] {key} 本地下载完成，删除 115 任务")
                elif st in (3, 4) or "失败" in (t.get("status_text") or ""):
                    _STATE["pending"].pop(key, None)
                    _save()
                    delete_after.append(h)
                    if lh:
                        local_delete_after.append(lh)
                    if ep:
                        retry_eps.append((ep, tried))
                    log(f"[auto] {key} 云下载失败：{t.get('status_text') or st}，将重试新链接")
                else:
                    now = int(time.time())
                    last_pct = info.get("last_pct")
                    check_ts = info.get("check_ts") or info.get("ts") or now
                    active_down = any(
                        (int(t.get("percentDone") or 0) > 0 and t.get("status") == 1)
                        for t in task_map.values()
                    )
                    if last_pct is None or pct != last_pct:
                        info["last_pct"] = pct
                        info["check_ts"] = now
                        _STATE["pending"][key] = info
                        _save()
                        log(f"[auto] {key} 云下载中（{pct}%）")
                    elif pct == 0 and st == 1:
                        if active_down:
                            info["queue_since"] = now
                            _STATE["pending"][key] = info
                            _save()
                            log(f"[auto] {key} 115 排队等待中（已有任务在下载）")
                        else:
                            base = info.get("queue_since") or check_ts
                            if wait_timeout > 0 and now - base >= wait_timeout * 60:
                                if lt and has_progress(lt):
                                    delete_after.append(h)
                                    _STATE["pending"][key] = info
                                    _save()
                                    log(f"[auto] {key} 本地已有进度，删除 115 任务，继续等本地")
                                else:
                                    _STATE["pending"].pop(key, None)
                                    _save()
                                    delete_after.append(h)
                                    if lh:
                                        local_delete_after.append(lh)
                                    if ep:
                                        retry_eps.append((ep, tried))
                                    log(f"[auto] {key} 等待 {wait_timeout} 分钟无 peer，删除任务并重试新链接")
                            else:
                                _STATE["pending"][key] = info
                                _save()
                                log(f"[auto] {key} 等待中（暂无 peer），{wait_timeout} 分钟后重试")
                    elif timeout_min > 0 and now - check_ts >= timeout_min * 60:
                        _STATE["pending"].pop(key, None)
                        _save()
                        delete_after.append(h)
                        if lh:
                            local_delete_after.append(lh)
                        if ep:
                            retry_eps.append((ep, tried))
                        log(f"[auto] {key} 超过 {timeout_min} 分钟无进展，删除任务并重试新链接")
                    else:
                        log(f"[auto] {key} 云下载中（{pct}%），{timeout_min} 分钟无进展会自动重试")
        for h in delete_after:
            if deleter and h:
                try:
                    deleter(cfg, h)
                except Exception:
                    pass
        for lh in local_delete_after:
            _local_del(lh, cfg)
        for nep, nfid in notify_after:
            _notify_drivemby(cfg, nep, nfid)
        for ep, tried in retry_eps:
            if only and (int(ep.get("tmdb_id") or 0), ep.get("media_type") or "tv") not in only:
                continue
            with _STATE_LOCK:
                if ep["key"] in _STATE["done"]:
                    continue
            keypair = (int(ep.get("tmdb_id") or 0), ep.get("media_type") or "tv")
            show = shows.get(keypair) or {}
            eff = _eff_cfg(cfg, show, presets, keypair)
            if _exists_in_tasks(task_map, ep):
                with _STATE_LOCK:
                    _STATE["done"][ep["key"]] = int(time.time())
                    _save()
                log(f"[auto] {ep['key']} 115 任务列表里已存在，标记完成")
                continue
            log(f"[auto] 重试 {ep['key']}（排除已尝试的 {len(tried)} 个候选）")
            _process_episode(cfg, ep, eff, dry_run, tried, timeout_min)
            time.sleep(1.2)
        for ep in episodes:
            keypair = (int(ep.get("tmdb_id") or 0), ep.get("media_type") or "tv")
            if only and keypair not in only:
                continue
            with _STATE_LOCK:
                if ep["key"] in _STATE["done"] or ep["key"] in _STATE.get("pending", {}):
                    continue
            if _exists_in_tasks(task_map, ep):
                with _STATE_LOCK:
                    _STATE["done"][ep["key"]] = int(time.time())
                    _save()
                log(f"[auto] {ep['key']} 115 任务列表里已存在，标记完成跳过")
                continue
            show = shows.get(keypair) or {}
            eff = _eff_cfg(cfg, show, presets, keypair)
            _process_episode(cfg, ep, eff, dry_run, set(), timeout_min)
            time.sleep(1.2)
    finally:
        _RUN_LOCK.release()


def is_running():
    return _RUN_LOCK.locked()


def start_run(dry_run=False, only_shows=None):
    cfg = _DEPS["get_cfg"]()
    t = threading.Thread(target=run_once, args=(cfg, dry_run, only_shows), daemon=True)
    t.start()
    return True


def _effective_interval(cfg):
    presets = _preset_map(cfg)
    vals = []
    for show in (cfg.get("auto_shows") or []):
        if show.get("enabled") is False:
            continue
        pr = presets.get(str(show.get("preset_id") or "")) or {}
        vals.append(int(pr.get("interval") or cfg.get("auto_interval") or 180))
    return max(5, min(vals)) if vals else max(5, int(cfg.get("auto_interval") or 180))


def loop():
    while True:
        try:
            cfg = _DEPS["get_cfg"]()
            shows = [x for x in (cfg.get("auto_shows") or []) if x.get("enabled") is not False]
            if shows:
                run_once(cfg, dry_run=False)
        except Exception as e:
            log(f"[auto] 循环异常: {e}")
        try:
            interval = _effective_interval(_DEPS["get_cfg"]())
        except Exception:
            interval = 180
        time.sleep(interval * 60)

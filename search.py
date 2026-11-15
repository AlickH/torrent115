#!/usr/bin/env python3
"""搜索：TMDB 标题解析 + 多站点 + PanSou。"""
import base64
import hashlib
import hmac
import json
import random
import re
import string
import time
import urllib.parse
from concurrent.futures import ThreadPoolExecutor

import requests

from net import UA, http_request

TAG_RE = re.compile(r"<[^>]+>")
TORRENT_HREF_RE = re.compile(r"href=[\"']([^\"']+\.torrent[^\"']*)[\"']", re.I)


_RESOLVE_CACHE = {}

def parse_name_meta(name):
    low = (name or "").lower()
    out = []
    m = re.search(r"(2160p|1080p|720p|480p|4k|8k)", low)
    if m:
        out.append(m.group(1).upper() if m.group(1) in ("4k", "8k") else m.group(1))
    m = re.search(r"(bluray|blu-ray|remux|webrip|web-dl|webdl|web|hdtv|dvdrip|bdrip|hdcam|ts)", low)
    if m:
        out.append({"webdl": "WEBDL", "blu-ray": "BluRay", "web-dl": "WEBDL"}.get(m.group(1), m.group(1).upper()))
    m = re.search(r"(x265|hevc|h265|x264|h264|av1)", low)
    if m:
        out.append(m.group(1).upper())
    m = re.search(r"\b(19\d{2}|20\d{2})\b", low)
    if m:
        out.append(m.group(1))
    return out

def parse_apibay(text, query=""):
    items = []
    tokens = title_tokens(query)
    try:
        arr = json.loads(text)
    except Exception:
        return items
    for it in arr if isinstance(arr, list) else []:
        ih, name = it.get("info_hash"), it.get("name")
        if not ih or not name or ih == "0" * 40:
            continue
        if not token_ok(name, tokens):
            continue
        try:
            date = time.strftime("%Y-%m-%d", time.localtime(int(it.get("added") or 0)))
        except Exception:
            date = ""
        cat = TPB_CATEGORIES.get(str(it.get("category") or ""), "")
        items.append({"source": "apibay", "kind": "magnet",
                      "title": name,
                      "url": f"magnet:?xt=urn:btih:{ih}&dn={urllib.parse.quote(name)}",
                      "seeders": int(it.get("seeders") or 0),
                      "leechers": int(it.get("leechers") or 0),
                      "meta": build_meta(cat, name, int(it.get("size") or 0), int(it.get("seeders") or 0), date)})
    return items


BT_KEY = "long2ice"

BM_TYPES = {"movie": "电影", "tv_show": "剧集", "music": "音乐", "ebook": "电子书",
            "comic": "漫画", "audiobook": "有声书", "game": "游戏", "software": "软件", "xxx": "成人"}


_STOP = {"the", "and", "of", "a", "an", "to", "in", "on", "for", "with", "its", "it's"}


def clean_text(s):
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", s)).strip()

def translate_title(q):
    url = "https://translate.googleapis.com/translate_a/single"
    try:
        r = requests.get(url, params={"client": "gtx", "sl": "auto", "tl": "en", "dt": "t", "q": q},
                         headers={"User-Agent": UA}, timeout=15)
        d = r.json()
        return "".join(x[0] for x in d[0] if x and x[0]).strip()
    except Exception:
        return ""

def imdb_suggest(q):
    url = "https://v2.sg.media-imdb.com/suggestion/x/" + urllib.parse.quote(q) + ".json"
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=15)
        d = r.json()
    except Exception:
        d = {}
    for it in d.get("d") or []:
        if str(it.get("id") or "").startswith("tt"):
            return {"imdb_id": it["id"], "imdb_title": it.get("l") or "",
                    "year": it.get("y"), "type": it.get("q") or ""}
    return None

_TMDB_CACHE = {}
_TMDB_TTL = 600


def tmdb_get(cfg, path, **params):
    key = (cfg.get("tmdb_api_key") or "").strip()
    if not key:
        return None
    params["api_key"] = key
    ck = (path, tuple(sorted((k, str(v)) for k, v in params.items() if k != "api_key")))
    now = time.time()
    hit = _TMDB_CACHE.get(ck)
    if hit and now - hit[0] < _TMDB_TTL:
        return hit[1]
    last = None
    for attempt in range(3):
        try:
            r = http_request(cfg, "GET", "https://api.themoviedb.org/3" + path, params=params,
                             timeout=20, headers={"User-Agent": UA})
            if r.status_code == 429:
                last = requests.HTTPError(f"429 rate limited {path}")
                time.sleep(2 * (attempt + 1))
                continue
            data = r.json()
            _TMDB_CACHE[ck] = (time.time(), data)
            return data
        except Exception as e:
            last = e
            time.sleep(1.0 * (attempt + 1))
    print(f"[tmdb] request failed {path}: {last}", flush=True)
    return None

def tmdb_resolve(cfg, q):
    key = (cfg.get("tmdb_api_key") or "").strip()
    if not key:
        return None
    search = tmdb_get(cfg, "/search/multi", query=q, language="zh-CN", include_adult="false")
    hit = None
    for r in (search or {}).get("results") or []:
        if r.get("media_type") in ("tv", "movie"):
            hit = r
            break
    if not hit:
        return None
    mid, mt = hit["id"], hit["media_type"]
    detail = tmdb_get(cfg, f"/{mt}/{mid}", language="en-US") or {}
    title_en = (detail.get("name") or detail.get("title") or "").strip()
    original = (detail.get("original_name") or detail.get("original_title") or "").strip()
    if not title_en:
        title_en = original or hit.get("original_name") or hit.get("original_title") or ""
    ext = tmdb_get(cfg, f"/{mt}/{mid}/external_ids") or {}
    year = (detail.get("first_air_date") or detail.get("release_date") or
            hit.get("first_air_date") or hit.get("release_date") or "")[:4]
    return {"imdb_id": ext.get("imdb_id") or "",
            "title_en": title_en, "query_en": title_en,
            "year": int(year) if year.isdigit() else None, "type": mt}


def resolve_title(cfg, q):
    if q in _RESOLVE_CACHE:
        return _RESOLVE_CACHE[q]
    base_q = re.sub(r"\s*(?:s\d{1,2}(?:e\d{1,3})?|season\s*\d+|第\s*\d+\s*季)\s*$", "", q, flags=re.I)
    base_q = re.sub(r"\s+(?:19|20)\d{2}$", "", base_q).strip() or q
    found = tmdb_resolve(cfg, base_q) or tmdb_resolve(cfg, q)
    if found and not found.get("imdb_id"):
        sug = imdb_suggest(found.get("title_en") or q) or {}
        found["imdb_id"] = sug.get("imdb_id") or ""
    if not found:
        en = translate_title(q) if re.search(r"[\u4e00-\u9fff]", q) else q
        imdb = imdb_suggest(en) or imdb_suggest(q) or {}
        found = {"imdb_id": imdb.get("imdb_id") or "",
                 "title_en": imdb.get("imdb_title") or en,
                 "query_en": en,
                 "year": imdb.get("year"), "type": imdb.get("type") or ""}
    if found.get("title_en") or found.get("imdb_id") or not re.search(r"[\u4e00-\u9fff]", q):
        _RESOLVE_CACHE[q] = found
    return found

def parse_rss(text, source, query=""):
    items = []
    tokens = title_tokens(query)
    for m in re.finditer(r"<item[\s>][\s\S]*?</item>", text, re.I):
        block = m.group(0)
        t = re.search(r"<title[^>]*>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", block, re.I)
        title = clean_text(t.group(1)) if t else ""
        size_b = 0
        sm = re.search(r"<nyaa:size>([^<]+)</nyaa:size>", block, re.I)
        if sm:
            txt = sm.group(1).strip().lower()
            mm = re.match(r"([\d.]+)\s*([kmgt]?)i?b", txt)
            if mm:
                mult = {"": 1, "k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}[mm.group(2)]
                size_b = int(float(mm.group(1)) * mult)
        seeders = 0
        sd = re.search(r"<nyaa:seeders>(\d+)</nyaa:seeders>", block, re.I)
        if sd:
            seeders = int(sd.group(1))
        cat = ""
        cm = re.search(r"<category>([^<]+)</category>", block, re.I)
        if cm:
            cat = clean_text(cm.group(1))
        meta = build_meta("动漫" if "anime" in cat.lower() else "", title, size_b, seeders, "", cat)
        ih = re.search(r"<nyaa:infoHash>([0-9a-fA-F]{40})</nyaa:infoHash>", block)
        enc = re.search(r"<enclosure[^>]*url=[\"']([^\"']+\.torrent[^\"']*)[\"']", block, re.I)
        if not token_ok(title, tokens):
            continue
        if ih:
            items.append({"source": source, "kind": "magnet", "title": title,
                          "url": f"magnet:?xt=urn:btih:{ih.group(1)}&dn={urllib.parse.quote(title)}",
                          "seeders": seeders or None, "meta": meta})
        elif enc:
            url = enc.group(1)
            if url.startswith("//"):
                url = "https:" + url
            items.append({"source": source, "kind": "torrent", "title": title, "url": url})
    return items

def search_btsearch(cfg, q):
    items, seen = [], set()
    qyear = explicit_year(q)
    limit, offset, cap = 100, 0, 200
    while offset < cap:
        try:
            d = bt_search_api(cfg, {"keyword": q, "limit": limit, "offset": offset, "mode": ""})
        except Exception as e:
            return items, (None if items else f"btsearch API 请求失败: {e}")
        data = d.get("data") or []
        for it in data:
            h = it.get("hash") or ""
            name = clean_text(it.get("name") or "")
            if qyear and not year_ok(name, qyear):
                continue
            if not h or h in seen:
                continue
            seen.add(h)
            mb = int(it.get("size") or 0) // 1048576
            items.append({"source": "btsearch", "kind": "magnet", "title": name,
                          "url": f"magnet:?xt=urn:btih:{h}&dn={urllib.parse.quote(name)}",
                          "meta": build_meta("", name, int(it.get("size") or 0), None, str(it.get("created_at") or "")[:10], f"files {it.get('count', '?')}")})
        offset += limit
        if offset >= min(int(d.get("total") or 0), cap):
            break
    return items, (None if items else "没有结果")

def search_eztv(cfg, resolved):
    imdb = (resolved.get("imdb_id") or "").strip()
    imdb = re.sub(r"^tt", "", imdb)
    if not re.fullmatch(r"\d{5,}", imdb):
        return [], "未解析到 IMDb ID，无法查 EZTV"
    items = []
    for page in range(1, 6):
        try:
            r = http_request(cfg, "GET", "https://eztvx.to/api/get-torrents",
                             params={"imdb_id": imdb, "limit": 100, "page": page},
                             headers={"User-Agent": UA}, timeout=20)
            if r.status_code != 200:
                return items, f"EZTV 返回 HTTP {r.status_code}"
            d = r.json()
        except Exception as e:
            return items, f"EZTV 请求失败: {e}"
        lst = d.get("torrents") or []
        for t in lst:
            title = t.get("title") or t.get("filename") or ""
            h = (t.get("hash") or "").lower()
            magnet = t.get("magnet_url") or (_magnet(h, title) if h else "")
            if not magnet:
                continue
            try:
                date = time.strftime("%Y-%m-%d", time.localtime(int(t.get("date_released_unix") or 0)))
            except Exception:
                date = ""
            items.append({"source": "eztv", "kind": "magnet", "title": title,
                          "url": magnet, "seeders": int(t.get("seeds") or 0),
                          "meta": build_meta("剧集", title, int(t.get("size_bytes") or 0), int(t.get("seeds") or 0), date)})
        if len(lst) < 100:
            break
    return items, (None if items else "EZTV 没有结果")

def search_knaben(cfg, q, resolved, query=None):
    query = query or resolved.get("query_en") or q
    yr = explicit_year(q)
    if yr and yr not in query:
        query = (query + " " + yr).strip()
    try:
        r = http_request(cfg, "POST", "https://api.knaben.org/v1",
                          json={"search_type": "100%", "search_field": "title", "query": query,
                                "order_by": "seeders", "order_direction": "desc",
                                "size": 200, "hide_unsafe": True, "hide_xxx": True},
                          headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return [], f"knaben 请求失败: {e}"
    tokens = title_tokens(query)
    items = []
    for h in d.get("hits") or []:
        title = h.get("title") or ""
        if not token_ok(title, tokens):
            continue
        hash_ = (h.get("hash") or "").lower()
        magnet = h.get("magnetUrl") or (_magnet(hash_, title) if hash_ else "")
        if not title or not magnet:
            continue
        items.append({"source": "knaben", "kind": "magnet", "title": title,
                      "url": magnet, "seeders": int(h.get("seeders") or 0),
                      "meta": build_meta("", title, int(h.get("bytes") or 0), int(h.get("seeders") or 0), h.get("date") or "", h.get("tracker") or "")})
    return items, (None if items else "knaben 没有结果")

def search_therarbg(cfg, q, resolved, query=None):
    query = query or resolved.get("query_en") or q
    yr = explicit_year(q)
    if yr and yr not in query:
        query = (query + " " + yr).strip()
    url = "https://therarbg.com/get-posts/keywords:" + urllib.parse.quote(query) + "/?format=json"
    items, seen = [], set()
    for _ in range(2):
        try:
            r = http_request(cfg, "GET", url, headers={"User-Agent": UA}, timeout=25)
            r.raise_for_status()
            d = r.json()
        except Exception as e:
            return items, (None if items else f"therarbg 请求失败: {e}")
        tokens = title_tokens(query)
        for t in d.get("results") or []:
            title = t.get("n") or ""
            hash_ = (t.get("h") or "").lower()
            if not title or not hash_ or hash_ in seen:
                continue
            if not token_ok(title, tokens):
                continue
            seen.add(hash_)
            try:
                date = time.strftime("%Y-%m-%d", time.localtime(int(t.get("a") or 0)))
            except Exception:
                date = ""
            items.append({"source": "therarbg", "kind": "magnet", "title": title,
                          "url": _magnet(hash_, title), "seeders": int(t.get("se") or 0),
                          "meta": build_meta("", title, int(t.get("s") or 0), int(t.get("se") or 0), date)})
        nxt = (d.get("links") or {}).get("next") or ""
        if not nxt:
            break
        url = nxt if nxt.startswith("http") else "https://therarbg.com" + nxt
    return items, (None if items else "therarbg 没有结果")

def search_bitmagnet(cfg, q, resolved):
    """直连 bitmagnet 的 PostgreSQL 查询，避免 GraphQL 中文罗马音索引带来的脏结果。"""
    query = effective_query(q, resolved)
    if re.search(r"[\u4e00-\u9fff]", query):
        query = re.sub(r"\s+(?:19|20)\d{2}$", "", query).strip()
        if re.search(r"[\u4e00-\u9fff]", query):
            return [], "未解析出英文标题，跳过 bitmagnet"
    terms = title_tokens(query)
    if not terms:
        return [], "搜索词过短"
    qyear = re.search(r"(?:19|20)\d{2}", q)
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=cfg.get("bitmagnet_db_host") or "127.0.0.1",
            port=int(cfg.get("bitmagnet_db_port") or 5433),
            user=cfg.get("bitmagnet_db_user") or "postgres",
            password=cfg.get("bitmagnet_db_password") or "postgres",
            dbname=cfg.get("bitmagnet_db_name") or "bitmagnet",
            connect_timeout=5,
        )
    except Exception as e:
        return [], f"bitmagnet 数据库连接失败: {e}"
    conds = ["tc.seeders IS NOT NULL"]
    params = []
    for term in terms:
        pat = r"\y" + term + r"\y"
        conds.append("(t.name ~* %s OR c.title ~* %s)")
        params.extend([pat, pat])
    rtype = (resolved or {}).get("type") or ""
    if rtype in ("movie", "tv"):
        conds.append("tc.content_type = %s")
        params.append("movie" if rtype == "movie" else "tv_show")
    if qyear:
        conds.append("(c.release_year = %s OR (c.release_year IS NULL AND t.name ~* %s))")
        params.extend([int(qyear.group(0)), r"\y" + qyear.group(0) + r"\y"])
    sql = """
        SELECT encode(t.info_hash, 'hex'), t.name, t.size, tc.seeders, tc.leechers, t.files_count,
               tc.content_type, tc.video_resolution, tc.video_source, tc.video_codec, tc.release_group,
               c.title, c.release_year
        FROM torrent_contents tc
        JOIN torrents t ON t.info_hash = tc.info_hash
        LEFT JOIN content c ON c.type = tc.content_type AND c.source = tc.content_source AND c.id = tc.content_id
        WHERE %s
        ORDER BY tc.seeders DESC NULLS LAST, t.size DESC
        LIMIT 50
    """ % " AND ".join(conds)
    try:
        with conn, conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    except Exception as e:
        return [], f"bitmagnet 查询失败: {e}"
    finally:
        conn.close()
    items = []
    for h, name, size, seeders, leechers, files_count, ctype, vres, vsrc, vcodec, group, ctitle, cyear in rows:
        h = (h or "").lower()
        if not h or not name:
            continue
        meta = [BM_TYPES.get(ctype, ctype or "未分类")]
        if vres:
            meta.append(str(vres).replace("V", ""))
        if vsrc:
            meta.append(str(vsrc))
        if vcodec:
            meta.append(str(vcodec))
        if group:
            meta.append(str(group))
        items.append({
            "source": "bitmagnet", "kind": "magnet", "title": name,
            "url": _magnet(h, name),
            "seeders": int(seeders or 0), "size": int(size or 0),
            "meta": " · ".join(meta), "tmdb": "",
        })
    return items, (None if items else "bitmagnet 索引里还没有匹配")


def search_jackett(cfg, q):
    site = (cfg.get("sites") or {}).get("jackett") or {}
    base = (cfg.get("jackett_url") or site.get("url") or "").rstrip("/")
    key = (cfg.get("jackett_api_key") or site.get("api_key") or "").strip()
    if not base:
        return [], "未配置 Jackett 地址"
    if not key:
        return [], "未配置 Jackett API Key"
    url = base + "/api/v2.0/indexers/all/results/torznab/api"
    try:
        r = http_request(cfg, "GET", url, params={"apikey": key, "t": "search", "q": q, "limit": 50},
                         headers={"User-Agent": UA}, timeout=45)
        r.raise_for_status()
    except Exception as e:
        return [], f"Jackett 请求失败: {e}"
    import xml.etree.ElementTree as ET
    try:
        root = ET.fromstring(r.content)
    except Exception as e:
        return [], f"Jackett 响应解析失败: {e}"
    ns = {"torznab": "http://torznab.com/schemas/2015/feed"}
    items, seen = [], set()
    for node in root.findall(".//item"):
        title = (node.findtext("title") or "").strip()
        link = (node.findtext("link") or "").strip()
        enclosure = node.find("enclosure")
        torrent = (enclosure.get("url") if enclosure is not None else "") or ""
        attrs = {}
        for a in node.findall("torznab:attr", ns):
            attrs[(a.get("name") or "").lower()] = a.get("value") or ""
        magnet = attrs.get("magneturl") or ""
        if not magnet and (link.startswith("magnet:") or torrent.startswith("magnet:")):
            magnet = link if link.startswith("magnet:") else torrent
        target = magnet or torrent or link
        if not title or not target:
            continue
        kind = "magnet" if target.startswith("magnet:") else "torrent"
        key_url = magnet.split("&")[0] if magnet else target
        if key_url in seen:
            continue
        seen.add(key_url)
        try:
            size = int(attrs.get("size") or 0)
        except Exception:
            size = 0
        items.append({
            "source": "jackett", "kind": kind, "title": title, "url": target,
            "seeders": int(attrs.get("seeders") or 0),
            "leechers": int(attrs.get("peers") or 0),
            "size": size,
            "meta": " · ".join(x for x in [attrs.get("category", ""), human_size(size)] if x),
            "tmdb": "",
        })
    return items, (None if items else "Jackett 没有匹配结果")

def search_site(cfg, key, q, resolved=None):
    site = (cfg.get("sites") or {}).get(key) or {}
    tmpl = site.get("url") or ""
    if not tmpl:
        return [], "未配置搜索地址"
    resolved = resolved or {}
    use_q = q
    if key in ("apibay", "nyaa", "knaben", "therarbg"):
        use_q = effective_query(q, resolved)
    qyear = explicit_year(q)
    if qyear and key in ("apibay", "nyaa") and qyear not in use_q:
        use_q = (use_q + " " + qyear).strip()
    if key == "btsearch":
        return search_btsearch(cfg, q)
    if key == "eztv":
        return search_eztv(cfg, resolved)
    if key == "knaben":
        return search_knaben(cfg, q, resolved, use_q)
    if key == "therarbg":
        return search_therarbg(cfg, q, resolved, use_q)
    if key == "bitmagnet":
        return search_bitmagnet(cfg, q, resolved)
    if key == "jackett":
        return search_jackett(cfg, effective_query(q, resolved))
    kind = site.get("kind")
    if kind not in ("json", "rss"):
        return [], "不支持的来源类型"
    tokens_q = (use_q + " " + (resolved.get("title_en") or "")).strip()
    queries = list(dict.fromkeys([use_q, resolved.get("title_en") or ""]))
    queries = [x for x in queries if x]
    items, seen = [], set()
    for qq in queries:
        url = tmpl.replace("{q}", urllib.parse.quote(qq))
        try:
            r = http_request(cfg, "GET", url, headers={"User-Agent": UA}, timeout=15)
            text = r.text
        except Exception:
            continue
        got = parse_apibay(text, tokens_q) if kind == "json" else parse_rss(text, key, tokens_q)
        for it in got:
            if qyear and not year_ok(it.get("title") or "", qyear):
                continue
            if it["url"] in seen:
                continue
            seen.add(it["url"])
            items.append(it)
    return items, (None if items else "没有解析到结果")

def search_pansou(cfg, q):
    base = (cfg.get("pansou_url") or "").rstrip("/")
    if not base:
        return [], "未配置 PanSou 地址"
    try:
        r = requests.post(base + "/api/search", json={"kw": q, "res": "merge"}, timeout=60)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return [], f"PanSou 请求失败: {e}"
    merged = ((d.get("data") or {}).get("merged_by_type") or {})
    items = []
    for it in (merged.get("115") or []):
        url = it.get("url") or ""
        if not url:
            continue
        items.append({"source": "pansou", "kind": "115",
                      "title": (it.get("note") or url[:70]),
                      "url": url, "password": it.get("password") or ""})
    for typ, kind in (("magnet", "magnet"), ("ed2k", "ed2k")):
        for it in (merged.get(typ) or []):
            url = it.get("url") or ""
            if not url:
                continue
            items.append({"source": "pansou-magnet", "kind": kind,
                          "title": (it.get("note") or url[:70]), "url": url})
    return items, None

def _collect(cfg, q, sources, want_sites):
    items, errors = [], {}
    resolved = resolve_title(cfg, q) or {}
    jobs = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        if "pansou" in sources:
            jobs.append(("pansou", ex.submit(search_pansou, cfg, q)))
        if want_sites:
            for key in ("apibay", "nyaa", "dmhy", "btsearch", "eztv", "knaben", "therarbg", "bitmagnet", "jackett"):
                if key in sources and (cfg.get("sites") or {}).get(key, {}).get("enabled", True):
                    jobs.append((key, ex.submit(search_site, cfg, key, q, resolved)))
        for name, fut in jobs:
            try:
                got, err = fut.result()
            except Exception as e:
                got, err = [], str(e)
            items += got
            if err:
                errors[name] = err
    return {"items": items, "errors": errors, "resolved": resolved}

def search_all_sources(cfg, queries, sources=None):
    sources = sources or ["pansou", "apibay", "nyaa", "dmhy", "btsearch", "eztv", "knaben", "therarbg", "bitmagnet"]
    items, seen = [], set()
    for q in queries:
        got = _collect(cfg, q, sources, True).get("items") or []
        for it in got:
            u = it.get("url")
            if u and u in seen:
                continue
            if u:
                seen.add(u)
            items.append(it)
    return items


def bare_season(q):
    m = re.search(r"(?<![a-zA-Z0-9])[sS](\d{1,2})(?![0-9eE])", q or "")
    return m

def expand_queries(q, max_ep=10):
    m = bare_season(q)
    if not m:
        return []
    season = int(m.group(1))
    out = []
    for ep in range(1, max_ep + 1):
        replacement = "s%02de%02d" % (season, ep)
        out.append(q[:m.start()] + replacement + q[m.end():])
    return out

def explicit_year(q):
    m = re.search(r"(?:^|\s)((?:19|20)\d{2})(?:\s|$)", q or "")
    return m.group(1) if m else ""


def year_ok(title, year):
    return bool(year) and bool(re.search(r"(?<!\d)" + year + r"(?!\d)", title or ""))


def effective_query(q, resolved):
    base = (resolved or {}).get("query_en") or (resolved or {}).get("title_en") or q
    if re.search(r"[\u4e00-\u9fff]", base):
        tr = translate_title(base)
        if tr:
            base = tr
    m = bare_season(q)
    if m and not bare_season(base):
        base = (base + " " + m.group(0).lower()).strip()
    return base

def title_tokens(q):
    return [t for t in re.split(r"[\W_]+", (q or "").lower()) if len(t) >= 3 and t not in _STOP]


def token_ok(name, tokens):
    if not tokens:
        return True
    low = (name or "").lower()
    return all(t in low for t in tokens)


TPB_CATEGORIES = {
    "100": "音乐", "101": "音乐", "102": "有声书", "103": "音效", "104": "音乐",
    "200": "视频", "201": "电影", "202": "电影", "203": "MV", "204": "视频片段",
    "205": "剧集", "206": "手持视频", "207": "高清电影", "208": "高清剧集", "209": "3D", "211": "4K",
    "300": "软件", "301": "软件", "302": "软件", "303": "软件", "304": "软件", "305": "软件", "306": "软件",
    "400": "游戏", "401": "游戏", "402": "游戏", "403": "游戏", "404": "游戏", "405": "游戏", "406": "游戏",
    "500": "成人", "501": "成人", "502": "成人", "503": "成人", "504": "成人", "505": "成人", "506": "成人",
    "600": "其他", "601": "电子书", "602": "漫画", "603": "图片", "604": "封面", "605": "3D模型", "699": "其他",
}

def human_size(n):
    try:
        n = int(n or 0)
    except Exception:
        return ""
    if n <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return (("%.1f" % n) if unit != "B" else str(n)).rstrip("0").rstrip(".") + " " + unit
        n /= 1024.0
    return ""

def build_meta(kind="", name="", size=0, seeders=None, date="", extra=""):
    parts = []
    if kind:
        parts.append(kind)
    parts += parse_name_meta(name)
    if extra:
        parts.append(extra)
    hs = human_size(size)
    if hs:
        parts.append(hs)
    if seeders:
        parts.append(f"{seeders} seeds")
    if date:
        parts.append(str(date)[:10])
    return " · ".join(parts)

def bt_search_api(cfg, params):
    ts = str(int(time.time()))
    nonce = "".join(random.choice(string.ascii_letters + string.digits) for _ in range(8))
    items = ["timestamp=" + ts, "nonce=" + nonce] + [f"{k}={v}" for k, v in params.items()]
    sign = hashlib.md5(("&".join(sorted(items)) + "&key=" + BT_KEY).encode()).hexdigest().upper()
    url = "https://www.btsearch.love/api/search?" + urllib.parse.urlencode(params)
    r = http_request(cfg, "GET", url, headers={"User-Agent": UA, "x-timestamp": ts, "x-nonce": nonce,
                                   "x-sign": sign, "Accept": "application/json",
                                   "Referer": "https://www.btsearch.love/"}, timeout=20)
    r.raise_for_status()
    return r.json()


def extract_infohash(url):
    m = re.search(r"btih:([0-9a-zA-Z]{32,40})", url or "")
    return m.group(1).lower() if m else ""

def _magnet(hash_, name):
    return f"magnet:?xt=urn:btih:{hash_}&dn={urllib.parse.quote(name or '')}"


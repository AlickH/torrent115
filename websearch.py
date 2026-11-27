#!/usr/bin/env python3
"""联网搜索：Parallel 匿名 MCP，或 DeepSeek 官方搜索（用户自己的 key）。"""
import json
import urllib.parse

import requests

PARALLEL_MCP = "https://search.parallel.ai/mcp"
UA = "torrent115 (+https://github.com/AlickH/torrent115)"


def _proxies(cfg):
    proxy = (cfg.get("outbound_proxy") or "").strip()
    return {"http": proxy, "https": proxy} if proxy else None


def _is_deepseek(base_url):
    try:
        host = urllib.parse.urlparse((base_url or "").strip()).hostname or ""
    except Exception:
        return False
    host = host.lower()
    return host == "api.deepseek.com" or host.endswith(".deepseek.com")


def _parallel(cfg, query, limit, timeout):
    body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": {
                "objective": "确认影视作品的准确片名，包括中文名、原名、别名。只给片名证据，不要下载链接。",
                "search_queries": [query],
            },
        },
    }
    r = requests.post(PARALLEL_MCP, json=body,
                      headers={"Content-Type": "application/json",
                               "Accept": "application/json, text/event-stream",
                               "User-Agent": UA},
                      proxies=_proxies(cfg), timeout=timeout)
    r.raise_for_status()
    result = (r.json() or {}).get("result") or {}
    text = "\n".join(part.get("text", "") for part in (result.get("content") or [])
                     if isinstance(part, dict))
    return _parse_parallel(text)[:limit]


def _parse_parallel(text):
    try:
        parsed = json.loads(text)
        results = parsed.get("results") if isinstance(parsed, dict) else None
    except Exception:
        results = None
    if not isinstance(results, list):
        return [{"title": "web search", "url": "", "snippet": text.strip()[:2000]}] if text.strip() else []
    hits = []
    for item in results:
        if not isinstance(item, dict):
            continue
        snippets = item.get("excerpts") if isinstance(item.get("excerpts"), list) else []
        if isinstance(item.get("excerpt"), str):
            snippets = snippets + [item["excerpt"]]
        url = item.get("url") or ""
        if not url and not snippets:
            continue
        hits.append({"title": item.get("title") or url,
                     "url": url,
                     "snippet": "\n".join(s for s in snippets if isinstance(s, str)).strip()})
    return hits


def _deepseek(cfg, query, limit, timeout):
    base = (cfg.get("ai_base_url") or "").strip().rstrip("/")
    base = base[:-3] if base.lower().endswith("/v1") else base
    key = (cfg.get("ai_api_key") or "").strip()
    if not base or not key:
        raise RuntimeError("DeepSeek 搜索需要 base url 和 api key")
    r = requests.post(base + "/v1/tools/search",
                      headers={"Authorization": "Bearer " + key,
                               "Content-Type": "application/json",
                               "User-Agent": UA},
                      json={"query": query[:128], "count": limit},
                      proxies=_proxies(cfg), timeout=timeout)
    r.raise_for_status()
    hits = []
    for item in (r.json().get("results") or []):
        if not isinstance(item, dict):
            continue
        snippet = "\n".join(x for x in (item.get("summary"), item.get("snippet")) if isinstance(x, str) and x.strip())
        if not snippet and isinstance(item.get("content"), str):
            snippet = item["content"][:2000]
        url = item.get("url") or ""
        if url or snippet:
            hits.append({"title": item.get("title") or url, "url": url, "snippet": snippet})
    return hits[:limit]


def search(cfg, query, limit=6, timeout=20):
    """联网搜索；失败返回空列表，调用方当作「没有网页证据」。"""
    query = (query or "").strip()
    if not query:
        return []
    try:
        if _is_deepseek(cfg.get("ai_base_url")) and (cfg.get("ai_api_key") or "").strip():
            return _deepseek(cfg, query, limit, timeout)
        return _parallel(cfg, query, limit, timeout)
    except Exception:
        return []


def render(hits, max_chars=6000):
    lines = []
    for i, hit in enumerate(hits, 1):
        head = f"{i}. {hit['title']}" + (f" — {hit['url']}" if hit["url"] else "")
        lines.append(head + (f"\n{hit['snippet']}" if hit["snippet"] else ""))
    return "\n".join(lines)[:max_chars]

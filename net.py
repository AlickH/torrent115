#!/usr/bin/env python3
"""HTTP 请求：直连失败重试 + 出口代理兜底。"""
import time

import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _proxy_map(cfg):
    p = (cfg.get("outbound_proxy") or "").strip()
    return {"http": p, "https": p} if p else None


def http_request(cfg, method, url, retries=2, proxy_fallback=True, **kw):
    """配置了出口代理时走代理优先，失败再直连兜底。"""
    kw.setdefault("timeout", 20)
    proxy = _proxy_map(cfg) if proxy_fallback else None
    routes = []
    if proxy:
        routes.append(proxy)
    routes.append(None)
    last = None
    for route in routes:
        for i in range(max(1, retries)):
            try:
                kw2 = dict(kw)
                if route:
                    kw2["proxies"] = route
                r = requests.request(method, url, **kw2)
                if r.status_code < 500:
                    return r
                last = requests.HTTPError(f"HTTP {r.status_code} for {url}")
            except Exception as e:
                last = e
            time.sleep(0.4 * (i + 1))
    raise last



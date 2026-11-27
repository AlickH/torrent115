#!/usr/bin/env python3
"""OpenAI 兼容大模型调用：chat / tool-calling / JSON。"""
import json
import time
import urllib.parse

import requests

DEFAULT_TIMEOUT = 60


LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1", "0.0.0.0"}


def proxies_for(cfg, url):
    """本地端点（ollama / LM Studio / 自建网关）不能走出口代理。"""
    proxy = (cfg.get("outbound_proxy") or "").strip()
    if not proxy:
        return None
    host = (urllib.parse.urlparse(url or "").hostname or "").lower()
    if host in LOOPBACK_HOSTS:
        return None
    return {"http": proxy, "https": proxy}


def _proxies(cfg):
    return proxies_for(cfg, cfg.get("ai_base_url"))


def _endpoint(cfg):
    base = (cfg.get("ai_base_url") or "https://api.openai.com/v1").strip().rstrip("/")
    return base + "/chat/completions"


def chat(cfg, messages, tools=None, tool_choice=None, temperature=0, timeout=DEFAULT_TIMEOUT):
    key = (cfg.get("ai_api_key") or "").strip()
    if not key:
        raise RuntimeError("未配置 AI API Key")
    body = {
        "model": cfg.get("ai_model") or "gpt-4o-mini",
        "messages": messages,
        "temperature": temperature,
    }
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"
    last = None
    for attempt in range(2):
        try:
            r = requests.post(_endpoint(cfg), headers={"Authorization": "Bearer " + key,
                                                      "Content-Type": "application/json"},
                              json=body, proxies=_proxies(cfg), timeout=timeout)
            if r.status_code in (429, 500, 502, 503, 504) and attempt == 0:
                last = RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                time.sleep(2)
                continue
            r.raise_for_status()
            return (r.json().get("choices") or [{}])[0].get("message") or {}
        except Exception as e:
            last = e
            if attempt == 0:
                time.sleep(1)
                continue
            raise
    raise last


def chat_text(cfg, messages, **kw):
    return (chat(cfg, messages, **kw).get("content") or "").strip()


def chat_json(cfg, messages, **kw):
    """让模型返回 JSON，容忍 ```json 围栏和前后废话。"""
    text = chat_text(cfg, messages, **kw)
    i_obj, i_arr = text.find("{"), text.find("[")
    if i_arr != -1 and (i_obj == -1 or i_arr < i_obj):
        start, end = i_arr, text.rfind("]")
    else:
        start, end = i_obj, text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except Exception:
        return None

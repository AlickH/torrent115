#!/usr/bin/env python3
"""Drivemby 刷新（手动通知 + 自动任务完成后触发）。"""
import urllib.parse

from net import http_request
from p115 import collect_leaves, p115_file_chain

def notify_drivemby(cfg, name, cid):
    base = (cfg.get("drivemby_prefix") or "/云下载").rstrip("/") + "/" + name
    leaves = []
    collect_leaves(cfg, cid, base, leaves)
    targets = leaves or [base]
    ok_all = True
    for path in targets:
        q = urllib.parse.urlencode({"token": cfg.get("drivemby_token") or "", "path": path})
        try:
            r = http_request(cfg, "POST", (cfg.get("drivemby_url") or "") + "?" + q, json={}, timeout=30)
            body = r.text[:400]
            print(f"[monitor] drivemby path={path} status={r.status_code} resp={body}", flush=True)
            ok_all = ok_all and r.status_code == 200
        except Exception as e:
            print(f"[monitor] drivemby path={path} ERROR {e}", flush=True)
            ok_all = False
    return ok_all


def auto_drivemby_refresh(cfg, file_id=None):
    if not cfg.get("drivemby_enabled", True):
        return False, "已关闭自动刷新"
    token = cfg.get("drivemby_token") or ""
    url = cfg.get("drivemby_url") or ""
    if not token or not url:
        return False, "未配置 Drivemby token/url"
    prefix = (cfg.get("drivemby_prefix") or "/云下载").rstrip("/")
    parts = [p for p in prefix.split("/") if p]
    targets = []
    if file_id:
        try:
            chain = p115_file_chain(cfg, file_id)
            names = [c["name"] for c in chain]
            if parts and parts[-1] in names:
                idx = names.index(parts[-1])
                if idx > 0:
                    sub = chain[idx - 1]
                    sub_path = prefix + "/" + sub["name"]
                    leaves = []
                    collect_leaves(cfg, sub["cid"], sub_path, leaves)
                    targets = leaves or [sub_path]
                else:
                    targets = [prefix]
        except Exception:
            targets = []
    if not targets:
        targets = [prefix]
    ok_all = True
    msgs = []
    for path in targets:
        q = urllib.parse.urlencode({"token": token, "path": path})
        try:
            r = http_request(cfg, "POST", url + "?" + q, json={}, timeout=30)
            body = r.text[:160]
            print(f"[auto] drivemby path={path} status={r.status_code} resp={body}", flush=True)
            ok_all = ok_all and r.status_code == 200
            msgs.append(f"{path} -> {r.status_code} {body}")
        except Exception as e:
            print(f"[auto] drivemby ERROR {e}", flush=True)
            ok_all = False
            msgs.append(f"{path} -> 失败 {e}")
    return ok_all, "; ".join(msgs)

#!/usr/bin/env python3
"""Torrent115 宿主机脚本代理：执行 App 提交的移动任务请求。"""
import json
import os
import shutil
import time

HOOK_DIR = "/vol1/@appdata/torrent115/data/hooks"
PENDING = os.path.join(HOOK_DIR, "pending")
DONE = os.path.join(HOOK_DIR, "done")
ALLOWED_ROOTS = ("/vol1/",)

def allowed(path):
    p = os.path.abspath(path)
    return any(p.startswith(root) for root in ALLOWED_ROOTS)

def write_result(job_id, payload):
    os.makedirs(DONE, exist_ok=True)
    tmp = os.path.join(DONE, job_id + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(DONE, job_id + ".json"))

def main():
    os.makedirs(PENDING, exist_ok=True)
    os.makedirs(DONE, exist_ok=True)
    for name in sorted(os.listdir(PENDING)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(PENDING, name)
        try:
            with open(path, encoding="utf-8") as f:
                job = json.load(f)
            job_id = job.get("id") or name[:-5]
            src = os.path.abspath(job.get("src") or "")
            dst = os.path.abspath(job.get("dst") or "")
            if job.get("action") != "move":
                raise ValueError("unsupported action")
            if not allowed(src) or not allowed(dst):
                raise ValueError("path not allowed")
            if not os.path.exists(src):
                raise FileNotFoundError(f"src not found: {src}")
            os.makedirs(dst, exist_ok=True)
            target = os.path.join(dst, os.path.basename(src))
            if os.path.exists(target):
                base, ext = os.path.splitext(target)
                target = f"{base}.{int(time.time())}{ext}"
            shutil.move(src, target)
            write_result(job_id, {"ok": True, "target": target})
        except Exception as e:
            try:
                write_result(job.get("id") or name[:-5], {"ok": False, "error": str(e)})
            except Exception:
                pass
        finally:
            try:
                os.remove(path)
            except Exception:
                pass

if __name__ == "__main__":
    main()

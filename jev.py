#!/usr/bin/env python3
"""Jev 候选预筛（TypeSafe 决策模型）：进 AI 之前剔掉无关/成人候选。"""
import json

import requests

JEV_MODEL = "jev-latest"
OPENROUTER_DECISIONS = "https://openrouter.ai/api/alpha/decisions"
CHUNK_SIZE = 150
TIMEOUT = 8
DROP_BELOW = 0.3
UNCERTAIN_BELOW = 0.7
NSFW_DROP_AT = 0.95
NSFW_SUSPECT_AT = 0.6

TV_RULES = ("同一IP的剧场版/电影/广播剧/有声书/漫画/游戏/衍生动画/综艺都不算这部剧集本身,必须判否。"
            "`target.year` 是首播年份:候选标注年份比首播年份早2年及以上,必定是同名/近名的另一部作品,应判否;"
            "标注年份晚于首播年份的可能是同一部剧的后续季,不能仅凭年份判否。")
MOVIE_RULES = "`target.aliases` 是原名/别名,候选用这些名字也算指向目标"


def _proxies(cfg):
    import ai_client
    url = (cfg.get("jev_base_url") or "").strip() or OPENROUTER_DECISIONS
    return ai_client.proxies_for(cfg, url)


def _instruction(target, key):
    if (target.get("media_type") or "tv") == "movie":
        return (f"`candidates.{key}` 明确是 `target.title`(`target.year`)这部电影本身,"
                f"而不是续集/前传/翻拍/同IP不同片/同名综艺或动画。{MOVIE_RULES}")
    return (f"`candidates.{key}` 明确指向 `target.title` 这部剧集/动漫作品"
            f"(不是仅关键词相似的其它作品;第1季可无季标记,第2季以上必须明确标出季)。{TV_RULES}")


def _nsfw_instruction(key):
    return (f"`candidates.{key}` 是色情或成人向资源:标题露骨描述性行为/身体,"
            "或明确标注 R18、成人版、H、AV、同人H本、裸聊直播等。"
            "正常电影/剧集/动漫/纪录片(包括情色题材的正规院线片、限制级剧情片)判否。")


def available(cfg):
    return bool(cfg.get("jev_enabled")) and bool((cfg.get("jev_api_key") or "").strip())


def _judge_chunk(cfg, target, rows):
    keys = [f"c{i}" for i in range(len(rows))]
    body = {
        "model": JEV_MODEL,
        "state": {
            "target": {
                "title": target.get("show") or "",
                "type": "movie" if (target.get("media_type") or "tv") == "movie" else "tv",
                "year": int(target["year"]) if str(target.get("year") or "").isdigit() else None,
                "aliases": [a for a in [target.get("show_en")] if a],
            },
            "candidates": {keys[i]: (rows[i].get("title") or "") for i in range(len(rows))},
        },
        "questions": dict(
            {keys[i]: {"type": "noul", "instructions": _instruction(target, keys[i])} for i in range(len(rows))},
            **{f"n{keys[i][1:]}": {"type": "noul", "instructions": _nsfw_instruction(keys[i])} for i in range(len(rows))},
        ),
    }
    r = requests.post((cfg.get("jev_base_url") or "").strip() or OPENROUTER_DECISIONS,
                      headers={"Authorization": "Bearer " + cfg["jev_api_key"].strip(),
                               "Content-Type": "application/json"},
                      json=body, proxies=_proxies(cfg), timeout=TIMEOUT)
    r.raise_for_status()
    answers = (r.json() or {}).get("answers") or {}
    out = []
    for i, key in enumerate(keys):
        ident = ((answers.get(key) or {}).get("noul"))
        nsfw = ((answers.get(f"n{key[1:]}") or {}).get("noul"))
        out.append((ident, nsfw))
    return out


def _drop(ident, nsfw):
    def num(v):
        return v if isinstance(v, (int, float)) and 0 <= v <= 1 else None
    ident, nsfw = num(ident), num(nsfw)
    if nsfw is not None and nsfw >= NSFW_DROP_AT:
        return True
    if nsfw is not None and nsfw >= NSFW_SUSPECT_AT and ident is not None and ident < UNCERTAIN_BELOW:
        return True
    return ident is not None and ident < DROP_BELOW


def judge(cfg, target, rows):
    """连通性测试入口：不加 fail-open，异常直接抛出。"""
    return _judge_chunk(cfg, target, rows)


def prefilter(cfg, target, rows):
    """返回 (kept, dropped_count, uncertain_marked)。任何失败都放行（fail-open）。"""
    if not available(cfg) or not rows:
        return rows, 0, 0
    kept, dropped = [], 0
    for start in range(0, len(rows), CHUNK_SIZE):
        chunk = rows[start:start + CHUNK_SIZE]
        try:
            scores = _judge_chunk(cfg, target, chunk)
        except Exception:
            kept.extend(chunk)
            continue
        for row, (ident, nsfw) in zip(chunk, scores):
            if _drop(ident, nsfw):
                dropped += 1
                continue
            if isinstance(ident, (int, float)) and ident < UNCERTAIN_BELOW:
                row = dict(row)
                row["_uncertain"] = round(float(ident), 2)
            kept.append(row)
    return kept, dropped, sum(1 for r in kept if r.get("_uncertain"))

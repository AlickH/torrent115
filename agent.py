#!/usr/bin/env python3
"""选种 agent：只读工具 + 终止决策，由系统执行转存。"""
import json

import ai_client

MAX_STEPS = 6
SEARCH_BUDGET = 3
RESEARCH_BUDGET = 2

SYSTEM = """你是影视资源的选种助手。系统已经按关键词搜到一批候选，你要读证据、决定把哪一个交给系统去转存。

规则（违反任何一条都算选错）：
- 证据先行：只能根据工具返回的候选标题、大小、来源、种子数判断，不要凭片名相似猜。
- 目标匹配：必须是目标作品本身。同名不同作品、续集/前传/翻拍、同 IP 的其它形态（剧场版/综艺/广播剧）、语言或年份明显不符的，一律不要。
- 覆盖优先：影视正片要能被候选标题明确覆盖（集号/范围/全集），拿不准就当没有；不要"先转了再看"。
- 黑盒最后：标题写明分辨率/体积/集数的（透明候选）优先；只有透明候选都不覆盖时才选黑盒，并在理由里说明。
- 死链常态：候选转存失败是正常的，系统会按你给的顺序继续试；你只需要把同一目标作品的候选按优劣排序。
- 系统级封停：如果系统提示配额不足/登录超时/需要 VIP/鉴权失败，那是账号问题不是资源问题，直接收尾上报，不要继续换候选。
- 已有任务：先用 check_task 看这个资源是否已在下载/已完成，避免重复。

你的动作只有两个：
1. 需要更多证据时调用工具（search_resources 换关键词、research_titles 查别名、check_task 查任务状态）。
2. 证据够了就调用 choose 给出候选 id（可给多个，按优先级）和一句理由；确实没有可用资源就调用 no_coverage 说明原因。

不要输出与工具无关的长篇解释。"""


def _tool_specs():
    return [
        {"type": "function", "function": {
            "name": "search_resources",
            "description": "用新关键词重新搜索候选。关键词必须包含作品名或别名，不要只给类型/年份。",
            "parameters": {"type": "object", "properties": {
                "keyword": {"type": "string", "description": "搜索关键词"},
            }, "required": ["keyword"]},
        }},
        {"type": "function", "function": {
            "name": "research_titles",
            "description": "联网查这个作品的其它片名（原名/港台译名/英文名），用于换关键词再搜。",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "作品名 + 年份"},
            }, "required": ["query"]},
        }},
        {"type": "function", "function": {
            "name": "check_task",
            "description": "查询某个候选（或磁力）在 115 云下载里的任务状态。",
            "parameters": {"type": "object", "properties": {
                "candidate_id": {"type": "integer", "description": "候选 id"},
            }, "required": ["candidate_id"]},
        }},
        {"type": "function", "function": {
            "name": "choose",
            "description": "给出要转存的候选，按优先级排序。",
            "parameters": {"type": "object", "properties": {
                "candidate_ids": {"type": "array", "items": {"type": "integer"},
                                  "description": "候选 id，最优在前"},
                "reason": {"type": "string", "description": "一句中文理由"},
            }, "required": ["candidate_ids", "reason"]},
        }},
        {"type": "function", "function": {
            "name": "no_coverage",
            "description": "确认没有可用资源时上报。",
            "parameters": {"type": "object", "properties": {
                "reason": {"type": "string", "description": "一句中文原因"},
            }, "required": ["reason"]},
        }},
    ]


def _row(index, c):
    return {"id": index, "title": (c.get("title") or "")[:180], "kind": c.get("kind"),
            "source": c.get("source") or "", "seeders": c.get("seeders") or 0,
            "size_gb": round((c.get("size") or 0) / (1024 ** 3), 2) if c.get("size") else None,
            "uncertain": c.get("_uncertain")}


class Decider:
    """把 agent 的工具调用接到调用方的真实函数上。"""

    def __init__(self, cfg, episode, candidates, search_more, check_task, research):
        self.cfg = cfg
        self.episode = episode
        self.candidates = list(candidates)
        self.search_more = search_more
        self.check_task = check_task
        self.research = research
        self.searches = 0
        self.researches = 0

    def _context(self):
        ep = self.episode
        target = ep.get("show") or ""
        if (ep.get("media_type") or "tv") == "movie":
            need = f"电影《{target}》{ep.get('year') or ''}"
        else:
            need = f"剧集《{target}》{ep.get('key') or ''}"
        rows = [_row(i, c) for i, c in enumerate(self.candidates)]
        return (f"目标：{need}\n"
                f"已搜到的候选（JSON）：{json.dumps(rows, ensure_ascii=False)}")

    def _dispatch(self, name, args):
        if name == "search_resources":
            keyword = (args.get("keyword") or "").strip()
            if not keyword:
                return {"error": "keyword 不能为空"}
            if keyword not in (self.episode.get("show") or "") and keyword not in (self.episode.get("show_en") or ""):
                alias_ok = self.researches > 0
                if not alias_ok:
                    return {"error": "关键词必须包含作品名或已查证的别名"}
            if self.searches >= SEARCH_BUDGET:
                return {"error": "搜索预算用完，用现有候选决定"}
            self.searches += 1
            items = self.search_more(keyword) or []
            base = len(self.candidates)
            self.candidates.extend(items)
            return {"candidates": [_row(base + i, c) for i, c in enumerate(items)]}
        if name == "research_titles":
            if self.researches >= RESEARCH_BUDGET:
                return {"error": "联网查询预算用完"}
            self.researches += 1
            return {"evidence": self.research((args.get("query") or "").strip())}
        if name == "check_task":
            try:
                cid = int(args.get("candidate_id"))
                c = self.candidates[cid]
            except Exception:
                return {"error": "candidate_id 无效"}
            return {"task": self.check_task(c)}
        return {"error": f"未知工具 {name}"}


def decide(cfg, episode, candidates, search_more, check_task, research):
    """返回 (选中的候选列表, 是否 no_coverage, 理由)。模型不可用时返回 (None, False, "")。"""
    if not cfg.get("ai_enabled") or not (cfg.get("ai_api_key") or "").strip() or not candidates:
        return None, False, ""
    dec = Decider(cfg, episode, candidates, search_more, check_task, research)
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": dec._context()},
    ]
    for _ in range(MAX_STEPS):
        msg = ai_client.chat(cfg, messages, tools=_tool_specs(), tool_choice="auto")
        calls = msg.get("tool_calls") or []
        if not calls:
            content = (msg.get("content") or "").strip()
            if content:
                messages.append({"role": "assistant", "content": content})
                messages.append({"role": "user", "content": "请用 choose 或 no_coverage 结束。"})
                continue
            return None, False, ""
        messages.append({"role": "assistant", "content": msg.get("content") or "", "tool_calls": calls})
        for call in calls:
            fn = (call.get("function") or {})
            name = fn.get("name") or ""
            try:
                args = json.loads(fn.get("arguments") or "{}")
            except Exception:
                args = {}
            if name == "choose":
                ids = [i for i in (args.get("candidate_ids") or []) if isinstance(i, int) and 0 <= i < len(dec.candidates)]
                if not ids:
                    return None, False, ""
                return [dec.candidates[i] for i in ids], False, (args.get("reason") or "")[:200]
            if name == "no_coverage":
                return [], True, (args.get("reason") or "")[:200]
            result = dec._dispatch(name, args)
            messages.append({"role": "tool", "tool_call_id": call.get("id") or name,
                             "content": json.dumps(result, ensure_ascii=False)})
    return None, False, ""

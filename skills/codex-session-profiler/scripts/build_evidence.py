#!/usr/bin/env python3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


QUERIES = {
    "context_control": r"不要.*全文|不要一次性|上下文爆炸|上下文|subagent|子agent|分片|小窗口",
    "tooling": r"\brg\b|\bsed\b|sqlite|CLI|命令|shell|脚本|批量",
    "verification": r"验证|测试|跑一下|检查|确认|审计|核对",
    "risk": r"不要删|删除|覆盖|保留|备份|恢复|安全|权限",
    "direct_execution": r"直接|执行|实现|改|保存|生成|创建|落地",
    "lark": r"飞书|Lark|lark-cli|多维表格|日程|会议",
    "media": r"图片|图像|视频|音频|截图|字幕|转写",
    "docs": r"文档|README|prompt|总结|报告|画像|markdown|知识库",
    "correction": r"不是|不对|错|你.*应该|不要|别|重新|漏了",
}


def clip(text, n=180):
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


sessions = json.load(open("data/extracted/sessions_summary.json"))
evidence = {k: [] for k in QUERIES}
cwd = Counter()
dates = Counter()
tags = Counter()
message_count = 0

for s in sessions:
    cwd[s.get("cwd") or "unknown"] += 1
    if s.get("created_at"):
        dates[s["created_at"][:10]] += 1
    tags.update(s.get("tags", []))
    for msg in s.get("user_messages", []):
        message_count += 1
        for key, pat in QUERIES.items():
            if re.search(pat, msg, re.I) and len(evidence[key]) < 30:
                evidence[key].append(
                    {
                        "session_id": s.get("session_id"),
                        "cwd": s.get("cwd"),
                        "created_at": s.get("created_at"),
                        "excerpt": clip(msg),
                    }
                )

out = {
    "counts": {
        "sessions": len(sessions),
        "user_messages": message_count,
        "cwd_distribution": cwd.most_common(),
        "date_distribution": sorted(dates.items()),
        "tag_distribution": tags.most_common(),
    },
    "evidence": evidence,
}
Path("reports").mkdir(exist_ok=True)
Path("reports/evidence_digest.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out["counts"], ensure_ascii=False, indent=2))

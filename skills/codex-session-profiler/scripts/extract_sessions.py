#!/usr/bin/env python3
import argparse
import json
import os
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


TAG_KEYWORDS = {
    "code_edit": ["改", "修", "实现", "代码", "patch", "edit", "commit", "测试", "bug", "fix"],
    "research": ["查", "调研", "搜索", "研究", "资料", "news", "latest", "browse", "web"],
    "debugging": ["报错", "错误", "失败", "debug", "排错", "日志", "traceback"],
    "refactor": ["重构", "refactor", "整理结构", "抽象", "迁移"],
    "automation": ["自动", "脚本", "批量", "workflow", "cron", "pipeline"],
    "docs": ["文档", "README", "prompt", "画像", "总结", "报告", "markdown", "doc"],
    "lark": ["飞书", "Lark", "lark", "多维表格", "日程", "会议", "审批"],
    "media": ["图片", "视频", "image", "video", "screenshot", "截图", "音频"],
    "cli": ["CLI", "命令", "terminal", "shell", "rg", "sed", "sqlite", "lark-cli"],
}


def truncate_text(text, limit):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def first_para(text):
    text = (text or "").strip()
    if not text:
        return ""
    parts = re.split(r"\n\s*\n", text)
    return truncate_text(parts[0], 280)


def content_to_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") in {"input_text", "text", "output_text"}:
                    parts.append(item.get("text", ""))
                elif "text" in item:
                    parts.append(item.get("text", ""))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(p for p in parts if p)
    return ""


def extract_user_text(payload):
    if not isinstance(payload, dict):
        return ""
    if payload.get("type") == "user_message":
        return payload.get("message", "")
    if payload.get("role") == "user":
        return content_to_text(payload.get("content"))
    if payload.get("type") == "message" and payload.get("role") == "user":
        return content_to_text(payload.get("content"))
    return ""


def extract_assistant_text(payload):
    if not isinstance(payload, dict):
        return ""
    if payload.get("type") == "message" and payload.get("role") == "assistant":
        return content_to_text(payload.get("content"))
    if payload.get("role") == "assistant":
        return content_to_text(payload.get("content"))
    if payload.get("type") in {"assistant_message", "agent_message"}:
        return payload.get("message", "") or content_to_text(payload.get("content"))
    return ""


def infer_preferences(user_messages):
    joined = "\n".join(user_messages)
    prefs = []
    checks = [
        (r"不要.*全文|不要一次性|上下文爆炸|分片|subagent|子agent", "强调上下文控制，倾向分片或 subagent 处理大任务"),
        (r"先.*查|先.*分析|先.*看|不要猜|确认|验证", "希望先调查和验证，再给结论或改动"),
        (r"直接.*改|直接.*做|可以任意使用|落地|执行", "偏好 agent 主动执行并产出可用文件"),
        (r"备份|不要删|不要覆盖|保留|恢复", "对数据安全、删除和覆盖敏感"),
        (r"简洁|少废话|直接给结论|结构化|中文", "偏好中文、简洁、结构化输出"),
        (r"rg|sed|小窗口|sqlite|命令", "会明确约束工具使用和命令行工作方式"),
    ]
    for pattern, label in checks:
        if re.search(pattern, joined, re.I):
            prefs.append(label)
    return prefs


def classify(messages):
    joined = "\n".join(messages)
    tags = []
    for tag, words in TAG_KEYWORDS.items():
        if any(w.lower() in joined.lower() for w in words):
            tags.append(tag)
    return tags


def parse_session(path):
    meta = {
        "session_id": None,
        "cwd": None,
        "created_at": None,
        "updated_at": None,
        "path": str(path),
        "user_messages": [],
        "assistant_first_paragraphs": [],
    }
    timestamps = []
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = event.get("timestamp")
            if ts:
                timestamps.append(ts)
            payload = event.get("payload", {})
            if event.get("type") == "session_meta" and isinstance(payload, dict):
                meta["session_id"] = payload.get("id") or meta["session_id"]
                meta["cwd"] = payload.get("cwd") or meta["cwd"]
                meta["created_at"] = payload.get("timestamp") or ts or meta["created_at"]
            user_text = extract_user_text(payload)
            if user_text and not user_text.startswith("<environment_context>"):
                meta["user_messages"].append(truncate_text(user_text, 900))
            assistant_text = extract_assistant_text(payload)
            if assistant_text:
                para = first_para(assistant_text)
                if para:
                    meta["assistant_first_paragraphs"].append(para)
    if timestamps:
        meta["created_at"] = meta["created_at"] or min(timestamps)
        meta["updated_at"] = max(timestamps)
    if not meta["session_id"]:
        match = re.search(r"rollout-[^-]+T[^-]+-(.+)\.jsonl$", path.name)
        meta["session_id"] = match.group(1) if match else path.stem
    meta["tags"] = classify(meta["user_messages"])
    meta["inferred_preferences"] = infer_preferences(meta["user_messages"])
    return meta


def sqlite_threads(db_path):
    rows = []
    if not Path(db_path).exists():
        return rows
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        for row in con.execute(
            "select id, rollout_path, cwd, title, created_at, updated_at, first_user_message "
            "from threads order by updated_at desc"
        ):
            rows.append(dict(row))
    finally:
        con.close()
    return rows


def group_key(session):
    cwd = session.get("cwd") or "unknown"
    name = Path(cwd).name or "unknown"
    created = session.get("created_at") or ""
    day = created[:10] if len(created) >= 10 else "unknown-date"
    return f"{name}__{day}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions", default=os.path.expanduser("~/.codex/sessions"))
    parser.add_argument("--state", default=os.path.expanduser("~/.codex/state_5.sqlite"))
    parser.add_argument("--out", default="data/extracted")
    parser.add_argument("--max-group-size", type=int, default=12)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    session_paths = sorted(Path(args.sessions).glob("**/*.jsonl"))
    summaries = [parse_session(p) for p in session_paths]
    threads = sqlite_threads(args.state)

    cwd_counts = Counter(s.get("cwd") or "unknown" for s in summaries)
    sqlite_cwd_counts = Counter(r.get("cwd") or "unknown" for r in threads)
    tags = Counter(tag for s in summaries for tag in s.get("tags", []))

    (out / "sessions_summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out / "state_threads_index.json").write_text(
        json.dumps(threads, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    stats = {
        "session_file_count": len(session_paths),
        "sqlite_thread_count": len(threads),
        "session_cwd_distribution": cwd_counts.most_common(),
        "sqlite_cwd_distribution": sqlite_cwd_counts.most_common(),
        "tag_distribution": tags.most_common(),
    }
    (out / "stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    buckets = defaultdict(list)
    for s in summaries:
        buckets[group_key(s)].append(s)

    manifest = []
    group_dir = Path("data/groups")
    group_dir.mkdir(parents=True, exist_ok=True)
    group_index = 1
    for key, items in sorted(buckets.items()):
        for start in range(0, len(items), args.max_group_size):
            chunk = items[start : start + args.max_group_size]
            group_id = f"group_{group_index:02d}"
            group_path = group_dir / f"{group_id}.json"
            group_path.write_text(json.dumps(chunk, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest.append(
                {
                    "group_id": group_id,
                    "key": key,
                    "count": len(chunk),
                    "path": str(group_path),
                    "cwd_values": sorted({x.get("cwd") or "unknown" for x in chunk}),
                    "date_values": sorted({(x.get("created_at") or "")[:10] for x in chunk}),
                }
            )
            group_index += 1
    (Path("data") / "groups_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps({"stats": stats, "groups": len(manifest)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

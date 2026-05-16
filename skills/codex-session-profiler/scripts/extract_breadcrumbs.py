#!/usr/bin/env python3
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


DATA = Path("data/extracted/sessions_summary.json")
OUT = Path("reports/breadcrumb-details.md")

CATEGORIES = {
    "开场/发起": [
        r"看下[^。！？\n]{0,40}",
        r"帮我[^。！？\n]{0,50}",
        r"检查一下[^。！？\n]{0,50}",
        r"简单看下[^。！？\n]{0,50}",
        r"继续[^。！？\n]{0,50}",
        r"测评[^。！？\n]{0,50}",
    ],
    "边界/上下文控制": [
        r"不要[^。！？\n]{0,70}",
        r"别[^。！？\n]{0,60}",
        r"只[^。！？\n]{0,70}",
        r"不要.*全文[^。！？\n]{0,40}",
        r"上下文[^。！？\n]{0,70}",
        r"subagent[^。！？\n]{0,70}",
        r"小窗口[^。！？\n]{0,70}",
    ],
    "执行/落地": [
        r"直接[^。！？\n]{0,70}",
        r"写进[^。！？\n]{0,70}",
        r"保存[^。！？\n]{0,70}",
        r"生成[^。！？\n]{0,70}",
        r"改成[^。！？\n]{0,70}",
        r"做成[^。！？\n]{0,70}",
        r"提交[^。！？\n]{0,70}",
    ],
    "验证/验收": [
        r"验证[^。！？\n]{0,70}",
        r"测试[^。！？\n]{0,70}",
        r"跑一下[^。！？\n]{0,70}",
        r"确认[^。！？\n]{0,70}",
        r"检查[^。！？\n]{0,70}",
        r"看看[^。！？\n]{0,70}",
    ],
    "纠偏/否定": [
        r"不对[^。！？\n]{0,70}",
        r"不是[^。！？\n]{0,70}",
        r"你[^。！？\n]{0,30}应该[^。！？\n]{0,50}",
        r"为啥[^。！？\n]{0,70}",
        r"怎么[^。！？\n]{0,70}",
        r"少了[^。！？\n]{0,70}",
        r"漏[^。！？\n]{0,70}",
    ],
    "风格/表达": [
        r"简洁[^。！？\n]{0,70}",
        r"说人话[^。！？\n]{0,70}",
        r"平实[^。！？\n]{0,70}",
        r"不要.*废话[^。！？\n]{0,50}",
        r"不要.*花哨[^。！？\n]{0,50}",
        r"中文[^。！？\n]{0,70}",
        r"结构化[^。！？\n]{0,70}",
    ],
    "工具/文件口径": [
        r"\.output[^。！？\n]{0,70}",
        r"\.input[^。！？\n]{0,70}",
        r"node [^。！？\n]{0,80}",
        r"README[^。！？\n]{0,70}",
        r"Markdown[^。！？\n]{0,70}",
        r"rg[^。！？\n]{0,70}",
        r"sed[^。！？\n]{0,70}",
        r"git[^。！？\n]{0,70}",
    ],
}


def norm(text):
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clip(text, n=120):
    text = norm(text)
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def clean_fragment(text):
    text = norm(text)
    text = re.sub(r"/Users/wswensw/[^ ]+", "<path>", text)
    text = re.sub(r"https?://[^ ]+", "<url>", text)
    text = text.strip(" -，,；;：:")
    return clip(text, 120)


def is_noise(text):
    bad = [
        "subagent_notification",
        "agent_path",
        "input_text",
        "environment_context",
        "markdown fences",
        "base_instructions",
    ]
    if any(x in text for x in bad):
        return True
    if text.count("{") + text.count("}") >= 2:
        return True
    if len(text) < 2:
        return True
    return False


def collect():
    sessions = json.loads(DATA.read_text())
    found = {k: [] for k in CATEGORIES}
    seen = {k: set() for k in CATEGORIES}
    verb_counter = Counter()
    constraint_counter = Counter()
    all_msgs = []

    for s in sessions:
        sid = s.get("session_id")
        cwd = s.get("cwd", "")
        for msg in s.get("user_messages", []):
            msg = norm(msg)
            if not msg:
                continue
            all_msgs.append(msg)
            for word in ["看下", "帮我", "检查", "继续", "直接", "改成", "做成", "写进", "保存", "生成", "提交", "验证", "测试", "确认", "不要", "只", "先"]:
                if word in msg:
                    verb_counter[word] += 1
            for word in ["不要", "只", "先", "直接", "默认", "保留", "不要全文", "不要改", "不要读", "不要删", "不 push", "不推送"]:
                if word in msg:
                    constraint_counter[word] += 1
            for cat, patterns in CATEGORIES.items():
                if len(found[cat]) >= 18:
                    continue
                for pat in patterns:
                    m = re.search(pat, msg, re.I)
                    if m:
                        text = clean_fragment(m.group(0))
                        if is_noise(text) or text in seen[cat]:
                            break
                        seen[cat].add(text)
                        found[cat].append(
                            {
                                "text": text,
                                "session_id": sid,
                                "cwd_name": Path(cwd).name or cwd,
                            }
                        )
                        break

    return sessions, found, verb_counter, constraint_counter


def write_report():
    sessions, found, verbs, constraints = collect()
    lines = [
        "# 面包屑细节：常用句式、表达习惯和协作口径",
        "",
        f"数据来源：`data/extracted/sessions_summary.json`，覆盖 {len(sessions)} 个 session。以下只保留用户消息中的短片段和模式，不展开长原文。",
        "",
        "## 高频触发词",
        "",
        "这些词经常标记任务推进方式：",
        "",
    ]
    for word, count in verbs.most_common(18):
        lines.append(f"- `{word}`：{count}")
    lines += ["", "## 高频约束词", ""]
    for word, count in constraints.most_common(14):
        lines.append(f"- `{word}`：{count}")

    lines += [
        "",
        "## 句式样本",
        "",
        "这些不是完整原文归档，而是用于保留语气、边界和协作习惯的短面包屑。",
        "",
    ]
    for cat, items in found.items():
        lines += [f"### {cat}", ""]
        for item in items[:12]:
            lines.append(f"- `{item['text']}` 〔{item['cwd_name']} / {item['session_id']}〕")
        lines.append("")

    lines += [
        "## 可沉淀的表达习惯",
        "",
        "- 常用短促发起式：`看下`、`帮我`、`检查一下`、`简单看下`、`继续`。",
        "- 常把任务从一次性动作推进成可复用工具：`做成脚本`、`做成插件`、`写进文档`、`保存到文档`。",
        "- 常用明确边界句：`不要读全文`、`不要改文件`、`只看这些`、`不要输出过程日志`。",
        "- 常用直接落地句：`直接改`、`直接执行`、`改成`、`生成`、`提交，不推送`。",
        "- 常用纠偏句：`不对`、`不是...`、`怎么还...`、`为啥...`、`漏了...`。",
        "- 风格要求偏负面约束：通过 `不要废话`、`不要花哨`、`保持简洁`、`说人话` 来压低表达噪音。",
        "- 验收口径偏具体：会点名默认目录、入口命令、输出文件、缓存、失败记录、是否 push。",
        "- 大任务偏好先建索引和分片，再抽取、汇总、去重，不接受主线程吞大文本。",
    ]

    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    write_report()

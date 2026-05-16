---
name: codex-session-profiler
description: Analyze Codex historical session logs into a personal coding-agent profile. Use when the user asks to analyze ~/.codex/sessions, Codex history, development habits, AI collaboration preferences, common workflows, prompt/profile generation, long-term memory extraction, or breadcrumb-style expression patterns from past sessions.
---

# Codex Session Profiler

Use this skill to turn Codex session history into a reusable AI coding-agent profile without loading raw logs into context.

## Resources

- `scripts/extract_sessions.py`: Extract compact per-session summaries, sqlite metadata, stats, and bounded group files.
- `scripts/build_evidence.py`: Generate aggregate counts and short evidence excerpts from extracted summaries.
- `scripts/extract_breadcrumbs.py`: Generate breadcrumb details such as common phrases, constraints, corrections, and command/file idioms.
- `references/session-profile-sop.md`: Full workflow, output contract, subagent prompt template, validation commands, and audit checklist. Read it when running the full workflow or changing the process.

## Minimal Workflow

1. Work from the target project directory so generated `data/` and `reports/` stay with that project.
2. Use the bundled scripts, or copy them into the project if the user wants a self-contained repo.
3. Run extraction before analysis. The extraction must focus on user messages and keep assistant output to the first paragraph only.
4. Analyze only `data/extracted/*.json`, `data/groups_manifest.json`, and `data/groups/*.json`; do not read raw session JSONL into context.
5. Use subagents or equivalent bounded slices for group analysis. Each slice should read only group summary files, not raw logs.
6. Write `reports/developer-profile.md`, `reports/breadcrumb-details.md`, and `reports/completion-audit.md`.

## Output Contract

The final profile must include:

- 工作方式
- 需求表达偏好
- 技术偏好
- AI 协作偏好
- 风险偏好
- 可复用个人 Prompt
- 可写入长期 Memory 的短句

The breadcrumb report must preserve high-information details such as frequent starters, boundary phrases, correction patterns, style preferences, and command/file conventions.

## Guardrails

- Do not bulk-read `~/.codex/sessions/**/*.jsonl`.
- Do not let subagents read raw session logs.
- Do not include full assistant replies in summaries.
- Do not turn one-off behavior into stable preference without corroboration.
- Do not skip breadcrumb details; abstract summaries alone are insufficient.
- Do not finish without a prompt-to-artifact completion audit.

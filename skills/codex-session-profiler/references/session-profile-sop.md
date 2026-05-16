# Codex 历史 Session 画像分析 SOP

## 目标

从 Codex 历史 session 中提炼用户的开发习惯、行为偏好、AI 协作偏好、风险偏好、常见工作流、常用句式和表达习惯，最终生成可用于配置 AI coding agent 的个人画像、可复用 prompt 和长期 memory。

## 输入

默认数据源：

- `~/.codex/sessions/**/*.jsonl`
- `~/.codex/state_5.sqlite`

只把 `state_5.sqlite` 当作元数据索引，用于校验线程数量、cwd 分布、时间和标题等信息。核心分析以 session 中的用户消息为主。

## 输出

建议固定输出到当前工作区：

- `data/extracted/sessions_summary.json`
- `data/extracted/state_threads_index.json`
- `data/extracted/stats.json`
- `data/groups_manifest.json`
- `data/groups/group_*.json`
- `reports/evidence_digest.json`
- `reports/developer-profile.md`
- `reports/breadcrumb-details.md`
- `reports/completion-audit.md`

脚本放在：

- `scripts/extract_sessions.py`
- `scripts/build_evidence.py`
- `scripts/extract_breadcrumbs.py`

## 核心原则

不要一次性读取所有 session 全文。先脚本化抽取结构化摘要，再让主 agent 和 subagent 读取摘要文件。

重点关注用户消息。assistant 回复只取第一行或首段，用于判断上下文，不要把 assistant 长文放进主上下文。

每个 session 只抽取这些字段：

1. `session_id`
2. `cwd`
3. `created_at`
4. `updated_at`
5. `user_messages`
6. `assistant_first_paragraphs`
7. `tags`
8. `inferred_preferences`

必须保留两层信息：

- 稳定偏好：抽象后的工作方式、协作偏好、技术偏好、风险偏好。
- 面包屑细节：常用句式、短促发起词、边界句、纠偏句、风格口径、命令和文件口径。

## 流程

### 1. 建立工作目录

```bash
mkdir -p scripts data/extracted data/groups reports docs
```

### 2. 列出 session 与 sqlite 概况

先用轻量命令确认数据规模：

```bash
find ~/.codex/sessions -type f -name '*.jsonl' | wc -l
sqlite3 ~/.codex/state_5.sqlite '.tables'
```

不要用 `sed` 直接扫原始 jsonl 的大段内容。session 前几行可能包含很大的系统指令块。

### 3. 抽取结构化摘要

运行：

```bash
python3 scripts/extract_sessions.py
```

脚本职责：

- 扫描 `~/.codex/sessions/**/*.jsonl`
- 查询 `~/.codex/state_5.sqlite` 的 `threads` 表
- 提取每个 session 的最小字段
- 对用户消息适度压缩，保留原意
- 对 assistant 只保留首段并截断
- 用关键词标注任务标签
- 初步推断偏好信号
- 按 `cwd + 日期` 生成 group

推荐分组上限：

- 单个 group 最多 12 个 session
- 大任务可进一步按项目目录、日期、主题拆分

### 4. 生成证据摘要

运行：

```bash
python3 scripts/build_evidence.py
```

证据摘要用于统计和引用，不替代最终判断。至少包含：

- session 数量
- 用户消息数量
- cwd 分布
- 日期分布
- tag 分布
- 各类偏好的短证据片段

### 5. 分派 subagent

subagent 只读 `data/groups/*.json` 和 `data/extracted/stats.json`，不要读取原始 jsonl。

推荐分派方式：

- 知识库 / atwiki 分片
- playground 通用开发分片
- CLI / Lark / 图片视频工具分片
- 小项目 / 其他分片

subagent 指令模板：

```text
你负责分析 Codex 历史 session 的 <项目簇> 分片。
只读取这些结构化摘要文件，不要读取 ~/.codex 原始 jsonl：
<group 文件列表>，以及 data/extracted/stats.json。

任务：输出结构化中文摘要，覆盖：
- 常见需求表达
- 工作方式偏好
- AI 协作偏好
- 风险敏感点
- 任务类型
- 经常纠正 AI 的点
- 可沉淀 memory

引用 group_id 和 session_id 作为证据，不输出原始长文本。
```

subagent 输出必须是结构化摘要。不要粘贴长原文。

### 6. 主 agent 汇总画像

主 agent 合并这些来源：

- `data/extracted/stats.json`
- `reports/evidence_digest.json`
- subagent 结构化摘要
- 必要时抽样查看 `data/groups/*.json`

最终画像固定包含这些章节：

```markdown
# 我的开发习惯画像

## 工作方式

## 需求表达偏好

## 技术偏好

## AI 协作偏好

## 风险偏好

## 可复用个人 Prompt

## 可写入长期 Memory 的短句
```

写作要求：

- 中文
- 直接给结论
- 不写泛泛评价
- 用具体任务类型和行为模式支撑结论
- prompt 要能直接贴给 Codex、Claude、ChatGPT 等 coding agent
- memory 短句建议 10 到 20 条

### 7. 抽取面包屑细节

运行：

```bash
python3 scripts/extract_breadcrumbs.py
```

面包屑文档用于保留画像里容易丢失的细节，不追求完整原文归档。

必须覆盖：

- 高频触发词，比如 `看下`、`帮我`、`继续`
- 高频约束词，比如 `不要`、`只`、`先`、`直接`
- 开场 / 发起句式
- 边界 / 上下文控制句式
- 执行 / 落地句式
- 验证 / 验收句式
- 纠偏 / 否定句式
- 风格 / 表达句式
- 工具 / 文件口径

抽取时要过滤：

- subagent 通知噪声
- 大段 JSON
- 系统指令
- 环境上下文
- 长路径和 URL，可替换成 `<path>`、`<url>`
- 重复片段

面包屑文档示例结构：

```markdown
# 面包屑细节：常用句式、表达习惯和协作口径

## 高频触发词

## 高频约束词

## 句式样本

### 开场/发起

### 边界/上下文控制

### 执行/落地

### 验证/验收

### 纠偏/否定

### 风格/表达

### 工具/文件口径

## 可沉淀的表达习惯
```

主画像必须引用这份面包屑文档，避免它成为孤立产物。

## 标签规则

最小标签集合：

- `code_edit`
- `research`
- `debugging`
- `refactor`
- `automation`
- `docs`
- `lark`
- `media`
- `cli`

标签只用于聚类和统计，不等同最终结论。最终画像必须由统计、短证据和 subagent 摘要共同支撑。

## 风险控制

禁止事项：

- 不要一次性读所有原始 session 全文
- 不要把 assistant 长回复整体放进摘要
- 不要让 subagent 读取 `~/.codex/sessions/**/*.jsonl`
- 不要只输出抽象结论，忽略常用句式和面包屑细节
- 不要把单次 session 的偶发现象写成稳定偏好
- 不要用通过脚本运行作为完成证明，必须做目标到产物的审计

允许事项：

- 用脚本逐行解析原始 jsonl
- 对用户消息适度压缩
- 对路径、URL、敏感字段做脱敏
- 使用 subagent 分片分析摘要文件
- 用 group_id、session_id 引用证据

## 完成审计

完成前必须生成 `reports/completion-audit.md`。

审计要包含：

- 目标复述
- 要求到产物的映射表
- 验证命令
- 实际观察结果
- 最终产物列表

最低验证项：

```bash
python3 - <<'PY'
import json, os
s = json.load(open('data/extracted/sessions_summary.json'))
m = json.load(open('data/groups_manifest.json'))
missing = []
for x in s:
    for k in ['session_id','cwd','created_at','updated_at','user_messages','assistant_first_paragraphs','tags','inferred_preferences']:
        if k not in x:
            missing.append((x.get('path'), k))
print('sessions', len(s))
print('groups', len(m))
print('covered', sum(g['count'] for g in m))
print('max_group_size', max(g['count'] for g in m))
print('missing_fields', len(missing))
print('all_group_paths_exist', all(os.path.exists(g['path']) for g in m))
PY
```

还要检查：

- `reports/developer-profile.md` 是否包含指定章节
- `reports/breadcrumb-details.md` 是否存在并包含句式样本
- `reports/developer-profile.md` 是否引用 `reports/breadcrumb-details.md`
- `reports/completion-audit.md` 是否把每个显式要求映射到实际产物

## 判断完成的标准

只有同时满足以下条件，才算完成：

- session 文件数和 sqlite thread 数已核对
- 所有 session 都进入分组
- 单组大小不超过预设上限
- 每个 session 的必需字段无缺失
- subagent 已分片输出结构化摘要
- 最终画像包含指定章节
- 可复用 prompt 可直接使用
- memory 短句数量符合要求
- 面包屑细节已单独保存
- 完成审计已保存并通过核对

## 复跑建议

新 session 增加后可复跑：

```bash
python3 scripts/extract_sessions.py
python3 scripts/build_evidence.py
python3 scripts/extract_breadcrumbs.py
```

复跑后需要重新检查：

- `data/extracted/stats.json`
- `data/groups_manifest.json`
- `reports/breadcrumb-details.md`
- `reports/developer-profile.md`
- `reports/completion-audit.md`

如果只想增量更新画像，先比较新旧 `sessions_summary.json` 中新增的 `session_id`，再单独分析新增 group。

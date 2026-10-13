# CC 注入 wire 格式台账（实测确认）

> 环境：官方 claude 2.1.296 linux-x64 原生二进制 + 本 skill 的 mock API。
> 所有结论来自真实抓包（/tmp/cc-mem-capture 原件）。新实验只把**实测验证过的**写进这里。

## 1. 请求总体结构

- 顶层 `system` = 数组：`[billing-header（无cc）, 身份行（cc:ephemeral）, 主 system prompt（cc:ephemeral）]`
- `messages` 数组中允许 **system role 出现在中间**（1P API 特性）：
  `# Environment`、mid-turn 补投、total_tokens 更新都走这个通道

## 2. 记忆召回（relevant memories）

### 赶趟（selector 在首答前完成）
```
messages[0] = {role:"user", content:"<system-reminder>
Retrieved for possible relevance — use only if it actually applies to what
the user asked.

Memory: /abs/path/skate-img-spec.md:

---
name: skate-img-spec
description: …
metadata:
  type: project
---
正文…

</system-reminder>"}          ← 每条记忆一条 user 消息；第一条带引导语；
                                 第二条只有 "Memory: <path>:\n\n正文"（同样 SR 包裹）
之后才是含用户 query 的 user 消息（其 content 数组内含 MEMORY.md 索引 SR 块 +
attribution SR 块 + query 文本，共 3 个 text block）
```

### 没赶趟（mid-turn 补投，工具结果之后）
```
{role:"system", content:[{type:"text",
  text:"<total_tokens>14999985 tokens left</total_tokens>\n\n
Retrieved for possible relevance — …\n\nMemory: /…/a.md:\n\n…\n\nMemory: /…/b.md:\n\n…",
  cache_control:{type:"ephemeral"}}]}
```
- **所有选中记忆打包进单个 text block**（不是每条一条消息）
- 无 `<system-reminder>` 外层包裹（与赶趟形态不同！）
- total_tokens 在前、召回在后，`\n\n` 分隔

## 3. total_tokens

- 位置：尾部 system 消息内（# Environment 末尾或独立 mid-turn system 消息）
- 形态：`<total_tokens>N tokens left</total_tokens>`（padded-countdown 默认 15,000,000 起倒数）
- 无赶趟时与召回合并同一条

## 4. MEMORY.md 索引（会话开始）

```
{role:"user", content:[…,
 {type:"text", text:"<system-reminder>
Codebase and user instructions are shown below…
Contents of /path/memory/MEMORY.md (user's auto-memory, persists across
conversations):

- [api-gateway](api-gateway.md) — …
</system-reminder>"},
 {type:"text", text:"<system-reminder>Attribution for git commits…</system-reminder>"},
 {type:"text", text:"用户query"}]}
```
- MEMORY.md 不存在时 CC **自动生成**（每条 `- [Title](file.md) — description`）

## 5. selector sideQuery 请求

```
system: [billing-header, "You are selecting memories that will be useful…"]
messages: [
 {role:"user", content:"Available memories:
- [project] skate-img-spec.md (2026-10-13T02:26:33.193Z): 滑板透明图规格：…"},
 {role:"user", content:"Select memories relevant to:
<用户query原文>"}
]
max_tokens: 2560, 非流式
```
- 清单：`- [type] filename (ISO-mtime): description`，mtime 倒序，≤200，MEMORY.md 不在列
- 无 type 的文件无 `[type] ` 前缀；无 description 的无 `: desc` 尾

## 6. 开关矩阵（实测有效组合）

| 目的 | 手段 |
|---|---|
| 强开 auto-memory | env `CLAUDE_CODE_DISABLE_AUTO_MEMORY=false`（值必须 "false"） |
| 强开召回 sideQuery | flag 种子 `tengu_moth_copse:true`（需 GB isEnabled，见下） |
| 首轮阻塞消费 | `tengu_mill_orange:true` |
| 提取 fork | `tengu_passport_quail:true` + `tengu_bramble_lintel:1` |
| total_tokens 模式 | `tengu_lapis_anchor:"padded-countdown"` + budget 15000000（兜底即此值） |
| GB isEnabled | 伪 OAuth（~/.claude/.credentials.json claudeAiOauth）+ `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1` |
| 种子载体 | ~/.claude.json 的 `cachedGrowthBookFeatures` |
| 反面清单 | `-p` 模式（无消费点）、NONESSENTIAL_TRAFFIC（杀GB）、env="1"（=关闭） |

## 7. 待测项（下次实验的候选）

- [ ] 单条记忆 >4KB / >200 行时的截断块与 Read 指路文案实测
- [ ] mtime>1 天的 staleness `<system-reminder>` 追加实测
- [ ] synthesize 模式触发条件与 `<synthesis:DIR>` 形态
- [ ] 提取 fork 的完整 prompt 抓包（当前 mock extract 回 'Nothing to save.'）
- [ ] 多用户回合后 selector 多轮对话形态（assistant 历史轮）
- [ ] `tengu_salt_marsh` 开启后 `<cc-memory>` 引用标注形态
- [ ] 账号/团队记忆（CLAUDE_MEMORY_STORES）注入通道
- [ ] mid-conversation-system 降级路径：无 beta 能力模型上 missed-train 召回是否退回 user-SR 消息（当前 mock 模型未声明该能力却出现了 system role——需对照声明/不声明能力两次抓包确认 gate 是否真的生效）

## 8. 证据等级标注约定

- 【capture】= 有真实抓包原件（最高等级；第 2/3/4/5 节均为 capture 级）
- 【code】= 二进制逆向代码路径推导（如降级路径、flag gate 链）
- 【single】= 仅一次成功抓包、复现不稳定（赶趟/没赶趟召回均为 single；引用时注明）

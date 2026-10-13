---
name: cc-injection-probe
description: 用 mock API 实测 Claude Code 官方二进制的注入 wire 格式（记忆召回/total_tokens/MEMORY.md/system分节）。当用户要"测 CC 的注入/抓 wire 格式/复现召回实验/验证注入位置"时使用。
---

# CC Injection Probe

对官方 Claude Code 原生二进制（2.1.296 逆向版，路径由环境变量 `CC_BIN` 指定）做**注入格式实测**：本地 mock API 截获全部请求体，观察记忆召回、total_tokens、MEMORY.md 索引、system 分节等注入的真实 wire 形态。

## 资产

- `scripts/mock_api.py` — mock Anthropic API（支持场景/延迟/选择列表/工具循环）
- `scripts/run_probe.sh` — 一键沙箱（伪造 HOME/OAuth/flag 种子 + 启 mock + 跑 CC）
- `scripts/analyze.py` — 抓包结构化摘要（注入位置自动标注）
- `references/wire-format.md` — 已实测确认的 wire 格式台账（读这个对照新抓包）
- 二进制路径环境变量 `CC_BIN` 可覆盖

## 快速开始

```bash
# 赶趟场景（selector 首答前完成 → 召回在第一次请求，user 角色）
bash ~/.hermes/skills/cc-injection-probe/scripts/run_probe.sh catch 4551 "你的问题"

# 没赶趟（召回在工具结果后，system 角色，与 total_tokens 合并）
bash ~/.hermes/skills/cc-injection-probe/scripts/run_probe.sh miss 4552 "你的问题"

# 无工具循环（看纯文本路径的注入）
bash ~/.hermes/skills/cc-injection-probe/scripts/run_probe.sh notool 4553 "你的问题"

# 结构化摘要
python3 ~/.hermes/skills/cc-injection-probe/scripts/analyze.py /tmp/cc-mem-capture
```

场景原理：`catch` = mock 把首个主请求延迟 4s（selector 秒回，赶在首答前注入）；`miss` = 零延迟（首答先发，召回经 mid-turn 通道补投）；`notool` = 主请求直接回文本。

## 关键坑（复现失败先查这里）

1. **必须交互模式**：`-p` 一次性模式没有 mid-turn 消费点，selector 首轮阻塞也需要 `tengu_mill_orange`。管道喂输入 `printf '问题\n/exit\n' | claude` 即可
2. **`CLAUDE_CODE_DISABLE_AUTO_MEMORY=false` 是强制开启**（不是关闭！）：`vs()` 解析 "false" → `forced_on`。设 `"1"`/`"0"` 都是关
3. **GrowthBook 双重门槛**：flag 走 `cachedGrowthBookFeatures`（~/.claude.json 磁盘缓存），但读取前提是 `isEnabled()`——需要伪 OAuth 凭据（`~/.claude/.credentials.json` 的 claudeAiOauth）+ `CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1`（否则第三方 base_url 直接判死）。env 覆盖通道在生产构建被 stub，无法走
4. **别设 `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC`**：它会关 GrowthBook，flag 种子全部失效
5. 沙箱隔离 HOME 必须（`run_probe.sh` 自动用 `/tmp/cc-probe`），否则污染真实 `~/.claude`
6. mock 必须支持 stream（CC 默认流式）和 tool_use 的 `input_json_delta` 事件
7. **mock+sandbox 装置可通用于一切“CC 往 wire 上放了什么”的问题**：工具可用性探测不需要 selector/工具循环——`--main-mode text` + 一次性 `claude -p`，对比各隔离配置抓到的 `tools` 数组即可（方法+已验结论见 agent-harness-source-analysis → references/cc-tool-availability-control.md）。跨会话要留存的探针脚手架放本 skill 的 scripts/ 或持久 lab 目录——scratch 缓存 24h 修剪，会中途删掉进行中的探针配置。

## 可调实验维度（mock_api.py 参数）

- `--select a.md,b.md`：selector 选中的记忆（测不同选择集）
- `--first-delay N`：主请求延迟（控制赶趟/没赶趟边界）
- `--main-mode text|tool_then_text` / `--tool-name X`：制造不同工具循环
- 记忆文件内容/数量/frontmatter 形态：直接改沙箱 `$SANDBOX/.claude/projects/<slug>/memory/`
- flag 种子：改 `run_probe.sh` 里的 `cachedGrowthBookFeatures`（如关 `tengu_mill_orange` 看 blocking 消费消失）

## 已实测结论（详见 references/wire-format.md）

- 赶趟：召回 = **user 消息**（每条记忆一条，`<system-reminder>` 包裹，首条带引导语），位置在用户 query **之前**
- 没赶趟：召回与 total_tokens **合并为一条 system 消息**（tool_result 之后，单 text block，带 cache_control: ephemeral）
- MEMORY.md 索引：user 消息内 `<system-reminder>` 块（会话开始）
- `# Environment`/`# Memory` 等：system role 消息（messages 数组中间，1P API 特性）
- selector sideQuery：单发、max_tokens 2560、json_schema 输出

## 复现不稳定说明（重要）

召回（selector）的强制开启依赖伪 OAuth + GrowthBook 磁盘 flag 的组合，**已验证成功过一次**
（完整 wire 格式已录入 wire-format.md 第 2 节，那次抓包为确凿证据），但后续同环境复刻
未再触发。已排除：settings.json 存在与否、`.claude.json` flags 被改写（CC 重写时保留
了种子）、`CLAUDE_MEMORY_STORES` env 支路。推测 GB 对 OAuth 新鲜度/会话状态有额外判定。
排障顺序（按成本递增）：
① 抓包里第一条主请求有没有 MEMORY.md 索引 `<system-reminder>` 块——没有 = 整条
auto-memory 路径都没开（Ou() false），先修这个再查 selector；
② debug 日志（`<home>/.claude/debug/<session>.txt`）找 `act_dont_rederive_arm_active
source=growthbook`（GB 生效标志行，出现即 flags 通道活着）；
③ 换全新沙箱 HOME 首跑（唯一未验证的杠杆）。
验证 prompt 侧不依赖抓包：会话 transcript `<slug>/<uuid>.jsonl` 里的 `prompt_snapshot`
附件带完整拼装 system prompt，grep `# Memory` 即可确认 Memory 节加载。
total_tokens / `# Environment` / MEMORY.md 注入的复现是稳定的（不依赖 GB），
references/captures-proof/ 有留档抓包。

## 与 umbrella skill 的关系

方法论（为什么这么测、minified 名字地图、flag 极性表、注入面模型）在
`autonomous-ai-agents/agent-harness-source-analysis`（其 references/claude-code-native-binary.md
是完整知识库）。本 skill 只负责**可运行的探针资产**（mock/沙箱/分析脚本）——改实验设计时
查那边，改脚本时改这边。

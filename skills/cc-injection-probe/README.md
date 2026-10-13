# cc-injection-probe

用本地 mock API 实测 **Claude Code 官方二进制**的注入 wire 格式：记忆召回（relevant memories）、`<total_tokens>` 预算、MEMORY.md 索引、system prompt 分节到底以什么角色、什么位置、什么包裹格式进入 API 请求。

逆向分析对象：`@anthropic-ai/claude-code` 2.1.296 linux-x64 原生二进制（Bun 编译）。

## 快速开始

```bash
git clone https://github.com/AstonyCat/cc-injection-probe.git
cd cc-injection-probe

# 场景一：召回赶上首答（selector 在第一次 API 请求前完成）
bash scripts/run_probe.sh catch 4551 "帮我把滑板商品图批量去背"

# 场景二：召回没赶上（工具结果后才注入）
bash scripts/run_probe.sh miss 4552 "同上"

# 场景三：无工具循环
bash scripts/run_probe.sh notool 4553 "同上"

# 查看抓包摘要（注入位置自动标注）
python3 scripts/analyze.py /tmp/cc-mem-capture
```

`run_probe.sh` 会自建沙箱 HOME（伪造 OAuth 凭证、GrowthBook flag 种子、记忆文件），不碰你真实的 `~/.claude`。环境变量 `CC_BIN` 指定被测 claude 二进制路径。

## 已实测的 wire 格式（详见 references/wire-format.md）

| 注入物 | 位置 | 角色 | 包裹 |
|---|---|---|---|
| 记忆召回（赶趟） | 用户 query **之前**，每条一条消息 | **user** | `<system-reminder>` |
| 记忆召回（没赶趟） | tool_result 之后，与 total_tokens 合并为单 text block | **system** | 无外层标签，带 `cache_control: ephemeral` |
| MEMORY.md 索引 | 会话首条 user 消息内 | user | `<system-reminder>` |
| `# Environment`/`# Memory` 等 | messages 数组中间 | **system** | 无（1P API 允许 mid-array system） |
| total_tokens | 尾部 system 消息 | system | `<total_tokens>N tokens left</total_tokens>` |

selector sideQuery：单发、`max_tokens: 2560`、`output_format: json_schema`，清单格式 `- [type] filename (ISO-mtime): description`。

## 组件

- `scripts/mock_api.py` — 可配置 mock Anthropic API（`--scenario catch|miss|notool`、`--first-delay`、`--select`、`--main-mode`、`--tool-name`）
- `scripts/run_probe.sh` — 一键沙箱 + mock + 被测 CC
- `scripts/analyze.py` — 抓包结构化摘要
- `references/wire-format.md` — wire 格式台账 + 开关矩阵 + 待测清单
- `references/captures-proof/` — 留档真实抓包样本

## 已知限制

召回（selector）的强制开启依赖伪 OAuth + GrowthBook 磁盘 flag 组合，验证成功过一次（格式已录入台账），但同环境复刻未再稳定触发——GB 对 OAuth 新鲜度似有瞬态判定。total_tokens / Environment / MEMORY.md 注入的复现是稳定的。排障顺序见 SKILL.md。

## 声明

仅用于研究学习。Claude Code 的所有权利归 Anthropic 所有。

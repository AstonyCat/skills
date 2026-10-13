# skills

个人 agent skills 集合。每个 skill 一个自包含目录（`SKILL.md` + 按需的 `scripts/`、`references/`），遵循 [Agent Skills 开放格式](https://code.claude.com/docs/en/skills)。

适配 Claude Code / Codex / Hermes 等任何支持 `SKILL.md` 约定的 agent。

## Skills

| Skill | 一句话说明 |
|---|---|
| [harness-prompt-design](skills/harness-prompt-design/) | 编写 system prompt、工具描述与参数 schema 的风格规范，提炼自生产级 agent harness 的线上 prompt。凡新写或修改任何交付给 LLM 的文本都必须用。 |
| [cc-injection-probe](skills/cc-injection-probe/) | 用 mock API 实测 Claude Code 官方二进制的注入 wire 格式（记忆召回 / total_tokens / MEMORY.md / system 分节），附可运行探针脚本。 |

## 安装

```bash
git clone https://github.com/AstonyCat/skills.git
# 拷贝整个 skill 目录到你的 agent 技能目录
cp -r skills/harness-prompt-design ~/.claude/skills/   # Claude Code
cp -r skills/cc-injection-probe ~/.hermes/skills/       # Hermes Agent
```

或符号链接，`git pull` 即更新：

```bash
ln -s "$(pwd)/skills/harness-prompt-design" ~/.claude/skills/harness-prompt-design
```

## 目录约定

```
skills/<name>/
├── SKILL.md        # 必需：YAML frontmatter（name/description）+ 正文
├── README.md       # 可选：面向人的使用说明（skill 本身只需 SKILL.md）
├── scripts/        # 可选：可运行脚本
└── references/     # 可选：深度参考文档
```

## License

MIT

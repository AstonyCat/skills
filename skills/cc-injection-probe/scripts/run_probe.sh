#!/usr/bin/env bash
# run_probe.sh — one-shot CC injection probe
# usage: run_probe.sh <scenario:catch|miss|notool> <port> "<user prompt>" [capture_dir]
set -euo pipefail
SCENARIO="${1:-catch}"
PORT="${2:-4545}"
PROMPT="${3:-帮我把滑板商品图批量去背，注意规格和轮架}"
CAPTURE="${4:-/tmp/cc-mem-capture}"
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SANDBOX="${PROBE_HOME:-/tmp/cc-probe}"
BIN="${CC_BIN:-claude}"

# 1) sandbox home (idempotent)
mkdir -p "$SANDBOX/.claude"
PROJ="$SANDBOX/project"; mkdir -p "$PROJ"
# CC 的 memory 目录 slug: 绝对路径去掉开头 / 后, 所有 / 换成 - => "/tmp/x" -> "-tmp-x"
PROJSlug="-$(echo "$PROJ" | sed 's|^/||; s|/|-|g')"
MEMDIR="$SANDBOX/.claude/projects/$PROJSlug/memory"
mkdir -p "$MEMDIR"

# seed memory files only if empty
if [ -z "$(ls -A "$MEMDIR" 2>/dev/null)" ]; then
  cat > "$MEMDIR/skate-img-spec.md" <<'EOF'
---
name: skate-img-spec
description: 滑板透明图规格：800x800 PNG 居中不切轮架
metadata:
  type: project
---
滑板透明 SKU 图必须 800x800 透明 PNG 居中，文件 100K-600K，严禁切掉轮子支架。
EOF
  cat > "$MEMDIR/user-profile.md" <<'EOF'
---
name: user-profile
description: 用户做儿童轮滑鞋和滑板电商运营
metadata:
  type: user
---
用户经营儿童轮滑鞋&滑板电商店铺，重视转化数据。
EOF
fi

# 2) fake OAuth credentials (GrowthBook isEnabled requires first-party auth context)
cat > "$SANDBOX/.claude/.credentials.json" <<'EOF'
{"claudeAiOauth": {
  "accessToken": "sk-ant-oat01-mockmockmockmockmockmockmockmockmockmock",
  "refreshToken": "sk-ant-ort01-mockmockmockmockmockmockmockmockmockmo",
  "expiresAt": 4102444800000,
  "scopes": ["user:inference", "user:profile"],
  "emailAddress": "mock@test.local",
  "accountUuid": "00000000-0000-0000-0000-000000000001"}}
EOF
chmod 600 "$SANDBOX/.claude/.credentials.json"

# 3) seed GrowthBook flags into ~/.claude.json (disk cache)
python3 - "$SANDBOX" <<'PYEOF'
import json, os, sys
home = sys.argv[1]
p = os.path.join(home, '.claude.json')
cfg = {}
if os.path.exists(p):
    try: cfg = json.load(open(p))
    except Exception: cfg = {}
cfg['cachedGrowthBookFeatures'] = {
    "tengu_moth_copse": True,        # memory recall sideQuery
    "tengu_passport_quail": True,    # extraction
    "tengu_bramble_lintel": 1,       # extraction every N turns
    "tengu_mill_orange": True,       # first-iteration blocking consume
    "tengu_lapis_anchor": "padded-countdown",
    "tengu_lapis_anchor_budget": 15000000,
}
json.dump(cfg, open(p, 'w'), indent=1)
PYEOF

# 4) settings
cat > "$SANDBOX/.claude/settings.json" <<'EOF'
{"autoMemoryEnabled": true}
EOF

# 5) launch mock (background, own session)
rm -f "$CAPTURE"/*.json 2>/dev/null || true; mkdir -p "$CAPTURE"
python3 "$SKILL_DIR/scripts/mock_api.py" --scenario "$SCENARIO" --port "$PORT" \
  --select 'skate-img-spec.md,user-profile.md' --capture "$CAPTURE" \
  > "$CAPTURE/mock.log" 2>&1 &
MOCK_PID=$!
trap 'kill $MOCK_PID 2>/dev/null || true' EXIT
sleep 1

# 6) run CC in interactive-pipe mode (NOT -p: one-shot mode lacks the consume points)
export HOME="$SANDBOX"
export ANTHROPIC_BASE_URL="http://127.0.0.1:$PORT"
export ANTHROPIC_API_KEY=sk-mock-local-probe
export ANTHROPIC_MODEL=claude-sonnet-5-5
export CLAUDE_CODE_SUBAGENT_MODEL=claude-sonnet-5-5
export CLAUDE_CODE_DISABLE_AUTO_MEMORY=false   # "false" => forced_on (value matters!)
export CLAUDE_CODE_PROVIDER_MANAGED_BY_HOST=1
cd "$PROJ"
printf '%s\n/exit\n' "$PROMPT" | timeout 90 "$BIN" --dangerously-skip-permissions 2>"$CAPTURE/cc.err" | tail -2
echo "---- captures ----"
ls "$CAPTURE" | grep -v mock.log

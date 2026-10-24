#!/bin/bash
# 薇萌的 Claude Code 技能自動安裝：把技能與 AI 員工裝到 Claude 身上（~/.claude），
# 不管開哪個專案都能用。任何一步失敗都只印提示，不會擋住對話。
# 用法（雲端環境設定 → Setup script）：
#   curl -fsSL https://raw.githubusercontent.com/JayWu6943/wm-claude-skills/main/install.sh | bash
#
# 雲端的 Setup script 結果會被暫存，不一定每次都重跑，所以這裡另外在 ~/.claude/settings.json
# 掛一個「對話開始時」的同步（wm-skills-sync.sh），每次開新對話都抓一次最新版技能，約 1 秒。
REPO="${WM_SKILLS_REPO:-https://github.com/JayWu6943/wm-claude-skills}"
SYNC="$HOME/.claude/wm-skills-sync.sh"
mkdir -p "$HOME/.claude"

# 1. 同步程式：下載技能庫，把 skills/、agents/ 複製到 ~/.claude
cat > "$SYNC" <<SYNC_EOF
#!/bin/bash
# 由 wm-claude-skills/install.sh 產生：每次開新對話時把最新版技能同步到 ~/.claude
REPO="\${WM_SKILLS_REPO:-$REPO}"
TMP="\$(mktemp -d)"
trap 'rm -rf "\$TMP"' EXIT
if timeout 25 git clone -q --depth 1 "\$REPO" "\$TMP/src" 2>/dev/null; then
  mkdir -p "\$HOME/.claude/skills" "\$HOME/.claude/agents"
  for d in "\$TMP"/src/skills/*/; do
    name="\$(basename "\$d")"
    rm -rf "\$HOME/.claude/skills/\$name"
    cp -r "\$d" "\$HOME/.claude/skills/\$name"
  done
  cp "\$TMP"/src/agents/*.md "\$HOME/.claude/agents/" 2>/dev/null
  chmod +x "\$HOME/.claude/skills/impeccable/scripts/impeccable" 2>/dev/null
  echo "[薇萌技能] 已同步 \$(ls "\$TMP"/src/skills | wc -l) 個技能、\$(ls "\$TMP"/src/agents | wc -l) 位 AI 員工"
else
  echo "[薇萌技能] 這次沒有連上技能庫，先用上次裝好的版本"
fi
exit 0
SYNC_EOF
chmod +x "$SYNC"
bash "$SYNC"

# 2. 在 ~/.claude/settings.json 掛「對話開始時同步」（已經掛過就不重複）
SETTINGS="$HOME/.claude/settings.json" node -e '
const fs = require("fs");
const p = process.env.SETTINGS;
let s = {};
try { s = JSON.parse(fs.readFileSync(p, "utf8")); } catch {}
s.hooks = s.hooks || {};
const list = (s.hooks.SessionStart = s.hooks.SessionStart || []);
const has = list.some((g) => (g.hooks || []).some((h) => String(h.command || "").includes("wm-skills-sync.sh")));
if (!has) {
  list.push({ hooks: [{ type: "command", command: "bash \"$HOME/.claude/wm-skills-sync.sh\"", timeout: 40 }] });
  fs.writeFileSync(p, JSON.stringify(s, null, 2) + "\n");
}
' 2>/dev/null || echo "[薇萌技能] 對話開始時自動同步沒有設定成功，技能仍可使用，只是要等環境重建才會更新"

# 3. impeccable：關掉匿名使用數據回傳
mkdir -p "$HOME/.impeccable"
[ -f "$HOME/.impeccable/config.json" ] || printf '{\n  "telemetry": false\n}\n' > "$HOME/.impeccable/config.json"

# 4. 專案地圖（Trail-code）與程式關係圖（Codebase Memory）的指令
command -v trail >/dev/null 2>&1 || npm install -g @trailhq/trail-code >/dev/null 2>&1 || echo "[薇萌技能] Trail-code 安裝失敗"
export PATH="$HOME/.local/bin:$PATH"
command -v codebase-memory-mcp >/dev/null 2>&1 || \
  curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash >/dev/null 2>&1 || \
  echo "[薇萌技能] Codebase Memory 安裝失敗"
exit 0

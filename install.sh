#!/bin/bash
# 薇萌的 Claude Code 技能自動安裝：每次開雲端對話時執行，把技能與 AI 員工裝到 Claude 身上（~/.claude），
# 不管開哪個專案都能用。任何一步失敗都只印提示，不會擋住對話。
# 用法（雲端環境設定 → Setup script）：
#   curl -fsSL https://raw.githubusercontent.com/JayWu6943/wm-claude-skills/main/install.sh | bash
REPO="${WM_SKILLS_REPO:-https://github.com/JayWu6943/wm-claude-skills}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

if git clone -q --depth 1 "$REPO" "$TMP/src" 2>/dev/null; then
  mkdir -p "$HOME/.claude/skills" "$HOME/.claude/agents"
  for d in "$TMP"/src/skills/*/; do
    name="$(basename "$d")"
    rm -rf "$HOME/.claude/skills/$name"
    cp -r "$d" "$HOME/.claude/skills/$name"
  done
  cp "$TMP"/src/agents/*.md "$HOME/.claude/agents/" 2>/dev/null
  chmod +x "$HOME/.claude/skills/impeccable/scripts/impeccable" 2>/dev/null
  echo "[薇萌技能] 已安裝 $(ls "$TMP"/src/skills | wc -l) 個技能、$(ls "$TMP"/src/agents | wc -l) 位 AI 員工"
else
  echo "[薇萌技能] 下載技能庫失敗，這次對話先用專案裡的技能"
fi

# impeccable：關掉匿名使用數據回傳
mkdir -p "$HOME/.impeccable"
[ -f "$HOME/.impeccable/config.json" ] || printf '{\n  "telemetry": false\n}\n' > "$HOME/.impeccable/config.json"

# 專案地圖（Trail-code）與程式關係圖（Codebase Memory）的指令
command -v trail >/dev/null 2>&1 || npm install -g @trailhq/trail-code >/dev/null 2>&1 || echo "[薇萌技能] Trail-code 安裝失敗"
export PATH="$HOME/.local/bin:$PATH"
command -v codebase-memory-mcp >/dev/null 2>&1 || \
  curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash >/dev/null 2>&1 || \
  echo "[薇萌技能] Codebase Memory 安裝失敗"
exit 0

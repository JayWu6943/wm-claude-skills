# 薇萌 WM Group 的 Claude Code 技能庫

這裡放的是薇萌在 Claude Code 使用的技能（快捷指令）與 AI 員工。雲端對話開始時會自動安裝到 Claude 身上，不管開哪個專案都能用。

**這是公開專案**：只放技能說明檔，不放任何密碼、金鑰、客戶資料或網站程式。

## 自動安裝

在 Claude Code 雲端環境的設定頁（對話視窗上方的環境選單 → Edit → Setup script）貼上：

```bash
#!/bin/bash
curl -fsSL https://raw.githubusercontent.com/JayWu6943/wm-claude-skills/main/install.sh | bash
exit 0
```

`install.sh` 會：

1. 把 `skills/` 的技能裝到 `~/.claude/skills/`，把 `agents/` 的 AI 員工裝到 `~/.claude/agents/`。
2. 關閉 impeccable 的匿名使用數據回傳。
3. 安裝專案地圖（Trail-code）與程式關係圖（Codebase Memory）的指令。
4. 在 `~/.claude/settings.json` 掛一個「對話開始時」的同步（`~/.claude/wm-skills-sync.sh`）。雲端的 Setup script 結果會被暫存，有了這個同步，每次開新對話都會抓最新版技能，約 1 秒。

任何一步失敗都只印提示，不會擋住對話。

## 有哪些

### 中文快捷指令（薇萌自製）

| 指令 | 做什麼 |
| --- | --- |
| `/小工具` | 總選單 |
| `/員工` | 叫 AI 員工幫忙、看名單、加新員工（附 282 位中文名冊） |
| `/找功能` | 用專案地圖找官網某個功能在哪、怎麼運作（只查不改） |
| `/關係圖` | 改東西之前先查會牽動哪些頁面（只查不刪） |
| `/做影片` | 用 OpenMontage 做品牌短片 |
| `/剪影片` | 把自己拍好的影片照後製流程自動剪成直式短片（會分辨引導的人和出鏡的人） |
| `/IG經營` | IG 工具箱 13 個功能：短影音腳本（開頭公式與評分）、爆款研究、貼文、輪播、限動、個人檔案健檢、每週計畫、留言、回覆、私訊、一變多、成效檢討、去 AI 味 |
| `/設計健檢` | 用 impeccable 幫官網或後台某一頁做設計健檢（只看不改，總監說「照改」才動手） |

### 第三方技能

| 技能 | 來源 | 授權 |
| --- | --- | --- |
| `frontend-design` | [anthropics/skills](https://github.com/anthropics/skills) | Apache 2.0（`skills/frontend-design/LICENSE.txt`） |
| `IG經營`（中文化） | [Jakeschincariol/instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill) | MIT（`skills/IG經營/授權.txt`） |
| `impeccable` v4.7.1 | [pbakaus/impeccable](https://github.com/pbakaus/impeccable) | Apache 2.0（`licenses/impeccable-LICENSE`、`licenses/impeccable-NOTICE.md`） |

### AI 員工（`agents/`）

- 7 位改成中文名的員工：IG 經營師、內容企劃師、短影音剪輯教練、介面設計師、SEO 優化師、AI 推薦曝光顧問、網頁體驗診斷師。來自 [msitarzewski/agency-agents](https://github.com/msitarzewski/agency-agents)，MIT 授權（`licenses/agency-agents-LICENSE`）。這裡只改了名字與中文說明。
- 4 位 impeccable 的輔助員工（`impeccable-*.md`）。

## 維護

官網（wm-website）、後台（wm-dashboard）、test 三個專案裡也各有一份同樣的技能。修改技能時，這裡要一起更新，不然新對話會裝到舊版。

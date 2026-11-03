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
5. 把 `CLAUDE.md`（每個新對話的開場規矩：先讀 GitHub 規則、先分類需求並建議員工、等總監決定）同步到 `~/.claude/CLAUDE.md`，每個對話都會讀到。本機那份如果是自己寫的，不會被覆蓋。

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
- AI 系統小組 5 位：產品經理、軟體架構師、專案管理師、測試工程師、上線維運工程師。同樣來自 agency-agents，只改了名字與中文說明。
- 資安 4 位：AI 程式安全檢查員、資深資安維運工程師、密鑰管理工程師、個資保護長。
- 2026-11-03 新增 5 位：品牌策略師、輪播圖文產製師、電子報行銷師、AI 搜尋優化師、社群行銷策略師。同樣來自 agency-agents，只改了名字與中文說明；輪播圖文產製師另外加了「薇萌規定」：只做草稿，不代為發文、不碰任何發文金鑰。
- 2026-11-03 新增 2 位薇萌自己寫的員工：
  - **美術總監**（`design-art-director.md`）：任何畫面（工具、官網、後台、輪播圖）做完先給他看截圖和程式碼，他會照「第一眼看什麼、字、留白、對齊、顏色、手機」逐條挑問題並給可以直接貼上的修改，再打分數。
  - **薇萌戰略顧問**（`wm-strategy-consultant.md`）：商業模式診斷、增長曲線、會員與合夥方案、招商與資本思維。
    **這裡只放乾淨版**——角色、工作方法（四角度檢查、一定要算帳、不當應聲蟲）、回覆格式、紅線、薇萌的公開資料。
    他的戰略框架來自付費課程，教材標示「僅供課堂使用　禁止轉載」，**所以框架、公式、案例數字一律不放這個公開專案**；薇萌的內部營運方針與自評弱點也不放。
    那些內容放在總監本機的 `~/.claude/wm-strategy-consultant-local.md`（不在 `agents/` 裡，所以同步時不會被覆蓋，也不會被當成另一位員工）。
    有補充檔的電腦，他照完整版工作；沒有的（例如雲端對話），他會**在回覆開頭明說「這次讀不到戰略知識庫，沒有套用總監的框架」**，並且不准憑記憶編公式或案例數字。

## 維護

官網（wm-website）、後台（wm-dashboard）、test 三個專案裡也各有一份同樣的技能。修改技能時，這裡要一起更新，不然新對話會裝到舊版。

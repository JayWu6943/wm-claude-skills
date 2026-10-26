---
name: 設計健檢
description: 用設計總監技能（impeccable）幫官網或後台的某一頁做設計健檢：使用體驗、無障礙、手機版、速度，列出問題和改法，總監點頭才改。總監打 /設計健檢、說「幫我看 OO 頁好不好看／好不好用」「上線前檢查一下」時使用。
---

# 設計健檢（impeccable）

總監不懂程式，全程繁體中文白話；不要一直問授權。健檢本身**只看不改**，要改等總監說「照改」。

## 1. 決定要檢查哪裡

- 預設是**官網** `/home/user/wm-website`（沒有就 `git clone https://github.com/JayWu6943/wm-website`）。
- 總監說「後台」就改成 `/home/user/wm-dashboard`（沒有就 clone `JayWu6943/wm-dashboard`）。
- 沒說哪一頁就用 AskUserQuestion 問（header：「哪一頁」），選項依專案給常用的 4 頁：
  - 官網：首頁、形象照服務頁、預約頁、關於薇萌
  - 後台：網站設定、客戶總覽、會員管理、文章管理
- 之後所有動作都在那個專案資料夾裡做；兩個專案都已裝好 impeccable、frontend-design，也都有 PRODUCT.md。

## 2. 健檢（只看不改）

照 `.claude/skills/impeccable/SKILL.md` 的 Setup 跑一次 `impeccable context`，再依序做：

1. **critique**（使用體驗）：讀 `reference/critique.md` 照做。官網是 Persuade 模式、後台是 Operate 模式。
2. **audit**（技術品質：無障礙、手機版、速度）：讀 `reference/audit.md` 照做。
3. **一定要看實際畫面**：電腦版 1440 寬、手機版 390 寬各拍一張。
   - 官網看正式站 https://wmgroup.com.tw 或 PR 的 Vercel 預覽網址。
   - 後台需要登入，拍不到就只看程式，並跟總監說明這點。
   - 雲端環境用 Playwright 開頁面時，Chromium 要加 `--ignore-certificate-errors-spki-list=<本機代理憑證的 SPKI 雜湊>`（只信任這台機器的代理憑證，不是關掉驗證；雜湊用 openssl 從 `/root/.ccr/agent-proxy-ca.crt` 算）。

## 3. 用白話回報

- 先講整體印象（2～3 句），再給分數（impeccable 的評分換成「幾分／滿分幾分」）。
- 問題依嚴重程度排序，最多 8 點。每點寫：在哪一段、為什麼是問題（對客人的影響）、怎麼改、標「小改」或「大改」。
- 最後列「建議先做的 3 件事」，並問總監要不要照改。
- 不要出現 CSS、元件名稱這類術語；必要時用括號解釋。

## 4. 總監說「照改」之後

1. 依問題選 impeccable 對應的指令來改（例如 polish、layout、typeset、clarify、adapt、harden），**改之前讀 `reference/craft-floor.md`**。
2. 先用 `/關係圖` 的做法查會牽動哪些頁面。
3. 遵守各專案 AGENTS.md：官網 `site/` 分支、後台 `app/` 分支；`npm run build` 通過；開 PR 等 Vercel 預覽 Ready。
4. 把預覽網址和改前改後截圖給總監看，總監說「上線」才合併；上線前先備份（推一條 `site/backup-…` 或 `app/backup-…` 分支）。

## 不要做

- 不改 H1、metadata、價格（只能「形象照 3,800 元起」）、財務相關文字、制度承諾句。
- 不新增外部字體、CDN、套件。
- 不編造客戶評價、客戶名稱、數字（PRODUCT.md 的 Evidence 寫得很清楚哪些沒有）。
- 新增的文字、圖片、連結要能在後台 wm-dashboard 更新（AGENTS.md 後台可更新原則）。

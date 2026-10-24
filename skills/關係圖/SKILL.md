---
name: 關係圖
description: 用程式關係圖（Codebase Memory）在改東西之前先查會牽動哪些頁面、找沒在用的程式、看整體架構，只查不改。老闆打 /關係圖、問「改 OO 會不會壞」「會影響哪裡」「有沒有沒在用的程式」時使用。
---

# 關係圖（改之前先查）

老闆不懂程式，用繁體中文白話回答；這個工具**只查、不改、不刪任何東西**。

## 先找到官網專案（不用跟老闆報告這步）

預設查的是薇萌官網（GitHub：JayWu6943/wm-website）。

1. 目前資料夾就是官網（有 `app/(site)/` 和 `.trail/`）的話，直接用。
2. 不是的話，改用 `/home/user/wm-website`。
3. 那裡也沒有，就 `git clone https://github.com/JayWu6943/wm-website /home/user/wm-website`。

之後的指令都在官網資料夾裡執行。老闆明說要查別的專案，就照他說的。

## 準備（不用跟老闆報告這步）

1. 沒有 `codebase-memory-mcp` 指令（也看看 `~/.local/bin/`）就先裝：
   `curl -fsSL https://raw.githubusercontent.com/DeusData/codebase-memory-mcp/main/install.sh | bash`
2. 重建關係圖，2 秒左右：
   `codebase-memory-mcp cli --quiet index_repository --repo-path "$PWD"`
3. 專案名稱是路徑把 `/` 換成 `-`，例如 `/home/user/wm-website` 就是 `home-user-wm-website`。不確定時用 `codebase-memory-mcp cli list_projects` 查。
4. 有 `mcp__codebase-memory-mcp__*` 工具就優先用；沒有就用 `codebase-memory-mcp cli <工具名> --help` 查參數，改用指令列。

## 沒帶文字時（只打 `/關係圖`）

用 AskUserQuestion 問（header：「關係圖」）：「要查什麼？」選項：

1. **改前先查**：要改某個東西，先看會牽動哪些頁面
2. **找沒在用的程式**：列出沒人用到的功能（只列不刪）
3. **看整體架構**：用白話說官網是怎麼組成的

選「改前先查」的話，再用一句話問要改什麼。

## 1. 改前先查

1. **找到它：** 用 `search_graph`（`--query` 或 `--name-pattern`）找出老闆說的東西在程式裡對應的功能。說法要先翻成英文關鍵字。
2. **往回查誰用到它：** 用 `trace_path`，參數 `--direction inbound --depth 3`。
3. **回答（白話）：**
   - 會影響幾個頁面、是哪些頁面（用中文頁名，例如「首頁、形象照服務頁、預約頁」）。
   - **風險：** 低（1～2 頁）、中（3～9 頁）、高（10 頁以上，或牽涉預約、登入、付款、小薇）。
   - **建議做法：** 例如「先在一個頁面試，確認沒問題再全部套用」。
   - 有相關的經驗筆記（`.trail/learnings/`）也要一起提醒。

## 2. 找沒在用的程式

1. **先查候選名單：**
   `query_graph`，查詢語句：`MATCH (f:Function) WHERE NOT EXISTS { (f)<-[:CALLS]-() } RETURN f.name, f.file_path`
2. **排除框架自動呼叫的：** 這些不是沒在用，從名單拿掉：
   - `page.tsx`、`layout.tsx`、`route.ts` 裡的預設輸出，以及 `generateMetadata`、`GET`、`POST`。
   - `actions.ts` 的伺服器動作。
   - `public/` 裡 HTML 用到的函式。
3. **逐一確認剩下的：** 每一個都用 `grep -rn "<名字>"` 搜整個專案確認。
   - 也想想是不是給外部用的，例如 n8n、小薇、LINE 會呼叫的。
   - 登入、Supabase 相關的也可能是套件自動呼叫的。
4. **分兩類列給老闆：**
   - ✅ 確定沒人用，可以刪。
   - ⚠️ 看起來沒用，但其實有用，並說明為什麼不能刪。
5. **最後一句：** 「要刪的話跟我說一聲」。**絕對不要自己刪。**

## 3. 看整體架構

用 `get_architecture`，再用 5～8 行白話說明：
- 有哪些主要頁面。
- 資料存在哪裡。
- 和哪些外部服務相連，例如 Supabase、Sanity、LINE、n8n。

## 不要做

- 不修改、不刪除任何檔案。
- 不把整份圖表或大段程式碼丟給老闆。

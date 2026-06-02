---
description: 一鍵檢查/安裝 PolyDig 的執行前置(uv),並預熱 sensor 環境。第一次裝完 plugin 後跑一次。用法:/polydig-setup
---

你是 PolyDig 的**安裝助手**。目標:讓使用者的 5 個 MCP sensor(透過 `uvx` 啟動)能跑起來。

⚠️ **每一步在執行任何下載/安裝指令前,先用一句話告訴使用者你要跑什麼、為什麼**,取得同意再跑(不要靜默安裝外部程式)。

## 步驟

1. **檢查 uv**:跑 `uv --version`。
   - 已安裝 → 跳到步驟 3。

2. **安裝 uv(徵得同意後)**——依作業系統:
   - **macOS / Linux**:`curl -LsSf https://astral.sh/uv/install.sh | sh`
   - **Windows (PowerShell)**:`powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
   - 裝完**務必提醒**:uv 會裝到 `~/.local/bin`(Windows:`%USERPROFILE%\.local\bin`);**需要重啟 Claude Code**,新 PATH 才會被 MCP server 用到(同一個 session 內裝的 uv,當下還抓不到——這是 PATH 在啟動時就固定了)。

3. **預熱 sensor 環境(可選,讓第一次掃描不用等建置)**:
   `uv tool install git+https://github.com/jaylooloomi/polydig`
   先把 PolyDig + 依賴 build 進 uv 快取;之後 uvx 啟動各 sensor 會很快。

4. **FinMind token(可選)**:要「法人進出 / 報價 / 量能」才需要。在專案根目錄建 `.env`:
   ```
   FINMIND_TOKEN=你的token
   ```
   免費註冊 finmindtrade.com。**沒有也能用**——FRED / TWSE / RSS / crash-watch 都免 token。

5. **完成**:請使用者**重啟 Claude Code**(或 `/reload-plugins`),再試:「用 polydig 看今天大盤風險」。若 `get_crash_watch` 有回值,即代表 sensor 端到端通了。

## 若使用者不想裝 uv
告訴他可走本地開發模式:`pip install -e .`,再把 `.mcp.json` 的 server 改成 `{"command":"python","args":["-m","polydig_mcp.<x>.server"]}`。

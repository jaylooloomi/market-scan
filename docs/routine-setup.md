# 把 PolyDig 掛成 Claude Code Routine(每日自動跑)

PolyDig 可以掛在 Claude Code 的 **Routines**(排程 / API / webhook 觸發)每天自動跑題材掃描。

## ⚠️ 必須用 Local routine,不要用 Remote
Remote routine 跑在雲端,**沒有**你的 `.env`(FinMind token)、本機 Python 套件、也讀不到專案相對路徑 → 會失敗。
PolyDig 依賴本機環境,所以**一定要選 local / 在本機這台跑**。

## 前置(一次性)
1. 套件已安裝:`pip install -e .`(在專案根目錄 `D:\git\harness-run\polydig`)。
2. `.env` 內有 `FINMIND_TOKEN`(沒有的話 FinMind 工具回 graceful error,其餘感測器照常)。
3. 5 個 MCP server 已註冊在 `.mcp.json`,權限已在 `.claude/settings.json` 預核 → 非互動 routine 不會卡權限提示。
4. 確認 `python` 指向裝了 polydig 的直譯器(本機為 `C:\Python314\python.exe`)。若 routine 環境的 `python` 不對,把 `.mcp.json` 的 `"command": "python"` 改成絕對路徑。

## 建立 routine
在 Routines UI 的「What do you want automated?」填(擇一):

**(A) 走 skill / LLM Reviewer(推薦,完整推理)**
> 每天早上掃描 PolyDig 台股題材:用 polydig-daily skill 跑今日掃描(scout → reviewer 因果樹 + 歷史對應 + 分級),把報告存到 reports/ 並摘要重點給我。

或直接用 slash command 當 routine prompt:
> `/dig today`

**(B) 走 headless CLI(最確定、最快,但 Reviewer 是啟發式)**
> 在專案目錄執行 `python -m polydig_mcp.daily_cli --db ./polydig.db`,然後把 reports/latest.md 的內容摘要給我。

- 時間:設 **08:00**(或你要的時間;設計 spec 預設 06:00)。
- 工作目錄(CWD):**專案根目錄** `D:\git\harness-run\polydig`(skill 讀 `themes.json` 相對路徑、`.env` 搜尋都靠這個)。

## 兩條路徑的差別
| | (A) skill / `/dig` | (B) `daily_cli` |
|---|---|---|
| Reviewer 推理 | **LLM**(Claude Code 自己的模型,免 API key) | 啟發式替身(`--mode dry`) |
| 因果樹品質 | 高(真實推理) | 借歷史對應的樹 |
| 確定性 / 速度 | 中(走 subagent) | 高、快 |
| 跨週新聞基線 | 需 skill 內呼叫帶 db | `--db` 自動啟用 |

> 想要「LLM 推理 + 跨週基線 + 落地」兼得:用 (A) 並在 routine prompt 內要求帶 `--db ./polydig.db` 落地,或先跑 (B) 落地再讓 (A) 解讀。

## 報告交付
- 每次跑會寫 `reports/YYYY-MM-DD.md` + 穩定路徑 `reports/latest.md`。
- 若要保留歷史 / 推到 GitHub,在 routine prompt 末尾加一句:
  > 最後執行 `git add reports/ && git commit -m "daily report $(date +%F)"`(本機 routine 才有 git）。

## 跨週基線會「越跑越準」
`--db ./polydig.db` 會每天把新聞詞頻落地。前幾天沒有基線(視為新發生),累積 ~3 週後,新聞異常偵測就能算出「跨週突起」而非只看當天 —— 這對「事件還沒發酵」的領先判斷很關鍵。

## 注意
- 不要同時用本檔的 routine 和 `python -m polydig_mcp.scheduler`(那是 OS-cron/APScheduler 的另一條路),擇一即可。
- routine 是無人值守:任何感測器失敗都會 graceful 跳過、報告照常產出(不會中斷)。

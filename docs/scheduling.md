# Market Scan Scheduling

The scheduler runs the daily pipeline at **06:00 Asia/Taipei**.

## Python scheduler (cross-platform)

```bash
pip install "market-scan[schedule]"
python -m market_scan_mcp.scheduler --mode dry --output reports
```

Options:
- `--mode dry|llm` — reviewer mode (llm requires `ANTHROPIC_API_KEY`)
- `--output <dir>` — where to write daily markdown reports
- `--persist <dir>` — Chroma vector DB persist dir (enables semantic RAG)
- `--db <path>` — SQLite db path for signal/verdict persistence

## Linux / macOS cron

```
# crontab -e
0 6 * * * cd /path/to/market-scan && /path/to/.venv/bin/python -m market_scan_mcp.scheduler --mode dry >> logs/scheduler.log 2>&1
```

Or run once per invocation (simpler, no daemon):

```
0 6 * * * cd /path/to/market-scan && /path/to/.venv/bin/market-scan-daily --mode dry >> logs/daily.log 2>&1
```

## Windows Task Scheduler (one-liner)

```powershell
schtasks /Create /SC DAILY /TN "MarketScanDaily" /TR "C:\Python314\python.exe -m market_scan_mcp.scheduler --mode dry" /ST 06:00 /F
```

Or using the CLI directly:

```powershell
schtasks /Create /SC DAILY /TN "MarketScanDaily" /TR "C:\path\to\.venv\Scripts\market-scan-daily.exe --mode dry" /ST 06:00 /F
```

To verify the task was created:

```powershell
schtasks /Query /TN "MarketScanDaily"
```

To delete it:

```powershell
schtasks /Delete /TN "MarketScanDaily" /F
```

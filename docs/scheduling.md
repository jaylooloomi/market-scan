# PolyDig Scheduling

The scheduler runs the daily pipeline at **06:00 Asia/Taipei**.

## Python scheduler (cross-platform)

```bash
pip install "polydig[schedule]"
python -m polydig_mcp.scheduler --mode dry --output reports
```

Options:
- `--mode dry|llm` — reviewer mode (llm requires `ANTHROPIC_API_KEY`)
- `--output <dir>` — where to write daily markdown reports
- `--persist <dir>` — Chroma vector DB persist dir (enables semantic RAG)
- `--db <path>` — SQLite db path for signal/verdict persistence

## Linux / macOS cron

```
# crontab -e
0 6 * * * cd /path/to/polydig && /path/to/.venv/bin/python -m polydig_mcp.scheduler --mode dry >> logs/scheduler.log 2>&1
```

Or run once per invocation (simpler, no daemon):

```
0 6 * * * cd /path/to/polydig && /path/to/.venv/bin/polydig-daily --mode dry >> logs/daily.log 2>&1
```

## Windows Task Scheduler (one-liner)

```powershell
schtasks /Create /SC DAILY /TN "PolyDigDaily" /TR "C:\Python314\python.exe -m polydig_mcp.scheduler --mode dry" /ST 06:00 /F
```

Or using the CLI directly:

```powershell
schtasks /Create /SC DAILY /TN "PolyDigDaily" /TR "C:\path\to\.venv\Scripts\polydig-daily.exe --mode dry" /ST 06:00 /F
```

To verify the task was created:

```powershell
schtasks /Query /TN "PolyDigDaily"
```

To delete it:

```powershell
schtasks /Delete /TN "PolyDigDaily" /F
```

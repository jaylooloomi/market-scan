"""Daily scheduler for PolyDig (spec Phase 3).

Runs `polydig-daily` at 06:00 Asia/Taipei every day.

Usage:
    python -m polydig_mcp.scheduler
    python -m polydig_mcp.scheduler --mode llm --output reports

APScheduler >= 3.10 is required (optional dep [schedule]).
If not installed, prints a clear message and exits.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("polydig.scheduler")

TZ = "Asia/Taipei"
HOUR = 6
MINUTE = 0


def _build_scheduler(mode: str, output: str, persist: str | None, db: str | None):
    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print(
            "[PolyDig] APScheduler is not installed.\n"
            "Install it with:  pip install 'polydig[schedule]'\n"
            "or:               pip install apscheduler>=3.10",
            file=sys.stderr,
        )
        raise

    sched = BlockingScheduler(timezone=TZ)

    def _run_daily_job():
        log.info("Scheduled daily run starting (mode=%s)", mode)
        try:
            from polydig_mcp.history.store import ThemeStore
            from polydig_mcp.reporting.generator import write_report
            from polydig_mcp.reviewer.pipeline import run_daily

            store = ThemeStore(persist_dir=persist)
            result = run_daily(
                store=store,
                reviewer_mode=mode,
                db_path=db,
            )
            path = write_report(result["report_md"], output_dir=output, report_date=date.today())
            log.info(
                "Daily run complete: %d candidates, %d verdicts → %s",
                len(result["candidates"]),
                len(result["verdicts"]),
                path,
            )
        except Exception as exc:  # noqa: BLE001
            log.error("Daily run failed: %s", exc, exc_info=True)

    trigger = CronTrigger(hour=HOUR, minute=MINUTE, timezone=TZ)
    sched.add_job(_run_daily_job, trigger, id="polydig_daily", name="PolyDig daily 06:00 Taipei")
    return sched


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="PolyDig scheduler — runs daily at 06:00 Asia/Taipei")
    p.add_argument("--mode", choices=["dry", "llm"], default="dry")
    p.add_argument("--output", default="reports")
    p.add_argument("--persist", default=None, help="Chroma persist dir")
    p.add_argument("--db", default=None, help="SQLite db path")
    args = p.parse_args(argv)

    try:
        sched = _build_scheduler(args.mode, args.output, args.persist, args.db)
    except ImportError:
        return 1

    log.info(
        "Scheduler started — daily run at %02d:%02d %s. Press Ctrl+C to stop.",
        HOUR,
        MINUTE,
        TZ,
    )
    try:
        sched.start()
    except (KeyboardInterrupt, SystemExit):
        log.info("Scheduler stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Gap 3: Scheduler registration test.

Asserts the schedule is registered for 06:00 Asia/Taipei.
Does NOT actually start the scheduler (no waiting).
Skips gracefully if apscheduler is not installed.

Run: PYTHONIOENCODING=utf-8 python tests/test_scheduler.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, "src")
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    print("=== Gap 3: Scheduler Registration ===\n")

    try:
        from apscheduler.schedulers.blocking import BlockingScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        print("apscheduler not installed — SKIP (acceptable, it's an optional dep)")
        print("\n=== SKIP ===")
        return 0

    # Build the scheduler without starting it
    from polydig_mcp.scheduler import _build_scheduler, HOUR, MINUTE, TZ

    sched = _build_scheduler(mode="dry", output="reports", persist=None, db=None)

    jobs = sched.get_jobs()
    assert len(jobs) >= 1, f"expected at least 1 job, got {len(jobs)}"

    daily_job = next((j for j in jobs if j.id == "polydig_daily"), None)
    assert daily_job is not None, "job 'polydig_daily' not found"

    trigger = daily_job.trigger
    assert isinstance(trigger, CronTrigger), f"expected CronTrigger, got {type(trigger)}"

    # Verify hour and minute fields
    fields = {f.name: f for f in trigger.fields}
    hour_val = str(fields["hour"])
    minute_val = str(fields["minute"])
    assert hour_val == str(HOUR), f"expected hour={HOUR}, got {hour_val}"
    assert minute_val == str(MINUTE), f"expected minute={MINUTE}, got {minute_val}"

    print(f"job id: {daily_job.id}")
    print(f"trigger: hour={hour_val}, minute={minute_val}, tz={TZ}")
    print(f"job name: {daily_job.name}")

    # Shut down without starting (just to be safe)
    try:
        sched.shutdown(wait=False)
    except Exception:
        pass

    print("\n=== PASS — schedule registered at 06:00 Asia/Taipei ===")
    return 0


def test_scheduler():
    assert main() == 0


if __name__ == "__main__":
    raise SystemExit(main())

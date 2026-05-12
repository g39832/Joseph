"""
scheduler/scheduler_manager.py
--------------------------------
Task scheduling and reminders for JOSEPH using APScheduler.

Handles:
- One-time reminders ("remind me at 3pm to call John")
- Recurring tasks ("every morning at 9am, give me a briefing")
- Daily briefing job
- Persistent jobs (survive restarts via SQLite job store)

The scheduler runs on a background thread and calls
a callback when a job fires — Joseph speaks the reminder aloud.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from configs.settings import settings

logger = logging.getLogger(__name__)


class SchedulerManager:
    """
    Manages all scheduled tasks and reminders for JOSEPH.

    Jobs persist between restarts via SQLite.
    When a job fires, it calls the on_reminder callback
    which speaks the reminder aloud via TTS.

    Usage:
        def speak_reminder(message):
            tts.speak(message)

        scheduler = SchedulerManager(on_reminder=speak_reminder)
        scheduler.start()
        scheduler.add_reminder("Call John", at_time="15:00")
        scheduler.add_daily_briefing(hour=9, minute=0)
    """

    def __init__(self, on_reminder: Optional[Callable] = None):
        self.on_reminder = on_reminder or (lambda msg: logger.info(f"REMINDER: {msg}"))
        self._scheduler: Optional[BackgroundScheduler] = None
        self._available = False
        self._jobs_db = settings.DATA_DIR / "scheduler_jobs.db"
        self._initialize()

    def _initialize(self) -> None:
        """Set up APScheduler with SQLite job store."""
        try:
            settings.DATA_DIR.mkdir(parents=True, exist_ok=True)

            jobstores = {
                "default": SQLAlchemyJobStore(
                    url=f"sqlite:///{self._jobs_db}"
                )
            }
            executors = {
                "default": ThreadPoolExecutor(max_workers=4)
            }
            job_defaults = {
                "coalesce": True,       # Merge missed jobs into one
                "max_instances": 1,     # Only one instance per job
                "misfire_grace_time": 60,  # 60s grace for missed jobs
            }

            self._scheduler = BackgroundScheduler(
                jobstores=jobstores,
                executors=executors,
                job_defaults=job_defaults,
            )
            self._available = True
            logger.info("SchedulerManager initialized")

        except Exception as e:
            logger.error(f"Scheduler init failed: {e}")
            self._available = False

    def start(self) -> bool:
        """Start the scheduler background thread."""
        if not self._available or not self._scheduler:
            return False
        try:
            if not self._scheduler.running:
                self._scheduler.start()
                logger.info("Scheduler started")
            return True
        except Exception as e:
            logger.error(f"Scheduler start failed: {e}")
            return False

    def stop(self) -> None:
        """Stop the scheduler cleanly."""
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    # ------------------------------------------------------------------ #
    # Adding Jobs
    # ------------------------------------------------------------------ #

    def add_reminder(
        self,
        message: str,
        at_time: Optional[str] = None,
        in_minutes: Optional[int] = None,
        in_hours: Optional[float] = None,
        job_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add a one-time reminder.

        Args:
            message: What to say when the reminder fires.
            at_time: Time string like "15:00" or "3:30pm".
            in_minutes: Fire in N minutes from now.
            in_hours: Fire in N hours from now.
            job_id: Optional custom job ID.

        Returns:
            Job ID string, or None if failed.
        """
        if not self._available:
            return None

        try:
            run_time = self._parse_time(at_time, in_minutes, in_hours)
            if not run_time:
                logger.error("Could not determine reminder time")
                return None

            jid = job_id or f"reminder_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            self._scheduler.add_job(
                func=self._fire_reminder,
                trigger=DateTrigger(run_date=run_time),
                args=[message],
                id=jid,
                name=f"Reminder: {message[:30]}",
                replace_existing=True,
            )

            logger.info(f"Reminder set: '{message}' at {run_time.strftime('%H:%M')}")
            return jid

        except Exception as e:
            logger.error(f"Add reminder failed: {e}")
            return None

    def add_recurring(
        self,
        message: str,
        hour: int,
        minute: int = 0,
        days: str = "mon-sun",
        job_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Add a recurring daily reminder.

        Args:
            message: What to say.
            hour: Hour (0-23).
            minute: Minute (0-59).
            days: Day pattern like "mon-fri" or "mon,wed,fri" or "mon-sun".
            job_id: Optional custom job ID.

        Returns:
            Job ID string, or None if failed.
        """
        if not self._available:
            return None

        try:
            jid = job_id or f"recurring_{hour:02d}{minute:02d}"

            self._scheduler.add_job(
                func=self._fire_reminder,
                trigger=CronTrigger(
                    hour=hour,
                    minute=minute,
                    day_of_week=days,
                ),
                args=[message],
                id=jid,
                name=f"Recurring: {message[:30]}",
                replace_existing=True,
            )

            logger.info(f"Recurring job set: '{message}' at {hour:02d}:{minute:02d} ({days})")
            return jid

        except Exception as e:
            logger.error(f"Add recurring failed: {e}")
            return None

    def add_daily_briefing(
        self,
        hour: int = 9,
        minute: int = 0,
        briefing_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """
        Schedule a daily morning briefing.

        Args:
            hour: Hour to deliver briefing (default 9am).
            minute: Minute (default 0).
            briefing_callback: Function that generates the briefing text.

        Returns:
            Job ID string.
        """
        if not self._available:
            return None

        callback = briefing_callback or self._default_briefing

        try:
            self._scheduler.add_job(
                func=callback,
                trigger=CronTrigger(hour=hour, minute=minute),
                id="daily_briefing",
                name="Daily Briefing",
                replace_existing=True,
            )
            logger.info(f"Daily briefing scheduled at {hour:02d}:{minute:02d}")
            return "daily_briefing"

        except Exception as e:
            logger.error(f"Daily briefing setup failed: {e}")
            return None

    def remove_job(self, job_id: str) -> bool:
        """Remove a scheduled job by ID."""
        if not self._available:
            return False
        try:
            self._scheduler.remove_job(job_id)
            logger.info(f"Job removed: {job_id}")
            return True
        except Exception as e:
            logger.warning(f"Remove job failed: {e}")
            return False

    def get_jobs(self) -> list[dict]:
        """Return all scheduled jobs as a list of dicts."""
        if not self._available or not self._scheduler:
            return []
        jobs = []
        for job in self._scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": next_run.strftime("%Y-%m-%d %H:%M") if next_run else "N/A",
            })
        return jobs

    def format_jobs(self) -> str:
        """Return a human-readable list of scheduled jobs."""
        jobs = self.get_jobs()
        if not jobs:
            return "No scheduled reminders."
        lines = ["Scheduled reminders:"]
        for job in jobs:
            lines.append(f"  • {job['name']} — next: {job['next_run']}")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Internal
    # ------------------------------------------------------------------ #

    def _fire_reminder(self, message: str) -> None:
        """Called when a reminder fires."""
        logger.info(f"Reminder fired: {message}")
        try:
            self.on_reminder(message)
        except Exception as e:
            logger.error(f"Reminder callback error: {e}")

    def _default_briefing(self) -> None:
        """Default briefing — just announces the time."""
        now = datetime.now()
        msg = f"Good morning. It's {now.strftime('%I:%M %p')}. Ready when you are."
        self._fire_reminder(msg)

    def _parse_time(
        self,
        at_time: Optional[str],
        in_minutes: Optional[int],
        in_hours: Optional[float],
    ) -> Optional[datetime]:
        """Parse various time formats into a datetime."""
        now = datetime.now()

        if in_minutes is not None:
            return now + timedelta(minutes=in_minutes)

        if in_hours is not None:
            return now + timedelta(hours=in_hours)

        if at_time:
            # Try parsing "15:00", "3:30pm", "3pm", etc.
            formats = ["%H:%M", "%I:%M%p", "%I%p", "%I:%M %p", "%I %p"]
            at_time_clean = at_time.strip().upper().replace(" ", "")
            for fmt in formats:
                try:
                    parsed = datetime.strptime(at_time_clean, fmt.upper())
                    run_time = now.replace(
                        hour=parsed.hour,
                        minute=parsed.minute,
                        second=0,
                        microsecond=0,
                    )
                    # If time already passed today, schedule for tomorrow
                    if run_time <= now:
                        run_time += timedelta(days=1)
                    return run_time
                except ValueError:
                    continue

        return None

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._scheduler is not None and self._scheduler.running

    def __repr__(self) -> str:
        jobs = len(self.get_jobs())
        return f"SchedulerManager(running={self.is_running}, jobs={jobs})"

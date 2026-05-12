"""
brain/proactive.py
-------------------
Proactive behavior system for JOSEPH.

Joseph monitors patterns and surfaces suggestions
without being asked. This makes him feel genuinely intelligent
rather than just reactive.

Proactive behaviors:
- Screen time alerts ("You've been working for 2 hours, take a break")
- Reminder about upcoming tasks ("You have a meeting in 30 minutes")
- Pattern detection ("You usually check emails around now")
- Idle suggestions ("You haven't used Joseph in a while — need anything?")
- Weather alerts ("It's going to rain today, heads up")
- Task nudges ("You have 3 high-priority tasks pending")

Runs on a background thread, checks conditions every few minutes.
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Callable, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

# How often to check proactive conditions (seconds)
CHECK_INTERVAL = 300  # 5 minutes

# Screen time alert threshold (minutes)
SCREEN_TIME_ALERT_MINUTES = 90


class ProactiveEngine:
    """
    Monitors usage patterns and surfaces proactive suggestions.

    Usage:
        engine = ProactiveEngine(on_suggestion=lambda msg: tts.speak(msg))
        engine.attach_services(notes=notes, weather=weather, scheduler=scheduler)
        engine.start()
    """

    def __init__(self, on_suggestion: Optional[Callable] = None):
        self.on_suggestion = on_suggestion
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._session_start = datetime.now()
        self._last_screen_time_alert = None
        self._last_task_nudge = None
        self._last_weather_alert = None
        self._suggestions_given: list[str] = []

        # Services (injected)
        self.notes = None
        self.weather = None
        self.scheduler = None
        self.memory = None

    def attach_services(self, **kwargs) -> None:
        """Attach services for proactive monitoring."""
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def start(self) -> None:
        """Start the proactive monitoring loop."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="Proactive-Engine",
        )
        self._thread.start()
        logger.info("Proactive engine started")

    def stop(self) -> None:
        """Stop the proactive monitoring loop."""
        self._running = False

    def _monitor_loop(self) -> None:
        """Main monitoring loop — runs every CHECK_INTERVAL seconds."""
        # Wait a bit before first check so startup isn't noisy
        time.sleep(60)

        while self._running:
            try:
                self._check_all_conditions()
            except Exception as e:
                logger.debug(f"Proactive check error: {e}")

            time.sleep(CHECK_INTERVAL)

    def _check_all_conditions(self) -> None:
        """Check all proactive conditions."""
        now = datetime.now()

        # Screen time alert
        self._check_screen_time(now)

        # Pending high-priority tasks
        self._check_pending_tasks(now)

        # Upcoming reminders
        self._check_upcoming_reminders(now)

        # Weather alert (morning only)
        self._check_weather_alert(now)

    def _check_screen_time(self, now: datetime) -> None:
        """Alert if user has been working too long."""
        session_minutes = (now - self._session_start).seconds // 60

        if session_minutes < SCREEN_TIME_ALERT_MINUTES:
            return

        # Only alert once per hour
        if (self._last_screen_time_alert and
                (now - self._last_screen_time_alert).seconds < 3600):
            return

        hours = session_minutes // 60
        mins = session_minutes % 60
        duration = f"{hours}h {mins}m" if hours > 0 else f"{mins} minutes"

        suggestion = (
            f"You've been working for {duration}. "
            "Consider taking a short break — it helps with focus."
        )

        self._surface_suggestion("screen_time", suggestion)
        self._last_screen_time_alert = now

    def _check_pending_tasks(self, now: datetime) -> None:
        """Nudge about high-priority pending tasks."""
        if not self.notes:
            return

        # Only nudge once per 2 hours
        if (self._last_task_nudge and
                (now - self._last_task_nudge).seconds < 7200):
            return

        # Only nudge in working hours (9am-6pm)
        if not (9 <= now.hour <= 18):
            return

        try:
            tasks = self.notes.get_pending_tasks(limit=20)
            high_priority = [t for t in tasks if t.get("priority") == 1]

            if len(high_priority) >= 2:
                suggestion = (
                    f"You have {len(high_priority)} high-priority tasks pending. "
                    f"The most urgent: {high_priority[0]['title']}"
                )
                self._surface_suggestion("tasks", suggestion)
                self._last_task_nudge = now

        except Exception as e:
            logger.debug(f"Task check error: {e}")

    def _check_upcoming_reminders(self, now: datetime) -> None:
        """Alert about reminders coming up in the next 10 minutes."""
        if not self.scheduler:
            return

        try:
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                next_run = job.get("next_run", "N/A")
                if next_run == "N/A":
                    continue

                try:
                    next_dt = datetime.strptime(next_run, "%Y-%m-%d %H:%M")
                    minutes_until = (next_dt - now).seconds // 60

                    if 0 < minutes_until <= 10:
                        name = job.get("name", "Reminder").replace("Reminder: ", "")
                        suggestion = f"Heads up — {name} in {minutes_until} minutes."
                        key = f"reminder_{job.get('id', '')}"
                        self._surface_suggestion(key, suggestion)

                except Exception:
                    pass

        except Exception as e:
            logger.debug(f"Reminder check error: {e}")

    def _check_weather_alert(self, now: datetime) -> None:
        """Surface weather alerts in the morning."""
        if not self.weather:
            return

        # Only in morning (7-10am)
        if not (7 <= now.hour <= 10):
            return

        # Only once per day
        today = now.date()
        if (self._last_weather_alert and
                self._last_weather_alert.date() == today):
            return

        try:
            weather = self.weather.get_weather()
            if not weather:
                return

            alerts = []

            if weather.get("precip_chance", 0) > 60:
                alerts.append(f"{weather['precip_chance']}% chance of rain today")

            if weather.get("temp_f", 70) < 32:
                alerts.append("freezing temperatures today")
            elif weather.get("temp_f", 70) > 95:
                alerts.append("very hot today")

            if weather.get("wind_mph", 0) > 25:
                alerts.append(f"strong winds ({weather['wind_mph']} mph)")

            if alerts:
                suggestion = (
                    f"Weather heads up: {', '.join(alerts)}. "
                    f"Currently {weather['temp_f']}°F."
                )
                self._surface_suggestion("weather", suggestion)
                self._last_weather_alert = now

        except Exception as e:
            logger.debug(f"Weather alert error: {e}")

    def _surface_suggestion(self, key: str, message: str) -> None:
        """
        Surface a suggestion to the user.
        Avoids repeating the same suggestion.
        """
        if key in self._suggestions_given:
            return

        self._suggestions_given.append(key)
        logger.info(f"Proactive suggestion [{key}]: {message[:60]}")

        if self.on_suggestion:
            try:
                self.on_suggestion(message)
            except Exception as e:
                logger.debug(f"Suggestion callback error: {e}")

    def trigger_manual_check(self) -> list[str]:
        """
        Manually trigger all checks and return any suggestions.
        Used for testing or on-demand proactive check.
        """
        suggestions = []
        original_callback = self.on_suggestion

        def collect(msg):
            suggestions.append(msg)

        self.on_suggestion = collect
        self._check_all_conditions()
        self.on_suggestion = original_callback
        return suggestions

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return f"ProactiveEngine(running={self._running})"


# Module-level singleton
proactive_engine = ProactiveEngine()

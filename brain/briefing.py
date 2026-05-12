"""
brain/briefing.py
------------------
Daily briefing system for JOSEPH.

Generates a personalized morning briefing that includes:
- Greeting based on time of day
- Current weather
- Pending tasks summary
- Scheduled reminders for today
- Memory of what was discussed recently

Joseph speaks this aloud at a scheduled time each morning,
or on demand when you say "give me a briefing".
"""

import logging
from datetime import datetime
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class BriefingSystem:
    """
    Generates and delivers daily briefings.

    Usage:
        briefing = BriefingSystem(
            weather_service=weather,
            notes_manager=notes,
            scheduler=scheduler,
            memory_manager=memory,
            tts=tts,
        )
        text = briefing.generate()
        briefing.deliver()  # Speaks it aloud
    """

    def __init__(
        self,
        weather_service=None,
        notes_manager=None,
        scheduler=None,
        memory_manager=None,
        tts=None,
    ):
        self.weather = weather_service
        self.notes = notes_manager
        self.scheduler = scheduler
        self.memory = memory_manager
        self.tts = tts

    def generate(self, include_weather: bool = True) -> str:
        """
        Generate the full briefing text.

        Returns:
            Briefing as a natural language string.
        """
        now = datetime.now()
        sections = []

        # Greeting
        hour = now.hour
        if 5 <= hour < 12:
            greeting = f"Good morning, {settings.USER_NAME}."
        elif 12 <= hour < 17:
            greeting = f"Good afternoon, {settings.USER_NAME}."
        elif 17 <= hour < 21:
            greeting = f"Good evening, {settings.USER_NAME}."
        else:
            greeting = f"Hey {settings.USER_NAME}."

        sections.append(
            f"{greeting} It's {now.strftime('%A, %B %d')} at {now.strftime('%I:%M %p')}."
        )

        # Weather
        if include_weather and self.weather:
            try:
                weather_text = self.weather.get_briefing_weather()
                if weather_text:
                    sections.append(weather_text)
            except Exception as e:
                logger.debug(f"Weather in briefing failed: {e}")

        # Tasks
        if self.notes:
            try:
                task_summary = self.notes.get_task_summary()
                if task_summary and task_summary != "No pending tasks.":
                    sections.append(task_summary)
            except Exception as e:
                logger.debug(f"Tasks in briefing failed: {e}")

        # Scheduled reminders today
        if self.scheduler:
            try:
                jobs = self.scheduler.get_jobs()
                today_jobs = []
                for job in jobs:
                    if job["next_run"] != "N/A":
                        next_run_date = job["next_run"][:10]
                        if next_run_date == now.strftime("%Y-%m-%d"):
                            # Extract time from "YYYY-MM-DD HH:MM"
                            time_str = job["next_run"][11:]
                            today_jobs.append(
                                f"{job['name'].replace('Reminder: ', '')} at {time_str}"
                            )
                if today_jobs:
                    reminders_text = "Today's reminders: " + ", ".join(today_jobs) + "."
                    sections.append(reminders_text)
            except Exception as e:
                logger.debug(f"Reminders in briefing failed: {e}")

        # Closing
        sections.append("What would you like to work on?")

        briefing = " ".join(sections)
        logger.info(f"Briefing generated ({len(briefing)} chars)")
        return briefing

    def deliver(self, include_weather: bool = True) -> str:
        """
        Generate and speak the briefing aloud.

        Returns:
            The briefing text.
        """
        text = self.generate(include_weather=include_weather)

        if self.tts:
            try:
                self.tts.speak(text)
            except Exception as e:
                logger.error(f"Briefing TTS error: {e}")

        return text

    def get_quick_status(self) -> str:
        """
        One-line status for the sidebar.
        """
        now = datetime.now()
        parts = [now.strftime("%H:%M")]

        if self.notes:
            try:
                stats = self.notes.get_stats()
                if stats["pending_tasks"] > 0:
                    parts.append(f"{stats['pending_tasks']} tasks")
            except Exception:
                pass

        return " · ".join(parts)

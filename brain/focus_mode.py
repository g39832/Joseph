"""
brain/focus_mode.py
--------------------
Focus Mode for JOSEPH.

"Start focus mode for 45 minutes" triggers:
1. Plays focus music on YouTube (or Spotify if configured)
2. Sets a timer for the specified duration
3. Blocks distracting sites (optional, via hosts file — requires admin)
4. Tracks focus sessions in SQLite
5. Sends break reminder when time is up
6. Gives productivity report at end of session

Focus sessions are logged so Joseph can track your productivity
over time and give you weekly summaries.
"""

import logging
import sqlite3
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.DATA_DIR / "focus_sessions.db"

# Default focus music queries
FOCUS_MUSIC = {
    "lofi": "lofi hip hop radio beats to study to",
    "classical": "classical music for studying",
    "ambient": "ambient focus music",
    "jazz": "jazz for studying",
    "nature": "nature sounds for focus",
    "default": "lofi hip hop radio beats to study to",
}

# Distracting sites to block (optional feature)
DISTRACTING_SITES = [
    "reddit.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "youtube.com",  # Only blocked if not using for music
]


class FocusSession:
    """Represents a single focus session."""

    def __init__(self, duration_minutes: int, music_type: str = "lofi"):
        self.duration_minutes = duration_minutes
        self.music_type = music_type
        self.start_time = datetime.now()
        self.end_time = self.start_time + timedelta(minutes=duration_minutes)
        self.completed = False
        self.interrupted = False
        self.actual_duration = 0

    def time_remaining(self) -> int:
        """Minutes remaining in session."""
        remaining = (self.end_time - datetime.now()).seconds // 60
        return max(0, remaining)

    def is_active(self) -> bool:
        return datetime.now() < self.end_time and not self.interrupted


class FocusMode:
    """
    Manages focus sessions for JOSEPH.

    Usage:
        focus = FocusMode(
            on_break=lambda: tts.speak("Time for a break!"),
            scheduler=scheduler,
        )
        focus.start(duration_minutes=45, music_type="lofi")
        focus.stop()
    """

    def __init__(
        self,
        on_break: Optional[Callable] = None,
        on_start: Optional[Callable] = None,
        scheduler=None,
        spotify=None,
        browser=None,
    ):
        self.on_break = on_break
        self.on_start = on_start
        self.scheduler = scheduler
        self.spotify = spotify
        self.browser = browser

        self._current_session: Optional[FocusSession] = None
        self._timer_thread: Optional[threading.Thread] = None
        self._init_db()

    def _init_db(self) -> None:
        """Initialize focus sessions database."""
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS focus_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    duration_planned INTEGER,
                    duration_actual INTEGER,
                    music_type TEXT,
                    completed INTEGER DEFAULT 0,
                    interrupted INTEGER DEFAULT 0,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ended_at TIMESTAMP
                )
            """)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def start(
        self,
        duration_minutes: int = 25,
        music_type: str = "lofi",
        play_music: bool = True,
    ) -> str:
        """
        Start a focus session.

        Args:
            duration_minutes: How long to focus (default 25 = Pomodoro).
            music_type: Type of focus music (lofi/classical/ambient/jazz/nature).
            play_music: Whether to play music automatically.

        Returns:
            Status message.
        """
        if self._current_session and self._current_session.is_active():
            remaining = self._current_session.time_remaining()
            return f"Focus session already active — {remaining} minutes remaining."

        self._current_session = FocusSession(duration_minutes, music_type)

        # Play focus music
        music_msg = ""
        if play_music:
            music_msg = self._start_music(music_type)

        # Schedule break reminder
        if self.scheduler:
            self.scheduler.add_reminder(
                f"Focus session complete! You focused for {duration_minutes} minutes.",
                in_minutes=duration_minutes,
                job_id="focus_break",
            )

        # Start background timer
        self._timer_thread = threading.Thread(
            target=self._session_timer,
            args=(duration_minutes,),
            daemon=True,
        )
        self._timer_thread.start()

        # Log session start
        self._log_session_start()

        if self.on_start:
            self.on_start(duration_minutes)

        response = f"Focus mode started — {duration_minutes} minutes. "
        if music_msg:
            response += music_msg
        response += " I'll remind you when it's time for a break."

        logger.info(f"Focus session started: {duration_minutes} minutes")
        return response

    def stop(self) -> str:
        """Stop the current focus session early."""
        if not self._current_session or not self._current_session.is_active():
            return "No active focus session."

        elapsed = int((datetime.now() - self._current_session.start_time).seconds / 60)
        self._current_session.interrupted = True
        self._current_session.actual_duration = elapsed
        self._log_session_end(completed=False)

        # Cancel break reminder
        if self.scheduler:
            try:
                self.scheduler.remove_job("focus_break")
            except Exception:
                pass

        logger.info(f"Focus session stopped after {elapsed} minutes")
        return f"Focus session ended. You focused for {elapsed} minutes."

    def status(self) -> str:
        """Get current focus session status."""
        if not self._current_session or not self._current_session.is_active():
            stats = self.get_today_stats()
            if stats["sessions_today"] > 0:
                return (
                    f"No active session. Today: {stats['sessions_today']} session(s), "
                    f"{stats['total_minutes_today']} minutes focused."
                )
            return "No active focus session."

        remaining = self._current_session.time_remaining()
        elapsed = int((datetime.now() - self._current_session.start_time).seconds / 60)
        return (
            f"Focus mode active — {remaining} minutes remaining "
            f"({elapsed} minutes elapsed)."
        )

    def _start_music(self, music_type: str) -> str:
        """Start focus music via Spotify or YouTube."""
        query = FOCUS_MUSIC.get(music_type, FOCUS_MUSIC["default"])

        # Try Spotify first
        if self.spotify and self.spotify.is_available:
            result = self.spotify.play(query)
            return f"Playing {music_type} music on Spotify."

        # Fall back to YouTube
        if self.browser:
            try:
                import asyncio
                loop = asyncio.new_event_loop()
                loop.run_until_complete(self.browser.play_youtube(query))
                loop.close()
                return f"Playing {music_type} music on YouTube."
            except Exception as e:
                logger.debug(f"YouTube music error: {e}")

        return ""

    def _session_timer(self, duration_minutes: int) -> None:
        """Background timer that fires when session ends."""
        time.sleep(duration_minutes * 60)

        if self._current_session and not self._current_session.interrupted:
            self._current_session.completed = True
            self._current_session.actual_duration = duration_minutes
            self._log_session_end(completed=True)

            if self.on_break:
                self.on_break(
                    f"Focus session complete! You focused for {duration_minutes} minutes. "
                    "Time for a well-deserved break."
                )

    def _log_session_start(self) -> None:
        """Log session start to database."""
        if not self._current_session:
            return
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO focus_sessions (duration_planned, music_type)
                   VALUES (?, ?)""",
                (self._current_session.duration_minutes, self._current_session.music_type),
            )

    def _log_session_end(self, completed: bool) -> None:
        """Log session end to database."""
        with self._conn() as conn:
            conn.execute(
                """UPDATE focus_sessions
                   SET duration_actual=?, completed=?, interrupted=?, ended_at=CURRENT_TIMESTAMP
                   WHERE id=(SELECT MAX(id) FROM focus_sessions)""",
                (
                    self._current_session.actual_duration if self._current_session else 0,
                    1 if completed else 0,
                    1 if not completed else 0,
                ),
            )

    def get_today_stats(self) -> dict:
        """Get today's focus statistics."""
        with self._conn() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as sessions,
                          COALESCE(SUM(duration_actual), 0) as total_minutes,
                          COALESCE(SUM(completed), 0) as completed
                   FROM focus_sessions
                   WHERE DATE(started_at) = DATE('now')"""
            ).fetchone()

        return {
            "sessions_today": row["sessions"],
            "total_minutes_today": row["total_minutes"],
            "completed_today": row["completed"],
        }

    def get_weekly_report(self) -> str:
        """Generate a weekly productivity report."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT DATE(started_at) as day,
                          COUNT(*) as sessions,
                          SUM(duration_actual) as minutes,
                          SUM(completed) as completed
                   FROM focus_sessions
                   WHERE started_at >= datetime('now', '-7 days')
                   GROUP BY DATE(started_at)
                   ORDER BY day DESC"""
            ).fetchall()

        if not rows:
            return "No focus sessions this week."

        total_minutes = sum(r["minutes"] or 0 for r in rows)
        total_sessions = sum(r["sessions"] for r in rows)
        hours = total_minutes // 60
        mins = total_minutes % 60

        lines = [f"Focus report — last 7 days:"]
        lines.append(f"  Total: {total_sessions} sessions, {hours}h {mins}m focused")
        lines.append("")
        for row in rows:
            day = row["day"]
            lines.append(
                f"  {day}: {row['sessions']} session(s), "
                f"{row['minutes'] or 0} min"
            )

        return "\n".join(lines)

    @property
    def is_active(self) -> bool:
        return bool(self._current_session and self._current_session.is_active())

    def __repr__(self) -> str:
        return f"FocusMode(active={self.is_active})"


# Module-level singleton
focus_mode = FocusMode()

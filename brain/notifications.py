"""
brain/notifications.py
-----------------------
Windows toast notification system for JOSEPH.

Sends native Windows notifications for:
- Reminders
- Task completions
- Important alerts
- Morning briefing
- Any message Joseph wants to surface

Uses winotify for Windows 10/11 toast notifications.
"""

import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class NotificationSystem:
    """
    Sends Windows toast notifications.

    Usage:
        notif = NotificationSystem()
        notif.send("Reminder", "Call John at 3pm")
        notif.send_reminder("Meeting in 5 minutes")
    """

    APP_NAME = "JOSEPH AI"
    ICON_PATH = None  # Set to path of .ico file if available

    def __init__(self):
        self._available = False
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            from winotify import Notification
            self._available = True
            logger.info("NotificationSystem: winotify available")
        except ImportError:
            logger.warning("NotificationSystem: winotify not installed")

    def send(
        self,
        title: str,
        message: str,
        duration: str = "short",
        sound: bool = True,
    ) -> bool:
        """
        Send a Windows toast notification.

        Args:
            title: Notification title.
            message: Notification body text.
            duration: "short" (5s) or "long" (25s).
            sound: Whether to play notification sound.

        Returns:
            True if sent successfully.
        """
        if not self._available:
            logger.debug(f"Notification (no winotify): {title} — {message}")
            return False

        def _send():
            try:
                from winotify import Notification, audio

                toast = Notification(
                    app_id=self.APP_NAME,
                    title=title,
                    msg=message,
                    duration=duration,
                )

                if sound:
                    toast.set_audio(audio.Default, loop=False)

                toast.show()
                logger.debug(f"Notification sent: {title}")

            except Exception as e:
                logger.error(f"Notification error: {e}")

        # Send in background thread so it never blocks
        threading.Thread(target=_send, daemon=True).start()
        return True

    def send_reminder(self, message: str) -> bool:
        """Send a reminder notification."""
        return self.send(
            title=f"⏰ {self.APP_NAME} Reminder",
            message=message,
            duration="long",
        )

    def send_briefing(self, summary: str) -> bool:
        """Send morning briefing notification."""
        return self.send(
            title=f"☀️ Good Morning — {self.APP_NAME}",
            message=summary[:200],
            duration="long",
        )

    def send_task_complete(self, task: str) -> bool:
        """Send task completion notification."""
        return self.send(
            title=f"✓ Task Complete",
            message=task,
            duration="short",
        )

    def send_alert(self, message: str) -> bool:
        """Send an important alert."""
        return self.send(
            title=f"⚡ {self.APP_NAME}",
            message=message,
            duration="long",
        )

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return f"NotificationSystem(available={self._available})"


# Module-level singleton
notifications = NotificationSystem()

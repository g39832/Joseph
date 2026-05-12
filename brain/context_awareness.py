"""
brain/context_awareness.py
---------------------------
Context awareness for JOSEPH.

Tracks what the user is currently doing:
- Active window title and application
- Clipboard content changes
- Screen context (what's visible)

This lets Joseph give more relevant responses.
Example: If you're in VS Code and ask "help me fix this",
Joseph knows you're coding and responds accordingly.
"""

import logging
import threading
import time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ContextAwareness:
    """
    Monitors system context to make Joseph more aware.

    Runs a lightweight background thread that polls
    the active window and clipboard every few seconds.

    Usage:
        ctx = ContextAwareness()
        ctx.start()
        info = ctx.get_context()
        print(info["active_window"])  # "Visual Studio Code"
    """

    def __init__(self, poll_interval: float = 3.0):
        self.poll_interval = poll_interval
        self._active_window = "Unknown"
        self._active_app = "Unknown"
        self._clipboard = ""
        self._clipboard_changed = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if required modules are available."""
        try:
            import pygetwindow
            import pyperclip
            return True
        except ImportError:
            logger.warning("Context awareness unavailable (pygetwindow/pyperclip missing)")
            return False

    def start(self) -> None:
        """Start background context monitoring."""
        if not self._available or self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="Context-Monitor",
        )
        self._thread.start()
        logger.info("Context awareness monitoring started")

    def stop(self) -> None:
        """Stop background monitoring."""
        self._running = False

    def _monitor_loop(self) -> None:
        """Background loop that polls system context."""
        while self._running:
            try:
                self._update_active_window()
                self._update_clipboard()
            except Exception as e:
                logger.debug(f"Context monitor error: {e}")
            time.sleep(self.poll_interval)

    def _update_active_window(self) -> None:
        """Update the active window title."""
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window and window.title:
                with self._lock:
                    self._active_window = window.title
                    # Extract app name from title
                    self._active_app = self._extract_app_name(window.title)
        except Exception:
            pass

    def _update_clipboard(self) -> None:
        """Check if clipboard content changed."""
        try:
            import pyperclip
            current = pyperclip.paste()
            with self._lock:
                if current != self._clipboard and current:
                    self._clipboard = current
                    self._clipboard_changed = True
        except Exception:
            pass

    def _extract_app_name(self, window_title: str) -> str:
        """Extract the application name from a window title."""
        # Common patterns: "File.py - VS Code", "YouTube - Chrome"
        separators = [" - ", " — ", " | "]
        for sep in separators:
            if sep in window_title:
                parts = window_title.split(sep)
                # Usually app name is last part
                return parts[-1].strip()
        return window_title.strip()

    def get_context(self) -> dict:
        """
        Get current system context.

        Returns:
            Dict with active_window, active_app, clipboard, timestamp.
        """
        with self._lock:
            ctx = {
                "active_window": self._active_window,
                "active_app": self._active_app,
                "clipboard": self._clipboard[:200] if self._clipboard else "",
                "clipboard_changed": self._clipboard_changed,
                "timestamp": datetime.now().strftime("%H:%M:%S"),
            }
            self._clipboard_changed = False  # Reset flag after reading
        return ctx

    def get_context_for_llm(self) -> str:
        """
        Format context as a string for LLM injection.

        Returns:
            Context string or empty string if nothing useful.
        """
        ctx = self.get_context()
        parts = []

        if ctx["active_app"] and ctx["active_app"] != "Unknown":
            parts.append(f"User is currently in: {ctx['active_app']}")

        if ctx["clipboard"] and len(ctx["clipboard"]) > 5:
            preview = ctx["clipboard"][:100]
            parts.append(f"Clipboard: {preview}")

        return "\n".join(parts) if parts else ""

    def get_active_window(self) -> str:
        """Return the current active window title."""
        with self._lock:
            return self._active_window

    def get_active_app(self) -> str:
        """Return the current active application name."""
        with self._lock:
            return self._active_app

    def read_clipboard(self) -> str:
        """Return current clipboard content."""
        with self._lock:
            return self._clipboard

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return (
            f"ContextAwareness(available={self._available}, "
            f"running={self._running}, "
            f"app='{self._active_app}')"
        )


# Module-level singleton
context_awareness = ContextAwareness()

"""
brain/clipboard_monitor.py
---------------------------
Smart clipboard monitor for JOSEPH.

Watches your clipboard passively and offers contextual help:
- Copy a URL → offers to summarize the page
- Copy code → offers to explain or debug it
- Copy text → offers to translate, rewrite, or summarize
- Keeps history of last 50 clipboard items

Non-intrusive: suggestions appear as subtle system messages,
not interruptions. You can ignore them completely.
"""

import logging
import re
import threading
import time
from collections import deque
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# How often to check clipboard (seconds)
POLL_INTERVAL = 1.5

# Max clipboard history items
MAX_HISTORY = 50

# Minimum text length to trigger suggestions
MIN_TEXT_LENGTH = 20


class ClipboardItem:
    """A single clipboard history entry."""

    def __init__(self, content: str, content_type: str):
        self.content = content
        self.content_type = content_type  # url, code, text, email
        self.timestamp = datetime.now()
        self.suggestion_shown = False

    def preview(self, max_len: int = 60) -> str:
        return self.content[:max_len] + "..." if len(self.content) > max_len else self.content

    def __repr__(self) -> str:
        return f"ClipboardItem(type={self.content_type}, preview='{self.preview(30)}')"


class ClipboardMonitor:
    """
    Monitors clipboard and provides smart suggestions.

    Usage:
        monitor = ClipboardMonitor(on_suggestion=lambda msg: show_in_ui(msg))
        monitor.start()
        history = monitor.get_history()
        monitor.stop()
    """

    # Patterns for content type detection
    URL_PATTERN = re.compile(r'https?://[^\s]+', re.IGNORECASE)
    CODE_PATTERNS = [
        re.compile(r'\bdef \w+\(', re.MULTILINE),
        re.compile(r'\bfunction \w+\(', re.MULTILINE),
        re.compile(r'\bclass \w+[:\{]', re.MULTILINE),
        re.compile(r'\bimport \w+', re.MULTILINE),
        re.compile(r'\bconst |let |var ', re.MULTILINE),
        re.compile(r'^\s{4,}', re.MULTILINE),  # Indented code
    ]
    EMAIL_PATTERN = re.compile(r'^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$')

    def __init__(self, on_suggestion: Optional[Callable] = None):
        self.on_suggestion = on_suggestion
        self._history: deque[ClipboardItem] = deque(maxlen=MAX_HISTORY)
        self._last_content = ""
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._available = False
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import pyperclip
            self._available = True
        except ImportError:
            logger.warning("ClipboardMonitor: pyperclip not available")

    def start(self) -> None:
        """Start clipboard monitoring."""
        if not self._available or self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="Clipboard-Monitor",
        )
        self._thread.start()
        logger.info("Clipboard monitor started")

    def stop(self) -> None:
        """Stop clipboard monitoring."""
        self._running = False

    def _monitor_loop(self) -> None:
        """Poll clipboard for changes."""
        while self._running:
            try:
                import pyperclip
                current = pyperclip.paste()

                if current and current != self._last_content and len(current) >= MIN_TEXT_LENGTH:
                    self._last_content = current
                    self._process_new_content(current)

            except Exception as e:
                logger.debug(f"Clipboard poll error: {e}")

            time.sleep(POLL_INTERVAL)

    def _process_new_content(self, content: str) -> None:
        """Detect content type and optionally suggest an action."""
        content_type = self._detect_type(content)
        item = ClipboardItem(content=content, content_type=content_type)
        self._history.appendleft(item)

        logger.debug(f"Clipboard changed: type={content_type}, len={len(content)}")

        # Generate contextual suggestion
        suggestion = self._get_suggestion(item)
        if suggestion and self.on_suggestion:
            item.suggestion_shown = True
            try:
                self.on_suggestion(suggestion, item)
            except Exception as e:
                logger.debug(f"Suggestion callback error: {e}")

    def _detect_type(self, content: str) -> str:
        """Detect the type of clipboard content."""
        stripped = content.strip()

        # URL
        if self.URL_PATTERN.match(stripped):
            return "url"

        # Email
        if self.EMAIL_PATTERN.match(stripped):
            return "email"

        # Code (check multiple patterns)
        code_score = sum(1 for p in self.CODE_PATTERNS if p.search(content))
        if code_score >= 2:
            return "code"

        # Long text (article, document)
        if len(content) > 500:
            return "long_text"

        return "text"

    def _get_suggestion(self, item: ClipboardItem) -> Optional[str]:
        """Generate a contextual suggestion for the clipboard content."""
        if item.content_type == "url":
            domain = re.search(r'https?://([^/]+)', item.content)
            site = domain.group(1) if domain else "that page"
            return f"📋 URL copied from {site} — ask me to summarize it"

        elif item.content_type == "code":
            lines = item.content.count('\n') + 1
            return f"📋 Code copied ({lines} lines) — ask me to explain or debug it"

        elif item.content_type == "long_text":
            words = len(item.content.split())
            return f"📋 Long text copied ({words} words) — ask me to summarize it"

        return None  # No suggestion for short text

    def get_history(self, limit: int = 10) -> list[ClipboardItem]:
        """Return recent clipboard history."""
        return list(self._history)[:limit]

    def get_history_text(self, limit: int = 10) -> str:
        """Format clipboard history as readable text."""
        items = self.get_history(limit)
        if not items:
            return "Clipboard history is empty."

        lines = [f"Last {len(items)} clipboard items:"]
        for i, item in enumerate(items, 1):
            ts = item.timestamp.strftime("%H:%M")
            lines.append(f"  {i}. [{ts}] [{item.content_type}] {item.preview()}")
        return "\n".join(lines)

    def search_history(self, query: str) -> list[ClipboardItem]:
        """Search clipboard history by content."""
        query_lower = query.lower()
        return [
            item for item in self._history
            if query_lower in item.content.lower()
        ]

    def get_last(self) -> Optional[ClipboardItem]:
        """Get the most recent clipboard item."""
        return self._history[0] if self._history else None

    def clear_history(self) -> None:
        """Clear clipboard history."""
        self._history.clear()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return (
            f"ClipboardMonitor(running={self._running}, "
            f"history={len(self._history)})"
        )


# Module-level singleton
clipboard_monitor = ClipboardMonitor()

"""
brain/hotkey_daemon.py
-----------------------
Global hotkey daemon for JOSEPH — Phase 8.

Lets you activate Joseph from ANYWHERE on Windows,
even when the window is minimized or in the background.

Default hotkeys:
  Ctrl+Shift+J  — Activate Joseph (push-to-talk)
  Ctrl+Shift+S  — Take screenshot and analyze
  Ctrl+Shift+C  — Read clipboard and respond
  Ctrl+Shift+B  — Give morning briefing
  Ctrl+Shift+N  — Quick note (type after pressing)

The daemon runs as a background thread and listens
for these key combinations system-wide.
"""

import logging
import threading
from typing import Callable, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class HotkeyDaemon:
    """
    System-wide hotkey listener for JOSEPH.

    Registers global hotkeys that work even when
    the Joseph window is not focused.

    Usage:
        daemon = HotkeyDaemon()
        daemon.on_activate = lambda: voice.push_to_talk()
        daemon.start()
    """

    def __init__(self):
        self._available = False
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: dict[str, Callable] = {}
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if keyboard module is available."""
        try:
            import keyboard
            self._available = True
            logger.info("HotkeyDaemon: keyboard module available")
        except ImportError:
            logger.warning("HotkeyDaemon: keyboard module not installed")
        except Exception as e:
            logger.warning(f"HotkeyDaemon: {e}")

    def register(self, hotkey: str, callback: Callable, description: str = "") -> bool:
        """
        Register a global hotkey.

        Args:
            hotkey: Key combination string e.g. "ctrl+shift+j"
            callback: Function to call when hotkey is pressed.
            description: Human-readable description.

        Returns:
            True if registered successfully.
        """
        if not self._available:
            return False

        try:
            import keyboard
            keyboard.add_hotkey(hotkey, callback, suppress=False)
            self._callbacks[hotkey] = callback
            logger.info(f"Hotkey registered: {hotkey} — {description}")
            return True
        except Exception as e:
            logger.error(f"Failed to register hotkey {hotkey}: {e}")
            return False

    def unregister(self, hotkey: str) -> bool:
        """Remove a registered hotkey."""
        if not self._available:
            return False
        try:
            import keyboard
            keyboard.remove_hotkey(hotkey)
            self._callbacks.pop(hotkey, None)
            return True
        except Exception as e:
            logger.debug(f"Hotkey unregister error: {e}")
            return False

    def start(
        self,
        on_activate: Optional[Callable] = None,
        on_screenshot: Optional[Callable] = None,
        on_clipboard: Optional[Callable] = None,
        on_briefing: Optional[Callable] = None,
        on_note: Optional[Callable] = None,
    ) -> bool:
        """
        Start the hotkey daemon with default bindings.

        Args:
            on_activate: Called when Ctrl+Shift+J pressed (voice activate).
            on_screenshot: Called when Ctrl+Shift+S pressed.
            on_clipboard: Called when Ctrl+Shift+C pressed.
            on_briefing: Called when Ctrl+Shift+B pressed.
            on_note: Called when Ctrl+Shift+N pressed.

        Returns:
            True if started successfully.
        """
        if not self._available:
            logger.warning("HotkeyDaemon not available")
            return False

        if self._running:
            return True

        # Register default hotkeys
        if on_activate:
            self.register("ctrl+shift+j", on_activate, "Activate Joseph (voice)")
        if on_screenshot:
            self.register("ctrl+shift+s", on_screenshot, "Screenshot + analyze")
        if on_clipboard:
            self.register("ctrl+shift+c", on_clipboard, "Read clipboard")
        if on_briefing:
            self.register("ctrl+shift+b", on_briefing, "Daily briefing")
        if on_note:
            self.register("ctrl+shift+n", on_note, "Quick note")

        self._running = True
        logger.info(
            f"HotkeyDaemon started with {len(self._callbacks)} hotkeys:\n"
            + "\n".join(f"  {k}" for k in self._callbacks.keys())
        )
        return True

    def stop(self) -> None:
        """Stop the hotkey daemon and unregister all hotkeys."""
        if not self._available or not self._running:
            return
        try:
            import keyboard
            keyboard.unhook_all_hotkeys()
            self._callbacks.clear()
            self._running = False
            logger.info("HotkeyDaemon stopped")
        except Exception as e:
            logger.debug(f"HotkeyDaemon stop error: {e}")

    def get_registered_hotkeys(self) -> dict[str, str]:
        """Return dict of registered hotkeys."""
        return {
            "ctrl+shift+j": "Activate Joseph (voice / push-to-talk)",
            "ctrl+shift+s": "Screenshot + analyze screen",
            "ctrl+shift+c": "Read clipboard content",
            "ctrl+shift+b": "Daily briefing",
            "ctrl+shift+n": "Quick note",
        }

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return (
            f"HotkeyDaemon(available={self._available}, "
            f"running={self._running}, "
            f"hotkeys={len(self._callbacks)})"
        )


# Module-level singleton
hotkey_daemon = HotkeyDaemon()

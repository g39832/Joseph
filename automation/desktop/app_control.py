"""
automation/desktop/app_control.py
-----------------------------------
Desktop application launching and window management.

Handles:
- Opening applications by name
- Switching between windows
- Getting active window info
- Reading clipboard
- Taking screenshots
"""

import logging
import os
import subprocess
import time
from typing import Optional

from automation.safety.permissions import permissions, RiskLevel

logger = logging.getLogger(__name__)

# Common Windows application shortcuts
APP_MAP = {
    # Browsers
    "chrome":       "chrome",
    "google chrome":"chrome",
    "firefox":      "firefox",
    "edge":         "msedge",
    "microsoft edge":"msedge",

    # Microsoft Office
    "word":         "winword",
    "excel":        "excel",
    "powerpoint":   "powerpnt",
    "outlook":      "outlook",
    "onenote":      "onenote",

    # Windows built-in
    "notepad":      "notepad",
    "calculator":   "calc",
    "paint":        "mspaint",
    "explorer":     "explorer",
    "file explorer":"explorer",
    "task manager": "taskmgr",
    "settings":     "ms-settings:",
    "control panel":"control",
    "cmd":          "cmd",
    "powershell":   "powershell",
    "terminal":     "wt",

    # Media
    "spotify":      "spotify",
    "vlc":          "vlc",
    "media player": "wmplayer",

    # Dev tools
    "vs code":      "code",
    "vscode":       "code",
    "visual studio code": "code",
    "git bash":     "git-bash",

    # Communication
    "discord":      "discord",
    "slack":        "slack",
    "teams":        "teams",
    "zoom":         "zoom",
}


class AppController:
    """
    Controls desktop applications and windows.

    Usage:
        app = AppController()
        app.open_app("notepad")
        app.get_active_window()
        app.read_clipboard()
    """

    def open_app(self, app_name: str) -> tuple[bool, str]:
        """
        Open an application by name.

        Args:
            app_name: Application name (e.g. "notepad", "chrome", "spotify")

        Returns:
            Tuple of (success, message)
        """
        app_lower = app_name.lower().strip()

        # Look up in app map
        command = APP_MAP.get(app_lower)

        if not command:
            # Try direct execution
            command = app_lower

        # Check permissions for shell execution
        if not permissions.request_permission(
            f"open application: {app_name}",
            RiskLevel.LOW,
        ):
            return False, "Permission denied"

        try:
            logger.info(f"Opening app: {app_name} (command: {command})")

            if command.startswith("ms-"):
                # Windows Settings URI
                os.startfile(command)
            else:
                subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

            time.sleep(0.5)  # Brief pause for app to start
            return True, f"Opening {app_name}."

        except FileNotFoundError:
            msg = f"Could not find '{app_name}'. Is it installed?"
            logger.warning(msg)
            return False, msg

        except Exception as e:
            logger.error(f"Failed to open {app_name}: {e}")
            return False, f"Failed to open {app_name}: {e}"

    def get_active_window(self) -> dict:
        """
        Get information about the currently active window.

        Returns:
            Dict with title, app name, position info.
        """
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window:
                return {
                    "title": window.title,
                    "left": window.left,
                    "top": window.top,
                    "width": window.width,
                    "height": window.height,
                }
        except Exception as e:
            logger.debug(f"Get active window error: {e}")

        return {"title": "Unknown", "left": 0, "top": 0, "width": 0, "height": 0}

    def get_all_windows(self) -> list[str]:
        """Return titles of all open windows."""
        try:
            import pygetwindow as gw
            return [w.title for w in gw.getAllWindows() if w.title.strip()]
        except Exception as e:
            logger.debug(f"Get all windows error: {e}")
            return []

    def read_clipboard(self) -> str:
        """
        Read the current clipboard content.

        Returns:
            Clipboard text content, or empty string.
        """
        try:
            import pyperclip
            content = pyperclip.paste()
            logger.debug(f"Clipboard read: {content[:50]}...")
            return content or ""
        except Exception as e:
            logger.error(f"Clipboard read error: {e}")
            return ""

    def write_clipboard(self, text: str) -> bool:
        """
        Write text to the clipboard.

        Args:
            text: Text to copy to clipboard.

        Returns:
            True if successful.
        """
        try:
            import pyperclip
            pyperclip.copy(text)
            logger.info(f"Copied to clipboard: {text[:50]}")
            return True
        except Exception as e:
            logger.error(f"Clipboard write error: {e}")
            return False

    def take_screenshot(self, save_path: Optional[str] = None) -> Optional[str]:
        """
        Take a screenshot of the entire screen.

        Args:
            save_path: Where to save the image. Auto-generates path if None.

        Returns:
            Path to saved screenshot, or None on failure.
        """
        try:
            import pyautogui
            from datetime import datetime
            from configs.settings import settings

            if save_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = str(
                    settings.EXPORTS_DIR / f"screenshot_{timestamp}.png"
                )

            screenshot = pyautogui.screenshot()
            screenshot.save(save_path)
            logger.info(f"Screenshot saved: {save_path}")
            return save_path

        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

    def list_known_apps(self) -> list[str]:
        """Return list of known application names."""
        return sorted(APP_MAP.keys())

    def __repr__(self) -> str:
        return "AppController()"

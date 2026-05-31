"""
tools/app_tools.py
-------------------
Desktop application control and system utilities.

Provides application launching, window management,
screenshot capture, and clipboard operations.
"""

import logging
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from configs.settings import settings
from tools.registry import ToolResult

logger = logging.getLogger(__name__)

APP_MAP: dict[str, str] = {
    "chrome": "chrome",
    "google chrome": "chrome",
    "firefox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "word": "winword",
    "excel": "excel",
    "powerpoint": "powerpnt",
    "outlook": "outlook",
    "onenote": "onenote",
    "notepad": "notepad",
    "calculator": "calc",
    "paint": "mspaint",
    "explorer": "explorer",
    "file explorer": "explorer",
    "task manager": "taskmgr",
    "settings": "ms-settings:",
    "control panel": "control",
    "cmd": "cmd",
    "powershell": "powershell",
    "terminal": "wt",
    "spotify": "spotify",
    "vlc": "vlc",
    "media player": "wmplayer",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
    "discord": "discord",
    "slack": "slack",
    "teams": "teams",
    "zoom": "zoom",
    "notion": "notion",
    "obsidian": "obsidian",
    "sublime": "sublime_text",
    "sublime text": "sublime_text",
    "intellij": "idea",
    "pycharm": "pycharm",
}


class AppTools:
    """
    Desktop application launch and control tools.

    Provides safe wrappers around:
      - Application launching (by name or path)
      - Process listing
      - Window focus
      - Screenshot capture
      - Clipboard read/write
    """

    def __init__(self):
        self._launch_log: list[dict] = []
        self._import_warnings: dict[str, bool] = {}

    def launch_app(self, app_name_or_path: str) -> ToolResult:
        """
        Launch an application by name or executable path.

        Uses APP_MAP for common apps, falls back to direct execution.

        Args:
            app_name_or_path: App name (e.g. "notepad") or file path.

        Returns:
            ToolResult with launch status.
        """
        name = app_name_or_path.strip()

        command = APP_MAP.get(name.lower())

        if not command:
            command = name

        try:
            logger.info(f"Launching app: {name} (command: {command})")

            if command.startswith("ms-"):
                os.startfile(command)
            else:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                subprocess.Popen(
                    command,
                    shell=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    startupinfo=startupinfo,
                )

            time.sleep(0.5)

            self._log_launch(name, command, True)
            return ToolResult(success=True, output=f"Launching {name}.")

        except FileNotFoundError:
            msg = f"Could not find application: {name}"
            self._log_launch(name, command, False)
            return ToolResult(success=False, output="", error=msg)

        except Exception as e:
            msg = f"Failed to launch {name}: {e}"
            self._log_launch(name, command, False)
            return ToolResult(success=False, output="", error=msg)

    def list_running_apps(self) -> ToolResult:
        """
        List running applications (top-level windows).

        Returns:
            ToolResult with list of running app windows.
        """
        try:
            import pygetwindow as gw
            windows = gw.getAllWindows()
            visible = [
                w.title for w in windows
                if w.title.strip() and w.visible
            ]
            unique = list(dict.fromkeys(visible))

            if not unique:
                return ToolResult(success=True, output="No visible windows found.")

            lines = [f"Running applications ({len(unique)}):"]
            for title in sorted(unique)[:50]:
                lines.append(f"  {title}")

            return ToolResult(success=True, output="\n".join(lines))

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="pygetwindow not installed. Run: pip install pygetwindow",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"List apps error: {e}",
            )

    def focus_app(self, app_name: str) -> ToolResult:
        """
        Bring an application window to the foreground.

        Args:
            app_name: Name of the application window to focus.

        Returns:
            ToolResult with focus status.
        """
        try:
            import pygetwindow as gw

            name_lower = app_name.lower()
            target = None

            for window in gw.getAllWindows():
                if name_lower in window.title.lower() and window.title.strip():
                    target = window
                    break

            if not target:
                return ToolResult(
                    success=False, output="",
                    error=f"No visible window found matching: {app_name}",
                )

            target.activate()
            time.sleep(0.3)
            return ToolResult(
                success=True,
                output=f"Focused: {target.title}",
            )

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="pygetwindow not installed. Run: pip install pygetwindow",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Focus error: {e}",
            )

    def take_screenshot(self, path: Optional[str] = None) -> ToolResult:
        """
        Capture a screenshot of the entire screen.

        Args:
            path: Optional save path. Auto-generates if not provided.

        Returns:
            ToolResult with path to saved screenshot.
        """
        try:
            import pyautogui

            if not path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = str(settings.EXPORTS_DIR / f"screenshot_{timestamp}.png")

            save_path = Path(path).expanduser().resolve()
            save_path.parent.mkdir(parents=True, exist_ok=True)

            screenshot = pyautogui.screenshot()
            screenshot.save(str(save_path))

            return ToolResult(
                success=True,
                output=f"Screenshot saved: {save_path}",
            )

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="pyautogui not installed. Run: pip install pyautogui",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Screenshot error: {e}",
            )

    def read_clipboard(self) -> ToolResult:
        """
        Read current clipboard content.

        Returns:
            ToolResult with clipboard text.
        """
        try:
            import pyperclip
            content = pyperclip.paste()

            if not content:
                return ToolResult(success=True, output="Clipboard is empty.")

            return ToolResult(
                success=True,
                output=content,
            )

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="pyperclip not installed. Run: pip install pyperclip",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Clipboard read error: {e}",
            )

    def write_clipboard(self, text: str) -> ToolResult:
        """
        Write text to the clipboard.

        Args:
            text: Text to copy.

        Returns:
            ToolResult with status.
        """
        try:
            import pyperclip
            pyperclip.copy(text)
            return ToolResult(
                success=True,
                output=f"Copied {len(text)} chars to clipboard.",
            )

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="pyperclip not installed. Run: pip install pyperclip",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Clipboard write error: {e}",
            )

    def get_active_window_info(self) -> ToolResult:
        """
        Get information about the currently active window.

        Returns:
            ToolResult with window details.
        """
        try:
            import pygetwindow as gw
            window = gw.getActiveWindow()
            if window and window.title.strip():
                info = (
                    f"Title: {window.title}\n"
                    f"Position: ({window.left}, {window.top})\n"
                    f"Size: {window.width}x{window.height}"
                )
                return ToolResult(success=True, output=info)

            return ToolResult(success=True, output="No active window detected.")

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="pygetwindow not installed.",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Window info error: {e}",
            )

    def _log_launch(self, name: str, command: str, success: bool) -> None:
        self._launch_log.append({
            "timestamp": datetime.now().isoformat(),
            "name": name,
            "command": command,
            "success": success,
        })

    def get_launch_log(self, limit: int = 20) -> list[dict]:
        return self._launch_log[-limit:]

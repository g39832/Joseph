"""
brain/screen_awareness.py
---------------------------
Computer Awareness Module — screenshot capture, active window detection,
screen analysis, and application awareness.

Requires user permission for all screen access.

Usage:
    sa = ScreenAwareness(vision_engine=ve)
    result = sa.capture_and_analyze()
    result.description  # what's on screen
    result.window_title  # active window
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ScreenResult:
    path: str
    description: str = ""
    window_title: str = ""
    application: str = ""
    text_detected: str = ""
    error: str = ""
    captured_at: str = ""

    def __post_init__(self):
        if not self.captured_at:
            self.captured_at = datetime.now().isoformat()


class ScreenAwareness:
    """
    Screen capture and analysis.

    All operations require explicit user permission.
    Permission is checked before every capture.
    """

    def __init__(self, vision_engine=None, data_dir=None):
        self._ve = vision_engine
        self._data_dir = data_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "data", "screenshots"
        )
        os.makedirs(self._data_dir, exist_ok=True)
        self._permission_granted = False
        self._check_permission()

    def _check_permission(self):
        """Check if screen capture permission has been configured."""
        import json
        config_path = os.path.join(
            os.path.dirname(self._data_dir), "screen_permission.json"
        )
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    self._permission_granted = cfg.get("granted", False)
            except Exception:
                self._permission_granted = False

    def request_permission(self) -> bool:
        """
        Request user permission for screen access.

        In GUI mode, this shows a dialog. In CLI, it prompts.
        Stores the consent to avoid asking every time.
        """
        import json
        config_path = os.path.join(
            os.path.dirname(self._data_dir), "screen_permission.json"
        )

        try:
            # Try GUI dialog
            import customtkinter as ctk
            import tkinter.messagebox as mb

            root = ctk.CTk()
            root.withdraw()
            result = mb.askyesno(
                "Screen Access Permission",
                "JOSEPH would like to capture your screen for analysis.\n\n"
                "This allows features like:\n"
                "- What's on my screen?\n"
                "- Analyze this error message\n"
                "- Explain this code\n\n"
                "Grant permission?",
            )
            root.destroy()

            if result:
                self._permission_granted = True
                with open(config_path, "w") as f:
                    json.dump({"granted": True, "timestamp": datetime.now().isoformat()}, f)
                logger.info("Screen capture permission granted")
                return True
            return False

        except Exception:
            # Fallback: manual config
            print("\nJOSEPH needs screen capture permission for screen awareness features.")
            print("To enable, create config/screen_permission.json with:")
            print('  {"granted": true}')
            return False

    def capture(self, region: tuple = None) -> Optional[str]:
        """
        Capture the screen (or a region) to a PNG file.

        Args:
            region: (left, top, right, bottom) or None for full screen.

        Returns:
            Path to screenshot file, or None if failed/permission denied.
        """
        if not self._permission_granted:
            logger.warning("Screen capture not permitted")
            return None

        try:
            import pyautogui

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"screenshot_{timestamp}.png"
            filepath = os.path.join(self._data_dir, filename)

            if region:
                screenshot = pyautogui.screenshot(region=region)
            else:
                screenshot = pyautogui.screenshot()

            screenshot.save(filepath)
            logger.info(f"Screenshot saved: {filepath}")
            return filepath

        except ImportError:
            logger.warning("pyautogui not available for screen capture")
            return None
        except Exception as e:
            logger.warning(f"Screen capture failed: {e}")
            return None

    def get_active_window_info(self) -> dict:
        """Get active window title and application name."""
        info = {"title": "", "application": ""}
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active:
                info["title"] = active.title
                info["application"] = active.title.split(" - ")[-1] if " - " in active.title else ""
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Active window detection failed: {e}")
        return info

    def capture_and_analyze(self, region: tuple = None) -> ScreenResult:
        """
        Capture the screen and analyze it using the Vision Engine.

        Returns a ScreenResult with description and window info.
        """
        if not self._permission_granted:
            return ScreenResult(
                path="", error="Screen capture permission not granted. "
                "Call request_permission() first."
            )

        filepath = self.capture(region)
        if not filepath:
            return ScreenResult(path="", error="Failed to capture screen.")

        window_info = self.get_active_window_info()

        description = ""
        if self._ve:
            result = self._ve.analyze_screenshot(filepath)
            description = result.description
        else:
            description = "Vision engine not available."

        return ScreenResult(
            path=filepath,
            description=description,
            window_title=window_info.get("title", ""),
            application=window_info.get("application", ""),
        )

    def capture_active_window(self) -> ScreenResult:
        """Capture only the active window instead of full screen."""
        try:
            import pygetwindow as gw
            active = gw.getActiveWindow()
            if active and hasattr(active, "box"):
                b = active.box
                region = (b.left, b.top, b.right, b.bottom)
                return self.capture_and_analyze(region=region)
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"Active window capture failed: {e}")
        return self.capture_and_analyze()

    def is_available(self) -> dict:
        """Check which screen capture dependencies are available."""
        available = {}
        for lib in ["pyautogui", "pygetwindow"]:
            try:
                __import__(lib)
                available[lib] = True
            except ImportError:
                available[lib] = False
        available["permission"] = self._permission_granted
        return available

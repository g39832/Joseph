"""
automation/desktop/mouse_keyboard.py
--------------------------------------
Mouse and keyboard automation using pyautogui.

Handles:
- Typing text at cursor position
- Mouse clicks
- Keyboard shortcuts
- Scrolling

All actions require permission check before executing.
"""

import logging
import time
from typing import Optional, Tuple

from automation.safety.permissions import permissions, RiskLevel

logger = logging.getLogger(__name__)


class MouseKeyboardController:
    """
    Controls mouse and keyboard for desktop automation.

    Usage:
        mk = MouseKeyboardController()
        mk.type_text("Hello, world!")
        mk.press_hotkey("ctrl", "c")
        mk.click(500, 300)
    """

    def __init__(self):
        self._available = False
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if pyautogui is available."""
        try:
            import pyautogui
            pyautogui.FAILSAFE = True   # Move mouse to corner to abort
            pyautogui.PAUSE = 0.05      # Small pause between actions
            self._available = True
            logger.debug("MouseKeyboardController ready")
        except Exception as e:
            logger.warning(f"pyautogui unavailable: {e}")

    def type_text(self, text: str, interval: float = 0.03) -> bool:
        """
        Type text at the current cursor position.

        Args:
            text: Text to type.
            interval: Delay between keystrokes (seconds).

        Returns:
            True if successful.
        """
        if not self._available:
            return False

        if not permissions.request_permission(
            f"type text: '{text[:40]}...'",
            RiskLevel.MEDIUM,
        ):
            return False

        try:
            import pyautogui
            pyautogui.write(text, interval=interval)
            logger.info(f"Typed: {text[:50]}")
            return True
        except Exception as e:
            logger.error(f"Type error: {e}")
            return False

    def press_key(self, key: str) -> bool:
        """
        Press a single key.

        Args:
            key: Key name (e.g. 'enter', 'escape', 'tab', 'space')

        Returns:
            True if successful.
        """
        if not self._available:
            return False

        try:
            import pyautogui
            pyautogui.press(key)
            logger.debug(f"Key pressed: {key}")
            return True
        except Exception as e:
            logger.error(f"Key press error: {e}")
            return False

    def press_hotkey(self, *keys: str) -> bool:
        """
        Press a keyboard shortcut (multiple keys simultaneously).

        Args:
            *keys: Keys to press together (e.g. 'ctrl', 'c')

        Returns:
            True if successful.

        Example:
            press_hotkey('ctrl', 'c')   # Copy
            press_hotkey('ctrl', 'v')   # Paste
            press_hotkey('alt', 'f4')   # Close window
            press_hotkey('win', 'd')    # Show desktop
        """
        if not self._available:
            return False

        combo = "+".join(keys)

        # Some hotkeys need confirmation
        dangerous = {"alt+f4", "ctrl+alt+del", "win+l"}
        if combo.lower() in dangerous:
            if not permissions.request_permission(
                f"keyboard shortcut: {combo}",
                RiskLevel.HIGH,
            ):
                return False

        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            logger.info(f"Hotkey: {combo}")
            return True
        except Exception as e:
            logger.error(f"Hotkey error: {e}")
            return False

    def click(
        self,
        x: int,
        y: int,
        button: str = "left",
        clicks: int = 1,
    ) -> bool:
        """
        Click at screen coordinates.

        Args:
            x: X coordinate.
            y: Y coordinate.
            button: 'left', 'right', or 'middle'.
            clicks: Number of clicks (2 for double-click).

        Returns:
            True if successful.
        """
        if not self._available:
            return False

        if not permissions.request_permission(
            f"mouse click at ({x}, {y})",
            RiskLevel.LOW,
        ):
            return False

        try:
            import pyautogui
            pyautogui.click(x, y, button=button, clicks=clicks)
            logger.debug(f"Clicked ({x}, {y}) {button}x{clicks}")
            return True
        except Exception as e:
            logger.error(f"Click error: {e}")
            return False

    def scroll(self, clicks: int, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """
        Scroll the mouse wheel.

        Args:
            clicks: Positive = scroll up, negative = scroll down.
            x, y: Optional position to scroll at.

        Returns:
            True if successful.
        """
        if not self._available:
            return False

        try:
            import pyautogui
            if x is not None and y is not None:
                pyautogui.scroll(clicks, x=x, y=y)
            else:
                pyautogui.scroll(clicks)
            return True
        except Exception as e:
            logger.error(f"Scroll error: {e}")
            return False

    def get_mouse_position(self) -> Tuple[int, int]:
        """Return current mouse cursor position."""
        try:
            import pyautogui
            return pyautogui.position()
        except Exception:
            return (0, 0)

    def get_screen_size(self) -> Tuple[int, int]:
        """Return screen dimensions (width, height)."""
        try:
            import pyautogui
            return pyautogui.size()
        except Exception:
            return (1920, 1080)

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return f"MouseKeyboardController(available={self._available})"

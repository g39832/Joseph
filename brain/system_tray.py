"""
brain/system_tray.py
---------------------
Windows system tray icon for JOSEPH.

Joseph lives in the taskbar tray so you can:
- See if Joseph is running at a glance
- Open/hide the main window
- Trigger voice activation
- Get a quick briefing
- Exit cleanly

The tray icon runs on its own thread.
"""

import logging
import threading
from typing import Callable, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


def _create_joseph_icon():
    """Create a simple Joseph icon programmatically using PIL."""
    try:
        from PIL import Image, ImageDraw, ImageFont

        # Create a 64x64 icon
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # Dark background circle
        draw.ellipse([2, 2, 62, 62], fill=(30, 30, 30, 255))

        # Blue accent ring
        draw.ellipse([2, 2, 62, 62], outline=(77, 157, 224, 255), width=3)

        # "J" letter in center
        try:
            font = ImageFont.truetype("segoeui.ttf", 32)
        except Exception:
            font = ImageFont.load_default()

        draw.text((20, 12), "J", fill=(77, 157, 224, 255), font=font)

        return img

    except Exception as e:
        logger.debug(f"Icon creation failed: {e}")
        # Fallback: solid blue square
        try:
            from PIL import Image
            img = Image.new("RGB", (64, 64), (77, 157, 224))
            return img
        except Exception:
            return None


class SystemTray:
    """
    Windows system tray icon for JOSEPH.

    Usage:
        tray = SystemTray()
        tray.start(
            on_show=lambda: window.deiconify(),
            on_voice=lambda: voice.push_to_talk(),
            on_exit=lambda: app.quit(),
        )
    """

    def __init__(self):
        self._available = False
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._check_availability()

    def _check_availability(self) -> None:
        try:
            import pystray
            from PIL import Image
            self._available = True
            logger.info("SystemTray: pystray available")
        except ImportError:
            logger.warning("SystemTray: pystray or PIL not available")

    def start(
        self,
        on_show: Optional[Callable] = None,
        on_hide: Optional[Callable] = None,
        on_voice: Optional[Callable] = None,
        on_briefing: Optional[Callable] = None,
        on_exit: Optional[Callable] = None,
    ) -> bool:
        """
        Start the system tray icon.

        Args:
            on_show: Called when "Show Joseph" is clicked.
            on_hide: Called when "Hide" is clicked.
            on_voice: Called when "Voice Activate" is clicked.
            on_briefing: Called when "Briefing" is clicked.
            on_exit: Called when "Exit" is clicked.

        Returns:
            True if tray started successfully.
        """
        if not self._available:
            return False

        if self._running:
            return True

        try:
            import pystray
            from pystray import MenuItem, Menu

            icon_image = _create_joseph_icon()
            if icon_image is None:
                return False

            # Build menu
            menu_items = []

            menu_items.append(
                MenuItem(
                    f"{settings.JOSEPH_NAME} — Personal AI",
                    lambda: None,
                    enabled=False,
                )
            )
            menu_items.append(Menu.SEPARATOR)

            if on_show:
                menu_items.append(MenuItem("Show Window", on_show, default=True))
            if on_hide:
                menu_items.append(MenuItem("Hide Window", on_hide))

            menu_items.append(Menu.SEPARATOR)

            if on_voice:
                menu_items.append(MenuItem("🎤 Voice Activate (Ctrl+Shift+J)", on_voice))
            if on_briefing:
                menu_items.append(MenuItem("☀️ Daily Briefing", on_briefing))

            menu_items.append(Menu.SEPARATOR)

            if on_exit:
                menu_items.append(MenuItem("Exit Joseph", on_exit))

            self._icon = pystray.Icon(
                name=settings.JOSEPH_NAME,
                icon=icon_image,
                title=f"{settings.JOSEPH_NAME} — Running",
                menu=Menu(*menu_items),
            )

            # Run tray in background thread
            self._thread = threading.Thread(
                target=self._icon.run,
                daemon=True,
                name="SystemTray",
            )
            self._thread.start()
            self._running = True
            logger.info("System tray icon started")
            return True

        except Exception as e:
            logger.error(f"System tray start error: {e}")
            return False

    def update_tooltip(self, text: str) -> None:
        """Update the tray icon tooltip text."""
        if self._icon and self._running:
            try:
                self._icon.title = text
            except Exception:
                pass

    def set_status(self, status: str) -> None:
        """Update tray tooltip with current status."""
        self.update_tooltip(f"{settings.JOSEPH_NAME} — {status}")

    def stop(self) -> None:
        """Stop the system tray icon."""
        if self._icon and self._running:
            try:
                self._icon.stop()
                self._running = False
                logger.info("System tray stopped")
            except Exception as e:
                logger.debug(f"Tray stop error: {e}")

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_running(self) -> bool:
        return self._running

    def __repr__(self) -> str:
        return f"SystemTray(available={self._available}, running={self._running})"


# Module-level singleton
system_tray = SystemTray()

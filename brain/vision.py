"""
brain/vision.py
----------------
Screen vision and image understanding for JOSEPH.

Capabilities:
- Take and analyze screenshots
- Describe what's on screen
- Read text from screen (OCR-lite via LLM)
- Understand active window context visually
- Answer questions about what's visible

Uses:
- PIL/Pillow for image capture and processing
- Base64 encoding to send to LLM
- Ollama vision models (llava, bakllava) if available
- Falls back to screenshot + text description
"""

import base64
import logging
import os
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class VisionSystem:
    """
    Gives JOSEPH the ability to see and understand the screen.

    Usage:
        vision = VisionSystem(llm=llm)
        description = vision.describe_screen()
        answer = vision.ask_about_screen("What application is open?")
    """

    def __init__(self, llm=None):
        self._llm = llm
        self._available = False
        self._vision_model = "llava"  # Ollama vision model
        self._has_vision_model = False
        self._check_availability()

    def _check_availability(self) -> None:
        """Check if PIL and vision model are available."""
        try:
            from PIL import Image, ImageGrab
            self._available = True
            logger.info("VisionSystem: PIL available")
        except ImportError:
            logger.warning("VisionSystem: PIL not available")
            return

        # Check if vision model is available in Ollama
        if self._llm:
            try:
                models = self._llm.client.list()
                available = [m.model.split(":")[0].lower() for m in models.models]
                if "llava" in available:
                    self._has_vision_model = True
                    self._vision_model = "llava"
                    logger.info("VisionSystem: llava model available")
                elif "bakllava" in available:
                    self._has_vision_model = True
                    self._vision_model = "bakllava"
                    logger.info("VisionSystem: bakllava model available")
                else:
                    logger.info(
                        "VisionSystem: No vision model found. "
                        "Install with: ollama pull llava"
                    )
            except Exception as e:
                logger.debug(f"Vision model check failed: {e}")

    def take_screenshot(self, save: bool = True) -> Optional[str]:
        """
        Take a screenshot and optionally save it.

        Args:
            save: Whether to save to exports folder.

        Returns:
            Path to saved screenshot, or None.
        """
        if not self._available:
            return None

        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()

            if save:
                settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                path = settings.EXPORTS_DIR / f"screenshot_{timestamp}.png"
                screenshot.save(str(path))
                logger.info(f"Screenshot saved: {path}")
                return str(path)

            return screenshot

        except Exception as e:
            logger.error(f"Screenshot error: {e}")
            return None

    def describe_screen(self) -> str:
        """
        Take a screenshot and describe what's on screen.

        Returns:
            Natural language description of the screen.
        """
        if not self._available:
            return "Vision system not available."

        try:
            from PIL import ImageGrab

            screenshot = ImageGrab.grab()

            if self._has_vision_model and self._llm:
                return self._analyze_with_vision_model(
                    screenshot,
                    "Describe what you see on this screen. Be concise and specific. "
                    "Mention the main application, any visible text, and what the user appears to be doing."
                )
            else:
                # Fallback: save and return path
                path = self.take_screenshot(save=True)
                return f"Screenshot taken and saved to {path}. Install llava for visual analysis: ollama pull llava"

        except Exception as e:
            logger.error(f"Screen description error: {e}")
            return f"Could not analyze screen: {e}"

    def ask_about_screen(self, question: str) -> str:
        """
        Answer a question about what's currently on screen.

        Args:
            question: What to ask about the screen.

        Returns:
            Answer based on visual analysis.
        """
        if not self._available:
            return "Vision system not available."

        if not self._has_vision_model:
            return (
                "I can take screenshots but can't analyze them visually yet. "
                "Install llava for visual analysis: ollama pull llava"
            )

        try:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab()
            return self._analyze_with_vision_model(screenshot, question)

        except Exception as e:
            logger.error(f"Screen question error: {e}")
            return f"Could not analyze screen: {e}"

    def read_screen_text(self) -> str:
        """
        Extract readable text from the current screen.
        Uses vision model if available, otherwise returns screenshot path.

        Returns:
            Text visible on screen.
        """
        return self.ask_about_screen(
            "Read and transcribe all visible text on this screen. "
            "Include text from menus, buttons, documents, and any other UI elements."
        )

    def _analyze_with_vision_model(self, image, prompt: str) -> str:
        """
        Send image to Ollama vision model for analysis.

        Args:
            image: PIL Image object.
            prompt: What to ask about the image.

        Returns:
            Model's response.
        """
        try:
            # Resize for faster processing (max 1280px wide)
            max_width = 1280
            if image.width > max_width:
                ratio = max_width / image.width
                new_size = (max_width, int(image.height * ratio))
                image = image.resize(new_size)

            # Convert to base64
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

            # Call vision model
            response = self._llm.client.chat(
                model=self._vision_model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [img_b64],
                }],
                options={"temperature": 0.1},
            )
            return response.message.content.strip()

        except Exception as e:
            logger.error(f"Vision model error: {e}")
            return f"Vision analysis failed: {e}"

    def get_active_window_screenshot(self) -> Optional[str]:
        """
        Take a screenshot of just the active window.

        Returns:
            Path to saved screenshot.
        """
        try:
            import pygetwindow as gw
            from PIL import ImageGrab

            window = gw.getActiveWindow()
            if not window:
                return self.take_screenshot()

            # Crop to window bounds
            bbox = (window.left, window.top, window.right, window.bottom)
            screenshot = ImageGrab.grab(bbox=bbox)

            settings.EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = settings.EXPORTS_DIR / f"window_{timestamp}.png"
            screenshot.save(str(path))
            return str(path)

        except Exception as e:
            logger.error(f"Window screenshot error: {e}")
            return self.take_screenshot()

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def has_vision_model(self) -> bool:
        return self._has_vision_model

    def __repr__(self) -> str:
        return (
            f"VisionSystem(available={self._available}, "
            f"vision_model={self._vision_model if self._has_vision_model else 'none'})"
        )


# Module-level singleton (initialized with LLM later)
vision_system = VisionSystem()

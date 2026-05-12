"""
automation/browser/playwright_controller.py
--------------------------------------------
Browser automation using Playwright (Chromium).

Handles all web-based tasks:
- Opening URLs
- Google search
- YouTube search and navigation
- General page interaction

Playwright runs a real Chromium browser instance.
headless=False means you can see the browser window.
headless=True runs invisibly in the background.
"""

import logging
import asyncio
from typing import Optional
from urllib.parse import quote_plus

from automation.safety.permissions import permissions, RiskLevel

logger = logging.getLogger(__name__)


class PlaywrightController:
    """
    Controls a Chromium browser via Playwright.

    Usage:
        browser = PlaywrightController()
        await browser.open_url("https://youtube.com")
        await browser.search_google("Python tutorials")
    """

    def __init__(self, headless: bool = False):
        self.headless = headless
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._available = False
        self._initialized = False

    async def initialize(self) -> bool:
        """
        Launch the browser. Call this before any other method.

        Returns:
            True if browser launched successfully.
        """
        if self._initialized:
            return True

        try:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            self._page = await self._context.new_page()
            self._initialized = True
            self._available = True
            logger.info("Playwright browser launched")
            return True

        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            self._available = False
            return False

    async def open_url(self, url: str) -> bool:
        """
        Navigate to a URL.

        Args:
            url: Full URL including https://

        Returns:
            True if navigation succeeded.
        """
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            if not await self._ensure_ready():
                return False
            logger.info(f"Opening URL: {url}")
            await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
            title = await self._page.title()
            logger.info(f"Page loaded: {title}")
            return True
        except Exception as e:
            error_str = str(e).lower()
            if "closed" in error_str or "target" in error_str or "context" in error_str:
                logger.warning("Browser was closed — reopening...")
                self._initialized = False
                self._page = None
                self._context = None
                self._browser = None
                if await self.initialize():
                    try:
                        await self._page.goto(url, wait_until="domcontentloaded", timeout=15000)
                        logger.info(f"Reopened and loaded: {url}")
                        return True
                    except Exception as e2:
                        logger.error(f"Reopen failed: {e2}")
                        return False
            logger.error(f"Failed to open URL {url}: {e}")
            return False

    async def search_google(self, query: str) -> bool:
        """
        Perform a Google search.

        Args:
            query: Search query string.

        Returns:
            True if search succeeded.
        """
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        logger.info(f"Google search: '{query}'")
        return await self.open_url(url)

    async def search_youtube(self, query: str) -> bool:
        """
        Search YouTube for a video.

        Args:
            query: Search query string.

        Returns:
            True if search succeeded.
        """
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        logger.info(f"YouTube search: '{query}'")
        return await self.open_url(url)

    async def play_youtube(self, query: str) -> bool:
        """
        Search YouTube and click the first video result.

        Args:
            query: What to play.

        Returns:
            True if video started.
        """
        if not await self.search_youtube(query):
            return False

        try:
            # Wait for results and click first video
            await self._page.wait_for_selector(
                "ytd-video-renderer a#video-title",
                timeout=8000,
            )
            first_video = self._page.locator("ytd-video-renderer a#video-title").first
            await first_video.click()
            logger.info(f"Playing first YouTube result for: '{query}'")
            return True

        except Exception as e:
            logger.warning(f"Could not click first video: {e}")
            return True  # Search page still opened

    async def get_page_text(self, max_chars: int = 2000) -> str:
        """
        Extract visible text from the current page.
        Useful for reading articles or search results.

        Args:
            max_chars: Maximum characters to return.

        Returns:
            Page text content.
        """
        if not self._page:
            return ""

        try:
            text = await self._page.evaluate(
                "() => document.body.innerText"
            )
            return text[:max_chars] if text else ""
        except Exception as e:
            logger.error(f"Failed to get page text: {e}")
            return ""

    async def click_element(self, selector: str) -> bool:
        """
        Click an element on the current page.

        Args:
            selector: CSS selector or text to click.

        Returns:
            True if click succeeded.
        """
        if not self._page:
            return False

        try:
            await self._page.click(selector, timeout=5000)
            return True
        except Exception as e:
            logger.error(f"Click failed for '{selector}': {e}")
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        """
        Type text into an input field.

        Args:
            selector: CSS selector for the input.
            text: Text to type.

        Returns:
            True if typing succeeded.
        """
        if not self._page:
            return False

        try:
            await self._page.fill(selector, text)
            return True
        except Exception as e:
            logger.error(f"Type failed for '{selector}': {e}")
            return False

    async def get_current_url(self) -> str:
        """Return the current page URL."""
        if self._page:
            return self._page.url
        return ""

    async def get_current_title(self) -> str:
        """Return the current page title."""
        if self._page:
            try:
                return await self._page.title()
            except Exception:
                pass
        return ""

    async def go_back(self) -> bool:
        """Navigate back in browser history."""
        if self._page:
            try:
                await self._page.go_back()
                return True
            except Exception:
                pass
        return False

    async def close(self) -> None:
        """Close the browser and clean up."""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.debug(f"Browser close error: {e}")
        finally:
            self._initialized = False
            self._available = False
            self._page = None
            self._context = None
            self._browser = None
            self._playwright = None
            logger.info("Browser closed")

    async def _ensure_ready(self) -> bool:
        """Ensure browser is initialized, launching if needed."""
        if not self._initialized or self._page is None:
            return await self.initialize()
        try:
            # Check if page is still alive
            _ = self._page.url
            return True
        except Exception:
            logger.warning("Page is dead — reinitializing browser")
            self._initialized = False
            self._page = None
            self._context = None
            self._browser = None
            return await self.initialize()

    @property
    def is_available(self) -> bool:
        return self._available

    def __repr__(self) -> str:
        return f"PlaywrightController(initialized={self._initialized}, headless={self.headless})"

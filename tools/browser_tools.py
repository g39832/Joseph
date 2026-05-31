"""
tools/browser_tools.py
-----------------------
Browser automation tools for JOSEPH.

Provides URL navigation, web search, YouTube search/play,
webpage reading with text extraction, and screenshot capture.
"""

import logging
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from configs.settings import settings
from tools.registry import ToolResult

logger = logging.getLogger(__name__)


class BrowserTools:
    """
    Browser automation tools.

    Supports:
      - Opening URLs in the default browser
      - Google search
      - YouTube search and playback
      - Webpage content extraction via requests
      - Screenshot capture via Playwright
    """

    def __init__(self, playwright_page=None, loop=None):
        self._page = playwright_page
        self._loop = loop
        self._browser_log: list[dict] = []

    def open_url(self, url: str) -> ToolResult:
        """
        Open a URL in the default web browser.

        Args:
            url: The URL to open.

        Returns:
            ToolResult with status.
        """
        if not url:
            return ToolResult(
                success=False, output="",
                error="No URL provided.",
            )

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            webbrowser.open(url)
            self._log_action("open_url", url)
            return ToolResult(success=True, output=f"Opened: {url}")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Could not open URL: {e}",
            )

    def search_web(self, query: str) -> ToolResult:
        """
        Perform a Google search in the default browser.

        Args:
            query: Search query string.

        Returns:
            ToolResult with status.
        """
        if not query:
            return ToolResult(
                success=False, output="",
                error="No search query provided.",
            )

        url = f"https://www.google.com/search?q={quote_plus(query)}"
        try:
            webbrowser.open(url)
            self._log_action("search_web", query)
            return ToolResult(success=True, output=f"Searching for '{query}'.")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Search error: {e}",
            )

    def search_youtube(self, query: str) -> ToolResult:
        """
        Search YouTube in the default browser.

        Args:
            query: Search query.

        Returns:
            ToolResult with status.
        """
        if not query:
            return ToolResult(
                success=False, output="",
                error="No search query provided.",
            )

        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        try:
            webbrowser.open(url)
            self._log_action("search_youtube", query)
            return ToolResult(success=True, output=f"Searching YouTube for '{query}'.")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"YouTube search error: {e}",
            )

    def play_youtube(self, query: str) -> ToolResult:
        """
        Search and play the first YouTube result.

        Uses Playwright if available, otherwise opens in browser.

        Args:
            query: Video name or search query.

        Returns:
            ToolResult with status.
        """
        if not query:
            return ToolResult(
                success=False, output="",
                error="No search query provided.",
            )

        if self._page and self._loop:
            try:
                self._loop.run_until_complete(
                    self._play_youtube_playwright(query)
                )
                self._log_action("play_youtube", query)
                return ToolResult(success=True, output=f"Playing '{query}'.")
            except Exception as e:
                logger.warning(f"Playwright playback failed, falling back: {e}")

        url = (
            f"https://www.youtube.com/results?search_query="
            f"{quote_plus(query)}"
        )
        try:
            webbrowser.open(url)
            self._log_action("play_youtube", query)
            return ToolResult(success=True, output=f"Showing YouTube results for '{query}'.")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"YouTube error: {e}",
            )

    async def _play_youtube_playwright(self, query: str) -> None:
        """Internal Playwright-based YouTube playback."""
        search_url = (
            f"https://www.youtube.com/results?search_query="
            f"{quote_plus(query)}"
        )
        await self._page.goto(search_url)
        await self._page.wait_for_timeout(3000)
        first_video = await self._page.query_selector("a#video-title")
        if first_video:
            await first_video.click()
            await self._page.wait_for_timeout(2000)

    def read_webpage(self, url: str, max_chars: int = 3000) -> ToolResult:
        """
        Fetch a webpage and extract readable text content.

        Strips HTML tags, scripts, and styles.
        Returns clean text suitable for LLM consumption.

        Args:
            url: The URL to fetch.
            max_chars: Maximum characters to return.

        Returns:
            ToolResult with extracted text.
        """
        if not url:
            return ToolResult(
                success=False, output="",
                error="No URL provided.",
            )

        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        try:
            import requests
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts: list[str] = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer", "header", "noscript"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer", "header", "noscript"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self.text_parts.append(data.strip())

            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.5",
            }

            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            parser = TextExtractor()
            parser.feed(resp.text)
            raw_text = " ".join(parser.text_parts)

            import re
            raw_text = re.sub(r'\s+', ' ', raw_text).strip()

            if not raw_text:
                return ToolResult(
                    success=True,
                    output="Page appears to have no extractable text content.",
                )

            if len(raw_text) > max_chars:
                raw_text = raw_text[:max_chars] + "\n\n[truncated]"

            content = f"Content from {url}:\n\n{raw_text}"
            self._log_action("read_webpage", url)
            return ToolResult(success=True, output=content)

        except requests.Timeout:
            return ToolResult(
                success=False, output="",
                error=f"Timeout fetching {url}",
            )
        except requests.RequestException as e:
            return ToolResult(
                success=False, output="",
                error=f"HTTP error fetching {url}: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="",
                error=f"Page read error: {e}",
            )

    def take_screenshot(self) -> ToolResult:
        """
        Take a screenshot of the browser page via Playwright.

        Returns:
            ToolResult with path to saved screenshot.
        """
        if not self._page:
            return ToolResult(
                success=False, output="",
                error="Playwright page not available.",
            )

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            path = settings.EXPORTS_DIR / f"browser_screenshot_{timestamp}.png"
            path.parent.mkdir(parents=True, exist_ok=True)

            self._loop.run_until_complete(
                self._page.screenshot(path=str(path))
            )

            return ToolResult(
                success=True,
                output=f"Browser screenshot saved: {path}",
            )

        except Exception as e:
            return ToolResult(
                success=False, output="",
                error=f"Browser screenshot error: {e}",
            )

    def get_page_title(self) -> ToolResult:
        """
        Get the current page title from Playwright.

        Returns:
            ToolResult with page title.
        """
        if not self._page:
            return ToolResult(
                success=False, output="",
                error="Playwright page not available.",
            )

        try:
            title = self._loop.run_until_complete(self._page.title())
            return ToolResult(success=True, output=title or "(no title)")
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Title error: {e}",
            )

    def _log_action(self, action: str, target: str) -> None:
        self._browser_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "target": target,
        })

    def get_browser_log(self, limit: int = 20) -> list[dict]:
        return self._browser_log[-limit:]

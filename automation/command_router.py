"""
automation/command_router.py
-----------------------------
LLM-powered command router for JOSEPH.

Uses the LLM to understand what the user wants, then executes it.
This means ANY phrasing works — not just rigid patterns.

Examples that all work:
  "yo open up YouTube"
  "can you pull up YouTube for me"
  "I want to watch something on YouTube"
  "search the web for Python tutorials"
  "look up the weather"
  "open my notes app"
  "launch Spotify"
  "take a screenshot real quick"
"""

import asyncio
import json
import logging
import re
from typing import Optional
from urllib.parse import quote_plus

from configs.settings import settings

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Fast pre-check patterns (avoid LLM call for obvious commands)
# ------------------------------------------------------------------ #

QUICK_BROWSER = re.compile(
    r"\b(open|go to|launch|pull up|bring up|show me|navigate to)\b.{0,30}"
    r"\b(youtube|google|reddit|twitter|github|netflix|spotify|twitch|"
    r"instagram|facebook|amazon|wikipedia|gmail|discord|twitch|x\.com)\b",
    re.IGNORECASE,
)

QUICK_SEARCH = re.compile(
    r"\b(search|look up|google|find|search for|look for)\b",
    re.IGNORECASE,
)

QUICK_DESKTOP = re.compile(
    r"\b(open|launch|start|run)\b.{0,20}"
    r"\b(notepad|calculator|paint|chrome|firefox|edge|spotify|discord|"
    r"vscode|vs code|visual studio|word|excel|powerpoint|terminal|"
    r"powershell|cmd|file explorer|settings|task manager|zoom|teams|slack)\b",
    re.IGNORECASE,
)

QUICK_SCREENSHOT = re.compile(
    r"\b(screenshot|screen shot|capture screen|take a picture of the screen)\b",
    re.IGNORECASE,
)

QUICK_CLIPBOARD = re.compile(
    r"\b(clipboard|what.s copied|what did i copy|read clipboard)\b",
    re.IGNORECASE,
)

# ------------------------------------------------------------------ #
# Site map
# ------------------------------------------------------------------ #

SITE_MAP = {
    "youtube":       "https://youtube.com",
    "google":        "https://google.com",
    "reddit":        "https://reddit.com",
    "twitter":       "https://twitter.com",
    "x":             "https://x.com",
    "github":        "https://github.com",
    "netflix":       "https://netflix.com",
    "spotify":       "https://open.spotify.com",
    "twitch":        "https://twitch.tv",
    "instagram":     "https://instagram.com",
    "facebook":      "https://facebook.com",
    "gmail":         "https://mail.google.com",
    "drive":         "https://drive.google.com",
    "docs":          "https://docs.google.com",
    "amazon":        "https://amazon.com",
    "wikipedia":     "https://wikipedia.org",
    "stackoverflow": "https://stackoverflow.com",
    "discord":       "https://discord.com",
    "chatgpt":       "https://chat.openai.com",
    "claude":        "https://claude.ai",
    "outlook":       "https://outlook.live.com",
    "linkedin":      "https://linkedin.com",
}

# ------------------------------------------------------------------ #
# LLM extraction prompt
# ------------------------------------------------------------------ #

EXTRACTION_PROMPT = """You are a command parser for an AI assistant. 
Analyze the user's request and extract the action they want.

Respond with ONLY a JSON object, no explanation, no markdown.

JSON format:
{
  "type": "BROWSER_OPEN" | "BROWSER_SEARCH" | "YOUTUBE_SEARCH" | "YOUTUBE_PLAY" | "DESKTOP_OPEN" | "SCREENSHOT" | "CLIPBOARD_READ" | "NONE",
  "target": "the website name, search query, app name, or null",
  "url": "full URL if applicable or null"
}

Examples:
User: "open YouTube" → {"type": "BROWSER_OPEN", "target": "youtube", "url": "https://youtube.com"}
User: "search for Python tutorials" → {"type": "BROWSER_SEARCH", "target": "Python tutorials", "url": null}
User: "play lofi music on YouTube" → {"type": "YOUTUBE_PLAY", "target": "lofi music", "url": null}
User: "open Notepad" → {"type": "DESKTOP_OPEN", "target": "notepad", "url": null}
User: "take a screenshot" → {"type": "SCREENSHOT", "target": null, "url": null}
User: "what's on my clipboard" → {"type": "CLIPBOARD_READ", "target": null, "url": null}
User: "how are you doing?" → {"type": "NONE", "target": null, "url": null}
User: "what time is it?" → {"type": "NONE", "target": null, "url": null}

User request: "{user_input}"
JSON:"""


class CommandRouter:
    """
    Routes user commands to automation handlers.
    Uses fast regex for obvious commands, LLM for ambiguous ones.
    """

    def __init__(self, llm=None):
        from automation.browser.playwright_controller import PlaywrightController
        from automation.desktop.app_control import AppController
        from automation.desktop.mouse_keyboard import MouseKeyboardController

        self.browser = PlaywrightController(headless=False)
        self.app_ctrl = AppController()
        self.mouse_kb = MouseKeyboardController()
        self._llm = llm  # Optional — used for smart parsing
        self._loop = asyncio.new_event_loop()

    def set_llm(self, llm) -> None:
        """Attach the LLM interface for smart command parsing."""
        self._llm = llm

    def handle_sync(self, user_input: str) -> tuple[str, bool]:
        """
        Synchronous wrapper — call this from non-async code.

        Returns:
            (response_text, was_automated)
        """
        try:
            return self._loop.run_until_complete(self.handle(user_input))
        except Exception as e:
            logger.error(f"Router sync error: {e}")
            return "", False

    async def handle(self, user_input: str) -> tuple[str, bool]:
        """
        Main entry point. Parse and execute a user command.

        Returns:
            (response_text, was_automated)
        """
        # Step 1: Fast regex pre-check
        result = await self._fast_check(user_input)
        if result[1]:  # was_automated
            return result

        # Step 2: LLM-powered parsing for ambiguous commands
        if self._llm:
            result = await self._llm_parse_and_execute(user_input)
            if result[1]:
                return result

        return "", False

    # ------------------------------------------------------------------ #
    # Fast regex checks
    # ------------------------------------------------------------------ #

    async def _fast_check(self, text: str) -> tuple[str, bool]:
        """Quick pattern matching for obvious commands."""

        # Screenshot
        if QUICK_SCREENSHOT.search(text):
            path = self.app_ctrl.take_screenshot()
            return (f"Screenshot saved.", True) if path else ("Screenshot failed.", True)

        # Clipboard
        if QUICK_CLIPBOARD.search(text):
            content = self.app_ctrl.read_clipboard()
            if content:
                preview = content[:300] + "..." if len(content) > 300 else content
                return f"Your clipboard contains:\n{preview}", True
            return "Your clipboard is empty.", True

        # Open known website
        match = QUICK_BROWSER.search(text)
        if match:
            site_word = match.group(2).lower().replace(".", "")
            url = SITE_MAP.get(site_word)
            if url:
                success = await self.browser.open_url(url)
                if success:
                    return f"Opening {site_word.capitalize()}.", True

        # YouTube play/search
        text_lower = text.lower()
        if "youtube" in text_lower:
            if any(w in text_lower for w in ["play", "watch", "put on", "start"]):
                query = self._strip_youtube_words(text)
                if query:
                    await self.browser.play_youtube(query)
                    return f"Playing '{query}' on YouTube.", True
            elif any(w in text_lower for w in ["search", "find", "look up"]):
                query = self._strip_youtube_words(text)
                if query:
                    await self.browser.search_youtube(query)
                    return f"Searching YouTube for '{query}'.", True

        # Google search
        if QUICK_SEARCH.search(text) and "youtube" not in text_lower:
            query = self._extract_search_query(text)
            if query and len(query) > 2:
                await self.browser.search_google(query)
                return f"Searching for '{query}'.", True

        # Open desktop app
        match = QUICK_DESKTOP.search(text)
        if match:
            app_name = match.group(2).strip()
            success, msg = self.app_ctrl.open_app(app_name)
            return msg, True

        return "", False

    # ------------------------------------------------------------------ #
    # LLM-powered parsing
    # ------------------------------------------------------------------ #

    async def _llm_parse_and_execute(self, user_input: str) -> tuple[str, bool]:
        """
        Use the LLM to understand ambiguous commands.
        Only called when fast regex didn't match.
        """
        try:
            prompt = EXTRACTION_PROMPT.replace("{user_input}", user_input)
            raw = self._llm.generate(prompt, temperature=0.0)

            # Extract JSON from response
            json_match = re.search(r'\{.*\}', raw, re.DOTALL)
            if not json_match:
                return "", False

            data = json.loads(json_match.group())
            cmd_type = data.get("type", "NONE")
            target = data.get("target") or ""
            url = data.get("url") or ""

            logger.info(f"LLM parsed command: type={cmd_type}, target={target}")

            if cmd_type == "NONE":
                return "", False

            elif cmd_type == "BROWSER_OPEN":
                # Check site map first
                target_lower = target.lower()
                site_url = SITE_MAP.get(target_lower) or url
                if not site_url:
                    # Try to construct URL
                    site_url = f"https://{target_lower}.com"
                success = await self.browser.open_url(site_url)
                return f"Opening {target}.", True

            elif cmd_type == "BROWSER_SEARCH":
                await self.browser.search_google(target)
                return f"Searching for '{target}'.", True

            elif cmd_type == "YOUTUBE_SEARCH":
                await self.browser.search_youtube(target)
                return f"Searching YouTube for '{target}'.", True

            elif cmd_type == "YOUTUBE_PLAY":
                await self.browser.play_youtube(target)
                return f"Playing '{target}' on YouTube.", True

            elif cmd_type == "DESKTOP_OPEN":
                success, msg = self.app_ctrl.open_app(target)
                return msg, True

            elif cmd_type == "SCREENSHOT":
                path = self.app_ctrl.take_screenshot()
                return "Screenshot saved.", True

            elif cmd_type == "CLIPBOARD_READ":
                content = self.app_ctrl.read_clipboard()
                return f"Clipboard: {content[:200]}" if content else "Clipboard is empty.", True

        except json.JSONDecodeError as e:
            logger.debug(f"LLM JSON parse error: {e} — raw: {raw[:100]}")
        except Exception as e:
            logger.debug(f"LLM parse error: {e}")

        return "", False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _extract_search_query(self, text: str) -> str:
        """Extract clean search query from text."""
        # Remove command words
        cleaned = re.sub(
            r"^(search|look up|google|find|search for|look for|can you search|"
            r"please search|search the web for|search online for)\s+",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        )
        return cleaned.strip().rstrip(".,!?")

    def _strip_youtube_words(self, text: str) -> str:
        """Remove YouTube command words to get the actual query."""
        cleaned = re.sub(
            r"\b(play|watch|search|find|look up|on youtube|youtube|"
            r"put on|start|open|for me|please|can you|could you)\b",
            "",
            text,
            flags=re.IGNORECASE,
        )
        return re.sub(r"\s+", " ", cleaned).strip().rstrip(".,!?")

    async def close(self) -> None:
        """Clean up resources."""
        await self.browser.close()
        try:
            self._loop.close()
        except Exception:
            pass

    def __repr__(self) -> str:
        return f"CommandRouter(llm={'yes' if self._llm else 'no'})"

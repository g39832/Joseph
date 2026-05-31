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

QUICK_WEATHER = re.compile(
    r"\b(weather|temperature|forecast|how.s outside|what.s it like outside|"
    r"is it (hot|cold|raining|sunny|cloudy))\b",
    re.IGNORECASE,
)

QUICK_REMINDER = re.compile(
    r"\b(remind me|set a reminder|reminder|alert me|notify me)\b",
    re.IGNORECASE,
)

QUICK_NOTE = re.compile(
    r"\b(add (to my |a )?note|save (a )?note|note (that|this|down)|"
    r"write (this |that |it )?down|jot (this |that )?down)\b",
    re.IGNORECASE,
)

QUICK_TASK = re.compile(
    r"\b(add (a )?task|new task|add to (my )?task|todo|to.do|"
    r"add to (my )?list|put on (my )?list)\b",
    re.IGNORECASE,
)

QUICK_BRIEFING = re.compile(
    r"\b(briefing|morning briefing|daily briefing|give me (a |my )?(briefing|update|summary)|"
    r"what.s (going on|happening|my day look like))\b",
    re.IGNORECASE,
)

QUICK_TASKS_LIST = re.compile(
    r"\b(my tasks|task list|what.s on my (list|tasks)|show (my )?tasks|"
    r"pending tasks|what do i (need to do|have to do))\b",
    re.IGNORECASE,
)

QUICK_NOTES_LIST = re.compile(
    r"\b(my notes|show (my )?notes|what.s in my notes|read (my )?notes)\b",
    re.IGNORECASE,
)

QUICK_RESEARCH = re.compile(
    r"\b(research|learn about|tell me about|explain|what is|what are|"
    r"how does|how do|how to|find information on|look into|"
    r"give me information on|i want to know about|"
    r"teach me about|educate me on|"
    r"background on|more about|"
    r"find out about|can you research|can you look up|"
    r"i.d like to know|i want to learn)\b",
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
  "type": "BROWSER_OPEN" | "BROWSER_SEARCH" | "RESEARCH" | "YOUTUBE_SEARCH" | "YOUTUBE_PLAY" | "DESKTOP_OPEN" | "SCREENSHOT" | "CLIPBOARD_READ" | "NONE",
  "target": "the website name, search query, app name, or null",
  "url": "full URL if applicable or null"
}

Examples:
User: "open YouTube" → {"type": "BROWSER_OPEN", "target": "youtube", "url": "https://youtube.com"}
User: "search the web for Python tutorials" → {"type": "BROWSER_SEARCH", "target": "Python tutorials", "url": null}
User: "research quantum computing" → {"type": "RESEARCH", "target": "quantum computing", "url": null}
User: "tell me about machine learning" → {"type": "RESEARCH", "target": "machine learning", "url": null}
User: "learn about the Roman Empire" → {"type": "RESEARCH", "target": "the Roman Empire", "url": null}
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

        # Phase 5 services (injected after init)
        self.weather = None
        self.notes = None
        self.scheduler = None
        self.briefing = None

        # Phase 9: Background research engine
        self.background_research = None

    def attach_background_research(self, engine):
        """Attach the background research engine."""
        self.background_research = engine

    def attach_services(self, weather=None, notes=None, scheduler=None, briefing=None):
        """Attach Phase 5 services to the router."""
        if weather: self.weather = weather
        if notes: self.notes = notes
        if scheduler: self.scheduler = scheduler
        if briefing: self.briefing = briefing

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

        # Weather
        if QUICK_WEATHER.search(text):
            if self.weather:
                summary = self.weather.get_summary()
                return summary, True
            return "Weather service not available.", True

        # Briefing
        if QUICK_BRIEFING.search(text):
            if self.briefing:
                briefing_text = self.briefing.generate()
                return briefing_text, True
            return "Briefing system not ready.", True

        # Add note
        if QUICK_NOTE.search(text):
            if self.notes:
                content = self._extract_note_content(text)
                if content:
                    self.notes.add_note(content)
                    return f"Note saved: {content}", True
            return "Notes not available.", True

        # Add task
        if QUICK_TASK.search(text):
            if self.notes:
                content = self._extract_task_content(text)
                if content:
                    self.notes.add_task(content)
                    return f"Task added: {content}", True
            return "Tasks not available.", True

        # Show tasks
        if QUICK_TASKS_LIST.search(text):
            if self.notes:
                tasks = self.notes.get_pending_tasks()
                return self.notes.format_tasks(tasks), True
            return "Tasks not available.", True

        # Show notes
        if QUICK_NOTES_LIST.search(text):
            if self.notes:
                note_list = self.notes.get_recent_notes(limit=5)
                return self.notes.format_notes(note_list), True
            return "Notes not available.", True

        # Set reminder
        if QUICK_REMINDER.search(text):
            if self.scheduler:
                result = self._parse_and_set_reminder(text)
                return result, True
            return "Scheduler not available.", True

        # Screenshot
        if QUICK_SCREENSHOT.search(text):
            path = self.app_ctrl.take_screenshot()
            return ("Screenshot saved.", True) if path else ("Screenshot failed.", True)

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

        # Google search (visible browser)
        if QUICK_SEARCH.search(text) and "youtube" not in text.lower():
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

            elif cmd_type == "RESEARCH":
                if self.background_research and target:
                    self.background_research.research(target)
                    return f"Researching '{target}' in the background.", True
                return f"I'll look into '{target}' for you.", True

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

    def _extract_note_content(self, text: str) -> str:
        """Extract note content from command."""
        cleaned = re.sub(
            r"^(add (to my |a )?note(s)?|save (a )?note|note (that|this|down)|"
            r"write (this |that |it )?down|jot (this |that )?down)[:\s]*",
            "", text.strip(), flags=re.IGNORECASE,
        )
        return cleaned.strip().strip('"\'')

    def _extract_task_content(self, text: str) -> str:
        """Extract task content from command."""
        cleaned = re.sub(
            r"^(add (a )?task|new task|add to (my )?task(s)?|todo|"
            r"add to (my )?list|put on (my )?list)[:\s]*",
            "", text.strip(), flags=re.IGNORECASE,
        )
        return cleaned.strip().strip('"\'')

    def _parse_and_set_reminder(self, text: str) -> str:
        """Parse a reminder command and schedule it."""
        import re as _re
        # Extract time
        time_match = _re.search(
            r"at (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            text, _re.IGNORECASE
        )
        minutes_match = _re.search(r"in (\d+) minutes?", text, _re.IGNORECASE)
        hours_match = _re.search(r"in (\d+) hours?", text, _re.IGNORECASE)

        # Extract message
        msg = _re.sub(
            r"remind me|set a reminder|reminder|alert me|notify me|"
            r"at \d{1,2}(?::\d{2})?\s*(?:am|pm)?|in \d+ (minutes?|hours?)|"
            r"to |that ",
            "", text, flags=_re.IGNORECASE
        ).strip().strip(".,")

        if not msg:
            msg = "Reminder"

        if time_match:
            job_id = self.scheduler.add_reminder(msg, at_time=time_match.group(1))
            if job_id:
                return f"Reminder set: '{msg}' at {time_match.group(1)}."
        elif minutes_match:
            mins = int(minutes_match.group(1))
            job_id = self.scheduler.add_reminder(msg, in_minutes=mins)
            if job_id:
                return f"Reminder set: '{msg}' in {mins} minutes."
        elif hours_match:
            hrs = int(hours_match.group(1))
            job_id = self.scheduler.add_reminder(msg, in_hours=hrs)
            if job_id:
                return f"Reminder set: '{msg}' in {hrs} hours."
        else:
            return "When should I remind you? Say something like 'remind me at 3pm to call John'."

        return "Reminder could not be set."

    def _extract_research_query(self, text: str) -> str:
        """Extract research query from natural language."""
        cleaned = re.sub(
            r"^(research|learn about|tell me about|explain|what is|what are|"
            r"how does|how do|how to|find information on|look into|"
            r"give me information on|i want to know about|"
            r"teach me about|educate me on|"
            r"background on|more about|"
            r"find out about|can you research|can you look up|"
            r"i.d like to know|i want to learn)\s+",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        )
        return cleaned.strip().rstrip(".,!?")

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

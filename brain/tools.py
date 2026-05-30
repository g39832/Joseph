"""
brain/tools.py
---------------
Tool use system for JOSEPH.

Instead of rigid pattern matching, Joseph now uses the LLM to decide
which tool to call and with what parameters. This means any phrasing works.

Available tools:
  - open_website      : Open a URL in the browser
  - search_web        : Google search
  - search_youtube    : YouTube search
  - play_youtube      : Play first YouTube result
  - open_app          : Launch a desktop application
  - take_screenshot   : Capture the screen
  - read_clipboard    : Read clipboard content
  - get_weather       : Get current weather
  - add_note          : Save a note
  - add_task          : Add a task
  - get_tasks         : List pending tasks
  - get_notes         : List recent notes
  - set_reminder      : Schedule a reminder
  - get_briefing      : Generate daily briefing
  - read_webpage      : Fetch and summarize a webpage
  - run_python        : Execute Python code safely
  - web_search_read   : Search and read top result

The LLM returns a JSON tool call, Joseph executes it.
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Tool definitions — shown to the LLM so it knows what's available
# ------------------------------------------------------------------ #

TOOL_DEFINITIONS = """
Available tools (respond with JSON only):

1. open_website: {"tool": "open_website", "url": "https://..."}
2. search_web: {"tool": "search_web", "query": "search terms"}
3. search_youtube: {"tool": "search_youtube", "query": "search terms"}
4. play_youtube: {"tool": "play_youtube", "query": "song or video name"}
5. open_app: {"tool": "open_app", "app": "notepad|chrome|spotify|calculator|..."}
6. take_screenshot: {"tool": "take_screenshot"}
7. read_clipboard: {"tool": "read_clipboard"}
8. get_weather: {"tool": "get_weather"}
9. add_note: {"tool": "add_note", "content": "note text"}
10. add_task: {"tool": "add_task", "title": "task description"}
11. get_tasks: {"tool": "get_tasks"}
12. get_notes: {"tool": "get_notes"}
13. set_reminder: {"tool": "set_reminder", "message": "reminder text", "time": "3pm|in 30 minutes|in 2 hours"}
14. get_briefing: {"tool": "get_briefing"}
15. read_webpage: {"tool": "read_webpage", "url": "https://..."}
16. run_python: {"tool": "run_python", "code": "print('hello')"}
17. read_file: {"tool": "read_file", "path": "~/Desktop/notes.txt"}
18. list_files: {"tool": "list_files", "directory": "~/Desktop"}
19. create_file: {"tool": "create_file", "path": "~/Desktop/note.txt", "content": "text here"}
20. search_files: {"tool": "search_files", "query": "filename or content", "directory": "~/Desktop"}
21. describe_screen: {"tool": "describe_screen"}
22. ask_screen: {"tool": "ask_screen", "question": "what app is open?"}
23. autonomous_goal: {"tool": "autonomous_goal", "goal": "complex multi-step goal description"}
24. get_calendar: {"tool": "get_calendar"}
25. get_emails: {"tool": "get_emails"}
26. spotify_play: {"tool": "spotify_play", "query": "song or artist name"}
27. spotify_pause: {"tool": "spotify_pause"}
28. spotify_next: {"tool": "spotify_next"}
29. spotify_status: {"tool": "spotify_status"}
30. start_focus: {"tool": "start_focus", "minutes": 25, "music": "lofi"}
31. stop_focus: {"tool": "stop_focus"}
32. focus_status: {"tool": "focus_status"}
33. email_triage: {"tool": "email_triage"}
34. none: {"tool": "none"}

If the user's request doesn't need a tool (just conversation), use: {"tool": "none"}
"""

TOOL_PROMPT = """You are a tool dispatcher. Analyze the user's request and output the correct tool call as JSON.
Output ONLY the JSON object, nothing else.

{tool_definitions}

User request: "{user_input}"

JSON tool call:"""


class ToolDispatcher:
    """
    Uses the LLM to intelligently dispatch tool calls.

    This replaces rigid regex matching with LLM understanding.
    Any phrasing works — the LLM figures out the intent.

    Usage:
        dispatcher = ToolDispatcher(llm=llm)
        dispatcher.attach_services(weather=w, notes=n, ...)
        result = dispatcher.dispatch("yo can you open youtube for me")
    """

    def __init__(self, llm=None):
        self._llm = llm
        self.weather = None
        self.notes = None
        self.scheduler = None
        self.briefing = None
        self.browser = None
        self.app_ctrl = None
        self._browser_loop = None
        # Phase 7
        self.file_manager = None
        self.vision = None
        self.autonomous_agent = None
        # Phase 8
        self.google = None
        # Phase 11
        self.spotify = None
        self.focus_mode = None
        self.email_triage = None
        # Tier 2 — structured output + confidence
        self._structured_output = None
        self._confidence_scorer = None

    def attach_llm(self, llm) -> None:
        self._llm = llm
        # Initialize structured output when LLM is attached
        if self._structured_output is None:
            from brain.structured_output import StructuredOutput
            self._structured_output = StructuredOutput(llm=llm)
        if self._confidence_scorer is None:
            from brain.confidence import ConfidenceScorer
            self._confidence_scorer = ConfidenceScorer()

    def attach_llm(self, llm) -> None:
        self._llm = llm

    def attach_services(self, **kwargs) -> None:
        """Attach all services at once."""
        for key, val in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, val)

    def attach_browser(self, browser, loop) -> None:
        self.browser = browser
        self._browser_loop = loop

    def dispatch(self, user_input: str) -> tuple[str, bool]:
        """
        Parse user input and execute the appropriate tool.
        Uses confidence scoring — asks for clarification if unsure.
        """
        if not self._llm:
            return "", False

        try:
            # Confidence check before executing
            if self._confidence_scorer:
                should_exec, conf, reason = self._confidence_scorer.should_execute(user_input)
                if not should_exec and conf < 40:
                    # Very low confidence — don't even try automation
                    logger.debug(f"Skipping automation (confidence={conf}%): {user_input[:40]}")
                    return "", False

            # Try structured output first (more reliable)
            if self._structured_output:
                tool_call = self._structured_output.extract_tool_call(user_input)
                if tool_call and tool_call.get("tool") != "none":
                    logger.info(f"Structured tool call: {tool_call}")
                    return self._execute_tool(tool_call)

            # Fall back to regex-based parsing
            tool_call = self._parse_tool_call(user_input)
            if not tool_call or tool_call.get("tool") == "none":
                return "", False

            return self._execute_tool(tool_call)

        except Exception as e:
            logger.error(f"Tool dispatch error: {e}")
            return "", False

    def _parse_tool_call(self, user_input: str) -> Optional[dict]:
        """Use LLM to parse the user input into a tool call."""
        try:
            prompt = TOOL_PROMPT.format(
                tool_definitions=TOOL_DEFINITIONS,
                user_input=user_input,
            )
            raw = self._llm.generate(prompt, temperature=0.0)

            # Extract JSON
            json_match = re.search(r'\{[^{}]*\}', raw, re.DOTALL)
            if not json_match:
                logger.debug(f"No JSON found in tool response: {raw[:100]}")
                return None

            tool_call = json.loads(json_match.group())
            logger.info(f"Tool call parsed: {tool_call}")
            return tool_call

        except json.JSONDecodeError as e:
            logger.debug(f"Tool JSON parse error: {e}")
            return None
        except Exception as e:
            logger.debug(f"Tool parse error: {e}")
            return None

    def _execute_tool(self, tool_call: dict) -> tuple[str, bool]:
        """Execute a parsed tool call."""
        tool = tool_call.get("tool", "none")

        try:
            # Browser tools
            if tool == "open_website":
                return self._run_browser("open_url", tool_call.get("url", ""))

            elif tool == "search_web":
                query = tool_call.get("query", "")
                from urllib.parse import quote_plus
                url = f"https://www.google.com/search?q={quote_plus(query)}"
                self._run_browser("open_url", url)
                return f"Searching for '{query}'.", True

            elif tool == "search_youtube":
                query = tool_call.get("query", "")
                from urllib.parse import quote_plus
                url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
                self._run_browser("open_url", url)
                return f"Searching YouTube for '{query}'.", True

            elif tool == "play_youtube":
                query = tool_call.get("query", "")
                if self.browser and self._browser_loop:
                    self._browser_loop.run_until_complete(
                        self.browser.play_youtube(query)
                    )
                return f"Playing '{query}' on YouTube.", True

            # Desktop tools
            elif tool == "open_app":
                app = tool_call.get("app", "")
                if self.app_ctrl:
                    success, msg = self.app_ctrl.open_app(app)
                    return msg, True
                return f"Opening {app}.", True

            elif tool == "take_screenshot":
                if self.app_ctrl:
                    path = self.app_ctrl.take_screenshot()
                    return "Screenshot saved.", True
                return "Screenshot tool not available.", True

            elif tool == "read_clipboard":
                if self.app_ctrl:
                    content = self.app_ctrl.read_clipboard()
                    if content:
                        preview = content[:300] + "..." if len(content) > 300 else content
                        return f"Clipboard:\n{preview}", True
                    return "Clipboard is empty.", True

            # Weather
            elif tool == "get_weather":
                if self.weather:
                    return self.weather.get_summary(), True
                return "Weather service not available.", True

            # Notes & Tasks
            elif tool == "add_note":
                content = tool_call.get("content", "")
                if self.notes and content:
                    self.notes.add_note(content)
                    return f"Note saved: {content}", True
                return "Could not save note.", True

            elif tool == "add_task":
                title = tool_call.get("title", "")
                if self.notes and title:
                    self.notes.add_task(title)
                    return f"Task added: {title}", True
                return "Could not add task.", True

            elif tool == "get_tasks":
                if self.notes:
                    tasks = self.notes.get_pending_tasks()
                    return self.notes.format_tasks(tasks), True
                return "Tasks not available.", True

            elif tool == "get_notes":
                if self.notes:
                    notes = self.notes.get_recent_notes(limit=10)
                    return self.notes.format_notes(notes), True
                return "Notes not available.", True

            # Scheduler
            elif tool == "set_reminder":
                if self.scheduler:
                    msg = tool_call.get("message", "Reminder")
                    time_str = tool_call.get("time", "")
                    return self._set_reminder(msg, time_str), True
                return "Scheduler not available.", True

            # Briefing
            elif tool == "get_briefing":
                if self.briefing:
                    return self.briefing.generate(), True
                return "Briefing not available.", True

            # Web reading
            elif tool == "read_webpage":
                url = tool_call.get("url", "")
                return self._read_webpage(url), True

            # Code execution
            elif tool == "run_python":
                code = tool_call.get("code", "")
                return self._run_python(code), True

            # Phase 7 — File management
            elif tool == "read_file":
                path = tool_call.get("path", "")
                if self.file_manager:
                    return self.file_manager.read_file(path), True
                return "File manager not available.", True

            elif tool == "list_files":
                directory = tool_call.get("directory", "~/Desktop")
                if self.file_manager:
                    return self.file_manager.list_directory(directory), True
                return "File manager not available.", True

            elif tool == "create_file":
                path = tool_call.get("path", "")
                content = tool_call.get("content", "")
                if self.file_manager:
                    return self.file_manager.create_file(path, content), True
                return "File manager not available.", True

            elif tool == "search_files":
                query = tool_call.get("query", "")
                directory = tool_call.get("directory", "~/Desktop")
                if self.file_manager:
                    return self.file_manager.search_files(query, directory), True
                return "File manager not available.", True

            # Phase 7 — Vision
            elif tool == "describe_screen":
                if self.vision:
                    return self.vision.describe_screen(), True
                return "Vision system not available.", True

            elif tool == "ask_screen":
                question = tool_call.get("question", "What do you see?")
                if self.vision:
                    return self.vision.ask_about_screen(question), True
                return "Vision system not available.", True

            # Phase 7 — Autonomous agent
            elif tool == "autonomous_goal":
                goal = tool_call.get("goal", "")
                if self.autonomous_agent and goal:
                    return self.autonomous_agent.run(goal), True
                return "Autonomous agent not available.", True

            # Phase 8 — Google
            elif tool == "get_calendar":
                if self.google and self.google.is_available:
                    events = self.google.get_upcoming_events(days=7)
                    return self.google.format_events(events), True
                return "Google Calendar not configured. Run: python brain/google_integration.py", True

            elif tool == "get_emails":
                if self.google and self.google.is_available:
                    emails = self.google.get_recent_emails()
                    return self.google.format_emails(emails), True
                return "Gmail not configured. Run: python -m brain.google_integration", True

            # Phase 11 — Spotify
            elif tool == "spotify_play":
                if self.spotify:
                    return self.spotify.play(tool_call.get("query", "")), True
                return "Spotify not configured. Add SPOTIFY_CLIENT_ID to .env", True

            elif tool == "spotify_pause":
                if self.spotify:
                    return self.spotify.pause(), True
                return "Spotify not configured.", True

            elif tool == "spotify_next":
                if self.spotify:
                    return self.spotify.next_track(), True
                return "Spotify not configured.", True

            elif tool == "spotify_status":
                if self.spotify:
                    return self.spotify.now_playing(), True
                return "Spotify not configured.", True

            # Phase 11 — Focus Mode
            elif tool == "start_focus":
                if self.focus_mode:
                    minutes = int(tool_call.get("minutes", 25))
                    music = tool_call.get("music", "lofi")
                    return self.focus_mode.start(minutes, music), True
                return "Focus mode not available.", True

            elif tool == "stop_focus":
                if self.focus_mode:
                    return self.focus_mode.stop(), True
                return "No active focus session.", True

            elif tool == "focus_status":
                if self.focus_mode:
                    return self.focus_mode.status(), True
                return "Focus mode not available.", True

            # Phase 11 — Email Triage
            elif tool == "email_triage":
                if self.email_triage:
                    return self.email_triage.get_morning_summary(), True
                return "Email triage not available.", True

            else:
                return "", False

        except Exception as e:
            logger.error(f"Tool execution error ({tool}): {e}")
            return f"I had trouble with that: {e}", True

    def _run_browser(self, method: str, *args) -> tuple[str, bool]:
        """Run a browser method synchronously."""
        if not self.browser or not self._browser_loop:
            return "Browser not available.", True
        try:
            coro = getattr(self.browser, method)(*args)
            self._browser_loop.run_until_complete(coro)
            return f"Done.", True
        except Exception as e:
            logger.error(f"Browser error: {e}")
            return f"Browser error: {e}", True

    def _set_reminder(self, message: str, time_str: str) -> str:
        """Parse time string and set reminder."""
        import re as _re

        time_match = _re.search(
            r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            time_str, _re.IGNORECASE
        )
        minutes_match = _re.search(r"in (\d+) minutes?", time_str, _re.IGNORECASE)
        hours_match = _re.search(r"in (\d+) hours?", time_str, _re.IGNORECASE)

        if minutes_match:
            mins = int(minutes_match.group(1))
            job_id = self.scheduler.add_reminder(message, in_minutes=mins)
            if job_id:
                return f"Reminder set: '{message}' in {mins} minutes."
        elif hours_match:
            hrs = int(hours_match.group(1))
            job_id = self.scheduler.add_reminder(message, in_hours=hrs)
            if job_id:
                return f"Reminder set: '{message}' in {hrs} hours."
        elif time_match:
            job_id = self.scheduler.add_reminder(message, at_time=time_match.group(1))
            if job_id:
                return f"Reminder set: '{message}' at {time_match.group(1)}."

        return "When should I remind you? Try: 'remind me in 30 minutes to...' or 'remind me at 3pm to...'"

    def _read_webpage(self, url: str) -> str:
        """Fetch and summarize a webpage."""
        if not url:
            return "No URL provided."
        try:
            import requests
            from html.parser import HTMLParser

            class TextExtractor(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text_parts = []
                    self._skip = False

                def handle_starttag(self, tag, attrs):
                    if tag in ("script", "style", "nav", "footer", "header"):
                        self._skip = True

                def handle_endtag(self, tag):
                    if tag in ("script", "style", "nav", "footer", "header"):
                        self._skip = False

                def handle_data(self, data):
                    if not self._skip and data.strip():
                        self.text_parts.append(data.strip())

            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()

            parser = TextExtractor()
            parser.feed(resp.text)
            raw_text = " ".join(parser.text_parts)

            # Clean up whitespace
            import re
            raw_text = re.sub(r'\s+', ' ', raw_text).strip()
            raw_text = raw_text[:3000]  # Limit for LLM context

            if self._llm and raw_text:
                summary_prompt = f"""Summarize this webpage content in 3-5 sentences. Be concise and factual.

Content: {raw_text}

Summary:"""
                summary = self._llm.generate(summary_prompt, temperature=0.2)
                return f"From {url}:\n{summary}"

            return f"Page content ({len(raw_text)} chars):\n{raw_text[:500]}..."

        except Exception as e:
            logger.error(f"Webpage read error: {e}")
            return f"Could not read that page: {e}"

    def _run_python(self, code: str) -> str:
        """
        Execute Python code safely in a restricted environment.
        Only allows safe operations — no file deletion, no network calls.
        """
        if not code:
            return "No code provided."

        # Safety check — block dangerous operations
        dangerous = [
            "os.remove", "os.unlink", "shutil.rmtree", "subprocess",
            "eval(", "exec(", "__import__", "open(", "socket",
            "requests", "urllib", "http", "smtplib",
        ]
        code_lower = code.lower()
        for danger in dangerous:
            if danger.lower() in code_lower:
                return f"I can't run that code — it contains restricted operations ({danger})."

        try:
            import io
            import contextlib

            # Capture stdout
            output = io.StringIO()
            safe_globals = {
                "__builtins__": {
                    "print": print,
                    "len": len, "range": range, "enumerate": enumerate,
                    "zip": zip, "map": map, "filter": filter,
                    "list": list, "dict": dict, "set": set, "tuple": tuple,
                    "str": str, "int": int, "float": float, "bool": bool,
                    "abs": abs, "round": round, "min": min, "max": max,
                    "sum": sum, "sorted": sorted, "reversed": reversed,
                    "isinstance": isinstance, "type": type,
                    "True": True, "False": False, "None": None,
                },
                "math": __import__("math"),
                "datetime": __import__("datetime"),
                "json": __import__("json"),
                "re": __import__("re"),
            }

            with contextlib.redirect_stdout(output):
                exec(code, safe_globals)

            result = output.getvalue().strip()
            if result:
                return f"Output:\n{result}"
            return "Code ran successfully (no output)."

        except Exception as e:
            return f"Code error: {type(e).__name__}: {e}"

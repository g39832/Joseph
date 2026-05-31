"""
tools/integration.py
---------------------
Wires all tool categories into a single ToolRegistry.

Provides a factory function that registers every tool definition,
connects to existing brain services (notes, weather, etc.),
and returns a ready-to-use ToolRegistry.
"""

import logging
from typing import Any, Optional

from tools.registry import (
    ToolRegistry,
    ToolDefinition,
    ToolResult,
    SafetyLevel,
)
from tools.permission_manager import PermissionManager
from tools.file_tools import FileTools
from tools.search_tools import SearchTools
from tools.app_tools import AppTools
from tools.browser_tools import BrowserTools
from tools.terminal_tools import TerminalTools

logger = logging.getLogger(__name__)

PARAM_STRING = {"type": "string"}
PARAM_OPT_STRING = {"type": "string", "default": ""}
PARAM_INT = {"type": "integer"}
PARAM_BOOL = {"type": "boolean"}
PARAM_ANY = {}


def create_tool_registry(
    permission_manager: Optional[PermissionManager] = None,
    llm: Any = None,
    file_manager: Any = None,
    notes: Any = None,
    weather: Any = None,
    scheduler: Any = None,
    briefing: Any = None,
    browser: Any = None,
    browser_loop: Any = None,
    app_ctrl: Any = None,
    vision: Any = None,
    autonomous_agent: Any = None,
    google: Any = None,
    spotify: Any = None,
    focus_mode: Any = None,
    email_triage: Any = None,
) -> ToolRegistry:
    """
    Factory that creates and populates a ToolRegistry with all tool categories.

    Connects to existing brain services for weather, notes, scheduling, etc.
    The resulting registry is the unified tool interface for JOSEPH.

    Args:
        permission_manager: Optional PermissionManager instance.
        llm: LLM interface for AI-powered tool features.
        file_manager: FileManager instance from brain/file_manager.py.
        notes: NotesManager instance from brain/notes.py.
        weather: Weather service instance.
        scheduler: APScheduler-based scheduler.
        briefing: Briefing service.
        browser: Playwright browser instance.
        browser_loop: Async event loop for browser operations.
        app_ctrl: AppController instance from automation/desktop/app_control.py.
        vision: Vision system for screen analysis.
        autonomous_agent: Autonomous agent for multi-step goals.
        google: Google integration service.
        spotify: Spotify controller.
        focus_mode: Focus mode controller.
        email_triage: Email triage service.

    Returns:
        Configured ToolRegistry with all tools registered.
    """
    pm = permission_manager or PermissionManager()
    registry = ToolRegistry(permission_manager=pm)

    _register_file_tools(registry)
    _register_search_tools(registry)
    _register_app_tools(registry, app_ctrl)
    _register_browser_tools(registry, browser, browser_loop)
    _register_terminal_tools(registry)
    _register_brain_tools(
        registry, llm, file_manager, notes, weather, scheduler,
        briefing, vision, autonomous_agent, google,
        spotify, focus_mode, email_triage,
    )

    logger.info(
        f"Tool registry created with {len(registry.list_tools())} tools"
    )
    return registry


def _register_file_tools(registry: ToolRegistry) -> None:
    """Register file operation tools."""
    ft = FileTools()

    registry.register(ToolDefinition(
        name="read_file",
        description="Read the contents of a text file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["path"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=ft.read_file,
    ))

    registry.register(ToolDefinition(
        name="write_file",
        description="Write content to a file (creates backup for rollback)",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=ft.write_file,
        rollback_handler=ft.rollback_write,
    ))

    registry.register(ToolDefinition(
        name="move_file",
        description="Move or rename a file",
        parameters={
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source path"},
                "dst": {"type": "string", "description": "Destination path"},
            },
            "required": ["src", "dst"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=ft.move_file,
        rollback_handler=ft.rollback_move,
    ))

    registry.register(ToolDefinition(
        name="copy_file",
        description="Copy a file to a new location",
        parameters={
            "type": "object",
            "properties": {
                "src": {"type": "string", "description": "Source path"},
                "dst": {"type": "string", "description": "Destination path"},
            },
            "required": ["src", "dst"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=ft.copy_file,
    ))

    registry.register(ToolDefinition(
        name="delete_file",
        description="Move a file to backup trash (safe deletion)",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["path"],
        },
        safety_level=SafetyLevel.RESTRICTED,
        handler=ft.delete_file,
        rollback_handler=ft.rollback_delete,
    ))

    registry.register(ToolDefinition(
        name="list_directory",
        description="List files and folders in a directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
                "show_hidden": {"type": "boolean", "description": "Show hidden files", "default": False},
            },
            "required": ["path"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=ft.list_directory,
    ))

    registry.register(ToolDefinition(
        name="get_file_info",
        description="Get metadata about a file or directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file"},
            },
            "required": ["path"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=ft.get_file_info,
    ))

    registry.register(ToolDefinition(
        name="create_directory",
        description="Create a new directory",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
            },
            "required": ["path"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=ft.create_directory,
    ))


def _register_search_tools(registry: ToolRegistry) -> None:
    """Register search and indexing tools."""
    st = SearchTools()

    registry.register(ToolDefinition(
        name="search_files",
        description="Search files by name and content",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
                "directory": {"type": "string", "description": "Directory to search", "default": "."},
                "search_content": {"type": "boolean", "description": "Also search file contents", "default": True},
                "max_results": {"type": "integer", "description": "Maximum results", "default": 30},
            },
            "required": ["query"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=st.search_files,
    ))

    registry.register(ToolDefinition(
        name="grep_pattern",
        description="Search files using regular expressions",
        parameters={
            "type": "object",
            "properties": {
                "pattern": {"type": "string", "description": "Regex pattern"},
                "directory": {"type": "string", "description": "Directory to search", "default": "."},
                "file_pattern": {"type": "string", "description": "Optional file glob filter"},
                "max_results": {"type": "integer", "description": "Maximum results", "default": 50},
            },
            "required": ["pattern"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=st.grep_pattern,
    ))

    registry.register(ToolDefinition(
        name="find_by_type",
        description="Find files by extension type",
        parameters={
            "type": "object",
            "properties": {
                "extension": {"type": "string", "description": "File extension (e.g. .py)"},
                "directory": {"type": "string", "description": "Directory to search", "default": "."},
            },
            "required": ["extension"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=st.find_by_type,
    ))

    registry.register(ToolDefinition(
        name="index_directory",
        description="Build a searchable text index of a directory",
        parameters={
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to index"},
            },
            "required": ["directory"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=st.index_directory,
    ))

    registry.register(ToolDefinition(
        name="search_index",
        description="Search the previously built file index",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term"},
            },
            "required": ["query"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=st.search_index,
    ))


def _register_app_tools(registry: ToolRegistry, app_ctrl: Any) -> None:
    """Register desktop application control tools."""
    at = AppTools()

    registry.register(ToolDefinition(
        name="launch_app",
        description="Launch a desktop application by name or path",
        parameters={
            "type": "object",
            "properties": {
                "app_name_or_path": {"type": "string", "description": "App name or executable path"},
            },
            "required": ["app_name_or_path"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=at.launch_app,
    ))

    registry.register(ToolDefinition(
        name="list_running_apps",
        description="List running application windows",
        parameters={
            "type": "object",
            "properties": {},
        },
        safety_level=SafetyLevel.SAFE,
        handler=at.list_running_apps,
    ))

    registry.register(ToolDefinition(
        name="focus_app",
        description="Bring an application window to the foreground",
        parameters={
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Window title to focus"},
            },
            "required": ["app_name"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=at.focus_app,
    ))

    registry.register(ToolDefinition(
        name="take_screenshot",
        description="Capture a screenshot of the entire screen",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Optional save path"},
            },
        },
        safety_level=SafetyLevel.SAFE,
        handler=at.take_screenshot,
    ))

    registry.register(ToolDefinition(
        name="read_clipboard",
        description="Read the current clipboard content",
        parameters={
            "type": "object",
            "properties": {},
        },
        safety_level=SafetyLevel.SAFE,
        handler=at.read_clipboard,
    ))

    registry.register(ToolDefinition(
        name="write_clipboard",
        description="Write text to the clipboard",
        parameters={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to copy"},
            },
            "required": ["text"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=at.write_clipboard,
    ))

    # Also register direct app_ctrl tools if available
    if app_ctrl:
        _register_legacy_app_tools(registry, app_ctrl)


def _register_legacy_app_tools(registry: ToolRegistry, app_ctrl: Any) -> None:
    """Register tool wrappers around the existing AppController."""
    registry.register(ToolDefinition(
        name="open_app",
        description="Open a desktop application (legacy map-based)",
        parameters={
            "type": "object",
            "properties": {
                "app": {"type": "string", "description": "Application name"},
            },
            "required": ["app"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=lambda app: _wrap_result(app_ctrl.open_app(app)),
    ))

    registry.register(ToolDefinition(
        name="get_active_window",
        description="Get information about the active window",
        parameters={
            "type": "object",
            "properties": {},
        },
        safety_level=SafetyLevel.SAFE,
        handler=lambda: ToolResult(
            success=True,
            output=str(app_ctrl.get_active_window()),
        ),
    ))


def _register_browser_tools(registry: ToolRegistry, browser: Any, browser_loop: Any) -> None:
    """Register browser automation tools."""
    bt = BrowserTools(playwright_page=browser, loop=browser_loop)

    registry.register(ToolDefinition(
        name="open_url",
        description="Open a URL in the default web browser",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to open"},
            },
            "required": ["url"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=bt.open_url,
    ))

    registry.register(ToolDefinition(
        name="search_web",
        description="Perform a Google search",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=bt.search_web,
    ))

    registry.register(ToolDefinition(
        name="search_youtube",
        description="Search YouTube",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
            },
            "required": ["query"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=bt.search_youtube,
    ))

    registry.register(ToolDefinition(
        name="play_youtube",
        description="Play the first YouTube result for a query",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Video or song name"},
            },
            "required": ["query"],
        },
        safety_level=SafetyLevel.CONFIRM,
        handler=bt.play_youtube,
    ))

    registry.register(ToolDefinition(
        name="read_webpage",
        description="Fetch and extract readable text from a webpage",
        parameters={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "The URL to read"},
            },
            "required": ["url"],
        },
        safety_level=SafetyLevel.SAFE,
        handler=bt.read_webpage,
    ))


def _register_terminal_tools(registry: ToolRegistry) -> None:
    """Register terminal execution tools."""
    tt = TerminalTools()

    registry.register(ToolDefinition(
        name="execute_command",
        description="Execute a shell command with timeout and safety checks",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "cwd": {"type": "string", "description": "Working directory"},
                "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
            },
            "required": ["command"],
        },
        safety_level=SafetyLevel.RESTRICTED,
        handler=tt.execute,
    ))

    registry.register(ToolDefinition(
        name="execute_command_with_approval",
        description="Execute a shell command with explicit user approval",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Command to execute"},
                "cwd": {"type": "string", "description": "Working directory"},
                "reason": {"type": "string", "description": "Why this command needs approval"},
            },
            "required": ["command"],
        },
        safety_level=SafetyLevel.DANGEROUS,
        handler=tt.execute_with_approval,
    ))

    registry.register(ToolDefinition(
        name="get_shell",
        description="Detect the current shell environment",
        parameters={
            "type": "object",
            "properties": {},
        },
        safety_level=SafetyLevel.SAFE,
        handler=lambda: ToolResult(success=True, output=tt.get_shell()),
    ))


def _register_brain_tools(
    registry: ToolRegistry,
    llm: Any,
    file_manager: Any,
    notes: Any,
    weather: Any,
    scheduler: Any,
    briefing: Any,
    vision: Any,
    autonomous_agent: Any,
    google: Any,
    spotify: Any,
    focus_mode: Any,
    email_triage: Any,
) -> None:
    """Register tools that bridge to existing brain services."""

    # Weather
    if weather:
        registry.register(ToolDefinition(
            name="get_weather",
            description="Get the current weather forecast",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(weather.get_summary()),
        ))

    # Notes
    if notes:
        registry.register(ToolDefinition(
            name="add_note",
            description="Save a note",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Note content"},
                },
                "required": ["content"],
            },
            safety_level=SafetyLevel.CONFIRM,
            handler=lambda content: _op_result(f"Note saved: {content}", notes.add_note(content)),
        ))

        registry.register(ToolDefinition(
            name="list_notes",
            description="List recent notes",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max notes", "default": 10},
                },
            },
            safety_level=SafetyLevel.SAFE,
            handler=lambda limit=10: _str_result(
                notes.format_notes(notes.get_recent_notes(limit=limit))
            ),
        ))

        registry.register(ToolDefinition(
            name="add_task",
            description="Add a task to the task list",
            parameters={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Task description"},
                    "priority": {"type": "integer", "description": "Priority 1-3", "default": 2},
                },
                "required": ["title"],
            },
            safety_level=SafetyLevel.CONFIRM,
            handler=lambda title, priority=2: _op_result(
                f"Task added: {title}",
                notes.add_task(title, priority=priority),
            ),
        ))

        registry.register(ToolDefinition(
            name="get_tasks",
            description="List pending tasks",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(
                notes.format_tasks(notes.get_pending_tasks())
            ),
        ))

    # Scheduler
    if scheduler:
        registry.register(ToolDefinition(
            name="set_reminder",
            description="Schedule a reminder",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Reminder text"},
                    "time": {"type": "string", "description": "Time like '3pm' or 'in 30 minutes'"},
                },
                "required": ["message", "time"],
            },
            safety_level=SafetyLevel.CONFIRM,
            handler=lambda message, time: _str_result(
                _schedule_reminder(scheduler, message, time),
            ),
        ))

    # Briefing
    if briefing:
        registry.register(ToolDefinition(
            name="get_briefing",
            description="Generate a daily briefing",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(briefing.generate()),
        ))

    # Vision
    if vision:
        registry.register(ToolDefinition(
            name="describe_screen",
            description="Describe what is on the screen",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(vision.describe_screen()),
        ))

        registry.register(ToolDefinition(
            name="ask_screen",
            description="Ask a question about the screen contents",
            parameters={
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question about the screen"},
                },
                "required": ["question"],
            },
            safety_level=SafetyLevel.SAFE,
            handler=lambda question: _str_result(
                vision.ask_about_screen(question),
            ),
        ))

    # Autonomous agent
    if autonomous_agent:
        registry.register(ToolDefinition(
            name="autonomous_goal",
            description="Execute a complex multi-step goal autonomously",
            parameters={
                "type": "object",
                "properties": {
                    "goal": {"type": "string", "description": "The goal to accomplish"},
                },
                "required": ["goal"],
            },
            safety_level=SafetyLevel.RESTRICTED,
            handler=lambda goal: _str_result(autonomous_agent.run(goal)),
        ))

    # Google
    if google:
        registry.register(ToolDefinition(
            name="get_calendar",
            description="Get upcoming calendar events",
            parameters={
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "description": "Number of days", "default": 7},
                },
            },
            safety_level=SafetyLevel.SAFE,
            handler=lambda days=7: _str_result(
                google.format_events(google.get_upcoming_events(days=days))
                if getattr(google, "is_available", True)
                else "Google Calendar not configured.",
            ),
        ))

        registry.register(ToolDefinition(
            name="get_emails",
            description="Get recent emails from Gmail",
            parameters={
                "type": "object",
                "properties": {
                    "max_results": {"type": "integer", "description": "Max emails", "default": 10},
                },
            },
            safety_level=SafetyLevel.SAFE,
            handler=lambda max_results=10: _str_result(
                google.format_emails(google.get_recent_emails(max_results=max_results))
                if getattr(google, "is_available", True)
                else "Gmail not configured.",
            ),
        ))

    # Spotify
    if spotify:
        registry.register(ToolDefinition(
            name="spotify_play",
            description="Play a song or artist on Spotify",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Song or artist name"},
                },
                "required": ["query"],
            },
            safety_level=SafetyLevel.CONFIRM,
            handler=lambda query: _str_result(spotify.play(query)),
        ))

        registry.register(ToolDefinition(
            name="spotify_pause",
            description="Pause Spotify playback",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(spotify.pause()),
        ))

        registry.register(ToolDefinition(
            name="spotify_next",
            description="Skip to next Spotify track",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(spotify.next_track()),
        ))

        registry.register(ToolDefinition(
            name="spotify_status",
            description="Get current Spotify playback status",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(spotify.now_playing()),
        ))

    # Focus mode
    if focus_mode:
        registry.register(ToolDefinition(
            name="start_focus",
            description="Start a focus session",
            parameters={
                "type": "object",
                "properties": {
                    "minutes": {"type": "integer", "description": "Session duration", "default": 25},
                    "music": {"type": "string", "description": "Music genre", "default": "lofi"},
                },
            },
            safety_level=SafetyLevel.CONFIRM,
            handler=lambda minutes=25, music="lofi": _str_result(
                focus_mode.start(minutes, music),
            ),
        ))

        registry.register(ToolDefinition(
            name="stop_focus",
            description="Stop the current focus session",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(focus_mode.stop()),
        ))

        registry.register(ToolDefinition(
            name="focus_status",
            description="Get focus session status",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(focus_mode.status()),
        ))

    # Email triage
    if email_triage:
        registry.register(ToolDefinition(
            name="email_triage",
            description="Get a morning email triage summary",
            parameters={"type": "object", "properties": {}},
            safety_level=SafetyLevel.SAFE,
            handler=lambda: _str_result(email_triage.get_morning_summary()),
        ))

    # File manager (legacy bridge)
    if file_manager:
        registry.register(ToolDefinition(
            name="legacy_list_files",
            description="List files using legacy file manager",
            parameters={
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Directory", "default": "~/Desktop"},
                },
            },
            safety_level=SafetyLevel.SAFE,
            handler=lambda directory="~/Desktop": _str_result(
                file_manager.list_directory(directory),
            ),
        ))

        registry.register(ToolDefinition(
            name="legacy_search_files",
            description="Search files using legacy file manager",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                    "directory": {"type": "string", "description": "Directory", "default": "~/Desktop"},
                },
                "required": ["query"],
            },
            safety_level=SafetyLevel.SAFE,
            handler=lambda query, directory="~/Desktop": _str_result(
                file_manager.search_files(query, directory),
            ),
        ))

    # LLM-powered run_python
    registry.register(ToolDefinition(
        name="run_python",
        description="Execute Python code safely in a restricted environment",
        parameters={
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
            },
            "required": ["code"],
        },
        safety_level=SafetyLevel.RESTRICTED,
        handler=lambda code: _str_result(_safe_run_python(code, llm)),
    ))


def _wrap_result(result: tuple) -> ToolResult:
    """Convert (success, message) tuple to ToolResult."""
    if isinstance(result, tuple) and len(result) == 2:
        return ToolResult(success=bool(result[0]), output=str(result[1]))
    return ToolResult(success=True, output=str(result))


def _str_result(value: str) -> ToolResult:
    """Wrap a string as a ToolResult."""
    return ToolResult(success=True, output=value)


def _op_result(msg: str, result) -> ToolResult:
    """Wrap an operation result as ToolResult with message."""
    return ToolResult(success=True, output=msg)


def _schedule_reminder(scheduler, message: str, time_str: str) -> str:
    """Schedule a reminder via the scheduler service."""
    import re as _re

    minutes_match = _re.search(r"in (\d+) minutes?", time_str, _re.IGNORECASE)
    hours_match = _re.search(r"in (\d+) hours?", time_str, _re.IGNORECASE)
    time_match = _re.search(
        r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
        time_str, _re.IGNORECASE,
    )

    if minutes_match:
        mins = int(minutes_match.group(1))
        job_id = scheduler.add_reminder(message, in_minutes=mins)
        if job_id:
            return f"Reminder set: '{message}' in {mins} minutes."
    elif hours_match:
        hrs = int(hours_match.group(1))
        job_id = scheduler.add_reminder(message, in_hours=hrs)
        if job_id:
            return f"Reminder set: '{message}' in {hrs} hours."
    elif time_match:
        job_id = scheduler.add_reminder(message, at_time=time_match.group(1))
        if job_id:
            return f"Reminder set: '{message}' at {time_match.group(1)}."

    return "Could not parse the time. Try: 'in 30 minutes' or 'at 3pm'"


def _safe_run_python(code: str, llm: Any = None) -> str:
    """Execute Python code in a restricted sandbox."""
    if not code:
        return "No code provided."

    dangerous = [
        "os.remove", "os.unlink", "shutil.rmtree", "subprocess",
        "eval(", "exec(", "__import__", "open(", "socket",
        "requests", "urllib", "http", "smtplib",
    ]
    code_lower = code.lower()
    for danger in dangerous:
        if danger.lower() in code_lower:
            return f"Blocked: code contains restricted operation ({danger})"

    try:
        import io
        import contextlib

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

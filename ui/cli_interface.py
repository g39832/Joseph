"""
ui/cli_interface.py
-------------------
The terminal-based chat interface for JOSEPH.

This is the primary interface for Phase 1.
It provides a rich, colored terminal experience using the 'rich' library.

Features:
- Colored output (Joseph = cyan, User = white, System = yellow)
- Streaming responses (text appears word by word)
- Timestamps on messages
- Memory status display
- Special commands (/help, /memory, /clear, /quit, etc.)
- Clean error display

Special commands (type these in chat):
  /help     — show available commands
  /memory   — show memory status
  /clear    — clear conversation history
  /facts    — show stored user facts
  /remember <text> — explicitly save a memory
  /search <query>  — search memories
  /quit     — exit Joseph
"""

import logging
import sys
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme

from configs.settings import settings

logger = logging.getLogger(__name__)

# Custom color theme for Joseph
JOSEPH_THEME = Theme(
    {
        "joseph": "bold cyan",
        "user": "bold white",
        "system": "bold yellow",
        "error": "bold red",
        "success": "bold green",
        "dim": "dim white",
        "memory": "bold magenta",
        "command": "bold blue",
    }
)


class CLIInterface:
    """
    Rich terminal interface for chatting with Joseph.

    Handles all display logic — the actual AI logic lives in
    the brain and memory modules.

    Usage:
        cli = CLIInterface()
        cli.show_welcome()
        user_input = cli.get_user_input()
        cli.show_joseph_response("Hello!")
    """

    def __init__(self):
        self.console = Console(theme=JOSEPH_THEME)
        self.show_timestamps = settings.SHOW_TIMESTAMPS
        self.show_memory_status = settings.SHOW_MEMORY_STATUS
        self.joseph_name = settings.JOSEPH_NAME
        self.user_name = settings.USER_NAME

    def show_welcome(self, memory_status: Optional[str] = None) -> None:
        """
        Display the startup banner and welcome message.

        Args:
            memory_status: Optional memory status string to display.
        """
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[joseph]  J O S E P H  [/joseph]\n"
                f"[dim]Personal AI Assistant v1.0[/dim]\n"
                f"[dim]Phase 1 — Foundation[/dim]",
                border_style="cyan",
                padding=(1, 4),
            )
        )
        self.console.print()

        if memory_status:
            self.console.print(f"[dim]{memory_status}[/dim]")
            self.console.print()

        self.console.print(
            "[dim]Type [command]/help[/command] for commands. "
            "Type [command]/quit[/command] to exit.[/dim]"
        )
        self.console.print()

    def show_joseph_response(
        self,
        text: str,
        is_streaming: bool = False,
    ) -> None:
        """
        Display Joseph's response with formatting.

        Args:
            text: The response text to display.
            is_streaming: If True, text is already being printed inline.
                          This method just adds the final newline/formatting.
        """
        if not is_streaming:
            timestamp = self._get_timestamp()
            prefix = Text()
            prefix.append(f"{self.joseph_name}", style="joseph")
            if timestamp:
                prefix.append(f" {timestamp}", style="dim")
            prefix.append(": ", style="joseph")

            self.console.print(prefix, end="")
            self.console.print(text)
            self.console.print()

    def start_joseph_response(self) -> None:
        """
        Print the Joseph prefix before streaming output begins.
        Call this before starting to stream text.
        """
        timestamp = self._get_timestamp()
        prefix = Text()
        prefix.append(f"\n{self.joseph_name}", style="joseph")
        if timestamp:
            prefix.append(f" {timestamp}", style="dim")
        prefix.append(": ", style="joseph")
        self.console.print(prefix, end="")

    def print_stream_chunk(self, chunk: str) -> None:
        """
        Print a single streaming chunk inline.
        No newline — text flows continuously.
        """
        self.console.print(chunk, end="", highlight=False)

    def end_joseph_response(self) -> None:
        """Print final newlines after streaming completes."""
        self.console.print("\n")

    def get_user_input(self) -> str:
        """
        Get input from the user with a styled prompt.

        Returns:
            The user's input string (stripped).
        """
        try:
            self.console.print(
                f"[user]{self.user_name}[/user][dim]:[/dim] ",
                end="",
            )
            user_input = input().strip()
            return user_input
        except (KeyboardInterrupt, EOFError):
            return "/quit"

    def show_system_message(self, message: str) -> None:
        """Display a system/status message in yellow."""
        self.console.print(f"[system]⚙ {message}[/system]")

    def show_error(self, message: str) -> None:
        """Display an error message in red."""
        self.console.print(f"[error]✗ {message}[/error]")

    def show_success(self, message: str) -> None:
        """Display a success message in green."""
        self.console.print(f"[success]✓ {message}[/success]")

    def show_memory_info(self, status_text: str) -> None:
        """Display memory status in a panel."""
        self.console.print(
            Panel(
                f"[memory]{status_text}[/memory]",
                title="[memory]Memory Status[/memory]",
                border_style="magenta",
            )
        )

    def show_facts(self, facts: dict) -> None:
        """Display stored user facts."""
        if not facts:
            self.console.print("[dim]No facts stored yet.[/dim]")
            return

        self.console.print(
            Panel(
                "\n".join([f"[dim]{k}:[/dim] {v}" for k, v in facts.items()]),
                title="[memory]Known Facts[/memory]",
                border_style="magenta",
            )
        )

    def show_memories(self, memories: list) -> None:
        """Display a list of memories."""
        if not memories:
            self.console.print("[dim]No memories found.[/dim]")
            return

        lines = []
        for i, mem in enumerate(memories, 1):
            lines.append(f"[dim]{i}.[/dim] {mem['content']}")
            if mem.get("created_at"):
                lines.append(f"   [dim]Saved: {mem['created_at']}[/dim]")

        self.console.print(
            Panel(
                "\n".join(lines),
                title="[memory]Memories[/memory]",
                border_style="magenta",
            )
        )

    def show_help(self) -> None:
        """Display the help panel with all available commands."""
        help_text = """
[command]/help[/command]              Show this help message
[command]/memory[/command]            Show memory system status
[command]/facts[/command]             Show stored facts about you
[command]/remember <text>[/command]   Explicitly save a memory
[command]/search <query>[/command]    Search your memories
[command]/clear[/command]             Clear current conversation history
[command]/status[/command]            Show system status
[command]/quit[/command] or [command]/exit[/command]   Exit Joseph

[dim]Just type normally to chat with Joseph.[/dim]
[dim]Joseph remembers your conversations between sessions.[/dim]
        """.strip()

        self.console.print(
            Panel(
                help_text,
                title="[command]Commands[/command]",
                border_style="blue",
            )
        )

    def show_divider(self, text: str = "") -> None:
        """Show a horizontal divider line."""
        if text:
            self.console.print(Rule(f"[dim]{text}[/dim]", style="dim"))
        else:
            self.console.print(Rule(style="dim"))

    def show_thinking(self) -> None:
        """Show a brief 'thinking' indicator."""
        self.console.print("[dim]...[/dim]", end="\r")

    def clear_line(self) -> None:
        """Clear the current terminal line (used after thinking indicator)."""
        self.console.print(" " * 20, end="\r")

    def show_goodbye(self) -> None:
        """Display goodbye message on exit."""
        self.console.print()
        self.console.print(
            Panel.fit(
                f"[joseph]Goodbye, {self.user_name}.[/joseph]\n"
                f"[dim]Session saved to memory.[/dim]",
                border_style="cyan",
                padding=(0, 2),
            )
        )
        self.console.print()

    def _get_timestamp(self) -> str:
        """Return formatted timestamp if enabled."""
        if self.show_timestamps:
            return f"[{datetime.now().strftime('%H:%M')}]"
        return ""

    def parse_command(self, user_input: str) -> tuple[Optional[str], Optional[str]]:
        """
        Parse a user input string to check if it's a special command.

        Args:
            user_input: Raw user input.

        Returns:
            Tuple of (command, argument) or (None, None) if not a command.
            Example: "/remember my dog is Max" -> ("remember", "my dog is Max")
        """
        if not user_input.startswith("/"):
            return None, None

        parts = user_input[1:].split(" ", 1)
        command = parts[0].lower()
        argument = parts[1].strip() if len(parts) > 1 else None
        return command, argument

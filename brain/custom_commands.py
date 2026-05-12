"""
brain/custom_commands.py
-------------------------
Custom command shortcuts for JOSEPH.

Define your own shortcuts so Joseph does exactly what you want
when you say specific phrases.

Examples:
  "morning routine" → open YouTube + check weather + give briefing
  "work mode" → open VS Code + open Chrome + play focus music
  "end of day" → show task summary + save notes + close apps

Commands are stored in configs/custom_commands.json
Edit that file directly or use the UI to add/remove commands.

Format:
{
  "morning routine": {
    "description": "Start my morning",
    "actions": [
      "give me a briefing",
      "open YouTube",
      "what's the weather"
    ]
  }
}
"""

import json
import logging
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

COMMANDS_FILE = settings.BASE_DIR / "configs" / "custom_commands.json"

# Default commands to create on first run
DEFAULT_COMMANDS = {
    "morning routine": {
        "description": "Start my morning with briefing and weather",
        "actions": [
            "give me a briefing",
            "what's the weather today"
        ]
    },
    "work mode": {
        "description": "Set up for work",
        "actions": [
            "open VS Code",
            "what are my pending tasks"
        ]
    },
    "end of day": {
        "description": "Wrap up the day",
        "actions": [
            "what tasks did I complete today",
            "show my pending tasks"
        ]
    },
    "focus mode": {
        "description": "Start a focus session",
        "actions": [
            "play lofi music on YouTube",
            "remind me in 45 minutes to take a break"
        ]
    }
}


class CustomCommandManager:
    """
    Manages user-defined command shortcuts.

    Usage:
        manager = CustomCommandManager()
        manager.add_command("my shortcut", ["open YouTube", "play lofi"])
        result = manager.execute("my shortcut", dispatcher)
    """

    def __init__(self):
        self._commands: dict = {}
        self._load()

    def _load(self) -> None:
        """Load commands from JSON file."""
        if COMMANDS_FILE.exists():
            try:
                with open(COMMANDS_FILE, encoding="utf-8") as f:
                    self._commands = json.load(f)
                logger.info(f"Loaded {len(self._commands)} custom commands")
            except Exception as e:
                logger.error(f"Failed to load custom commands: {e}")
                self._commands = {}
        else:
            # Create default commands file
            self._commands = DEFAULT_COMMANDS.copy()
            self._save()
            logger.info("Created default custom commands file")

    def _save(self) -> None:
        """Save commands to JSON file."""
        try:
            COMMANDS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(COMMANDS_FILE, "w", encoding="utf-8") as f:
                json.dump(self._commands, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save custom commands: {e}")

    def match(self, user_input: str) -> Optional[str]:
        """
        Check if user input matches a custom command.

        Args:
            user_input: The user's message.

        Returns:
            Command key if matched, None otherwise.
        """
        input_lower = user_input.lower().strip()

        # Exact match
        if input_lower in self._commands:
            return input_lower

        # Partial match (command phrase appears in input)
        for cmd_key in self._commands:
            if cmd_key in input_lower:
                return cmd_key

        return None

    def execute(self, command_key: str, dispatcher) -> str:
        """
        Execute a custom command by running all its actions.

        Args:
            command_key: The command to execute.
            dispatcher: ToolDispatcher to run actions.

        Returns:
            Combined result string.
        """
        command = self._commands.get(command_key)
        if not command:
            return f"Command '{command_key}' not found."

        actions = command.get("actions", [])
        if not actions:
            return f"Command '{command_key}' has no actions."

        results = []
        for action in actions:
            try:
                response, was_handled = dispatcher.dispatch(action)
                if was_handled and response:
                    results.append(response)
                elif not was_handled:
                    # Try as LLM chat if not automated
                    results.append(f"[{action}]")
            except Exception as e:
                logger.error(f"Custom command action error: {e}")

        return " ".join(results) if results else f"Executed '{command_key}'."

    def add_command(
        self,
        name: str,
        actions: list[str],
        description: str = "",
    ) -> bool:
        """
        Add a new custom command.

        Args:
            name: Command trigger phrase.
            actions: List of actions to execute.
            description: Optional description.

        Returns:
            True if added successfully.
        """
        self._commands[name.lower()] = {
            "description": description or f"Custom command: {name}",
            "actions": actions,
        }
        self._save()
        logger.info(f"Custom command added: '{name}' ({len(actions)} actions)")
        return True

    def remove_command(self, name: str) -> bool:
        """Remove a custom command."""
        key = name.lower()
        if key in self._commands:
            del self._commands[key]
            self._save()
            logger.info(f"Custom command removed: '{name}'")
            return True
        return False

    def list_commands(self) -> str:
        """Return formatted list of all custom commands."""
        if not self._commands:
            return "No custom commands defined."

        lines = ["Custom commands:"]
        for name, cmd in self._commands.items():
            desc = cmd.get("description", "")
            actions = cmd.get("actions", [])
            lines.append(f"\n  '{name}'")
            if desc:
                lines.append(f"    {desc}")
            lines.append(f"    Actions: {', '.join(actions[:2])}" +
                         (f" +{len(actions)-2} more" if len(actions) > 2 else ""))
        return "\n".join(lines)

    def get_all(self) -> dict:
        """Return all commands as dict."""
        return self._commands.copy()

    @property
    def command_count(self) -> int:
        return len(self._commands)

    def __repr__(self) -> str:
        return f"CustomCommandManager(commands={self.command_count})"


# Module-level singleton
custom_commands = CustomCommandManager()

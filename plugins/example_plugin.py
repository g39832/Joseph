"""
Example JOSEPH Plugin

Copy this file and modify it to create your own plugin.
"""

PLUGIN_NAME = "Example Plugin"
PLUGIN_DESCRIPTION = "An example plugin that says hello"
PLUGIN_COMMANDS = ["say hello", "plugin test", "example"]


def handle(command: str, context: dict) -> str:
    """
    Handle a command.

    Args:
        command: The user's command text.
        context: Dict with llm, memory, notes, weather, etc.

    Returns:
        Response string.
    """
    return f"Hello from the example plugin! You said: {command}"


def on_load(context: dict) -> None:
    """Called when plugin loads. Optional."""
    print(f"Example plugin loaded!")

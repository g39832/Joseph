"""
brain/plugin_system.py
-----------------------
Plugin system for JOSEPH.

Drop a .py file into the /plugins folder and Joseph
automatically gains new capabilities.

Plugin format — create a file like plugins/my_plugin.py:

    PLUGIN_NAME = "My Plugin"
    PLUGIN_DESCRIPTION = "Does something cool"
    PLUGIN_COMMANDS = ["my command", "do the thing"]

    def handle(command: str, context: dict) -> str:
        # context contains: llm, memory, notes, weather, etc.
        return "Plugin response"

    def on_load(context: dict) -> None:
        # Optional: called when plugin loads
        pass

Joseph will automatically:
- Detect the plugin
- Add its commands to the tool system
- Call handle() when a matching command is detected
"""

import importlib.util
import logging
import sys
from pathlib import Path
from typing import Callable, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

PLUGINS_DIR = settings.BASE_DIR / "plugins"


class Plugin:
    """Represents a loaded plugin."""

    def __init__(self, name: str, module, path: Path):
        self.name = name
        self.description = getattr(module, "PLUGIN_DESCRIPTION", "No description")
        self.commands = getattr(module, "PLUGIN_COMMANDS", [])
        self.handle: Optional[Callable] = getattr(module, "handle", None)
        self.on_load: Optional[Callable] = getattr(module, "on_load", None)
        self.path = path
        self.module = module
        self.enabled = True

    def __repr__(self) -> str:
        return f"Plugin(name={self.name}, commands={len(self.commands)})"


class PluginSystem:
    """
    Manages JOSEPH plugins.

    Automatically discovers and loads plugins from the /plugins directory.
    Provides a unified interface for dispatching commands to plugins.

    Usage:
        plugins = PluginSystem()
        plugins.load_all(context={"llm": llm, "notes": notes})
        response = plugins.dispatch("my command", context)
    """

    def __init__(self):
        self._plugins: dict[str, Plugin] = {}
        self._command_map: dict[str, str] = {}  # command -> plugin name
        PLUGINS_DIR.mkdir(exist_ok=True)
        self._create_example_plugin()

    def _create_example_plugin(self) -> None:
        """Create an example plugin if none exist."""
        example_path = PLUGINS_DIR / "example_plugin.py"
        if not example_path.exists():
            example_path.write_text(
                '"""\nExample JOSEPH Plugin\n\nCopy this file and modify it to create your own plugin.\n"""\n\n'
                'PLUGIN_NAME = "Example Plugin"\n'
                'PLUGIN_DESCRIPTION = "An example plugin that says hello"\n'
                'PLUGIN_COMMANDS = ["say hello", "plugin test", "example"]\n\n\n'
                'def handle(command: str, context: dict) -> str:\n'
                '    """\n'
                '    Handle a command.\n\n'
                '    Args:\n'
                '        command: The user\'s command text.\n'
                '        context: Dict with llm, memory, notes, weather, etc.\n\n'
                '    Returns:\n'
                '        Response string.\n'
                '    """\n'
                '    return f"Hello from the example plugin! You said: {command}"\n\n\n'
                'def on_load(context: dict) -> None:\n'
                '    """Called when plugin loads. Optional."""\n'
                '    print(f"Example plugin loaded!")\n',
                encoding="utf-8",
            )

    def load_all(self, context: Optional[dict] = None) -> int:
        """
        Discover and load all plugins from the plugins directory.

        Args:
            context: Services to pass to plugins (llm, memory, notes, etc.)

        Returns:
            Number of plugins loaded.
        """
        loaded = 0
        ctx = context or {}

        for plugin_file in PLUGINS_DIR.glob("*.py"):
            if plugin_file.name.startswith("_"):
                continue
            if plugin_file.name == "example_plugin.py":
                continue  # Skip example by default

            try:
                plugin = self._load_plugin(plugin_file, ctx)
                if plugin:
                    self._plugins[plugin.name] = plugin
                    # Register commands
                    for cmd in plugin.commands:
                        self._command_map[cmd.lower()] = plugin.name
                    loaded += 1
                    logger.info(f"Plugin loaded: {plugin.name} ({len(plugin.commands)} commands)")

            except Exception as e:
                logger.error(f"Failed to load plugin {plugin_file.name}: {e}")

        if loaded > 0:
            logger.info(f"Loaded {loaded} plugin(s)")
        return loaded

    def _load_plugin(self, path: Path, context: dict) -> Optional[Plugin]:
        """Load a single plugin file."""
        spec = importlib.util.spec_from_file_location(path.stem, path)
        if not spec or not spec.loader:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[path.stem] = module
        spec.loader.exec_module(module)

        name = getattr(module, "PLUGIN_NAME", path.stem)
        plugin = Plugin(name=name, module=module, path=path)

        # Call on_load if defined
        if plugin.on_load:
            try:
                plugin.on_load(context)
            except Exception as e:
                logger.warning(f"Plugin {name} on_load error: {e}")

        return plugin

    def dispatch(self, command: str, context: Optional[dict] = None) -> tuple[str, bool]:
        """
        Try to handle a command with a plugin.

        Args:
            command: The user's command text.
            context: Services context.

        Returns:
            (response, was_handled) tuple.
        """
        command_lower = command.lower().strip()
        ctx = context or {}

        # Exact match
        if command_lower in self._command_map:
            plugin_name = self._command_map[command_lower]
            return self._call_plugin(plugin_name, command, ctx)

        # Partial match
        for cmd_key, plugin_name in self._command_map.items():
            if cmd_key in command_lower:
                return self._call_plugin(plugin_name, command, ctx)

        return "", False

    def _call_plugin(self, plugin_name: str, command: str, context: dict) -> tuple[str, bool]:
        """Call a specific plugin's handle function."""
        plugin = self._plugins.get(plugin_name)
        if not plugin or not plugin.handle or not plugin.enabled:
            return "", False

        try:
            response = plugin.handle(command, context)
            return str(response), True
        except Exception as e:
            logger.error(f"Plugin {plugin_name} error: {e}")
            return f"Plugin error: {e}", True

    def get_all_plugins(self) -> list[dict]:
        """Return info about all loaded plugins."""
        return [
            {
                "name": p.name,
                "description": p.description,
                "commands": p.commands,
                "enabled": p.enabled,
                "file": p.path.name,
            }
            for p in self._plugins.values()
        ]

    def enable_plugin(self, name: str) -> bool:
        """Enable a plugin."""
        if name in self._plugins:
            self._plugins[name].enabled = True
            return True
        return False

    def disable_plugin(self, name: str) -> bool:
        """Disable a plugin without unloading it."""
        if name in self._plugins:
            self._plugins[name].enabled = False
            return True
        return False

    def reload_plugin(self, name: str, context: Optional[dict] = None) -> bool:
        """Reload a plugin from disk."""
        plugin = self._plugins.get(name)
        if not plugin:
            return False

        try:
            new_plugin = self._load_plugin(plugin.path, context or {})
            if new_plugin:
                self._plugins[name] = new_plugin
                return True
        except Exception as e:
            logger.error(f"Plugin reload error: {e}")
        return False

    @property
    def plugin_count(self) -> int:
        return len(self._plugins)

    def __repr__(self) -> str:
        return f"PluginSystem(plugins={self.plugin_count}, commands={len(self._command_map)})"


# Module-level singleton
plugin_system = PluginSystem()

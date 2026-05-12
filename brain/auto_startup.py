"""
brain/auto_startup.py
----------------------
Windows auto-startup configuration for JOSEPH.

Adds Joseph to Windows startup so it launches automatically
when you log in. Starts minimized to the system tray.

Uses the Windows Registry (HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run)
— the safest, most standard way to add startup programs on Windows.

No admin rights required.
"""

import logging
import sys
from pathlib import Path

from configs.settings import settings

logger = logging.getLogger(__name__)

REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "JosephAI"


def enable_auto_startup() -> bool:
    """
    Add Joseph to Windows startup.

    Creates a registry entry that launches Joseph minimized
    to the system tray when Windows starts.

    Returns:
        True if successfully added.
    """
    try:
        import winreg

        # Build the startup command
        python_exe = sys.executable
        main_py = settings.BASE_DIR / "main.py"
        command = f'"{python_exe}" "{main_py}" --minimized'

        # Write to registry
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
        winreg.CloseKey(key)

        logger.info(f"Auto-startup enabled: {command}")
        return True

    except Exception as e:
        logger.error(f"Failed to enable auto-startup: {e}")
        return False


def disable_auto_startup() -> bool:
    """
    Remove Joseph from Windows startup.

    Returns:
        True if successfully removed.
    """
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_SET_VALUE,
        )
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)

        logger.info("Auto-startup disabled")
        return True

    except FileNotFoundError:
        logger.info("Auto-startup was not enabled")
        return True
    except Exception as e:
        logger.error(f"Failed to disable auto-startup: {e}")
        return False


def is_auto_startup_enabled() -> bool:
    """Check if Joseph is set to auto-start."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return bool(value)

    except FileNotFoundError:
        return False
    except Exception:
        return False


def get_startup_command() -> str:
    """Return the current startup command if set."""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            REGISTRY_KEY,
            0,
            winreg.KEY_READ,
        )
        value, _ = winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return value

    except Exception:
        return ""


if __name__ == "__main__":
    """Run directly to toggle auto-startup."""
    if is_auto_startup_enabled():
        print(f"Joseph auto-startup is currently ENABLED.")
        print(f"Command: {get_startup_command()}")
        choice = input("Disable auto-startup? (yes/no): ").strip().lower()
        if choice in ("yes", "y"):
            if disable_auto_startup():
                print("✓ Auto-startup disabled.")
            else:
                print("✗ Failed to disable.")
    else:
        print("Joseph auto-startup is currently DISABLED.")
        choice = input("Enable auto-startup? (yes/no): ").strip().lower()
        if choice in ("yes", "y"):
            if enable_auto_startup():
                print("✓ Auto-startup enabled. Joseph will start with Windows.")
            else:
                print("✗ Failed to enable.")

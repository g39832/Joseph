"""
tools/terminal_tools.py
------------------------
Terminal command execution with safety controls.

Provides:
  - Shell command execution with timeout and logging
  - Dangerous command blocking
  - User approval requirement for sensitive commands
  - Shell detection
"""

import logging
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.registry import ToolResult

logger = logging.getLogger(__name__)

DANGEROUS_COMMANDS: set[str] = {
    "rm -rf", "rm -r /", "rm -fr", "del /f", "del /s",
    "format", "format:", "mkfs", "dd if=",
    "shutdown", "reboot", "halt", "poweroff",
    "init 0", "init 6", "telinit",
    "chmod 777", "chown -R",
    "> /dev/sda", "| sh", "| bash",
    ":(){ :|:& };:", "forkbomb",
    "wget -O - | sh", "curl -sSL | sh",
    "mv /* ", "cp /* ",
    "rd /s /q", "rmdir /s /q",
    "taskkill /f /im", "tskill",
    "reg delete", "reg add",
    "netsh firewall", "netsh advfirewall",
    "sc delete", "sc config",
    "bcdedit", "bootrec",
    "diskpart", "diskutil",
    "vssadmin", "wmic",
}

SENSITIVE_PATTERNS: list[str] = [
    "net user", "net localgroup",
    "net use", "net share",
    "cacls", "icacls",
    "takeown",
    "del ", "rm ",
    "move ", "ren ",
    "copy ", "xcopy", "robocopy",
    "mkdir", "md ",
    "attrib",
    "reg ",
    "schtasks",
    "wmic ",
    "powershell -", "pwsh -",
    "start-process",
    "stop-process",
    "invoke-",
]


class TerminalTools:
    """
    Terminal command execution with safety controls.

    Features:
      - Blocked dangerous commands (rm -rf, format, etc.)
      - Timeout to prevent hanging
      - Full logging of every command
      - Optional approval flow for sensitive commands
      - Captures both stdout and stderr
    """

    def __init__(self):
        self._execution_log: list[dict] = []
        self._blocked_commands = DANGEROUS_COMMANDS.copy()
        self._sensitive_patterns = SENSITIVE_PATTERNS.copy()

    def execute(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
        env: Optional[dict] = None,
    ) -> ToolResult:
        """
        Execute a shell command safely.

        Args:
            command: The command to execute.
            cwd: Working directory (defaults to current).
            timeout: Maximum execution time in seconds.
            env: Optional environment variable overrides.

        Returns:
            ToolResult with stdout on success, stderr on error.
        """
        if not command or not command.strip():
            return ToolResult(
                success=False, output="",
                error="No command provided.",
            )

        # Check for blocked commands
        blocked = self._check_blocked(command)
        if blocked:
            logger.warning(f"Blocked dangerous command: {command}")
            return ToolResult(
                success=False, output="",
                error=f"Command blocked for safety: '{blocked}'",
            )

        resolved_cwd = self._resolve_cwd(cwd)

        logger.info(f"Executing command: {command[:200]}")
        logger.info(f"  working directory: {resolved_cwd}")

        try:
            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)

            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(resolved_cwd) if resolved_cwd else None,
                env=merged_env,
                text=True,
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                self._log_execution(command, resolved_cwd, False, "TIMEOUT")
                return ToolResult(
                    success=False,
                    output=stdout or "",
                    error=f"Command timed out after {timeout}s",
                )

            exit_code = process.returncode
            success = exit_code == 0

            self._log_execution(command, resolved_cwd, success, exit_code)

            if success:
                output = stdout.rstrip("\n") if stdout else "(completed with no output)"
                return ToolResult(success=True, output=output)
            else:
                error_msg = stderr.rstrip("\n") if stderr else f"Exit code: {exit_code}"
                return ToolResult(
                    success=False,
                    output=stdout.rstrip("\n") if stdout else "",
                    error=error_msg,
                )

        except FileNotFoundError as e:
            return ToolResult(
                success=False, output="",
                error=f"Command not found: {e}",
            )
        except Exception as e:
            return ToolResult(
                success=False, output="",
                error=f"Execution error: {type(e).__name__}: {e}",
            )

    def execute_with_approval(
        self,
        command: str,
        cwd: Optional[str] = None,
        timeout: int = 30,
        reason: str = "",
    ) -> ToolResult:
        """
        Execute a command that requires explicit user approval.

        Prompts via terminal before executing.

        Args:
            command: The command to execute.
            cwd: Working directory.
            timeout: Maximum execution time.
            reason: Explanation for why this command needs approval.

        Returns:
            ToolResult with execution result or denial.
        """
        print(f"\n Command Requires Approval")
        print(f"Command: {command}")
        if reason:
            print(f"Reason: {reason}")
        if cwd:
            print(f"Directory: {cwd}")
        print("Allow this command? (yes/no): ", end="", flush=True)

        try:
            response = input().strip().lower()
        except (KeyboardInterrupt, EOFError):
            return ToolResult(
                success=False, output="",
                error="Command execution cancelled.",
            )

        if response not in ("yes", "y", "allow", "confirm", "ok", "sure"):
            return ToolResult(
                success=False, output="",
                error="Command execution denied by user.",
            )

        return self.execute(command, cwd, timeout)

    def get_shell(self) -> str:
        """
        Detect the current shell being used.

        Returns:
            Shell name (e.g. "powershell", "cmd", "bash", "zsh").
        """
        if platform.system() == "Windows":
            parent = self._get_parent_process()
            if parent and "powershell" in parent.lower():
                return "powershell"
            if parent and "pwsh" in parent.lower():
                return "pwsh"
            try:
                comspec = os.environ.get("COMSPEC", "").lower()
                if "powershell" in comspec or "pwsh" in comspec:
                    return "powershell"
            except Exception:
                pass
            return "cmd"

        shell = os.environ.get("SHELL", "")
        if "zsh" in shell:
            return "zsh"
        if "bash" in shell:
            return "bash"
        if "fish" in shell:
            return "fish"
        if "sh" in shell:
            return "sh"
        return shell or "unknown"

    def add_blocked_command(self, pattern: str) -> None:
        """Add a command pattern to the blocked list."""
        self._blocked_commands.add(pattern.lower())
        logger.info(f"Added blocked command pattern: {pattern}")

    def remove_blocked_command(self, pattern: str) -> None:
        """Remove a command pattern from the blocked list."""
        self._blocked_commands.discard(pattern.lower())
        logger.info(f"Removed blocked command pattern: {pattern}")

    def is_command_blocked(self, command: str) -> bool:
        """Check if a command would be blocked."""
        return self._check_blocked(command) is not None

    def _check_blocked(self, command: str) -> Optional[str]:
        """Check command against blocked patterns. Returns matched pattern or None."""
        cmd_lower = command.lower().strip()

        for blocked in sorted(self._blocked_commands, key=len, reverse=True):
            if blocked in cmd_lower:
                return blocked

        return None

    def _resolve_cwd(self, cwd: Optional[str]) -> Optional[Path]:
        """Resolve working directory path."""
        if not cwd:
            return None
        try:
            path = Path(cwd).expanduser().resolve()
            if path.exists() and path.is_dir():
                return path
            logger.warning(f"Working directory not found: {cwd}")
            return None
        except Exception:
            return None

    def _get_parent_process(self) -> Optional[str]:
        """Get the name of the parent process (for shell detection)."""
        try:
            import psutil
            current = psutil.Process()
            parent = current.parent()
            if parent:
                return parent.name()
        except ImportError:
            pass
        except Exception:
            pass
        return None

    def _log_execution(
        self,
        command: str,
        cwd: Optional[Path],
        success: bool,
        exit_code_or_status,
    ) -> None:
        """Log a command execution."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command[:500],
            "cwd": str(cwd) if cwd else os.getcwd(),
            "user": os.environ.get("USERNAME", os.environ.get("USER", "unknown")),
            "success": success,
            "exit_code": exit_code_or_status if isinstance(exit_code_or_status, int) else str(exit_code_or_status),
        }
        self._execution_log.append(entry)
        logger.info(f"Command {'succeeded' if success else 'failed'}: {command[:80]}")

    def get_execution_log(self, limit: int = 50) -> list[dict]:
        """Return recent command executions."""
        return self._execution_log[-limit:]

    def get_stats(self) -> dict:
        """Return execution statistics."""
        total = len(self._execution_log)
        successes = sum(1 for e in self._execution_log if e["success"])
        return {
            "total_executions": total,
            "successful": successes,
            "failed": total - successes,
        }

"""
tools/registry.py
-----------------
Formal tool registry for JOSEPH Phase 5.

Provides:
  - SafetyLevel enum for classifying tool risk
  - ToolDefinition dataclass for structured tool metadata
  - ToolResult dataclass for uniform return values
  - ToolRegistry class that registers, executes, and rolls back tools

Integrates with PermissionManager for safety checks.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class SafetyLevel(Enum):
    """Risk classification for tool operations."""
    SAFE = "safe"
    CONFIRM = "confirm"
    RESTRICTED = "restricted"
    DANGEROUS = "dangerous"


@dataclass
class ToolDefinition:
    """Defines a registered tool and its metadata."""
    name: str
    description: str
    parameters: dict[str, Any]
    safety_level: SafetyLevel
    handler: Callable[..., Any]
    rollback_handler: Optional[Callable[..., Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "safety_level": self.safety_level.value,
        }


@dataclass
class ToolResult:
    """Uniform return value from all tool executions."""
    success: bool
    output: str
    error: Optional[str] = None
    rollback_data: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


class ToolRegistry:
    """
    Central registry for all tools.

    Handles registration, execution, rollback, and permission checking.
    Every execution is logged with timestamps and results.
    """

    def __init__(self, permission_manager: Optional[Any] = None):
        self._tools: dict[str, ToolDefinition] = {}
        self._execution_log: list[dict] = []
        self._rollback_stack: list[dict] = []
        self._permission_manager = permission_manager

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        if tool.name in self._tools:
            logger.warning(f"Overwriting existing tool: {tool.name}")
        self._tools[tool.name] = tool
        logger.info(f"Registered tool: {tool.name} [{tool.safety_level.value}]")

    def execute(
        self,
        name: str,
        params: Optional[dict] = None,
        permission_manager: Optional[Any] = None,
    ) -> ToolResult:
        """
        Execute a registered tool by name.

        Checks permissions before execution, logs the result,
        and stores rollback data if the tool provides it.
        """
        params = params or {}
        pm = permission_manager or self._permission_manager

        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}",
            )

        if pm:
            allowed = pm.request_permission(name, params)
            if not allowed:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Permission denied for tool: {name}",
                )

        logger.info(f"Executing tool: {name} with params: {params}")
        start = datetime.now()

        try:
            result = tool.handler(**params)
            if isinstance(result, ToolResult):
                output = result
            else:
                output = ToolResult(success=True, output=str(result))

            elapsed = (datetime.now() - start).total_seconds()
            self._log_execution(name, params, output, elapsed)

            if output.rollback_data and tool.rollback_handler:
                self._rollback_stack.append({
                    "name": name,
                    "rollback_data": output.rollback_data,
                    "timestamp": datetime.now().isoformat(),
                })

            return output

        except Exception as e:
            elapsed = (datetime.now() - start).total_seconds()
            error_result = ToolResult(
                success=False,
                output="",
                error=f"{type(e).__name__}: {e}",
            )
            self._log_execution(name, params, error_result, elapsed)
            logger.exception(f"Tool execution failed: {name}")
            return error_result

    def rollback(self, name: str, rollback_data: dict) -> ToolResult:
        """
        Roll back a previous tool execution using its rollback handler.
        """
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}",
            )

        if not tool.rollback_handler:
            return ToolResult(
                success=False,
                output="",
                error=f"No rollback handler for tool: {name}",
            )

        logger.info(f"Rolling back tool: {name}")
        try:
            result = tool.rollback_handler(**rollback_data)
            if isinstance(result, ToolResult):
                return result
            return ToolResult(success=True, output=str(result))
        except Exception as e:
            logger.exception(f"Rollback failed for tool: {name}")
            return ToolResult(
                success=False,
                output="",
                error=f"Rollback error: {type(e).__name__}: {e}",
            )

    def rollback_last(self) -> Optional[ToolResult]:
        """Roll back the most recent tool execution."""
        if not self._rollback_stack:
            return None
        entry = self._rollback_stack.pop()
        return self.rollback(entry["name"], entry["rollback_data"])

    def list_tools(self) -> list[ToolDefinition]:
        """Return all registered tools."""
        return list(self._tools.values())

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Look up a tool by name."""
        return self._tools.get(name)

    def get_execution_log(
        self,
        limit: int = 50,
        tool_name: Optional[str] = None,
    ) -> list[dict]:
        """Return recent execution log entries, optionally filtered by tool."""
        log = self._execution_log
        if tool_name:
            log = [e for e in log if e["tool"] == tool_name]
        return log[-limit:]

    def _log_execution(
        self,
        name: str,
        params: dict,
        result: ToolResult,
        elapsed: float,
    ) -> None:
        """Record a tool execution in the log."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": name,
            "params": params,
            "success": result.success,
            "error": result.error,
            "elapsed_seconds": round(elapsed, 3),
        }
        self._execution_log.append(entry)
        logger.debug(f"Tool execution logged: {name} success={result.success} ({elapsed:.2f}s)")

    def get_stats(self) -> dict[str, Any]:
        """Return summary statistics about tool usage."""
        total = len(self._execution_log)
        successes = sum(1 for e in self._execution_log if e["success"])
        failures = total - successes
        by_tool: dict[str, int] = {}
        for e in self._execution_log:
            by_tool[e["tool"]] = by_tool.get(e["tool"], 0) + 1
        return {
            "total_executions": total,
            "successful": successes,
            "failed": failures,
            "registered_tools": len(self._tools),
            "tools_by_usage": dict(sorted(by_tool.items(), key=lambda x: -x[1])),
        }

    def clear_log(self) -> None:
        """Clear the execution log."""
        self._execution_log.clear()
        logger.info("Execution log cleared")

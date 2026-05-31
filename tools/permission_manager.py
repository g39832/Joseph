"""
tools/permission_manager.py
---------------------------
Permission management for JOSEPH tool execution.

Provides:
  - PermissionRequest dataclass for tracking pending requests
  - PermissionManager class that logs, queues, and persists permissions
  - Safety level overrides for individual tools
  - Persistent permission settings to JSON file
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from configs.settings import settings
from tools.registry import SafetyLevel

logger = logging.getLogger(__name__)


@dataclass
class PermissionRequest:
    """A pending permission request awaiting user response."""
    tool_name: str
    params: dict[str, Any]
    user_response: Optional[bool] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    request_id: str = field(default_factory=lambda: f"perm_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "user_response": self.user_response,
            "timestamp": self.timestamp,
        }


class PermissionManager:
    """
    Manages tool execution permissions with request queuing and persistence.

    Features:
      - Requests user approval for tools above their safety level
      - Allows overriding safety levels at runtime
      - Persists permission settings to a JSON file
      - Maintains a full permission request log
    """

    DEFAULT_PERMS_FILE = settings.DATA_DIR / "permissions.json"

    def __init__(self, perms_file: Optional[Union[str, Path]] = None):
        raw = perms_file or self.DEFAULT_PERMS_FILE
        self._perms_file = Path(raw) if isinstance(raw, str) else raw
        self._requests: dict[str, PermissionRequest] = {}
        self._permission_log: list[dict] = []
        self._safety_overrides: dict[str, SafetyLevel] = {}
        self._auto_approve_patterns: list[str] = []
        self._deny_patterns: list[str] = []
        self._request_counter = 0
        self._confirm_callback: Optional[callable] = None
        self._load_settings()

    def set_confirm_callback(self, callback: callable) -> None:
        """Set a callback for user confirmation UI."""
        self._confirm_callback = callback

    def request_permission(self, tool_name: str, params: dict) -> bool:
        """
        Check if a tool execution is permitted.

        Returns True if the tool is auto-approved, False if denied.
        Pends a request for user approval otherwise.
        """
        request = PermissionRequest(tool_name=tool_name, params=params)
        self._request_counter += 1

        effective_level = self._safety_overrides.get(
            tool_name,
            self._get_default_safety(tool_name),
        )

        if effective_level == SafetyLevel.SAFE:
            self._log_permission(request, "auto-approved")
            return True

        if effective_level == SafetyLevel.DANGEROUS:
            self._log_permission(request, "denied-dangerous")
            return False

        if self._matches_pattern(tool_name, self._auto_approve_patterns):
            self._log_permission(request, "auto-approved-pattern")
            return True

        if self._matches_pattern(tool_name, self._deny_patterns):
            self._log_permission(request, "denied-pattern")
            return False

        if effective_level == SafetyLevel.RESTRICTED:
            allowed = self._ask_user(request)
            if not allowed:
                self._log_permission(request, "denied")
                return False
            self._log_permission(request, "approved")
            return True

        if effective_level == SafetyLevel.CONFIRM:
            allowed = self._ask_user(request)
            if not allowed:
                self._log_permission(request, "denied")
                return False
            self._log_permission(request, "approved")
            return True

        self._log_permission(request, "auto-approved")
        return True

    def _get_default_safety(self, tool_name: str) -> SafetyLevel:
        """Determine default safety level by tool name patterns."""
        dangerous_keywords = ["delete", "remove", "format", "wipe", "exec", "shell"]
        confirm_keywords = ["write", "move", "copy", "launch", "install"]
        for kw in dangerous_keywords:
            if kw in tool_name.lower():
                return SafetyLevel.RESTRICTED
        for kw in confirm_keywords:
            if kw in tool_name.lower():
                return SafetyLevel.CONFIRM
        return SafetyLevel.SAFE

    def _matches_pattern(self, tool_name: str, patterns: list[str]) -> bool:
        """Check if tool name matches any glob-like pattern."""
        from fnmatch import fnmatch
        return any(fnmatch(tool_name, p) for p in patterns)

    def _ask_user(self, request: PermissionRequest) -> bool:
        """Ask user for permission, via callback or terminal."""
        self._requests[request.request_id] = request

        if self._confirm_callback:
            return self._confirm_callback(request.tool_name, request.params)

        return self._terminal_confirm(request)

    def _terminal_confirm(self, request: PermissionRequest) -> bool:
        """Default terminal-based confirmation prompt."""
        print(f"\n Permission Required")
        print(f"Tool: {request.tool_name}")
        if request.params:
            print(f"Parameters: {json.dumps(request.params, indent=2)}")
        print("Allow this action? (yes/no): ", end="", flush=True)
        try:
            response = input().strip().lower()
            approved = response in ("yes", "y", "confirm", "allow", "ok", "sure")
            request.user_response = approved
            return approved
        except (KeyboardInterrupt, EOFError):
            request.user_response = False
            return False

    def approve(self, request_id: str) -> bool:
        """Approve a pending permission request."""
        request = self._requests.get(request_id)
        if not request:
            logger.warning(f"No pending request: {request_id}")
            return False
        request.user_response = True
        self._log_permission(request, "approved-api")
        return True

    def deny(self, request_id: str) -> bool:
        """Deny a pending permission request."""
        request = self._requests.get(request_id)
        if not request:
            logger.warning(f"No pending request: {request_id}")
            return False
        request.user_response = False
        self._log_permission(request, "denied-api")
        return True

    def set_tool_safety(self, name: str, level: SafetyLevel) -> None:
        """Override the safety level for a specific tool."""
        self._safety_overrides[name] = level
        self._save_settings()
        logger.info(f"Safety override: {name} -> {level.value}")

    def remove_tool_safety(self, name: str) -> None:
        """Remove a safety level override."""
        self._safety_overrides.pop(name, None)
        self._save_settings()
        logger.info(f"Safety override removed: {name}")

    def add_auto_approve_pattern(self, pattern: str) -> None:
        """Add a glob pattern for auto-approved tools."""
        if pattern not in self._auto_approve_patterns:
            self._auto_approve_patterns.append(pattern)
            self._save_settings()

    def add_deny_pattern(self, pattern: str) -> None:
        """Add a glob pattern for auto-denied tools."""
        if pattern not in self._deny_patterns:
            self._deny_patterns.append(pattern)
            self._save_settings()

    def get_pending_requests(self) -> list[PermissionRequest]:
        """Return all requests awaiting user response."""
        return [
            r for r in self._requests.values()
            if r.user_response is None
        ]

    def get_permission_log(
        self,
        limit: int = 100,
    ) -> list[dict]:
        """Return the permission request history."""
        return self._permission_log[-limit:]

    def is_approved(self, tool_name: str) -> bool:
        """Check if a tool is currently approved for execution."""
        effective_level = self._safety_overrides.get(
            tool_name,
            self._get_default_safety(tool_name),
        )
        if effective_level == SafetyLevel.DANGEROUS:
            return False
        if effective_level == SafetyLevel.SAFE:
            return True
        if self._matches_pattern(tool_name, self._auto_approve_patterns):
            return True
        if self._matches_pattern(tool_name, self._deny_patterns):
            return False
        return effective_level in (SafetyLevel.CONFIRM, SafetyLevel.RESTRICTED)

    def get_safety_level(self, tool_name: str) -> SafetyLevel:
        """Get the effective safety level for a tool."""
        return self._safety_overrides.get(
            tool_name,
            self._get_default_safety(tool_name),
        )

    def _log_permission(self, request: PermissionRequest, status: str) -> None:
        """Record a permission decision."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "request_id": request.request_id,
            "tool_name": request.tool_name,
            "params": request.params,
            "status": status,
        }
        self._permission_log.append(entry)
        logger.info(f"Permission {status}: {request.tool_name}")

    def _load_settings(self) -> None:
        """Load permission settings from JSON file."""
        try:
            if self._perms_file.exists():
                data = json.loads(self._perms_file.read_text(encoding="utf-8"))
                overrides = data.get("safety_overrides", {})
                for name, level_str in overrides.items():
                    try:
                        self._safety_overrides[name] = SafetyLevel(level_str)
                    except ValueError:
                        logger.warning(f"Invalid safety level '{level_str}' for {name}")
                self._auto_approve_patterns = data.get("auto_approve_patterns", [])
                self._deny_patterns = data.get("deny_patterns", [])
                logger.info(
                    f"Loaded permissions: {len(self._safety_overrides)} overrides, "
                    f"{len(self._auto_approve_patterns)} approve patterns, "
                    f"{len(self._deny_patterns)} deny patterns"
                )
        except Exception as e:
            logger.warning(f"Could not load permissions file: {e}")

    def _save_settings(self) -> None:
        """Save permission settings to JSON file."""
        try:
            self._perms_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "safety_overrides": {
                    name: level.value
                    for name, level in self._safety_overrides.items()
                },
                "auto_approve_patterns": self._auto_approve_patterns,
                "deny_patterns": self._deny_patterns,
            }
            self._perms_file.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Could not save permissions file: {e}")

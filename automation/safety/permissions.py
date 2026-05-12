"""
automation/safety/permissions.py
---------------------------------
Safety and permissions system for JOSEPH.

JOSEPH must NEVER perform high-risk actions without explicit user confirmation.
This module enforces that rule for all automation modules.

Risk levels:
  LOW    — read-only, reversible (open website, search, read file)
  MEDIUM — creates/modifies things (create file, type text, click)
  HIGH   — destructive or sensitive (delete file, send email, run shell command)
  CRITICAL — irreversible or financial (purchase, format drive, mass delete)

All HIGH and CRITICAL actions require user confirmation before execution.
"""

import logging
from enum import Enum
from typing import Callable, Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk classification for automation actions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PermissionDeniedError(Exception):
    """Raised when a user denies permission for an action."""
    pass


class PermissionsManager:
    """
    Enforces safety rules for all automation actions.

    Usage:
        perms = PermissionsManager()

        # This will ask for confirmation before proceeding
        if perms.request_permission("delete file 'report.txt'", RiskLevel.HIGH):
            delete_the_file()
        else:
            print("Action cancelled.")
    """

    # Actions that always require confirmation regardless of settings
    ALWAYS_CONFIRM = {
        "delete",
        "remove",
        "format",
        "purchase",
        "buy",
        "send email",
        "send message",
        "shell command",
        "execute script",
        "run command",
    }

    def __init__(self, confirm_callback: Optional[Callable] = None):
        """
        Args:
            confirm_callback: Optional function to call for confirmation UI.
                              If None, uses terminal input.
                              Signature: (action: str, risk: RiskLevel) -> bool
        """
        self._confirm_callback = confirm_callback or self._terminal_confirm
        self._audit_log: list[dict] = []

    def request_permission(
        self,
        action_description: str,
        risk_level: RiskLevel = RiskLevel.MEDIUM,
        force_confirm: bool = False,
    ) -> bool:
        """
        Request permission to perform an action.

        For LOW risk: auto-approved (logged only).
        For MEDIUM risk: auto-approved unless settings say otherwise.
        For HIGH/CRITICAL: always requires confirmation.

        Args:
            action_description: Human-readable description of what will happen.
            risk_level: The risk classification of this action.
            force_confirm: Force confirmation even for low-risk actions.

        Returns:
            True if approved, False if denied.
        """
        # Log the request
        self._log_action(action_description, risk_level, "requested")

        # Check if this action always requires confirmation
        action_lower = action_description.lower()
        always_confirm = any(
            keyword in action_lower for keyword in self.ALWAYS_CONFIRM
        )

        # Determine if confirmation is needed
        needs_confirm = (
            force_confirm
            or always_confirm
            or risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL)
            or (
                risk_level == RiskLevel.MEDIUM
                and settings.REQUIRE_CONFIRMATION_FOR_SHELL
            )
        )

        if not needs_confirm:
            logger.info(f"Auto-approved [{risk_level.value}]: {action_description}")
            self._log_action(action_description, risk_level, "auto-approved")
            return True

        # Request confirmation
        approved = self._confirm_callback(action_description, risk_level)

        status = "approved" if approved else "denied"
        self._log_action(action_description, risk_level, status)
        logger.info(f"Permission {status} [{risk_level.value}]: {action_description}")

        return approved

    def _terminal_confirm(
        self, action_description: str, risk_level: RiskLevel
    ) -> bool:
        """
        Default confirmation via terminal input.

        Args:
            action_description: What Joseph wants to do.
            risk_level: Risk level of the action.

        Returns:
            True if user confirms, False otherwise.
        """
        risk_colors = {
            RiskLevel.LOW: "",
            RiskLevel.MEDIUM: "",
            RiskLevel.HIGH: "⚠ ",
            RiskLevel.CRITICAL: "🚨 ",
        }
        prefix = risk_colors.get(risk_level, "")

        print(f"\n{prefix}Permission Required [{risk_level.value.upper()}]")
        print(f"Action: {action_description}")
        print("Confirm? (yes/no): ", end="", flush=True)

        try:
            response = input().strip().lower()
            return response in ("yes", "y", "confirm", "ok", "sure")
        except (KeyboardInterrupt, EOFError):
            return False

    def _log_action(
        self, action: str, risk_level: RiskLevel, status: str
    ) -> None:
        """Add an entry to the audit log."""
        from datetime import datetime

        self._audit_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "action": action,
                "risk_level": risk_level.value,
                "status": status,
            }
        )

    def get_audit_log(self) -> list[dict]:
        """Return the full audit log of permission requests."""
        return self._audit_log.copy()

    def set_confirm_callback(self, callback: Callable) -> None:
        """
        Replace the confirmation UI callback.
        Used by voice interface to ask verbally instead of via terminal.
        """
        self._confirm_callback = callback


# Module-level singleton
permissions = PermissionsManager()

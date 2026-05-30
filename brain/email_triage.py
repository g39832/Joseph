"""
brain/email_triage.py
----------------------
Email triage agent for JOSEPH.

Every morning Joseph reads your unread emails,
categorizes them, and gives you a spoken summary.

Categories:
  URGENT   — needs response today (keywords: urgent, asap, deadline, etc.)
  ACTION   — requires action but not urgent
  FYI      — informational, no action needed
  PROMO    — promotional/marketing emails
  SPAM     — likely spam

Requires Google integration to be set up first.
Run: python -m brain.google_integration
"""

import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# Keywords for categorization
URGENT_KEYWORDS = [
    "urgent", "asap", "immediately", "deadline", "today", "emergency",
    "critical", "important", "action required", "response needed",
    "time sensitive", "expires", "last chance",
]

PROMO_KEYWORDS = [
    "unsubscribe", "sale", "% off", "discount", "offer", "deal",
    "newsletter", "marketing", "promotion", "subscribe", "click here",
    "limited time", "free shipping", "coupon",
]

SPAM_KEYWORDS = [
    "winner", "congratulations", "lottery", "prize", "million dollars",
    "nigerian", "inheritance", "bitcoin", "crypto investment",
    "click to claim", "verify your account immediately",
]


class EmailTriage:
    """
    Categorizes and summarizes emails for JOSEPH.

    Usage:
        triage = EmailTriage(google=google_integration, llm=llm)
        summary = triage.get_morning_summary()
        # Returns spoken summary of important emails
    """

    def __init__(self, google=None, llm=None):
        self.google = google
        self.llm = llm

    def categorize_email(self, email: dict) -> str:
        """
        Categorize a single email.

        Args:
            email: Email dict with subject, sender, snippet.

        Returns:
            Category string: URGENT/ACTION/FYI/PROMO/SPAM
        """
        subject = (email.get("subject") or "").lower()
        snippet = (email.get("snippet") or "").lower()
        sender = (email.get("sender") or "").lower()
        text = f"{subject} {snippet}"

        # Check spam first
        if any(kw in text for kw in SPAM_KEYWORDS):
            return "SPAM"

        # Check promotional
        if any(kw in text for kw in PROMO_KEYWORDS):
            return "PROMO"

        # Check urgent
        if any(kw in text for kw in URGENT_KEYWORDS):
            return "URGENT"

        # Check if it's from a person (not automated)
        automated_patterns = [
            "noreply", "no-reply", "donotreply", "notifications@",
            "alerts@", "updates@", "newsletter@", "mailer@",
        ]
        is_automated = any(p in sender for p in automated_patterns)

        if is_automated:
            return "FYI"

        return "ACTION"

    def triage_emails(self, emails: list[dict]) -> dict:
        """
        Categorize a list of emails.

        Args:
            emails: List of email dicts.

        Returns:
            Dict with categories as keys, email lists as values.
        """
        categorized = {
            "URGENT": [],
            "ACTION": [],
            "FYI": [],
            "PROMO": [],
            "SPAM": [],
        }

        for email in emails:
            category = self.categorize_email(email)
            categorized[category].append(email)

        return categorized

    def get_morning_summary(self, max_emails: int = 20) -> str:
        """
        Generate a morning email briefing.

        Reads unread emails, categorizes them, and returns
        a natural language summary suitable for speaking aloud.

        Returns:
            Summary string.
        """
        if not self.google or not self.google.is_available:
            return (
                "Gmail not connected. Run 'python -m brain.google_integration' "
                "to set up email access."
            )

        try:
            emails = self.google.get_recent_emails(
                max_results=max_emails,
                unread_only=True,
            )

            if not emails:
                return "No unread emails."

            categorized = self.triage_emails(emails)

            urgent = categorized["URGENT"]
            action = categorized["ACTION"]
            fyi = categorized["FYI"]
            promo = categorized["PROMO"]

            parts = []

            # Urgent emails — always mention by name
            if urgent:
                parts.append(f"{len(urgent)} urgent email(s):")
                for e in urgent[:3]:
                    sender = e["sender"].split("<")[0].strip().split("@")[0]
                    parts.append(f"  From {sender}: {e['subject'][:50]}")

            # Action emails
            if action:
                parts.append(f"{len(action)} email(s) need your attention.")
                if len(action) <= 3:
                    for e in action:
                        sender = e["sender"].split("<")[0].strip()
                        parts.append(f"  {sender}: {e['subject'][:40]}")

            # FYI
            if fyi:
                parts.append(f"{len(fyi)} informational email(s).")

            # Promo (just count)
            if promo:
                parts.append(f"{len(promo)} promotional email(s) — probably safe to ignore.")

            if not parts:
                return f"You have {len(emails)} unread emails, nothing urgent."

            total = len(emails)
            summary = f"You have {total} unread email(s). " + " ".join(parts)
            return summary

        except Exception as e:
            logger.error(f"Email triage error: {e}")
            return f"Couldn't check emails: {e}"

    def get_detailed_report(self) -> str:
        """Get a detailed formatted email report."""
        if not self.google or not self.google.is_available:
            return "Gmail not connected."

        try:
            emails = self.google.get_recent_emails(max_results=30, unread_only=True)
            if not emails:
                return "No unread emails."

            categorized = self.triage_emails(emails)
            lines = [f"Email Triage Report — {datetime.now().strftime('%B %d')}"]
            lines.append("=" * 40)

            for category in ["URGENT", "ACTION", "FYI", "PROMO", "SPAM"]:
                items = categorized[category]
                if not items:
                    continue

                emoji = {"URGENT": "🔴", "ACTION": "🟡", "FYI": "🔵",
                         "PROMO": "⚪", "SPAM": "🗑️"}.get(category, "")
                lines.append(f"\n{emoji} {category} ({len(items)})")

                for e in items[:5]:
                    sender = e["sender"].split("<")[0].strip()[:20]
                    subject = e["subject"][:45]
                    lines.append(f"  • {sender}: {subject}")

                if len(items) > 5:
                    lines.append(f"  ... and {len(items) - 5} more")

            return "\n".join(lines)

        except Exception as e:
            return f"Error: {e}"

    def __repr__(self) -> str:
        return f"EmailTriage(google={'connected' if self.google and self.google.is_available else 'not connected'})"

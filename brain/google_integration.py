"""
brain/google_integration.py
-----------------------------
Google Calendar and Gmail integration for JOSEPH — Phase 8.

Provides:
- Read upcoming calendar events
- Create calendar events
- Read recent emails (subject + sender)
- Draft email replies (with confirmation before sending)

Setup required (one-time):
  1. Go to https://console.cloud.google.com
  2. Create a project
  3. Enable Gmail API and Google Calendar API
  4. Create OAuth 2.0 credentials (Desktop app)
  5. Download credentials.json to joseph/configs/
  6. Run: python brain/google_integration.py --setup
  7. Follow the browser auth flow

After setup, a token.json is saved and auto-refreshes.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)

CREDENTIALS_FILE = settings.BASE_DIR / "configs" / "google_credentials.json"
TOKEN_FILE = settings.BASE_DIR / "configs" / "google_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
]


class GoogleIntegration:
    """
    Google Calendar and Gmail integration.

    Requires OAuth setup — see module docstring.
    Falls back gracefully if not configured.

    Usage:
        google = GoogleIntegration()
        if google.is_available:
            events = google.get_upcoming_events()
            emails = google.get_recent_emails()
    """

    def __init__(self):
        self._creds = None
        self._calendar_service = None
        self._gmail_service = None
        self._available = False
        self._setup_complete = TOKEN_FILE.exists()
        if self._setup_complete:
            self._initialize()

    def _initialize(self) -> None:
        """Load credentials and initialize Google API services."""
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build

            creds = None

            # Load existing token
            if TOKEN_FILE.exists():
                creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                self._save_token(creds)

            if not creds or not creds.valid:
                logger.warning("Google credentials invalid — run setup")
                return

            self._creds = creds
            self._calendar_service = build("calendar", "v3", credentials=creds)
            self._gmail_service = build("gmail", "v1", credentials=creds)
            self._available = True
            logger.info("Google integration initialized (Calendar + Gmail)")

        except Exception as e:
            logger.warning(f"Google integration init failed: {e}")
            self._available = False

    def setup(self) -> bool:
        """
        Run the OAuth setup flow.
        Opens a browser for Google authentication.

        Returns:
            True if setup completed successfully.
        """
        if not CREDENTIALS_FILE.exists():
            print(
                f"\nSetup required:\n"
                f"1. Go to https://console.cloud.google.com\n"
                f"2. Create a project and enable Gmail + Calendar APIs\n"
                f"3. Create OAuth 2.0 credentials (Desktop app)\n"
                f"4. Download as: {CREDENTIALS_FILE}\n"
                f"5. Run this script again\n"
            )
            return False

        try:
            from google_auth_oauthlib.flow import InstalledAppFlow

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CREDENTIALS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=0)
            self._save_token(creds)
            self._initialize()
            print("✓ Google integration setup complete!")
            return True

        except Exception as e:
            logger.error(f"Google setup failed: {e}")
            return False

    def _save_token(self, creds) -> None:
        """Save credentials token to file."""
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    # ------------------------------------------------------------------ #
    # Calendar
    # ------------------------------------------------------------------ #

    def get_upcoming_events(self, days: int = 7, max_results: int = 10) -> list[dict]:
        """
        Get upcoming calendar events.

        Args:
            days: How many days ahead to look.
            max_results: Maximum events to return.

        Returns:
            List of event dicts with summary, start, end, location.
        """
        if not self._available or not self._calendar_service:
            return []

        try:
            now = datetime.utcnow()
            end = now + timedelta(days=days)

            result = self._calendar_service.events().list(
                calendarId="primary",
                timeMin=now.isoformat() + "Z",
                timeMax=end.isoformat() + "Z",
                maxResults=max_results,
                singleEvents=True,
                orderBy="startTime",
            ).execute()

            events = []
            for item in result.get("items", []):
                start = item["start"].get("dateTime", item["start"].get("date", ""))
                end_time = item["end"].get("dateTime", item["end"].get("date", ""))
                events.append({
                    "id": item.get("id"),
                    "summary": item.get("summary", "No title"),
                    "start": start,
                    "end": end_time,
                    "location": item.get("location", ""),
                    "description": item.get("description", ""),
                })

            return events

        except Exception as e:
            logger.error(f"Calendar fetch error: {e}")
            return []

    def format_events(self, events: list[dict]) -> str:
        """Format events as readable text."""
        if not events:
            return "No upcoming events."

        lines = ["Upcoming events:"]
        for event in events:
            start = event["start"]
            # Parse and format datetime
            try:
                if "T" in start:
                    dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    formatted = dt.strftime("%a %b %d at %I:%M %p")
                else:
                    dt = datetime.fromisoformat(start)
                    formatted = dt.strftime("%a %b %d (all day)")
            except Exception:
                formatted = start

            line = f"  • {event['summary']} — {formatted}"
            if event.get("location"):
                line += f" @ {event['location']}"
            lines.append(line)

        return "\n".join(lines)

    def create_event(
        self,
        title: str,
        start_time: str,
        duration_minutes: int = 60,
        description: str = "",
        location: str = "",
    ) -> Optional[str]:
        """
        Create a calendar event.

        Args:
            title: Event title.
            start_time: ISO format datetime string.
            duration_minutes: Event duration.
            description: Optional description.
            location: Optional location.

        Returns:
            Event ID if created, None if failed.
        """
        if not self._available or not self._calendar_service:
            return None

        try:
            from automation.safety.permissions import permissions, RiskLevel
            if not permissions.request_permission(
                f"create calendar event: {title}",
                RiskLevel.MEDIUM,
            ):
                return None

            start_dt = datetime.fromisoformat(start_time)
            end_dt = start_dt + timedelta(minutes=duration_minutes)

            event = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
            }

            result = self._calendar_service.events().insert(
                calendarId="primary", body=event
            ).execute()

            logger.info(f"Calendar event created: {title}")
            return result.get("id")

        except Exception as e:
            logger.error(f"Create event error: {e}")
            return None

    # ------------------------------------------------------------------ #
    # Gmail
    # ------------------------------------------------------------------ #

    def get_recent_emails(self, max_results: int = 10, unread_only: bool = True) -> list[dict]:
        """
        Get recent emails from Gmail.

        Args:
            max_results: Maximum emails to return.
            unread_only: Only return unread emails.

        Returns:
            List of email dicts with subject, sender, snippet, date.
        """
        if not self._available or not self._gmail_service:
            return []

        try:
            query = "is:unread" if unread_only else ""
            result = self._gmail_service.users().messages().list(
                userId="me",
                maxResults=max_results,
                q=query,
            ).execute()

            messages = result.get("messages", [])
            emails = []

            for msg in messages[:max_results]:
                detail = self._gmail_service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date"],
                ).execute()

                headers = {
                    h["name"]: h["value"]
                    for h in detail.get("payload", {}).get("headers", [])
                }

                emails.append({
                    "id": msg["id"],
                    "subject": headers.get("Subject", "No subject"),
                    "sender": headers.get("From", "Unknown"),
                    "date": headers.get("Date", ""),
                    "snippet": detail.get("snippet", ""),
                })

            return emails

        except Exception as e:
            logger.error(f"Gmail fetch error: {e}")
            return []

    def format_emails(self, emails: list[dict]) -> str:
        """Format emails as readable text."""
        if not emails:
            return "No unread emails."

        lines = [f"{len(emails)} unread email(s):"]
        for i, email in enumerate(emails, 1):
            sender = email["sender"].split("<")[0].strip()
            lines.append(f"\n  {i}. From: {sender}")
            lines.append(f"     Subject: {email['subject']}")
            if email.get("snippet"):
                snippet = email["snippet"][:80] + "..." if len(email["snippet"]) > 80 else email["snippet"]
                lines.append(f"     Preview: {snippet}")

        return "\n".join(lines)

    def draft_reply(self, email_id: str, reply_text: str) -> Optional[str]:
        """
        Create a draft reply to an email.
        Does NOT send — creates a draft only.

        Args:
            email_id: The email to reply to.
            reply_text: The reply content.

        Returns:
            Draft ID if created, None if failed.
        """
        if not self._available or not self._gmail_service:
            return None

        try:
            import base64
            from email.mime.text import MIMEText

            # Get original email details
            original = self._gmail_service.users().messages().get(
                userId="me", id=email_id, format="metadata",
                metadataHeaders=["Subject", "From", "Message-ID"],
            ).execute()

            headers = {
                h["name"]: h["value"]
                for h in original.get("payload", {}).get("headers", [])
            }

            # Build reply
            msg = MIMEText(reply_text)
            msg["To"] = headers.get("From", "")
            msg["Subject"] = "Re: " + headers.get("Subject", "")
            msg["In-Reply-To"] = headers.get("Message-ID", "")

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()

            draft = self._gmail_service.users().drafts().create(
                userId="me",
                body={"message": {"raw": raw, "threadId": original.get("threadId")}},
            ).execute()

            logger.info(f"Email draft created: {draft.get('id')}")
            return draft.get("id")

        except Exception as e:
            logger.error(f"Draft reply error: {e}")
            return None

    def get_calendar_summary(self) -> str:
        """One-line calendar summary for briefing."""
        events = self.get_upcoming_events(days=1, max_results=3)
        if not events:
            return "No events today."
        titles = [e["summary"] for e in events]
        return f"Today: {', '.join(titles)}"

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def is_setup(self) -> bool:
        return self._setup_complete

    def get_setup_instructions(self) -> str:
        """Return setup instructions as a string."""
        return (
            "Google integration not set up yet.\n\n"
            "To enable Gmail and Calendar:\n"
            "1. Go to https://console.cloud.google.com\n"
            "2. Create a project\n"
            "3. Enable Gmail API and Google Calendar API\n"
            "4. Create OAuth 2.0 credentials (Desktop app type)\n"
            f"5. Download credentials as: {CREDENTIALS_FILE}\n"
            "6. Run: python brain/google_integration.py\n"
            "7. Complete the browser auth flow\n\n"
            "After setup, Joseph can read your emails and calendar."
        )

    def __repr__(self) -> str:
        return f"GoogleIntegration(available={self._available}, setup={self._setup_complete})"


# Module-level singleton
google_integration = GoogleIntegration()


if __name__ == "__main__":
    """Run this script directly to set up Google integration."""
    g = GoogleIntegration()
    if not g.is_setup:
        print("Starting Google OAuth setup...")
        g.setup()
    else:
        print("Google integration already set up.")
        events = g.get_upcoming_events(days=3)
        print(g.format_events(events))

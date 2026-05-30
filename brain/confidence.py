"""
brain/confidence.py
--------------------
Confidence scoring for JOSEPH automation.

Before executing an automation command, Joseph rates his
confidence 0-100%. Below the threshold, he asks for
clarification instead of guessing wrong.

This prevents embarrassing mistakes like opening the wrong
app or searching for the wrong thing.

Confidence factors:
- How clearly the command matches a known pattern
- Whether the target (app/site/query) is recognized
- Ambiguity in the request
- Context from conversation history
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Confidence threshold — below this, ask for clarification
CONFIDENCE_THRESHOLD = 65

# High-confidence patterns (clear, unambiguous commands)
HIGH_CONFIDENCE_PATTERNS = [
    (r"\bopen (youtube|google|reddit|github|netflix|spotify)\b", 95),
    (r"\bplay .+ on youtube\b", 90),
    (r"\bsearch (google |web )?for .+", 88),
    (r"\bopen (notepad|calculator|chrome|firefox|vscode)\b", 92),
    (r"\btake a screenshot\b", 98),
    (r"\bwhat.s the weather\b", 95),
    (r"\bgive me a briefing\b", 95),
    (r"\badd (to my )?notes?:? .+", 90),
    (r"\badd (a )?task:? .+", 90),
    (r"\bremind me .+", 85),
    (r"\bpause (the )?music\b", 92),
    (r"\bskip (this )?song\b", 92),
]

# Low-confidence patterns (ambiguous)
LOW_CONFIDENCE_PATTERNS = [
    (r"^open .{1,5}$", 40),          # "open X" where X is very short/unknown
    (r"\bdo (that|it|this)\b", 35),   # Vague references
    (r"\bthe (thing|stuff)\b", 30),   # Very vague
]


class ConfidenceScorer:
    """
    Scores confidence for automation commands.

    Usage:
        scorer = ConfidenceScorer()
        score, reason = scorer.score("open YouTube")
        if score >= 65:
            execute_command()
        else:
            ask_for_clarification()
    """

    def __init__(self, threshold: int = CONFIDENCE_THRESHOLD):
        self.threshold = threshold

    def score(self, command: str) -> tuple[int, str]:
        """
        Score confidence for a command.

        Args:
            command: The user's command text.

        Returns:
            (confidence_score 0-100, reason_string)
        """
        command_lower = command.lower().strip()

        # Check high-confidence patterns first
        for pattern, conf in HIGH_CONFIDENCE_PATTERNS:
            if re.search(pattern, command_lower):
                return conf, f"Matches known pattern ({conf}%)"

        # Check low-confidence patterns
        for pattern, conf in LOW_CONFIDENCE_PATTERNS:
            if re.search(pattern, command_lower):
                return conf, f"Ambiguous command ({conf}%)"

        # Default scoring based on command characteristics
        score = 70  # Start at 70% (reasonable default)
        reasons = []

        # Longer, more specific commands are more confident
        word_count = len(command.split())
        if word_count >= 5:
            score += 10
            reasons.append("specific command")
        elif word_count <= 2:
            score -= 15
            reasons.append("very short command")

        # Commands with known targets are more confident
        known_sites = ["youtube", "google", "reddit", "github", "netflix", "spotify",
                       "twitter", "instagram", "amazon", "wikipedia"]
        known_apps = ["notepad", "calculator", "chrome", "firefox", "vscode",
                      "spotify", "discord", "word", "excel"]

        if any(site in command_lower for site in known_sites):
            score += 15
            reasons.append("known website")
        elif any(app in command_lower for app in known_apps):
            score += 15
            reasons.append("known application")

        # Question marks reduce confidence (might be a question, not a command)
        if "?" in command:
            score -= 20
            reasons.append("contains question mark")

        score = max(0, min(100, score))
        reason = ", ".join(reasons) if reasons else "default scoring"
        return score, reason

    def should_execute(self, command: str) -> tuple[bool, int, str]:
        """
        Determine if a command should be executed or clarified.

        Returns:
            (should_execute, confidence_score, reason)
        """
        conf, reason = self.score(command)
        return conf >= self.threshold, conf, reason

    def get_clarification_prompt(self, command: str, confidence: int) -> str:
        """
        Generate a clarification question for low-confidence commands.

        Args:
            command: The ambiguous command.
            confidence: The confidence score.

        Returns:
            A natural clarification question.
        """
        if confidence < 40:
            return f"I'm not sure what you mean by '{command}'. Could you be more specific?"
        elif confidence < 55:
            return f"Just to confirm — you want me to {command}?"
        else:
            return f"I think you want me to {command}, but I'm not 100% sure. Is that right?"

    def __repr__(self) -> str:
        return f"ConfidenceScorer(threshold={self.threshold})"


# Module-level singleton
confidence_scorer = ConfidenceScorer()

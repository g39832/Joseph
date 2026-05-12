"""
brain/personality_engine.py
-----------------------------
Advanced personality and emotional intelligence for JOSEPH — Phase 7.

Tracks:
- Conversation mood and emotional context
- User's current state (stressed, happy, focused, tired)
- Relationship depth (how well Joseph knows the user)
- Response style adaptation
- Empathy responses
- Humor calibration

Joseph becomes more personalized the more you interact with him.
After many sessions, he adapts his tone to match your preferences.
"""

import logging
import random
from datetime import datetime
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class EmotionalContext:
    """Tracks the emotional state of the current conversation."""

    MOODS = ["neutral", "positive", "negative", "stressed", "excited", "tired", "focused"]

    def __init__(self):
        self.current_mood = "neutral"
        self.user_energy = "normal"  # low, normal, high
        self.conversation_depth = 0  # How deep/personal the conversation is
        self.frustration_level = 0   # 0-5, increases on repeated failures

    def update_from_message(self, message: str) -> None:
        """Detect emotional signals in user message."""
        msg_lower = message.lower()

        # Frustration signals
        frustration_words = ["ugh", "damn", "not working", "broken", "useless", "stupid", "again"]
        if any(w in msg_lower for w in frustration_words):
            self.frustration_level = min(5, self.frustration_level + 1)
            self.current_mood = "negative"
            return

        # Reset frustration on positive signals
        positive_words = ["thanks", "great", "perfect", "awesome", "nice", "good job", "love it"]
        if any(w in msg_lower for w in positive_words):
            self.frustration_level = max(0, self.frustration_level - 1)
            self.current_mood = "positive"

        # Energy signals
        tired_words = ["tired", "exhausted", "sleepy", "can't focus", "long day"]
        if any(w in msg_lower for w in tired_words):
            self.user_energy = "low"

        excited_words = ["excited", "can't wait", "amazing", "incredible", "wow"]
        if any(w in msg_lower for w in excited_words):
            self.user_energy = "high"

        self.conversation_depth += 1

    def get_tone_modifier(self) -> str:
        """Return a tone instruction for the LLM based on current emotional context."""
        modifiers = []

        if self.frustration_level >= 3:
            modifiers.append("The user seems frustrated. Be extra patient and helpful. Acknowledge any difficulties.")
        elif self.frustration_level >= 1:
            modifiers.append("Be straightforward and efficient — don't add unnecessary fluff.")

        if self.current_mood == "positive":
            modifiers.append("The user is in a good mood. Match their energy.")
        elif self.current_mood == "negative":
            modifiers.append("Be calm and supportive.")

        if self.user_energy == "low":
            modifiers.append("Keep responses brief — the user seems tired.")
        elif self.user_energy == "high":
            modifiers.append("The user has high energy. Be engaging.")

        return " ".join(modifiers) if modifiers else ""


class RelationshipMemory:
    """
    Tracks the relationship between Joseph and the user over time.
    Gets richer with each session.
    """

    def __init__(self):
        self.total_sessions = 0
        self.total_messages = 0
        self.first_interaction: Optional[datetime] = None
        self.last_interaction: Optional[datetime] = None
        self.topics_discussed: list[str] = []
        self.user_preferences: dict = {}
        self.inside_references: list[str] = []  # Things only they would know

    def get_familiarity_level(self) -> str:
        """
        Return familiarity level based on interaction history.

        Returns:
            'new', 'acquaintance', 'familiar', 'close'
        """
        if self.total_sessions < 3:
            return "new"
        elif self.total_sessions < 10:
            return "acquaintance"
        elif self.total_sessions < 30:
            return "familiar"
        else:
            return "close"

    def get_greeting_style(self) -> str:
        """Return appropriate greeting style based on familiarity."""
        level = self.get_familiarity_level()
        styles = {
            "new": "polite and professional",
            "acquaintance": "warm and helpful",
            "familiar": "casual and friendly",
            "close": "natural and personal",
        }
        return styles.get(level, "warm and helpful")


class AdvancedPersonality:
    """
    Full personality system for JOSEPH.

    Combines emotional intelligence, relationship memory,
    and adaptive response styling.

    Usage:
        personality = AdvancedPersonality()
        personality.update(user_message="I'm so tired today")
        modifier = personality.get_system_modifier()
        # Inject modifier into system prompt
    """

    # Response style variations to avoid repetition
    ACKNOWLEDGMENTS = [
        "", "", "", "",  # Empty = most natural
        "Got it.",
        "Sure.",
        "On it.",
        "Understood.",
        "Right.",
    ]

    THINKING_PHRASES = [
        "Let me think...",
        "One moment.",
        "Give me a second.",
        "Processing...",
    ]

    COMPLETION_PHRASES = [
        "Done.",
        "All set.",
        "There you go.",
        "Finished.",
        "Complete.",
    ]

    ERROR_PHRASES = [
        "Something went wrong on my end.",
        "I ran into an issue with that.",
        "That didn't work as expected.",
        "Hit a snag — want me to try again?",
    ]

    def __init__(self):
        self.emotional_context = EmotionalContext()
        self.relationship = RelationshipMemory()
        self.session_start = datetime.now()
        self.interaction_count = 0
        self._last_acknowledgment = ""

    def update(self, user_message: str) -> None:
        """
        Update personality state based on user message.
        Call this after every user message.

        Args:
            user_message: The user's latest message.
        """
        self.emotional_context.update_from_message(user_message)
        self.interaction_count += 1
        self.relationship.total_messages += 1
        self.relationship.last_interaction = datetime.now()

    def get_system_modifier(self) -> str:
        """
        Get a modifier string to append to the system prompt.
        Adjusts Joseph's tone based on current context.

        Returns:
            Modifier string, or empty string if no adjustment needed.
        """
        parts = []

        # Emotional tone
        tone = self.emotional_context.get_tone_modifier()
        if tone:
            parts.append(tone)

        # Familiarity level
        familiarity = self.relationship.get_familiarity_level()
        if familiarity == "close":
            parts.append(f"You know {settings.USER_NAME} well. Be natural and personal.")
        elif familiarity == "familiar":
            parts.append(f"You're familiar with {settings.USER_NAME}. Be warm and casual.")

        # Session context
        session_mins = int((datetime.now() - self.session_start).seconds / 60)
        if session_mins > 30:
            parts.append("This has been a long session. Be efficient.")

        return " ".join(parts)

    def get_acknowledgment(self) -> str:
        """Get a varied acknowledgment phrase (avoids repetition)."""
        options = [a for a in self.ACKNOWLEDGMENTS if a != self._last_acknowledgment]
        choice = random.choice(options)
        self._last_acknowledgment = choice
        return choice

    def get_error_phrase(self) -> str:
        """Get a natural error message."""
        return random.choice(self.ERROR_PHRASES)

    def format_response(self, raw: str) -> str:
        """
        Clean and format a raw LLM response.

        Removes robotic openers, cleans whitespace,
        applies personality touches.
        """
        response = raw.strip()

        # Remove robotic openers
        robotic = [
            "As an AI language model,",
            "As an AI,",
            "I am an AI",
            "I'm an AI",
            "Certainly! ",
            "Absolutely! ",
            "Of course! ",
            "Sure thing! ",
            "Great question! ",
            "That's a great question",
        ]
        for opener in robotic:
            if response.startswith(opener):
                response = response[len(opener):].strip()
                if response:
                    response = response[0].upper() + response[1:]

        return response

    def get_session_summary(self) -> str:
        """Return a brief session summary."""
        duration = datetime.now() - self.session_start
        minutes = int(duration.total_seconds() / 60)
        return (
            f"Session: {minutes}m active, "
            f"{self.interaction_count} exchanges, "
            f"mood: {self.emotional_context.current_mood}"
        )

    def load_from_memory(self, memory_manager) -> None:
        """
        Load relationship data from long-term memory.
        Call this at session start.
        """
        try:
            stats = memory_manager.long_term.get_memory_stats()
            self.relationship.total_sessions = stats.get("total_sessions", 0)
            self.relationship.total_messages = stats.get("total_memories", 0)
        except Exception as e:
            logger.debug(f"Could not load relationship memory: {e}")


# Module-level singleton
advanced_personality = AdvancedPersonality()

"""
brain/personality.py
--------------------
Manages Joseph's personality state and dynamic response shaping.

This module tracks:
- Conversation mood/tone
- User relationship level (familiarity over time)
- Response style preferences
- Greeting variations so Joseph doesn't sound repetitive

It does NOT call the LLM — it shapes inputs/outputs around LLM calls.
"""

import logging
import random
from datetime import datetime
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class PersonalityEngine:
    """
    Controls how Joseph presents himself in conversation.

    The personality engine adjusts:
    - Greetings based on time of day
    - Response prefixes to avoid repetition
    - Tone based on conversation context
    - Familiarity level as the user interacts more
    """

    # Greetings by time of day
    MORNING_GREETINGS = [
        "Good morning, {name}. Ready when you are.",
        "Morning, {name}. What are we working on today?",
        "Good morning. How can I help you start the day?",
    ]

    AFTERNOON_GREETINGS = [
        "Good afternoon, {name}. What do you need?",
        "Afternoon. I'm here — what's on your mind?",
        "Good afternoon. How can I assist?",
    ]

    EVENING_GREETINGS = [
        "Good evening, {name}. What can I do for you?",
        "Evening. Still at it? What do you need?",
        "Good evening. I'm listening.",
    ]

    NIGHT_GREETINGS = [
        "Working late, {name}? I'm here.",
        "Late night session? What do you need?",
        "I'm here, {name}. What's up?",
    ]

    # Wake-word responses (when user says "Joseph")
    WAKE_RESPONSES = [
        "Yes?",
        "I'm here.",
        "Go ahead.",
        "Listening.",
        "What do you need?",
        "Yes, {name}?",
    ]

    # Acknowledgment phrases (before answering)
    ACKNOWLEDGMENTS = [
        "",  # Often no prefix is most natural
        "",
        "",
        "Got it.",
        "Sure.",
        "Of course.",
        "On it.",
        "Understood.",
    ]

    # Completion phrases
    COMPLETION_PHRASES = [
        "Done.",
        "All set.",
        "Finished.",
        "That's taken care of.",
        "Complete.",
    ]

    # Thinking/processing phrases
    THINKING_PHRASES = [
        "Let me think about that...",
        "One moment...",
        "Processing...",
        "Give me a second...",
    ]

    def __init__(self):
        self.user_name = settings.USER_NAME
        self.assistant_name = settings.JOSEPH_NAME
        self.interaction_count = 0
        self.session_start = datetime.now()
        self._last_greeting_type = None

    def get_greeting(self) -> str:
        """
        Return a time-appropriate greeting.
        Varies the greeting so it doesn't feel repetitive.
        """
        hour = datetime.now().hour

        if 5 <= hour < 12:
            pool = self.MORNING_GREETINGS
        elif 12 <= hour < 17:
            pool = self.AFTERNOON_GREETINGS
        elif 17 <= hour < 21:
            pool = self.EVENING_GREETINGS
        else:
            pool = self.NIGHT_GREETINGS

        greeting = random.choice(pool)
        return greeting.format(name=self.user_name)

    def get_wake_response(self) -> str:
        """
        Response when the wake word is detected.
        Short, natural, varied.
        """
        response = random.choice(self.WAKE_RESPONSES)
        return response.format(name=self.user_name)

    def get_acknowledgment(self) -> str:
        """
        Optional prefix before a response.
        Returns empty string often — silence is natural.
        """
        return random.choice(self.ACKNOWLEDGMENTS)

    def get_completion_phrase(self) -> str:
        """Phrase to use when a task is completed."""
        return random.choice(self.COMPLETION_PHRASES)

    def get_thinking_phrase(self) -> str:
        """Phrase to use while processing a complex request."""
        return random.choice(self.THINKING_PHRASES)

    def format_response(self, raw_response: str, task_completed: bool = False) -> str:
        """
        Optionally shape a raw LLM response with personality touches.

        Currently:
        - Strips excessive whitespace
        - Ensures response doesn't start with robotic phrases
        - Increments interaction counter

        Args:
            raw_response: The raw text from the LLM.
            task_completed: Whether this response signals task completion.

        Returns:
            Formatted response string.
        """
        self.interaction_count += 1

        # Clean up whitespace
        response = raw_response.strip()

        # Remove common robotic LLM openers
        robotic_openers = [
            "As an AI language model,",
            "As an AI,",
            "I am an AI assistant",
            "I'm an AI assistant",
            "Certainly! ",
            "Absolutely! ",
            "Of course! ",
            "Sure thing! ",
        ]
        for opener in robotic_openers:
            if response.startswith(opener):
                response = response[len(opener):].strip()
                # Capitalize first letter after removal
                if response:
                    response = response[0].upper() + response[1:]

        return response

    def get_error_response(self, error_type: str = "general") -> str:
        """
        Natural error messages instead of technical stack traces.

        Args:
            error_type: Type of error (general, connection, timeout, etc.)

        Returns:
            A natural-sounding error message.
        """
        error_messages = {
            "general": "Something went wrong on my end. Want to try again?",
            "connection": f"I can't reach the language model right now. Make sure Ollama is running.",
            "timeout": "That took too long and I had to stop. Try a simpler request or check if Ollama is running.",
            "model_not_found": (
                f"The model '{settings.OLLAMA_MODEL}' isn't available. "
                f"Run: ollama pull {settings.OLLAMA_MODEL}"
            ),
            "memory": "I had trouble accessing memory right now, but I can still chat.",
        }
        return error_messages.get(error_type, error_messages["general"])

    def get_session_summary(self) -> str:
        """Return a brief summary of the current session."""
        duration = datetime.now() - self.session_start
        minutes = int(duration.total_seconds() / 60)
        return (
            f"Session active for {minutes} minute(s). "
            f"{self.interaction_count} interaction(s) this session."
        )

    def __repr__(self) -> str:
        return (
            f"PersonalityEngine(interactions={self.interaction_count}, "
            f"session_start={self.session_start.strftime('%H:%M')})"
        )


# Module-level singleton
personality = PersonalityEngine()

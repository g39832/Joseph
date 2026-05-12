"""
agents/planner_agent.py
------------------------
Planner agent — decides HOW to handle complex user requests.

Sits between the user input and execution layer.
Decides: is this a simple chat? A single action? A multi-step task?
"""

import logging
import re

logger = logging.getLogger(__name__)

# Indicators of multi-step tasks
MULTI_STEP_PATTERNS = [
    r"\band then\b",
    r"\bafter that\b",
    r"\bthen\b.{0,20}\b(open|search|play|type|click)\b",
    r"\bfirst.{0,30}then\b",
    r"\balso\b.{0,20}\b(open|search|play)\b",
]


class PlannerAgent:
    """
    Analyzes user requests and routes them appropriately.

    Determines if a request needs:
    - Simple chat response
    - Single automation action
    - Multi-step task execution
    """

    def __init__(self, task_agent=None, llm=None):
        self.task_agent = task_agent
        self.llm = llm

    def analyze(self, user_input: str) -> str:
        """
        Analyze request type.

        Returns: 'chat', 'single_action', 'multi_step'
        """
        text_lower = user_input.lower()

        # Check for multi-step indicators
        for pattern in MULTI_STEP_PATTERNS:
            if re.search(pattern, text_lower):
                return "multi_step"

        # Check for single action keywords
        action_words = [
            "open", "search", "play", "launch", "go to",
            "screenshot", "clipboard", "type", "find"
        ]
        if any(word in text_lower for word in action_words):
            return "single_action"

        return "chat"

    def should_use_task_agent(self, user_input: str) -> bool:
        """Return True if this request needs multi-step execution."""
        return self.analyze(user_input) == "multi_step"

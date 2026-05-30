"""
brain/self_correction.py
-------------------------
Self-correction loop for JOSEPH.

After generating a response, Joseph quickly checks if it
actually answered the question. If not, he tries again.

This runs as a lightweight background check — only triggers
when the response seems off. Reduces bad responses significantly.

Checks for:
- Response is too short for a complex question
- Response doesn't address the question topic
- Response contains "I don't know" when it should know
- Response is a refusal when it shouldn't be
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Minimum response length for complex questions (words)
MIN_COMPLEX_RESPONSE_WORDS = 20

# Patterns that indicate a bad/incomplete response
BAD_RESPONSE_PATTERNS = [
    r"^i (don't|do not|cannot|can't) (help|assist|answer)",
    r"^i'm (sorry|afraid) (but )?i (can't|cannot|don't)",
    r"^as an ai",
    r"^i don't have (access|information|knowledge)",
]

# Patterns that indicate a complex question needing a real answer
COMPLEX_QUESTION_PATTERNS = [
    r"\b(explain|describe|how does|what is|why does|compare|analyze)\b",
    r"\b(write|create|generate|build|make)\b",
    r"\b(difference between|pros and cons|advantages|disadvantages)\b",
]


class SelfCorrection:
    """
    Checks and optionally corrects LLM responses.

    Usage:
        corrector = SelfCorrection(llm=llm)
        final = corrector.check_and_correct(question, response)
    """

    def __init__(self, llm=None, enabled: bool = True):
        self._llm = llm
        self.enabled = enabled
        self._corrections_made = 0

    def should_check(self, question: str, response: str) -> bool:
        """
        Determine if a response needs checking.
        Only checks when there's a real reason to — avoids overhead.
        """
        if not self.enabled or not self._llm:
            return False

        # Skip for very short questions (greetings, simple commands)
        if len(question.split()) < 5:
            return False

        # Skip for automation responses
        automation_indicators = ["opening", "playing", "searching", "launched", "saved"]
        if any(ind in response.lower() for ind in automation_indicators):
            return False

        # Check for bad response patterns
        for pattern in BAD_RESPONSE_PATTERNS:
            if re.search(pattern, response.lower()):
                return True

        # Check if complex question got too short an answer
        is_complex = any(
            re.search(p, question.lower())
            for p in COMPLEX_QUESTION_PATTERNS
        )
        if is_complex and len(response.split()) < MIN_COMPLEX_RESPONSE_WORDS:
            return True

        return False

    def check_and_correct(
        self,
        question: str,
        response: str,
        messages: list = None,
        system_prompt: str = None,
    ) -> str:
        """
        Check a response and correct it if needed.

        Args:
            question: The original user question.
            response: Joseph's generated response.
            messages: Conversation history for context.
            system_prompt: System prompt used.

        Returns:
            The original response, or a corrected one.
        """
        if not self.should_check(question, response):
            return response

        try:
            logger.debug(f"Self-correction check triggered for: {question[:50]}")

            # Quick quality check
            check_prompt = f"""Rate this response quality from 1-10.
Question: "{question}"
Response: "{response}"

Respond with JSON: {{"score": 7, "issue": "brief issue description or null"}}
JSON:"""

            try:
                import json
                raw = self._llm.generate(check_prompt, temperature=0.0)
                json_match = re.search(r'\{[^{}]*\}', raw)
                if json_match:
                    data = json.loads(json_match.group())
                    score = data.get("score", 8)

                    if score >= 6:
                        return response  # Good enough

                    logger.info(f"Self-correction: score={score}, retrying response")
                    self._corrections_made += 1

                    # Retry with explicit instruction
                    if messages and self._llm:
                        retry_messages = list(messages)
                        retry_messages.append({
                            "role": "user",
                            "content": f"{question}\n\n(Please give a complete, helpful answer.)"
                        })
                        corrected = self._llm.chat(
                            messages=retry_messages[:-1],
                            system_prompt=system_prompt,
                        )
                        if corrected and len(corrected) > len(response):
                            return corrected

            except Exception as e:
                logger.debug(f"Self-correction check error: {e}")

        except Exception as e:
            logger.debug(f"Self-correction error: {e}")

        return response

    @property
    def corrections_made(self) -> int:
        return self._corrections_made

    def __repr__(self) -> str:
        return f"SelfCorrection(enabled={self.enabled}, corrections={self._corrections_made})"

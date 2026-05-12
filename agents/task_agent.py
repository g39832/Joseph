"""
agents/task_agent.py
---------------------
Task execution agent — handles multi-step tasks autonomously.

Given a goal like "search YouTube for lofi music and play the first result",
the task agent breaks it into steps and executes them in sequence.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class TaskAgent:
    """
    Executes multi-step tasks autonomously.

    Usage:
        agent = TaskAgent(router=command_router, llm=llm)
        result = agent.execute("search YouTube for lofi music and play it")
    """

    def __init__(self, router=None, llm=None):
        self.router = router
        self.llm = llm

    def set_router(self, router) -> None:
        self.router = router

    def set_llm(self, llm) -> None:
        self.llm = llm

    def execute(self, goal: str) -> str:
        """
        Execute a potentially multi-step goal.

        Args:
            goal: Natural language description of what to do.

        Returns:
            Result description string.
        """
        if not self.router:
            return "Task agent not ready — no router available."

        # Try direct execution first
        response, was_automated = self.router.handle_sync(goal)
        if was_automated:
            return response

        # If LLM available, try to decompose into steps
        if self.llm:
            return self._decompose_and_execute(goal)

        return ""

    def _decompose_and_execute(self, goal: str) -> str:
        """Use LLM to break goal into steps and execute each."""
        try:
            prompt = f"""Break this task into 1-3 simple steps. 
Each step should be a single action Joseph can take.
Output ONLY the steps, one per line, no numbering.

Task: {goal}

Steps:"""
            steps_text = self.llm.generate(prompt, temperature=0.1)
            steps = [s.strip() for s in steps_text.strip().split("\n") if s.strip()]

            results = []
            for step in steps[:3]:  # Max 3 steps for safety
                response, was_automated = self.router.handle_sync(step)
                if was_automated and response:
                    results.append(response)

            if results:
                return " ".join(results)

        except Exception as e:
            logger.error(f"Task decomposition error: {e}")

        return ""

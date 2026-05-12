"""
agents/autonomous_agent.py
---------------------------
Autonomous agent loop for JOSEPH — Phase 7.

Given a high-level goal, Joseph breaks it into steps,
executes them in sequence, observes results, and adapts.

This is the "Jarvis" behavior — give Joseph a goal and
he figures out how to accomplish it without hand-holding.

Example goals:
  "Research the latest Python frameworks and save a summary"
  "Find all .txt files on my desktop and tell me what's in them"
  "Search YouTube for lofi music, open it, then set a reminder to stop in 1 hour"
  "Check the weather, add it to my notes, and give me a briefing"

The agent uses a ReAct-style loop:
  Thought → Action → Observation → Thought → Action → ...
"""

import logging
from typing import Callable, Optional

logger = logging.getLogger(__name__)

MAX_STEPS = 8  # Safety limit — never run more than 8 steps

AGENT_SYSTEM_PROMPT = """You are JOSEPH's autonomous execution engine.

Given a goal, you break it into steps and execute them one at a time.
After each step, you observe the result and decide what to do next.

Available actions:
- TOOL: <tool_call_json>  — execute a tool
- CHAT: <message>         — respond to the user directly
- DONE: <final_message>   — goal complete, give final summary

Rules:
- Be efficient — don't repeat steps
- If a step fails, try an alternative approach
- Maximum {max_steps} steps total
- Always end with DONE when the goal is achieved or cannot be achieved

Current step: {step}/{max_steps}
Goal: {goal}
History so far:
{history}

What is your next action? (respond with exactly one of: TOOL:, CHAT:, or DONE:)"""


class AutonomousAgent:
    """
    Executes multi-step goals autonomously.

    Uses a ReAct-style loop:
    1. Think about what to do next
    2. Execute an action (tool call or response)
    3. Observe the result
    4. Repeat until goal is achieved

    Usage:
        agent = AutonomousAgent(llm=llm, tool_dispatcher=dispatcher)
        result = agent.run("Research Python and save a summary to my notes")
        print(result)
    """

    def __init__(
        self,
        llm=None,
        tool_dispatcher=None,
        on_step: Optional[Callable] = None,
    ):
        """
        Args:
            llm: LLM interface for reasoning.
            tool_dispatcher: ToolDispatcher for executing actions.
            on_step: Optional callback called after each step with (step_num, action, result).
        """
        self.llm = llm
        self.tool_dispatcher = tool_dispatcher
        self.on_step = on_step

    def run(self, goal: str) -> str:
        """
        Execute a goal autonomously.

        Args:
            goal: Natural language goal description.

        Returns:
            Final result/summary string.
        """
        if not self.llm:
            return "Autonomous agent not ready — LLM not connected."

        logger.info(f"Autonomous agent starting: {goal}")
        history = []
        step = 0

        while step < MAX_STEPS:
            step += 1

            # Build the reasoning prompt
            history_text = "\n".join(history) if history else "None yet."
            prompt = AGENT_SYSTEM_PROMPT.format(
                max_steps=MAX_STEPS,
                step=step,
                goal=goal,
                history=history_text,
            )

            # Get next action from LLM
            try:
                action_text = self.llm.generate(prompt, temperature=0.2)
                action_text = action_text.strip()
                logger.info(f"Agent step {step}: {action_text[:100]}")
            except Exception as e:
                logger.error(f"Agent LLM error: {e}")
                return f"Agent encountered an error: {e}"

            # Parse and execute the action
            if action_text.startswith("DONE:"):
                final = action_text[5:].strip()
                logger.info(f"Agent completed in {step} steps")
                if self.on_step:
                    self.on_step(step, "DONE", final)
                return final

            elif action_text.startswith("CHAT:"):
                message = action_text[5:].strip()
                history.append(f"Step {step} — Response: {message}")
                if self.on_step:
                    self.on_step(step, "CHAT", message)
                # For CHAT actions, continue the loop
                continue

            elif action_text.startswith("TOOL:"):
                tool_json = action_text[5:].strip()
                result = self._execute_tool_action(tool_json)
                history.append(f"Step {step} — Tool: {tool_json[:80]} → Result: {result[:100]}")
                if self.on_step:
                    self.on_step(step, "TOOL", result)

            else:
                # LLM didn't follow format — treat as DONE
                logger.warning(f"Agent unexpected format: {action_text[:100]}")
                return action_text

        # Hit step limit
        logger.warning(f"Agent hit step limit ({MAX_STEPS}) for goal: {goal}")
        return f"I worked through {MAX_STEPS} steps on that goal. Here's what I accomplished:\n" + "\n".join(history[-3:])

    def _execute_tool_action(self, tool_json_str: str) -> str:
        """
        Execute a tool call from the agent's action.

        Args:
            tool_json_str: JSON string of the tool call.

        Returns:
            Result string from the tool.
        """
        if not self.tool_dispatcher:
            return "Tool dispatcher not available."

        try:
            import json
            import re

            # Extract JSON from the action text
            json_match = re.search(r'\{[^{}]*\}', tool_json_str, re.DOTALL)
            if not json_match:
                # Try treating the whole string as a natural language command
                response, was_handled = self.tool_dispatcher.dispatch(tool_json_str)
                return response if was_handled else "Tool not found."

            tool_call = json.loads(json_match.group())
            response, was_handled = self.tool_dispatcher._execute_tool(tool_call)
            return response if was_handled else "Tool execution returned no result."

        except Exception as e:
            logger.error(f"Agent tool execution error: {e}")
            return f"Tool error: {e}"

    def run_with_streaming(self, goal: str, callback: Callable) -> str:
        """
        Run the agent with step-by-step streaming updates.

        Args:
            goal: The goal to accomplish.
            callback: Called with each step update (step_num, action_type, result).

        Returns:
            Final result string.
        """
        self.on_step = callback
        return self.run(goal)

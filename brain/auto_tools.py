"""
brain/auto_tools.py
-------------------
Automatic tool selection — Phase 6.

Uses the LLM to decide which tool to invoke, respecting safety levels
and permission controls. Wraps both the Phase 3 ToolDispatcher and the
Phase 5 ToolRegistry.
"""

import json
import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class AutomaticToolSelector:
    """
    LLM-driven tool selection and execution.

    Tries Phase 5 registry first (formal),
    falls back to Phase 3 ToolDispatcher (flexible).
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._registry = None
        self._dispatcher = None
        self._permission_manager = None
        self._last_tool_result = None

    def _lazy_registry(self):
        if self._registry is None:
            try:
                from tools.registry import ToolRegistry
                self._registry = ToolRegistry()
            except Exception as e:
                logger.debug(f"ToolRegistry unavailable: {e}")
        return self._registry

    def _lazy_dispatcher(self):
        if self._dispatcher is None:
            try:
                from brain.tools import ToolDispatcher
                self._dispatcher = ToolDispatcher(llm=self.llm)
            except Exception as e:
                logger.debug(f"ToolDispatcher unavailable: {e}")
        return self._dispatcher

    def _lazy_permission_manager(self):
        if self._permission_manager is None:
            try:
                from tools.permission_manager import PermissionManager
                self._permission_manager = PermissionManager()
            except Exception as e:
                logger.debug(f"PermissionManager unavailable: {e}")
        return self._permission_manager

    def select_and_execute(self, user_input: str) -> dict:
        """
        Analyze user input, select a tool, execute it, return results.

        Returns:
            Dict with keys: used_tool, result, error, source.
        """
        result = {"used_tool": None, "result": None, "error": None, "source": None}

        # Try Phase 5 registry first
        registry = self._lazy_registry()
        if registry:
            tool_names = registry.list_tools()
            if tool_names:
                tool_name = self._classify_tool(user_input, tool_names)
                if tool_name and tool_name != "none":
                    # Check permission
                    pm = self._lazy_permission_manager()
                    if pm and not pm.is_approved(tool_name):
                        approved = pm.request_approval(tool_name, user_input)
                        if not approved:
                            result["error"] = f"Tool '{tool_name}' not approved"
                            return result

                    try:
                        tool_fn = registry.get_tool(tool_name)
                        if tool_fn:
                            args = self._extract_args(user_input, tool_name, tool_fn)
                            tool_result = tool_fn(**args)
                            self._last_tool_result = tool_result
                            result.update({
                                "used_tool": tool_name,
                                "result": str(tool_result)[:2000],
                                "source": "registry",
                            })
                            return result
                    except Exception as e:
                        logger.debug(f"Registry tool error: {e}")

        # Fall back to Phase 3 ToolDispatcher
        dispatcher = self._lazy_dispatcher()
        if dispatcher:
            try:
                response, was_automated = dispatcher.dispatch(user_input)
                if was_automated and response:
                    self._last_tool_result = response
                    result.update({
                        "used_tool": "dispatcher",
                        "result": str(response)[:2000],
                        "source": "dispatcher",
                    })
                    return result
            except Exception as e:
                logger.debug(f"Dispatcher error: {e}")

        result["error"] = "No suitable tool found"
        return result

    def _classify_tool(self, user_input: str, tool_names: list[str]) -> Optional[str]:
        """Use LLM to pick the best tool for the input."""
        if not self.llm:
            return None

        prompt = (
            "You are a tool classifier. Given the user request, choose the best tool from the list.\n\n"
            f"Available tools: {', '.join(tool_names)}\n\n"
            f"User request: \"{user_input}\"\n\n"
            'Respond with ONLY a tool name from the list, or "none" if no tool fits.\n'
            "Tool name:"
        )
        try:
            response = self.llm.generate(prompt, temperature=0.1).strip().lower()
            for name in tool_names:
                if name.lower() in response or response == name.lower():
                    return name
            if "none" in response:
                return None
            return None
        except Exception as e:
            logger.debug(f"Tool classification error: {e}")
            return None

    def _extract_args(self, user_input: str, tool_name: str, tool_fn) -> dict:
        """Use LLM to extract keyword arguments for the tool."""
        if not self.llm:
            return {}

        prompt = (
            f"You are an argument extractor. Extract JSON parameters for tool '{tool_name}' "
            f"from the user request.\n\n"
            f"User request: \"{user_input}\"\n\n"
            "Respond with ONLY a JSON object of parameters (can be empty {{}}).\n"
            "JSON:"
        )
        try:
            response = self.llm.generate(prompt, temperature=0.1).strip()
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {}
        except Exception:
            return {}

    def get_last_result(self) -> Optional[str]:
        return self._last_tool_result

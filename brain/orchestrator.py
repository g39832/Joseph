"""
brain/orchestrator.py
---------------------
Assistant Router — Phase 6 unified orchestration engine.

Routes each user request to the appropriate subsystems based on intent,
builds execution plans, combines results, and returns unified responses
with explanation traces.
"""

import json
import logging
import re
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Intent categories
INTENT_CONVERSATION = "conversation"
INTENT_CODING = "coding"
INTENT_RESEARCH = "research"
INTENT_PROJECT = "project"
INTENT_TOOL = "tool"
INTENT_MEMORY = "memory"
INTENT_FILE_OPERATION = "file_operation"
INTENT_CODE_ANALYSIS = "code_analysis"
INTENT_VOICE_COMMAND = "voice_command"
INTENT_MIXED = "mixed"

ALL_INTENTS = [
    INTENT_CONVERSATION,
    INTENT_CODING,
    INTENT_RESEARCH,
    INTENT_PROJECT,
    INTENT_TOOL,
    INTENT_MEMORY,
    INTENT_FILE_OPERATION,
    INTENT_CODE_ANALYSIS,
    INTENT_VOICE_COMMAND,
    INTENT_MIXED,
]

# Routing table: intent → subsystems to invoke
ROUTING_TABLE = {
    INTENT_CONVERSATION: {
        "subsystems": ["memory", "graph"],
        "response_mode": "llm_stream",
    },
    INTENT_CODING: {
        "subsystems": ["engineer", "graph", "memory"],
        "response_mode": "llm_stream",
    },
    INTENT_RESEARCH: {
        "subsystems": ["research", "graph", "memory"],
        "response_mode": "llm_stream",
    },
    INTENT_PROJECT: {
        "subsystems": ["project_manager", "graph", "memory"],
        "response_mode": "llm_stream",
    },
    INTENT_TOOL: {
        "subsystems": ["tools", "memory"],
        "response_mode": "tool_result",
    },
    INTENT_MEMORY: {
        "subsystems": ["memory"],
        "response_mode": "tool_result",
    },
    INTENT_FILE_OPERATION: {
        "subsystems": ["tools", "memory"],
        "response_mode": "tool_result",
    },
    INTENT_CODE_ANALYSIS: {
        "subsystems": ["engineer", "graph", "memory"],
        "response_mode": "llm_stream",
    },
    INTENT_VOICE_COMMAND: {
        "subsystems": ["tools", "memory"],
        "response_mode": "tool_result",
    },
    INTENT_MIXED: {
        "subsystems": ["tools", "graph", "memory", "project_manager"],
        "response_mode": "llm_stream",
    },
}


class ExecutionPlan:
    """
    A plan describing which subsystems to invoke and in what order.
    """

    def __init__(self, intent: str, subsystems: list[str], response_mode: str):
        self.intent = intent
        self.subsystems = subsystems
        self.response_mode = response_mode
        self.steps: list[dict] = []

    def add_step(self, subsystem: str, action: str, params: Optional[dict] = None):
        self.steps.append({
            "subsystem": subsystem,
            "action": action,
            "params": params or {},
            "status": "pending",
            "result": None,
            "duration_ms": 0,
        })

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "subsystems": self.subsystems,
            "response_mode": self.response_mode,
            "steps": self.steps,
        }


class OrchestrationResult:
    """
    Result of a single orchestrated turn.
    """

    def __init__(self):
        self.intent: str = INTENT_CONVERSATION
        self.plan: Optional[ExecutionPlan] = None
        self.context_sources: list[dict] = []
        self.tool_result: Optional[str] = None
        self.llm_response: Optional[str] = None
        self.graph_updates: list[dict] = []
        self.subsystem_outputs: dict[str, str] = {}
        self.duration_ms: float = 0.0
        self.error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "intent": self.intent,
            "plan": self.plan.to_dict() if self.plan else None,
            "context_sources": self.context_sources,
            "tool_result": self.tool_result[:500] if self.tool_result else None,
            "llm_response": self.llm_response[:500] if self.llm_response else None,
            "graph_updates": self.graph_updates,
            "subsystem_outputs": {
                k: v[:200] for k, v in self.subsystem_outputs.items()
            },
            "duration_ms": round(self.duration_ms, 1),
            "error": self.error,
        }


class AssistantRouter:
    """
    Central orchestration engine for JOSEPH Phase 6.

    Routes user input to the right subsystems, executes plans,
    and returns combined results with full explanation traces.
    """

    def __init__(
        self,
        llm=None,
        memory=None,
        hyper_engine=None,
        memory_relevance=None,
        smart_cache=None,
    ):
        self.llm = llm
        self.memory = memory
        self.hyper_engine = hyper_engine
        self._memory_relevance = memory_relevance
        self._smart_cache = smart_cache
        self._context_assembler = None
        self._auto_tools = None
        self._graph_automation = None
        self._last_result: Optional[OrchestrationResult] = None

    def _lazy_context_assembler(self):
        if self._context_assembler is None:
            from brain.context_assembler import ContextAssembler
            self._context_assembler = ContextAssembler(
                llm=self.llm,
                memory=self.memory,
                hyper_engine=self.hyper_engine,
                memory_relevance=self._memory_relevance,
                smart_cache=self._smart_cache,
            )
        return self._context_assembler

    def _lazy_auto_tools(self):
        if self._auto_tools is None:
            from brain.auto_tools import AutomaticToolSelector
            self._auto_tools = AutomaticToolSelector(llm=self.llm)
        return self._auto_tools

    def _lazy_graph_automation(self):
        if self._graph_automation is None:
            from brain.graph_automation import GraphAutomation
            self._graph_automation = GraphAutomation(llm=self.llm)
        return self._graph_automation

    def detect_intent(self, user_input: str) -> str:
        """
        Use LLM to classify the user's intent.

        Falls back to heuristic detection if LLM is unavailable.
        """
        if not self.llm:
            return self._heuristic_intent(user_input)

        prompt = (
            "Classify the user's request into exactly one intent category.\n\n"
            "Categories:\n"
            "- conversation: general chat, opinions, casual talk\n"
            "- coding: write code, explain code, debug, review\n"
            "- research: find information, compare, analyze data\n"
            "- project: manage tasks, milestones, goals, planning\n"
            "- tool: use a tool, open app, weather, notes, reminders\n"
            "- memory: recall, save, search memories or facts\n"
            "- file_operation: read, write, move, delete files\n"
            "- code_analysis: analyze architecture, dependencies, bugs\n"
            "- voice_command: voice-related instruction\n"
            "- mixed: combines multiple of the above\n\n"
            f"User request: \"{user_input}\"\n\n"
            "Category:"
        )
        try:
            response = self.llm.generate(prompt, temperature=0.1).strip().lower()
            for intent in ALL_INTENTS:
                if intent in response:
                    return intent
            return INTENT_CONVERSATION
        except Exception as e:
            logger.debug(f"Intent detection error, falling back: {e}")
            return self._heuristic_intent(user_input)

    def _heuristic_intent(self, user_input: str) -> str:
        """Simple keyword-based intent detection fallback."""
        lower = user_input.lower()
        words = set(lower.split())

        # Research (check before generic tools to avoid "search" matching tool)
        if any(w in lower for w in ["research", "search for", "find information", "tell me about"]):
            return INTENT_RESEARCH
        if any(w in lower for w in ["explain", "compare", "difference between"]):
            return INTENT_RESEARCH
        if lower.startswith("what is") and "weather" not in lower:
            return INTENT_RESEARCH

        # Code-related
        if any(w in lower for w in ["write code", "function", "class ", "def ", "bug", "debug", "refactor", "implement"]):
            if any(w in lower for w in ["analyze", "architecture", "dependency", "diagram"]):
                return INTENT_CODE_ANALYSIS
            return INTENT_CODING

        # File operations (broader matching)
        if any(w in lower for w in ["create file", "read file", "write file", "delete file", "move file", "list files", "save file"]):
            return INTENT_FILE_OPERATION
        if any(w in lower for w in ["create a file", "new file", "make a file"]):
            return INTENT_FILE_OPERATION

        # Memory (check before generic tools)
        if any(w in lower for w in ["remember", "forget", "memory", "recall", "what do you know"]):
            return INTENT_MEMORY

        # Project management
        if any(w in lower for w in ["project", "task", "milestone", "goal", "deadline", "plan"]):
            return INTENT_PROJECT

        # Voice
        if any(w in lower for w in ["voice", "speak", "say ", "talk"]):
            return INTENT_VOICE_COMMAND

        # Tools (generic - last check before conversation)
        if any(w in lower for w in ["open ", "weather", "note", "remind", "screenshot", "play ", "calendar", "email"]):
            return INTENT_TOOL
        if len(words & {"search", "find"}) > 0 and not any(w in lower for w in ["how to", "what is", "explain"]):
            return INTENT_TOOL

        return INTENT_CONVERSATION

    def build_plan(self, intent: str, user_input: str) -> ExecutionPlan:
        """Create an execution plan from the detected intent."""
        route = ROUTING_TABLE.get(intent, ROUTING_TABLE[INTENT_CONVERSATION])
        plan = ExecutionPlan(
            intent=intent,
            subsystems=list(route["subsystems"]),
            response_mode=route["response_mode"],
        )

        for subsystem in route["subsystems"]:
            if subsystem == "memory":
                plan.add_step("memory", "retrieve_context", {"query": user_input})
                plan.add_step("memory", "save_interaction", {})
            elif subsystem == "graph":
                plan.add_step("graph", "build_context", {"query": user_input})
                plan.add_step("graph", "extract_entities", {})
            elif subsystem == "tools":
                plan.add_step("tools", "select_and_execute", {"user_input": user_input})
            elif subsystem == "engineer":
                plan.add_step("engineer", "analyze_request", {"query": user_input})
            elif subsystem == "research":
                plan.add_step("research", "search_context", {"query": user_input})
            elif subsystem == "project_manager":
                plan.add_step("project_manager", "get_context", {"query": user_input})

        return plan

    def execute_plan(self, plan: ExecutionPlan, user_input: str, response: str = "") -> dict:
        """
        Execute an execution plan and return subsystem outputs.

        Args:
            plan: The execution plan.
            user_input: The user's input text.
            response: The LLM response (for graph extraction after streaming).

        Returns:
            Dict of subsystem_name → output.
        """
        outputs: dict[str, str] = {}

        for step in plan.steps:
            start = time.perf_counter()
            subsystem = step["subsystem"]
            action = step["action"]

            try:
                if subsystem == "memory":
                    if action == "retrieve_context":
                        assembler = self._lazy_context_assembler()
                        ctx = assembler.assemble(user_input)
                        outputs["memory_context"] = ctx.assemble()
                        outputs["context_sources"] = str(ctx.sources)
                    elif action == "save_interaction":
                        pass  # handled by the caller

                elif subsystem == "graph":
                    if action == "build_context":
                        assembler = self._lazy_context_assembler()
                        ctx = assembler.assemble(user_input, include_memory=False, include_graph=True, include_project=False, include_research=False)
                        if ctx.graph_context:
                            outputs["graph_context"] = ctx.graph_context
                    elif action == "extract_entities" and response:
                        ga = self._lazy_graph_automation()
                        updates = ga.extract_and_store(user_input, response)
                        outputs["graph_updates"] = json.dumps(updates)

                elif subsystem == "tools":
                    if action == "select_and_execute":
                        at = self._lazy_auto_tools()
                        tool_result = at.select_and_execute(user_input)
                        outputs["tool_result"] = json.dumps(tool_result)
                        if tool_result.get("result"):
                            outputs["tool_output"] = tool_result["result"]

                elif subsystem == "engineer":
                    outputs["engineer"] = "Engineering Assistant available"
                    try:
                        from engineer.engineering_assistant import EngineeringAssistant
                        ea = EngineeringAssistant()
                        analysis = ea.analyze(user_input)
                        outputs["engineer_result"] = str(analysis)[:1000]
                    except Exception as e:
                        outputs["engineer_error"] = str(e)

                elif subsystem == "research":
                    outputs["research"] = "Research subsystem available"
                    if self.memory:
                        try:
                            search = self.memory.search(user_input)
                            outputs["research_result"] = json.dumps({
                                k: str(v)[:300] for k, v in search.items() if v
                            })
                        except Exception as e:
                            outputs["research_error"] = str(e)

                elif subsystem == "project_manager":
                    try:
                        from projects.project_manager import ProjectManager
                        pm = ProjectManager()
                        dashboard = pm.get_dashboard_data()
                        outputs["project_dashboard"] = json.dumps(dashboard)[:1000]
                    except Exception as e:
                        outputs["project_error"] = str(e)

            except Exception as e:
                logger.debug(f"Plan step error ({subsystem}/{action}): {e}")
                outputs[f"{subsystem}_error"] = str(e)

            duration = (time.perf_counter() - start) * 1000
            step["status"] = "completed" if f"{subsystem}_error" not in outputs else "error"
            step["duration_ms"] = round(duration, 1)

        return outputs

    def route(
        self,
        user_input: str,
        llm_response: str = "",
    ) -> OrchestrationResult:
        """
        Full routing pipeline: detect intent → build plan → execute.

        Args:
            user_input: The user's message.
            llm_response: The LLM's response (provided after streaming).

        Returns:
            OrchestrationResult with full trace.
        """
        start = time.perf_counter()
        result = OrchestrationResult()

        try:
            # 1. Detect intent
            intent = self.detect_intent(user_input)
            result.intent = intent

            # 2. Build plan
            plan = self.build_plan(intent, user_input)
            result.plan = plan

            # 3. Execute plan
            outputs = self.execute_plan(plan, user_input, llm_response)
            result.subsystem_outputs = outputs

            # 4. Extract graph updates
            if "graph_updates" in outputs:
                try:
                    result.graph_updates = json.loads(outputs["graph_updates"])
                except Exception:
                    pass

            # 5. Extract tool result
            if "tool_result" in outputs:
                try:
                    tr = json.loads(outputs["tool_result"])
                    result.tool_result = tr.get("result") or tr.get("error")
                except Exception:
                    result.tool_result = outputs.get("tool_output")

            result.llm_response = llm_response

        except Exception as e:
            logger.error(f"Routing error: {e}")
            result.error = str(e)

        result.duration_ms = (time.perf_counter() - start) * 1000
        self._last_result = result
        return result

    def get_last_result(self) -> Optional[OrchestrationResult]:
        return self._last_result

    def get_context_for_user_input(self, user_input: str) -> str:
        """
        Convenience: get assembled context for a user input.
        Used by the UI to enrich system prompts.
        """
        assembler = self._lazy_context_assembler()
        ctx = assembler.assemble(user_input)
        return ctx.assemble()


def create_router(llm=None, memory=None, hyper_engine=None,
                  memory_relevance=None, smart_cache=None) -> AssistantRouter:
    """Convenience factory for creating an AssistantRouter."""
    return AssistantRouter(llm=llm, memory=memory, hyper_engine=hyper_engine,
                          memory_relevance=memory_relevance, smart_cache=smart_cache)

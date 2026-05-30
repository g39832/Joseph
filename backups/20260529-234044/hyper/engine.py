"""
hyper/engine.py
----------------
HyperIntelligenceEngine — Phase 2 of the Hyper-Intelligence Layer.

Sits ABOVE the existing AI system and coordinates advanced capabilities.
Never replaces existing intelligence — only enhances it.

Responsibilities:
- Long-term reasoning coordination
- Multi-step planning
- Task decomposition
- Goal tracking
- Knowledge synthesis
- Self-improvement analysis
- Context management
- Learning from previous interactions

All existing modules continue to work exactly as before.
This engine wraps and enhances them.
"""

import logging
import threading
from datetime import datetime
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class HyperIntelligenceEngine:
    """
    Top-level coordinator for all advanced AI capabilities.

    This engine is optional — Joseph works fine without it.
    When present, it enhances every interaction.

    Usage:
        engine = HyperIntelligenceEngine()
        engine.attach(llm=llm, memory=memory)
        engine.start()

        # Enhance a response
        enhanced = engine.enhance_response(user_input, base_response)
    """

    VERSION = "1.0.0"

    def __init__(self):
        self._llm = None
        self._memory = None
        self._running = False
        self._initialized = False

        # Sub-engines (lazy loaded)
        self._learning_engine = None
        self._web_intelligence = None
        self._gpu_manager = None
        self._personality_engine = None
        self._agent_orchestrator = None
        self._task_planner = None
        self._system_monitor = None

        # Feature flags — all off by default, enable as needed
        self.features = {
            "learning": settings.ENABLE_HYPER_LEARNING,
            "web_intelligence": settings.ENABLE_HYPER_WEB,
            "gpu_acceleration": settings.ENABLE_HYPER_GPU,
            "multi_agent": settings.ENABLE_HYPER_AGENT_ORCHESTRATION,
            "task_planning": True,
            "monitoring": True,
            "self_correction": True,
            "confidence_scoring": True,
        }

        # Goal tracking
        self._active_goals: list[dict] = []
        self._completed_goals: list[dict] = []

        logger.info(f"HyperIntelligenceEngine v{self.VERSION} initialized")

    def attach(self, llm=None, memory=None, **kwargs) -> None:
        """Attach existing system components."""
        if llm:
            self._llm = llm
        if memory:
            self._memory = memory
        for key, val in kwargs.items():
            setattr(self, f"_{key}", val)

    def start(self) -> bool:
        """Start all enabled sub-engines in background threads."""
        if self._running:
            return True

        self._running = True
        threading.Thread(target=self._initialize_engines, daemon=True).start()
        return True

    def stop(self) -> None:
        """Stop all sub-engines cleanly."""
        self._running = False
        if self._system_monitor:
            try:
                self._system_monitor.stop()
            except Exception:
                pass
        logger.info("HyperIntelligenceEngine stopped")

    def _initialize_engines(self) -> None:
        """Initialize all sub-engines in background."""
        try:
            if self.features.get("monitoring"):
                from hyper.monitor import SystemMonitor
                self._system_monitor = SystemMonitor()
                self._system_monitor.start()

            if self.features.get("learning") and self._memory:
                from hyper.learning import LearningEngine
                self._learning_engine = LearningEngine(
                    memory=self._memory,
                    llm=self._llm,
                )

            if self.features.get("web_intelligence"):
                from hyper.web_intelligence import WebIntelligenceEngine
                self._web_intelligence = WebIntelligenceEngine(llm=self._llm)

            if self.features.get("gpu_acceleration"):
                from hyper.gpu_manager import GPUComputeManager
                self._gpu_manager = GPUComputeManager()
                self._gpu_manager.initialize()

            if self.features.get("multi_agent") and self._llm:
                from hyper.agents import AgentOrchestrator
                self._agent_orchestrator = AgentOrchestrator(
                    llm=self._llm,
                    memory=self._memory,
                    web=self._web_intelligence,
                    planner=self._task_planner,
                    gpu=self._gpu_manager,
                    monitor=self._system_monitor,
                )

            if self.features.get("task_planning") and self._llm:
                from hyper.task_planner import TaskPlanner
                self._task_planner = TaskPlanner(llm=self._llm, memory=self._memory)

            if self.features.get("multi_agent") and self._agent_orchestrator:
                # Refresh orchestrator references after planner init.
                self._agent_orchestrator.planner = self._task_planner

            if self.features.get("self_correction") and self._memory:
                from hyper.personality import AssistantPersonalityEngine
                self._personality_engine = AssistantPersonalityEngine(memory=self._memory)

            self._initialized = True
            logger.info("HyperIntelligenceEngine fully initialized")

        except Exception as e:
            logger.warning(f"HyperIntelligenceEngine partial init: {e}")

    # ------------------------------------------------------------------ #
    # Core Enhancement Methods
    # ------------------------------------------------------------------ #

    def enhance_response(
        self,
        user_input: str,
        base_response: str,
        context: Optional[dict] = None,
    ) -> str:
        """
        Optionally enhance a base LLM response.

        This is called AFTER the base response is generated.
        It can add context, correct errors, or improve quality.
        Always returns a valid response — never blocks.

        Args:
            user_input: What the user asked.
            base_response: The base LLM response.
            context: Optional additional context.

        Returns:
            Enhanced response (or original if enhancement fails/not needed).
        """
        if not self._initialized:
            return base_response

        try:
            # Record interaction for learning
            if self._learning_engine:
                threading.Thread(
                    target=self._learning_engine.record_interaction,
                    args=(user_input, base_response),
                    daemon=True,
                ).start()

            # Give personality engine a chance to normalize tone without changing meaning.
            if self._personality_engine:
                base_response = self._personality_engine.format_response(base_response)

            return base_response

        except Exception as e:
            logger.debug(f"Response enhancement error: {e}")
            return base_response

    def get_context_enhancement(self, user_input: str) -> str:
        """
        Get additional context to inject into the system prompt.
        Called before generating a response.

        Returns:
            Additional context string, or empty string.
        """
        if not self._initialized:
            return ""

        parts = []

        try:
            # Add active goals context
            if self._active_goals:
                goal_text = "\n".join(
                    f"- {g['goal']}" for g in self._active_goals[:3]
                )
                parts.append(f"Active goals:\n{goal_text}")

            # Add system health context
            if self._system_monitor:
                health = self._system_monitor.get_health_summary()
                if health.get("warnings"):
                    parts.append(f"System: {', '.join(health['warnings'])}")

            # Add personality suggestions if available
            if self._personality_engine:
                suggestions = self._personality_engine.suggest_next_actions(user_input)
                if suggestions:
                    parts.append("Assistant focus: " + "; ".join(suggestions[:2]))

        except Exception as e:
            logger.debug(f"Context enhancement error: {e}")

        return "\n".join(parts)

    # ------------------------------------------------------------------ #
    # Goal Tracking
    # ------------------------------------------------------------------ #

    def add_goal(self, goal: str, priority: int = 2) -> str:
        """Track a user goal."""
        goal_entry = {
            "id": f"goal_{len(self._active_goals)}",
            "goal": goal,
            "priority": priority,
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }
        self._active_goals.append(goal_entry)
        logger.info(f"Goal added: {goal}")
        return goal_entry["id"]

    def complete_goal(self, goal_id: str) -> bool:
        """Mark a goal as completed."""
        for goal in self._active_goals:
            if goal["id"] == goal_id:
                goal["status"] = "completed"
                goal["completed_at"] = datetime.now().isoformat()
                self._completed_goals.append(goal)
                self._active_goals.remove(goal)
                return True
        return False

    def get_goals(self) -> dict:
        """Return active and completed goals."""
        return {
            "active": self._active_goals,
            "completed": self._completed_goals,
        }

    # ------------------------------------------------------------------ #
    # Web Research
    # ------------------------------------------------------------------ #

    def research(self, query: str, sources: int = 3) -> str:
        """
        Conduct multi-source web research on a topic.

        Args:
            query: Research topic.
            sources: Number of sources to consult.

        Returns:
            Synthesized research summary.
        """
        if not self._web_intelligence:
            return f"Web intelligence not initialized. Query: {query}"

        try:
            return self._web_intelligence.research(query, max_sources=sources)
        except Exception as e:
            logger.error(f"Research error: {e}")
            return f"Research failed: {e}"

    # ------------------------------------------------------------------ #
    # Multi-Agent Tasks
    # ------------------------------------------------------------------ #

    def run_agent_task(self, task: str, agent_type: str = "auto") -> str:
        """
        Run a task using the multi-agent framework.

        Args:
            task: Task description.
            agent_type: Which agent to use (research/planning/reasoning/auto).

        Returns:
            Task result.
        """
        if not self._agent_orchestrator:
            return ""

        try:
            return self._agent_orchestrator.run(task, agent_type=agent_type)
        except Exception as e:
            logger.error(f"Agent task error: {e}")
            return ""

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def get_status(self) -> dict:
        """Return full status of the hyper-intelligence layer."""
        return {
            "version": self.VERSION,
            "initialized": self._initialized,
            "running": self._running,
            "features": self.features,
            "active_goals": len(self._active_goals),
            "completed_goals": len(self._completed_goals),
            "engines": {
                "learning": self._learning_engine is not None,
                "web_intelligence": self._web_intelligence is not None,
                "gpu_manager": self._gpu_manager is not None,
                "agent_orchestrator": self._agent_orchestrator is not None,
                "task_planner": self._task_planner is not None,
                "system_monitor": self._system_monitor is not None,
                "personality_engine": self._personality_engine is not None,
            },
        }

    def __repr__(self) -> str:
        return (
            f"HyperIntelligenceEngine(v{self.VERSION}, "
            f"initialized={self._initialized}, "
            f"features={sum(self.features.values())}/{len(self.features)})"
        )

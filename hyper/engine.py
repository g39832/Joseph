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
import time
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
        self._knowledge_graph = None
        self._improvement_analyzer = None
        self._last_turn: dict = {}
        self._session_id: Optional[str] = None
        self._improvement_cache: dict = {}
        self._improvement_cache_ts: float = 0.0

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
            "knowledge_graph": settings.ENABLE_HYPER_GRAPH,
            "improvement_analysis": settings.ENABLE_HYPER_ANALYZER,
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
                self._system_monitor = SystemMonitor(sample_interval=settings.HYPER_MONITOR_INTERVAL)
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

            if self.features.get("task_planning") and self._llm:
                from hyper.task_planner import TaskPlanner
                self._task_planner = TaskPlanner(llm=self._llm, memory=self._memory)

            if self.features.get("knowledge_graph"):
                from hyper.knowledge_graph import KnowledgeGraph
                self._knowledge_graph = KnowledgeGraph()

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

            if self.features.get("self_correction") and self._memory:
                from hyper.personality import AssistantPersonalityEngine
                self._personality_engine = AssistantPersonalityEngine(memory=self._memory)

            if self.features.get("improvement_analysis"):
                from hyper.improvement_analyzer import ImprovementAnalyzer
                self._improvement_analyzer = ImprovementAnalyzer()

            if self._system_monitor and self._session_id:
                self._system_monitor.set_session(self._session_id)

            self._initialized = True
            logger.info("HyperIntelligenceEngine fully initialized")

        except Exception as e:
            logger.warning(f"HyperIntelligenceEngine partial init: {e}")

    def set_session_context(self, session_id: Optional[str] = None) -> None:
        """Attach session metadata for monitoring and dashboards."""
        if session_id:
            self._session_id = session_id
        if self._system_monitor and self._session_id:
            self._system_monitor.set_session(self._session_id)

    def _extract_topic(self, text: str) -> str:
        words = [w.strip(".,!?") for w in text.split()]
        for word in words:
            if len(word) > 4 and word[:1].isalpha():
                return word.lower()
        return "general"

    def _get_improvement_summary(self, max_age_seconds: float = 60.0) -> dict:
        """Return a cached improvement summary to avoid repeated full scans."""
        if not self._improvement_analyzer:
            return {}
        now = time.time()
        if self._improvement_cache and (now - self._improvement_cache_ts) < max_age_seconds:
            return self._improvement_cache
        try:
            self._improvement_cache = self._improvement_analyzer.summarize()
            self._improvement_cache_ts = now
        except Exception as e:
            logger.debug(f"Improvement summary cache failed: {e}")
            self._improvement_cache = {}
        return self._improvement_cache

    def prepare_turn(self, user_input: str, memory=None) -> dict:
        """
        Build the hyper-enhanced pre-response packet.

        This is the runtime path that keeps the hyper layer active.
        """
        if not self._initialized:
            return {
                "enabled": False,
                "system_context": "",
                "trace": {},
                "response_plan": "",
            }

        start = time.perf_counter()
        active_memory = memory or self._memory

        memory_context = ""
        memory_bundle = {}
        graph_context = ""
        coordinator = None
        research = ""
        research_bundle = {}
        planning = ""
        reasoning = ""
        memory_trace = ""

        try:
            if active_memory:
                memory_context = active_memory.get_context_for_llm(query=user_input)
                memory_bundle = active_memory.search(user_input)
                if hasattr(active_memory, "get_companion_context"):
                    companion = active_memory.get_companion_context()
                    if companion:
                        memory_context = f"{companion}\n\n{memory_context}" if memory_context else companion
                if self._knowledge_graph:
                    self._knowledge_graph.link_user_interest(
                        settings.USER_NAME,
                        self._extract_topic(user_input),
                        relation="asking_about",
                    )

            if self._knowledge_graph:
                try:
                    self._knowledge_graph.ingest_from_text(user_input, source_type="user_input")
                    graph_context = self._knowledge_graph.build_context(user_input)
                except Exception as e:
                    logger.debug(f"Knowledge graph context failed: {e}")

            if self._agent_orchestrator:
                coordinator = self._agent_orchestrator.coordinate_structured(user_input)
                research = coordinator["results"].get("research", "") or ""
                planning = coordinator["results"].get("planning", "") or ""
                reasoning = coordinator["results"].get("reasoning", "") or ""
                memory_trace = coordinator["results"].get("memory", "") or ""
            else:
                if self._web_intelligence:
                    research = self._web_intelligence.research(user_input, max_sources=3, memory_manager=active_memory)
                if self._task_planner:
                    plan = self._task_planner.create_plan(user_input)
                    planning = self._task_planner.get_progress_report(plan["id"]) if plan else ""
                if self._llm:
                    reasoning = self._llm.generate(
                        f"Analyze this request and suggest a safe next step:\n\n{user_input}",
                        temperature=0.2,
                    )

            research = research[:1500]
            planning = planning[:1500]
            reasoning = reasoning[:1500]
            memory_trace = memory_trace[:1000]

            if self._knowledge_graph and research:
                try:
                    self._knowledge_graph.ingest_from_text(research, source_type="research")
                except Exception:
                    pass

            if self._web_intelligence:
                try:
                    research_bundle = self._web_intelligence.get_last_research_bundle(user_input)
                except Exception:
                    research_bundle = {}

            system_parts = []
            if memory_context:
                system_parts.append(memory_context)
            if graph_context:
                system_parts.append(graph_context)
            if research:
                system_parts.append(f"Research agent:\n{research}")
            if planning:
                system_parts.append(f"Planning agent:\n{planning}")
            if reasoning:
                system_parts.append(f"Reasoning agent:\n{reasoning}")
            if memory_trace:
                system_parts.append(f"Memory agent:\n{memory_trace}")
            if coordinator and coordinator.get("final_response"):
                system_parts.append(f"Coordinator summary:\n{coordinator['final_response'][:2000]}")

            if self._personality_engine:
                suggestions = self._personality_engine.suggest_next_actions(user_input, memory_context=memory_context)
                if suggestions:
                    system_parts.append("Next actions:\n" + "\n".join(f"- {s}" for s in suggestions[:3]))

            if self._improvement_analyzer:
                summary = self._get_improvement_summary()
                if summary.get("high_priority"):
                    top = summary.get("findings", [])[:2]
                    lines = [f"- {item['issue']} @ {item['location']}" for item in top]
                    system_parts.append("Improvement watchlist:\n" + "\n".join(lines))

            packet = {
                "enabled": True,
                "session_id": self._session_id,
                "memory_context": memory_context,
                "memory_bundle": memory_bundle,
                "graph_context": graph_context,
                "research": research,
                "research_bundle": research_bundle,
                "planning": planning,
                "reasoning": reasoning,
                "coordinator": coordinator,
                "system_context": "\n\n".join([part for part in system_parts if part]).strip(),
                "trace": {
                    "memory_retrieval": bool(memory_context or memory_bundle),
                    "research": bool(research),
                    "planning": bool(planning),
                    "reasoning": bool(reasoning),
                    "coordinator": bool(coordinator),
                    "knowledge_graph": bool(graph_context),
                },
                "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 2),
            }
            self._last_turn = packet
            if self._system_monitor:
                self._system_monitor.record_api_latency(packet["elapsed_ms"])
            return packet

        except Exception as e:
            logger.debug(f"Hyper turn preparation failed: {e}")
            return {
                "enabled": True,
                "session_id": self._session_id,
                "memory_context": memory_context,
                "graph_context": graph_context,
                "research": research,
                "research_bundle": research_bundle,
                "planning": planning,
                "reasoning": reasoning,
                "coordinator": coordinator,
                "system_context": "\n\n".join([part for part in [memory_context, graph_context, research, planning, reasoning] if part]),
                "trace": {"error": str(e)},
                "elapsed_ms": round((time.perf_counter() - start) * 1000.0, 2),
            }

    def finalize_turn(self, user_input: str, response_text: str, elapsed_seconds: Optional[float] = None, memory=None) -> None:
        """Record response metrics and enrich the graph after a turn."""
        if not self._initialized:
            return
        try:
            active_memory = memory or self._memory
            if self._system_monitor and elapsed_seconds is not None:
                self._system_monitor.record_response_metrics(elapsed_seconds, response_text)
            if self._knowledge_graph and user_input:
                topic = self._extract_topic(user_input)
                self._knowledge_graph.add_relation(
                    settings.USER_NAME,
                    topic,
                    "discussed",
                    source_type="user",
                    target_type="topic",
                    evidence=response_text[:200],
                )
            if active_memory and response_text and hasattr(active_memory, "save_explicit_memory"):
                # Store only highly informative responses, not every reply.
                if len(response_text.split()) > 80 or "research" in user_input.lower():
                    try:
                        active_memory.save_explicit_memory(
                            f"Assistant response for '{user_input[:120]}': {response_text[:1500]}",
                            tags=["hyper", "response"],
                        )
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"Finalize turn skipped: {e}")

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

    def get_dashboard_data(self) -> dict:
        """Return real-time diagnostics data for dashboards."""
        status = self.get_status()
        memory_stats = None
        if self._memory:
            try:
                memory_stats = self._memory.get_status()
            except Exception:
                memory_stats = None

        research_bundle = self._web_intelligence.get_cache_size() if self._web_intelligence else 0
        gpu_status = self._gpu_manager.get_status() if self._gpu_manager else None
        monitor = self._system_monitor.get_metrics_snapshot() if self._system_monitor else {}
        agent_logs = self._agent_orchestrator.get_logs(limit=20) if self._agent_orchestrator else []
        graph_stats = self._knowledge_graph.summarize() if self._knowledge_graph else {}
        improvement = self._get_improvement_summary() if self._improvement_analyzer else {}

        return {
            "system": {
                "hyper_enabled": True,
                "model": self._llm.get_active_model() if self._llm and hasattr(self._llm, "get_active_model") else None,
                "session_id": self._session_id,
                "uptime_seconds": monitor.get("uptime_seconds", 0),
                "initialized": status["initialized"],
                "running": status["running"],
            },
            "performance": monitor,
            "agent_activity": {
                "active_agents": [name for name, enabled in status["engines"].items() if enabled],
                "execution_times": [entry.get("duration_ms", 0) for entry in agent_logs[-10:]],
                "decisions": agent_logs[-10:],
                "task_queue": self._task_planner.get_active_plans() if self._task_planner else [],
            },
            "memory": {
                "stats": memory_stats,
                "knowledge_graph": graph_stats,
                "vector_cache_entries": self._memory.chroma.get_count() if self._memory and hasattr(self._memory, "chroma") else 0,
            },
            "research": {
                "cache_entries": research_bundle,
                "last_turn": {
                    "research": bool(self._last_turn.get("research")),
                    "planning": bool(self._last_turn.get("planning")),
                    "reasoning": bool(self._last_turn.get("reasoning")),
                    "citation_count": len((self._last_turn.get("research_bundle") or {}).get("sources", [])),
                },
                "source_rankings": [
                    source.get("ranking", {})
                    for source in (self._last_turn.get("research_bundle") or {}).get("sources", [])
                ],
                "active_searches": 1 if self._last_turn.get("research") else 0,
            },
            "gpu": gpu_status,
            "self_improvement": improvement,
        }

    def get_audit_snapshot(self) -> dict:
        """Return a concise audit snapshot for documentation and diagnostics."""
        return {
            "version": self.VERSION,
            "initialized": self._initialized,
            "running": self._running,
            "features": self.features,
            "engines": self.get_status()["engines"],
            "last_turn": self._last_turn,
        }

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

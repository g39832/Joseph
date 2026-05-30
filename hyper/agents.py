"""
hyper/agents.py
---------------
Multi-agent orchestration for research, planning, reasoning, memory, and optimization.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AgentMessage:
    agent: str
    phase: str
    content: str
    duration_ms: float = 0.0
    metadata: Optional[dict] = None


class AgentOrchestrator:
    """Coordinates specialized agents and merges their output."""

    def __init__(self, llm=None, memory=None, web=None, planner=None, gpu=None, monitor=None):
        self.llm = llm
        self.memory = memory
        self.web = web
        self.planner = planner
        self.gpu = gpu
        self.monitor = monitor
        self._interaction_log: list[dict] = []

    def _route(self, task: str, agent_type: str) -> str:
        text = task.lower()
        if agent_type != "auto":
            return agent_type
        if any(word in text for word in ["research", "find sources", "verify", "fact"]):
            return "research"
        if any(word in text for word in ["plan", "roadmap", "milestone", "organize"]):
            return "planning"
        if any(word in text for word in ["memory", "remember", "context", "preference"]):
            return "memory"
        if any(word in text for word in ["optimize", "performance", "speed", "gpu"]):
            return "optimization"
        return "reasoning"

    def _research_agent(self, task: str) -> str:
        start = time.perf_counter()
        if self.web:
            result = self.web.research(task, max_sources=3, memory_manager=self.memory)
        else:
            result = "Research agent unavailable."
        self._log("research", "result", result, start)
        return result

    def _planning_agent(self, task: str) -> str:
        start = time.perf_counter()
        if self.planner:
            plan = self.planner.create_plan(task)
            result = self.planner.get_progress_report(plan["id"]) if plan else "Planning failed."
        else:
            result = "Planning agent unavailable."
        self._log("planning", "result", result, start)
        return result

    def _reasoning_agent(self, task: str) -> str:
        start = time.perf_counter()
        if self.llm:
            prompt = f"""Provide a concise expert analysis for the task below.
Focus on decision support, risks, and the best next step.

Task: {task}

Analysis:"""
            result = self.llm.generate(prompt, temperature=0.2)
        else:
            result = "Reasoning agent unavailable."
        self._log("reasoning", "result", result, start)
        return result

    def _memory_agent(self, task: str) -> str:
        start = time.perf_counter()
        if not self.memory:
            result = "Memory agent unavailable."
            self._log("memory", "result", result, start)
            return result
        try:
            context = self.memory.get_context_for_llm(query=task)
            result = context or "No memory context found."
        except Exception as e:
            result = f"Memory retrieval failed: {e}"
        self._log("memory", "result", result, start)
        return result

    def _optimization_agent(self, task: str) -> str:
        start = time.perf_counter()
        parts = []
        if self.gpu:
            parts.append(f"GPU backend: {self.gpu.get_best_backend()}")
            util = self.gpu.get_utilization()
            parts.append(
                f"GPU usage {util.get('gpu_usage', 0)}%, VRAM {util.get('vram_used_mb', 0)}/{util.get('vram_total_mb', 0)} MB"
            )
        if self.monitor:
            health = self.monitor.get_health_summary()
            if health.get("warnings"):
                parts.append("Warnings: " + ", ".join(health["warnings"]))
            else:
                parts.append("System health looks good.")
        if not parts:
            parts.append("No optimization signals available.")
        result = " ".join(parts)
        self._log("optimization", "result", result, start)
        return result

    def _log(self, agent: str, phase: str, content: str, start_time: float, metadata: Optional[dict] = None) -> None:
        entry = AgentMessage(
            agent=agent,
            phase=phase,
            content=content[:2000],
            duration_ms=round((time.perf_counter() - start_time) * 1000.0, 2),
            metadata=metadata or {},
        )
        self._interaction_log.append(asdict(entry))

    def run(self, task: str, agent_type: str = "auto") -> str:
        """Run the best agent or coordinate multiple specialized agents."""
        selected = self._route(task, agent_type)

        if selected == "research":
            return self._research_agent(task)
        if selected == "planning":
            return self._planning_agent(task)
        if selected == "memory":
            return self._memory_agent(task)
        if selected == "optimization":
            return self._optimization_agent(task)
        if selected == "reasoning":
            return self._reasoning_agent(task)
        return self.coordinate(task)

    def coordinate(self, task: str) -> str:
        """
        Run several agents in parallel and combine their results.
        """
        structured = self.coordinate_structured(task)
        return structured["final_response"]

    def coordinate_structured(self, task: str) -> dict:
        """
        Run several agents in parallel and return structured outputs.
        """
        jobs = {
            "research": self._research_agent,
            "planning": self._planning_agent,
            "reasoning": self._reasoning_agent,
            "memory": self._memory_agent,
            "optimization": self._optimization_agent,
        }
        results = {}
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {executor.submit(fn, task): name for name, fn in jobs.items()}
            for future in as_completed(future_map):
                name = future_map[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = f"{name} agent error: {e}"

        sections = []
        order = ["research", "planning", "reasoning", "memory", "optimization"]
        for name in order:
            value = results.get(name)
            if value:
                sections.append(f"[{name.upper()}]\n{value}")
        final_response = "\n\n".join(sections)
        self._log("coordinator", "final", final_response, start, metadata={"task": task})
        return {
            "task": task,
            "results": results,
            "final_response": final_response,
            "duration_ms": round((time.perf_counter() - start) * 1000.0, 2),
            "message_count": len(self._interaction_log),
        }

    def get_status(self) -> dict:
        return {
            "has_llm": self.llm is not None,
            "has_memory": self.memory is not None,
            "has_web": self.web is not None,
            "has_planner": self.planner is not None,
            "has_gpu": self.gpu is not None,
            "has_monitor": self.monitor is not None,
            "log_entries": len(self._interaction_log),
        }

    def get_logs(self, limit: int = 50) -> list[dict]:
        return self._interaction_log[-limit:]

    def __repr__(self) -> str:
        return f"AgentOrchestrator({self.get_status()})"

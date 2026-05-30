"""
hyper/agents.py
---------------
Multi-agent orchestration for research, planning, reasoning, memory, and optimization.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Coordinates specialized agents and merges their output."""

    def __init__(self, llm=None, memory=None, web=None, planner=None, gpu=None, monitor=None):
        self.llm = llm
        self.memory = memory
        self.web = web
        self.planner = planner
        self.gpu = gpu
        self.monitor = monitor

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
        if self.web:
            return self.web.research(task, max_sources=3)
        return "Research agent unavailable."

    def _planning_agent(self, task: str) -> str:
        if self.planner:
            plan = self.planner.create_plan(task)
            return self.planner.get_progress_report(plan["id"]) if plan else "Planning failed."
        return "Planning agent unavailable."

    def _reasoning_agent(self, task: str) -> str:
        if self.llm:
            prompt = f"""Provide a concise expert analysis for the task below.
Focus on decision support, risks, and the best next step.

Task: {task}

Analysis:"""
            return self.llm.generate(prompt, temperature=0.2)
        return "Reasoning agent unavailable."

    def _memory_agent(self, task: str) -> str:
        if not self.memory:
            return "Memory agent unavailable."
        try:
            context = self.memory.get_context_for_llm(query=task)
            return context or "No memory context found."
        except Exception as e:
            return f"Memory retrieval failed: {e}"

    def _optimization_agent(self, task: str) -> str:
        parts = []
        if self.gpu:
            parts.append(f"GPU backend: {self.gpu.get_best_backend()}")
        if self.monitor:
            health = self.monitor.get_health_summary()
            if health.get("warnings"):
                parts.append("Warnings: " + ", ".join(health["warnings"]))
            else:
                parts.append("System health looks good.")
        if not parts:
            parts.append("No optimization signals available.")
        return " ".join(parts)

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
        jobs = {
            "research": self._research_agent,
            "planning": self._planning_agent,
            "reasoning": self._reasoning_agent,
            "memory": self._memory_agent,
            "optimization": self._optimization_agent,
        }
        results = {}
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
        return "\n\n".join(sections)

    def get_status(self) -> dict:
        return {
            "has_llm": self.llm is not None,
            "has_memory": self.memory is not None,
            "has_web": self.web is not None,
            "has_planner": self.planner is not None,
            "has_gpu": self.gpu is not None,
            "has_monitor": self.monitor is not None,
        }

    def __repr__(self) -> str:
        return f"AgentOrchestrator({self.get_status()})"


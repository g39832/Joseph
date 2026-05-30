"""
tests/test_hyper_layer.py
-------------------------
Smoke tests for the Hyper-Intelligence layer.

These tests are intentionally offline-safe and use fallback behavior so they
can run in restricted environments.
"""

import os
import sys
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_bootstrap_disabled():
    from hyper.bootstrap import create_hyper_engine

    engine = create_hyper_engine(enabled=False)
    assert engine is None


def test_gpu_manager_detects_or_falls_back():
    from hyper.gpu_manager import GPUComputeManager

    gpu = GPUComputeManager()
    assert isinstance(gpu.initialize(), bool)
    status = gpu.get_status()
    assert "backend" in status
    assert "initialized" in status


def test_system_monitor_health_summary():
    from hyper.monitor import SystemMonitor

    monitor = SystemMonitor()
    health = monitor.get_health_summary()
    assert "ok" in health
    assert "warnings" in health
    assert "metrics" in health


def test_personality_engine_suggestions():
    from hyper.personality import AssistantPersonalityEngine

    engine = AssistantPersonalityEngine()
    modifier = engine.get_modifier("please research this for me")
    suggestions = engine.suggest_next_actions("please research this for me")

    assert isinstance(modifier, str)
    assert isinstance(suggestions, list)
    assert len(suggestions) > 0


def test_task_planner_creates_plan():
    from hyper.task_planner import TaskPlanner

    planner = TaskPlanner(db_path=Path("hyper_tasks_test.db"))
    plan = planner.create_plan("research the hyper layer and summarize it")
    assert plan["goal"] == "research the hyper layer and summarize it"
    assert len(plan["steps"]) >= 1
    report = planner.get_progress_report(plan["id"])
    assert "Progress" in report


def test_web_intelligence_offline_synthesis():
    from hyper.web_intelligence import WebIntelligenceEngine

    web = WebIntelligenceEngine()
    web._search_sources = lambda query, max_sources=3: [
        {"url": "https://example.com/a", "title": "A", "snippet": ""},
        {"url": "https://example.com/b", "title": "B", "snippet": ""},
    ]
    web._fetch_text = lambda url, limit=4000: f"Content from {url} about the topic."

    report = web.research("test query", max_sources=2)
    assert "Research query: test query" in report
    assert "Sources:" in report


def test_agent_orchestrator_coordinate():
    from hyper.agents import AgentOrchestrator

    fake_llm = Mock()
    fake_llm.generate.return_value = "Reasoned summary."

    fake_memory = Mock()
    fake_memory.get_context_for_llm.return_value = "Memory context"

    fake_web = Mock()
    fake_web.research.return_value = "Research summary."

    fake_planner = Mock()
    fake_plan = {"id": 1, "goal": "x", "steps": [{"status": "pending", "title": "step"}], "progress": 0.0}
    fake_planner.create_plan.return_value = fake_plan
    fake_planner.get_progress_report.return_value = "Plan report."

    orchestrator = AgentOrchestrator(
        llm=fake_llm,
        memory=fake_memory,
        web=fake_web,
        planner=fake_planner,
    )

    output = orchestrator.coordinate("research and plan the task")
    assert "[RESEARCH]" in output
    assert "[PLANNING]" in output
    assert "[REASONING]" in output


def test_hyper_engine_context_and_enhancement():
    from hyper.engine import HyperIntelligenceEngine

    class FakeLearning:
        def record_interaction(self, user_input, response):
            return None

    class FakeMonitor:
        def get_health_summary(self):
            return {"warnings": ["High CPU"], "ok": False}

    class FakePersonality:
        def format_response(self, raw):
            return raw.strip()

        def suggest_next_actions(self, user_input):
            return ["Do the next thing."]

    engine = HyperIntelligenceEngine()
    engine._learning_engine = FakeLearning()
    engine._system_monitor = FakeMonitor()
    engine._personality_engine = FakePersonality()
    engine._initialized = True

    context = engine.get_context_enhancement("please help me research")
    enhanced = engine.enhance_response("please help me research", "Base response")

    assert "High CPU" in context
    assert "Assistant focus" in context
    assert enhanced == "Base response"


if __name__ == "__main__":
    tests = [
        test_bootstrap_disabled,
        test_gpu_manager_detects_or_falls_back,
        test_system_monitor_health_summary,
        test_personality_engine_suggestions,
        test_task_planner_creates_plan,
        test_web_intelligence_offline_synthesis,
        test_agent_orchestrator_coordinate,
        test_hyper_engine_context_and_enhancement,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print(f"PASS {test.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {test.__name__}: {e}")

    print(f"Results: {passed} passed, {failed} failed")
    raise SystemExit(0 if failed == 0 else 1)

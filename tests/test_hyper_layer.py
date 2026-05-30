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


def test_knowledge_graph_context():
    from hyper.knowledge_graph import KnowledgeGraph
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        graph = KnowledgeGraph(db_path=Path(tmpdir) / "graph.db")
        graph.add_relation("User", "Computer Engineering", "interested_in")
        graph.add_relation("Computer Engineering", "Embedded Systems", "includes")

        context = graph.build_context("computer engineering embedded systems")
        assert "Knowledge graph context" in context
        assert "Computer Engineering" in context


def test_improvement_analyzer_detects_duplicate_defs():
    from hyper.improvement_analyzer import ImprovementAnalyzer
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        p = Path(tmpdir) / "sample.py"
        p.write_text(
            "def demo():\n    return 1\n\ndef demo():\n    return 2\n",
            encoding="utf-8",
        )
        analyzer = ImprovementAnalyzer(root=Path(tmpdir))
        findings = analyzer.analyze_repository()
        assert any("Duplicate function definition" in f["issue"] for f in findings)


def test_dashboard_snapshot_from_engine():
    from hyper.engine import HyperIntelligenceEngine

    engine = HyperIntelligenceEngine()
    engine._initialized = True
    engine._llm = Mock()
    engine._llm.get_active_model.return_value = "llama3"
    engine._memory = Mock()
    engine._memory.get_status.return_value = {"short_term_messages": 2}
    engine._memory.chroma = Mock()
    engine._memory.chroma.get_count.return_value = 7
    engine._system_monitor = Mock()
    engine._system_monitor.get_metrics_snapshot.return_value = {
        "cpu_usage": 11,
        "memory_usage": 22,
        "gpu_usage": 33,
        "vram_usage": 44,
        "api_latency_ms": 55,
        "response_time_ms": 66,
        "tokens_per_second": 77,
        "tool_failures": 0,
        "model_performance": 88,
        "response_quality": 0.9,
        "session_id": "abc",
        "uptime_seconds": 1.2,
    }
    engine._system_monitor.get_health_summary.return_value = {"warnings": [], "ok": True}
    engine._gpu_manager = Mock()
    engine._gpu_manager.get_status.return_value = {"backend": "cuda"}
    engine._agent_orchestrator = Mock()
    engine._agent_orchestrator.get_logs.return_value = [{"agent": "coordinator", "duration_ms": 12}]
    engine._task_planner = Mock()
    engine._task_planner.get_active_plans.return_value = [{"id": 1}]
    engine._web_intelligence = Mock()
    engine._web_intelligence.get_cache_size.return_value = 4
    engine._knowledge_graph = Mock()
    engine._knowledge_graph.summarize.return_value = {"nodes": 2, "edges": 1}
    engine._improvement_analyzer = Mock()
    engine._improvement_analyzer.summarize.return_value = {"finding_count": 1, "high_priority": 1, "findings": [{"issue": "x", "location": "y"}]}

    data = engine.get_dashboard_data()
    assert data["system"]["hyper_enabled"] is True
    assert data["memory"]["vector_cache_entries"] == 7
    assert data["research"]["cache_entries"] == 4
    assert data["self_improvement"]["finding_count"] == 1


def test_prepare_turn_structured_pipeline():
    from hyper.engine import HyperIntelligenceEngine

    class FakeMemory:
        def get_context_for_llm(self, query):
            return f"Memory context for {query}"

        def search(self, query):
            return {"semantic_results": [], "keyword_results": [], "facts": {}}

        def get_companion_context(self):
            return "Recent memory context"

    class FakeOrchestrator:
        def coordinate_structured(self, task):
            return {
                "task": task,
                "results": {
                    "research": "Research report.",
                    "planning": "Plan report.",
                    "reasoning": "Reasoning report.",
                    "memory": "Memory report.",
                    "optimization": "Optimization report.",
                },
                "final_response": "[RESEARCH]\nResearch report.",
                "duration_ms": 12.3,
                "message_count": 1,
            }

        def get_logs(self, limit=50):
            return [{"agent": "coordinator", "phase": "final", "duration_ms": 12.3}]

    class FakeGraph:
        def link_user_interest(self, *args, **kwargs):
            return None

        def ingest_from_text(self, *args, **kwargs):
            return 1

        def build_context(self, query):
            return "Knowledge graph context:"

        def summarize(self):
            return {"nodes": 1, "edges": 1}

    class FakeMonitor:
        def __init__(self):
            self.latencies = []

        def record_api_latency(self, value):
            self.latencies.append(value)

        def get_metrics_snapshot(self):
            return {
                "cpu_usage": 1,
                "memory_usage": 2,
                "gpu_usage": 3,
                "vram_usage": 4,
                "api_latency_ms": 5,
                "response_time_ms": 6,
                "tokens_per_second": 7,
                "tool_failures": 0,
                "model_performance": 0.9,
                "response_quality": 0.8,
                "session_id": "sess",
                "uptime_seconds": 1.5,
            }

        def get_health_summary(self):
            return {"warnings": [], "ok": True}

    class FakeLearning:
        def record_interaction(self, user_input, response):
            return None

    class FakePlanner:
        def create_plan(self, task):
            return {"id": 1}

        def get_progress_report(self, plan_id):
            return "Plan report"

    class FakeWeb:
        def research(self, query, max_sources=3, memory_manager=None):
            return "Web research report."

    class FakePersonality:
        def suggest_next_actions(self, user_input, memory_context=""):
            return ["Next step"]

    engine = HyperIntelligenceEngine()
    engine._initialized = True
    engine._memory = FakeMemory()
    engine._agent_orchestrator = FakeOrchestrator()
    engine._knowledge_graph = FakeGraph()
    engine._system_monitor = FakeMonitor()
    engine._learning_engine = FakeLearning()
    engine._web_intelligence = FakeWeb()
    engine._task_planner = FakePlanner()
    engine._personality_engine = FakePersonality()
    engine._improvement_analyzer = Mock()
    engine._improvement_analyzer.summarize.return_value = {"high_priority": 0, "findings": []}

    packet = engine.prepare_turn("Research embedded systems")
    assert packet["enabled"] is True
    assert packet["trace"]["memory_retrieval"] is True
    assert packet["trace"]["research"] is True
    assert packet["trace"]["planning"] is True
    assert packet["trace"]["reasoning"] is True
    assert "Research agent" in packet["system_context"]
    assert "Coordinator summary" in packet["system_context"]


def test_long_term_memory_edit_pin_archive_delete():
    from memory.long_term import LongTermMemory
    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "memory.db"
        memory = LongTermMemory(db_path=db_path)
        memory_id = memory.save_memory("Remember the blue theme", tags=["ui"], importance=4)

        record = memory.get_memory_by_id(memory_id)
        assert record is not None
        assert record["content"] == "Remember the blue theme"

        assert memory.update_memory(memory_id, content="Remember the indigo theme", importance=7)
        assert memory.pin_memory(memory_id, enabled=True)
        assert memory.archive_memory(memory_id, enabled=True)

        updated = memory.get_memory_by_id(memory_id)
        assert updated["content"] == "Remember the indigo theme"
        assert "pinned" in updated["tags"]
        assert "archived" in updated["tags"]

        assert memory.delete_memory(memory_id)
        assert memory.get_memory_by_id(memory_id) is None


def test_hyper_engine_improvement_cache():
    from hyper.engine import HyperIntelligenceEngine

    class FakeAnalyzer:
        def __init__(self):
            self.calls = 0

        def summarize(self):
            self.calls += 1
            return {
                "finding_count": 1,
                "high_priority": 1,
                "medium_priority": 0,
                "low_priority": 0,
                "findings": [{"issue": "x", "location": "y"}],
            }

    engine = HyperIntelligenceEngine()
    analyzer = FakeAnalyzer()
    engine._improvement_analyzer = analyzer

    first = engine._get_improvement_summary(max_age_seconds=60)
    second = engine._get_improvement_summary(max_age_seconds=60)

    assert first["finding_count"] == 1
    assert second["finding_count"] == 1
    assert analyzer.calls == 1


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
        test_knowledge_graph_context,
        test_improvement_analyzer_detects_duplicate_defs,
        test_dashboard_snapshot_from_engine,
        test_prepare_turn_structured_pipeline,
        test_long_term_memory_edit_pin_archive_delete,
        test_hyper_engine_improvement_cache,
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

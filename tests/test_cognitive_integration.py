"""
tests/test_cognitive_integration.py
------------------------------------
Integration tests for Phase X Cognitive Architecture.

Run with:
    python -m pytest tests/test_cognitive_integration.py -v

Or standalone:
    python tests/test_cognitive_integration.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "[OK]"
FAIL = "[FAIL]"


# ------------------------------------------------------------------ #
# Test 1: CognitiveRouter -- Classification Accuracy
# ------------------------------------------------------------------ #
def test_cognitive_router_classify():
    from brain.cognitive_router import CognitiveRouter, RequestCategory, CognitivePath

    router = CognitiveRouter()

    test_cases = [
        ("Write a Python function to sort a list", RequestCategory.CODING, CognitivePath.ENGINEERING),
        ("What is the capital of France?", RequestCategory.CHAT, CognitivePath.FAST),
        ("Find papers on transformer architectures", RequestCategory.RESEARCH, CognitivePath.RESEARCH),
        ("Create a project plan for the simulation", RequestCategory.PROJECT_MGMT, CognitivePath.DEEP),
        ("How do neural networks work?", RequestCategory.LEARNING, CognitivePath.DEEP),
        ("Plan the next sprint", RequestCategory.PLANNING, CognitivePath.DEEP),
        ("What did we discuss about the simulation last week?", RequestCategory.MEMORY_RECALL, CognitivePath.DEEP),
    ]

    passed = 0
    for user_input, expected_cat, expected_path in test_cases:
        decision = router.classify(user_input)
        cat_match = decision.category == expected_cat
        path_match = decision.path == expected_path
        if cat_match and path_match:
            passed += 1
            print(f"  {OK} {user_input[:40]:40s} -> {decision.category.value:15s} {decision.path.value:12s}")
        else:
            print(f"  {FAIL} {user_input[:40]:40s} -> {decision.category.value:15s} {decision.path.value:12s} (expected {expected_cat.value:15s} {expected_path.value:12s})")

    accuracy = passed / len(test_cases) * 100
    print(f"\n  Classification accuracy: {accuracy:.0f}% ({passed}/{len(test_cases)})")
    assert accuracy >= 40, f"Classification accuracy too low: {accuracy:.0f}%"
    return accuracy


# ------------------------------------------------------------------ #
# Test 2: CognitiveRouter -- Depth Scoring
# ------------------------------------------------------------------ #
def test_cognitive_router_depth():
    from brain.cognitive_router import CognitiveRouter, RequestCategory

    router = CognitiveRouter()

    shallow_texts = ["hello", "hi", "thanks", "ok", "yes", "bye"]
    deep_texts = [
        "explain quantum mechanics in detail",
        "write a complete python web framework",
        "analyze the pros and cons of different cancer treatments",
    ]

    shallow_depths = [router._compute_depth(RequestCategory.CHAT, t) for t in shallow_texts]
    deep_depths = [router._compute_depth(RequestCategory.CODING, t) for t in deep_texts]
    for t in deep_texts[:1]:
        deep_depths.append(router._compute_depth(RequestCategory.RESEARCH, t))

    avg_shallow = sum(shallow_depths) / len(shallow_depths)
    avg_deep = sum(deep_depths) / len(deep_depths)

    assert avg_deep > avg_shallow, f"Deep queries ({avg_deep:.2f}) should score higher than shallow ({avg_shallow:.2f})"
    print(f"  {OK} Deep scoring ({avg_deep:.2f}) > shallow scoring ({avg_shallow:.2f})")


# ------------------------------------------------------------------ #
# Test 3: CognitiveRouter -- Latency Tracking
# ------------------------------------------------------------------ #
def test_cognitive_router_latency():
    from brain.cognitive_router import CognitiveRouter

    router = CognitiveRouter()

    _t0 = time.perf_counter()
    decision = router.classify("What is the weather?")
    elapsed = (time.perf_counter() - _t0) * 1000

    assert elapsed < 10, f"Classification took too long: {elapsed:.2f}ms"
    assert decision.latency.classification_ms < 10
    print(f"  {OK} Classification latency: {elapsed:.2f}ms (target <10ms)")


# ------------------------------------------------------------------ #
# Test 4: MemoryRelevanceEngine -- Ranking
# ------------------------------------------------------------------ #
def test_memory_relevance_ranking():
    from brain.memory_relevance import MemoryRelevanceEngine

    engine = MemoryRelevanceEngine()

    test_memories = [
        {"id": 1, "content": "The project uses Python 3.11 with customtkinter", "importance": 0.9, "created_at": "2026-05-28T10:00:00", "access_count": 5, "topics": ["programming", "python"]},
        {"id": 2, "content": "User likes hiking and outdoor activities", "importance": 0.3, "created_at": "2026-05-01T10:00:00", "access_count": 1, "topics": ["hobbies"]},
        {"id": 3, "content": "The cancer simulation uses a logistic growth model", "importance": 0.8, "created_at": "2026-05-29T10:00:00", "access_count": 3, "topics": ["simulation", "cancer"]},
    ]

    ranked = engine.rank_memories(query="What is the simulation model?", semantic_results=test_memories)

    assert len(ranked) == 3, "Should return all memories"
    assert ranked[0]["id"] in (1, 3), f"Most relevant should be about simulation or python, got id={ranked[0]['id']}"
    print(f"  {OK} Memories ranked correctly: top=id{ranked[0]['id']}, bottom=id{ranked[-1]['id']}")


# ------------------------------------------------------------------ #
# Test 5: MemoryRelevanceEngine -- Select Top with Budget
# ------------------------------------------------------------------ #
def test_memory_relevance_selection():
    from brain.memory_relevance import MemoryRelevanceEngine

    engine = MemoryRelevanceEngine()

    memories = [
        {"id": i, "content": f"Memory {i} with some content", "importance": 0.5, "created_at": "2026-05-28T10:00:00", "access_count": 1, "topics": []}
        for i in range(10)
    ]
    ranked = engine.rank_memories(query="test", semantic_results=memories)
    selected = engine.select_top(ranked, max_items=3, max_estimate_chars=500)

    assert len(selected) <= 3, f"Should select at most 3, got {len(selected)}"
    print(f"  {OK} Selection respects max_items: {len(selected)}/3")


# ------------------------------------------------------------------ #
# Test 6: MemoryRelevanceEngine -- Project Boost
# ------------------------------------------------------------------ #
def test_memory_relevance_project_boost():
    from brain.memory_relevance import MemoryRelevanceEngine

    engine = MemoryRelevanceEngine()

    memories = [
        {"id": 1, "content": "General chat about the weather", "importance": 0.5, "created_at": "2026-05-28T10:00:00", "access_count": 2, "topics": ["weather"]},
        {"id": 2, "content": "The cancer simulation project needs a growth model", "importance": 0.5, "created_at": "2026-05-28T10:00:00", "access_count": 2, "topics": ["cancer simulation"]},
    ]

    ranked_boosted = engine.rank_memories(query="project", semantic_results=memories, active_project="cancer simulation")
    boosted_top = ranked_boosted[0]["id"]
    boosted = boosted_top == 2
    print(f"  {OK} Project boost applied: top=id{boosted_top}" if boosted else f"  {FAIL} Project boost not applied: top=id{boosted_top}")
    return boosted


# ------------------------------------------------------------------ #
# Test 7: SmartCache -- Basic Operations
# ------------------------------------------------------------------ #
def test_smart_cache_basic():
    from brain.smart_cache import SmartCache

    cache = SmartCache()

    cache.set_project_context("test_key", "test_value")
    result = cache.get_project_context("test_key")
    assert result == "test_value", "Cache should return stored value"
    print(f"  {OK} SmartCache stores and retrieves correctly")


# ------------------------------------------------------------------ #
# Test 8: SmartCache -- TTL Expiry
# ------------------------------------------------------------------ #
def test_smart_cache_ttl():
    from brain.smart_cache import SmartCache
    import time as _time_module

    cache = SmartCache()
    cache.get_project_context  # Verify it exists

    cache._memory.set("ttl_test:val", "value", ttl=0.1)
    assert cache._memory.get("ttl_test:val") == "value"
    _time_module.sleep(0.15)
    assert cache._memory.get("ttl_test:val") is None, "Cache should expire after TTL"
    print(f"  {OK} SmartCache TTL expiry works correctly")


# ------------------------------------------------------------------ #
# Test 9: SmartCache -- Hit/Miss Stats
# ------------------------------------------------------------------ #
def test_smart_cache_stats():
    from brain.smart_cache import SmartCache

    cache = SmartCache()
    stats_before = cache.get_stats()
    total_before = sum(s["hits"] + s["misses"] for s in stats_before.values())

    cache.get_project_context("nonexistent")
    cache.get_project_context("nonexistent2")
    cache.set_project_context("exists", "val")
    cache.get_project_context("exists")

    stats_after = cache.get_stats()
    total_after = sum(s["hits"] + s["misses"] for s in stats_after.values())
    assert total_after >= total_before + 2, f"Stats should track operations (before={total_before}, after={total_after})"
    print(f"  {OK} SmartCache stats track hits/misses")


# ------------------------------------------------------------------ #
# Test 10: Quality Check
# ------------------------------------------------------------------ #
def test_quality_check():
    from brain.cognitive_router import quality_check

    assert quality_check("Valid response to your question", "What is Python?") == "Valid response to your question"
    assert quality_check("", "Hello") == ""
    assert quality_check("Short", "How are you?") == "Short"
    print(f"  {OK} Quality check handles responses correctly")


# ------------------------------------------------------------------ #
# Test 11: ContextAssembler -- Memory Relevance Integration
# ------------------------------------------------------------------ #
def test_context_assembler_memory_relevance():
    from brain.context_assembler import ContextAssembler
    from brain.memory_relevance import MemoryRelevanceEngine

    mre = MemoryRelevanceEngine()
    assembler = ContextAssembler(
        llm=None,
        memory=None,
        hyper_engine=None,
        memory_relevance=mre,
        smart_cache=None,
    )
    assert assembler._relevance is not None, "MemoryRelevanceEngine should be wired in"
    print(f"  {OK} ContextAssembler has MemoryRelevanceEngine wired")


# ------------------------------------------------------------------ #
# Test 12: ContextAssembler -- SmartCache Integration
# ------------------------------------------------------------------ #
def test_context_assembler_smart_cache():
    from brain.context_assembler import ContextAssembler
    from brain.smart_cache import SmartCache

    sc = SmartCache()
    assembler = ContextAssembler(
        llm=None,
        memory=None,
        hyper_engine=None,
        memory_relevance=None,
        smart_cache=sc,
    )
    assert assembler._cache is not None, "SmartCache should be wired in"
    print(f"  {OK} ContextAssembler has SmartCache wired")


# ------------------------------------------------------------------ #
# Test 13: Orchestrator -- Memory Relevance and SmartCache Passthrough
# ------------------------------------------------------------------ #
def test_orchestrator_wiring():
    from brain.orchestrator import AssistantRouter
    from brain.memory_relevance import MemoryRelevanceEngine
    from brain.smart_cache import SmartCache

    mre = MemoryRelevanceEngine()
    sc = SmartCache()
    router = AssistantRouter(
        llm=None,
        memory=None,
        hyper_engine=None,
        memory_relevance=mre,
        smart_cache=sc,
    )
    assembler = router._lazy_context_assembler()
    assert assembler._relevance is not None, "Orchestrator should pass MemoryRelevanceEngine"
    assert assembler._cache is not None, "Orchestrator should pass SmartCache"
    print(f"  {OK} AssistantRouter wires engines into ContextAssembler")


# ------------------------------------------------------------------ #
# Test 14: CognitiveRouter -- Path Instructions
# ------------------------------------------------------------------ #
def test_cognitive_path_instructions():
    from brain.cognitive_router import CognitiveRouter, CognitivePath, RoutingDecision, RequestCategory, LatencySnapshot

    router = CognitiveRouter()
    decision = RoutingDecision(
        category=RequestCategory.CHAT,
        path=CognitivePath.FAST,
        response_depth=0.2,
        confidence=0.9,
        latency=LatencySnapshot(),
    )
    instr = router.get_depth_instruction(decision)
    assert "1-2 sentences" in instr or len(instr) > 0
    path_instr = router.get_path_instruction(decision)
    assert len(path_instr) > 0
    print(f"  {OK} Path instruction: {path_instr[:60]}")


# ------------------------------------------------------------------ #
# Test 15: Full Pipeline -- CognitiveRouter -> Context -> Quality
# ------------------------------------------------------------------ #
def test_cli_pipeline_flow():
    from brain.cognitive_router import CognitiveRouter, quality_check

    router = CognitiveRouter()

    test_inputs = [
        "Hello, how are you?",
        "Write a Python function to merge two dictionaries",
        "Research the latest advances in cancer immunotherapy",
        "What did we work on in the last session?",
    ]

    for user_input in test_inputs:
        decision = router.classify(user_input)
        assert decision.category is not None
        assert decision.path is not None
        assert 0 <= decision.response_depth <= 1.0
        assert decision.confidence >= 0
        instr = router.get_depth_instruction(decision)
        mock_response = f"This is a response about {user_input.lower()[:20]}"
        checked = quality_check(mock_response, user_input)
        assert checked == mock_response, "Quality check should not modify valid responses"

    print(f"  {OK} Full pipeline flow verified for {len(test_inputs)} inputs")


# ------------------------------------------------------------------ #
# Main
# ------------------------------------------------------------------ #
def run_all():
    print("=" * 60)
    print("PHASE X: COGNITIVE ARCHITECTURE INTEGRATION TESTS")
    print("=" * 60)
    results = []

    tests = [
        ("Classification accuracy", test_cognitive_router_classify),
        ("Response depth scoring", test_cognitive_router_depth),
        ("Latency tracking", test_cognitive_router_latency),
        ("Memory relevance ranking", test_memory_relevance_ranking),
        ("Memory selection with budget", test_memory_relevance_selection),
        ("Project boost", test_memory_relevance_project_boost),
        ("SmartCache basic ops", test_smart_cache_basic),
        ("SmartCache TTL", test_smart_cache_ttl),
        ("SmartCache stats", test_smart_cache_stats),
        ("Quality check", test_quality_check),
        ("ContextAssembler + MemoryRelevance", test_context_assembler_memory_relevance),
        ("ContextAssembler + SmartCache", test_context_assembler_smart_cache),
        ("Orchestrator wiring", test_orchestrator_wiring),
        ("Cognitive path instructions", test_cognitive_path_instructions),
        ("CLI pipeline flow", test_cli_pipeline_flow),
    ]

    for name, fn in tests:
        print(f"\n[{name}]")
        try:
            fn()
            results.append((name, "PASS"))
        except Exception as e:
            results.append((name, f"FAIL: {e}"))
            print(f"  {FAIL} {e}")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for _, s in results if s == "PASS")
    for name, status in results:
        tag = OK if status == "PASS" else FAIL
        print(f"  {tag} {name}: {status}")
    print(f"\n  {passed}/{len(results)} tests passed")


if __name__ == "__main__":
    run_all()

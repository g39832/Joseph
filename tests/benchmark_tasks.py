"""
tests/benchmark_tasks.py
-------------------------
Intelligence Benchmark Suite for Phase X Cognitive Architecture.

Run standalone:
    python tests/benchmark_tasks.py
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "[OK]"
FAIL = "[FAIL]"


def _check_imports() -> bool:
    try:
        from brain.cognitive_router import CognitiveRouter, quality_check
        from brain.memory_relevance import MemoryRelevanceEngine
        from brain.smart_cache import SmartCache
        return True
    except Exception as e:
        print(f"  IMPORT FAILURE: {e}")
        return False


# ================================================================== #
# BENCHMARK 1: Classification Speed & Accuracy
# ================================================================== #
def benchmark_classification() -> dict:
    from brain.cognitive_router import CognitiveRouter

    router = CognitiveRouter()

    test_set = [
        ("hello how are you", "chat"),
        ("write a function to reverse a linked list", "coding"),
        ("find papers on quantum computing", "research"),
        ("create project roadmap for app", "planning"),
        ("what did we discuss yesterday", "memory_recall"),
        ("explain how transformers work", "learning"),
        ("update the project status", "project_mgmt"),
        ("what's the weather like", "chat"),
        ("debug this error: index out of range", "coding"),
        ("summarize this research paper", "research"),
    ]

    times = []
    correct = 0

    for user_input, expected_category in test_set:
        _t0 = time.perf_counter()
        decision = router.classify(user_input)
        elapsed = (time.perf_counter() - _t0) * 1000
        times.append(elapsed)
        cat = decision.category.value.lower().replace(" ", "_")
        if cat == expected_category:
            correct += 1

    avg_time = sum(times) / len(times)
    max_time = max(times)
    accuracy = correct / len(test_set) * 100

    return {
        "test": "Classification Speed & Accuracy",
        "num_samples": len(test_set),
        "correct": correct,
        "accuracy_pct": round(accuracy, 1),
        "avg_time_ms": round(avg_time, 3),
        "max_time_ms": round(max_time, 3),
        "result": "PASS" if accuracy >= 60 and avg_time < 5 else "FAIL",
    }


# ================================================================== #
# BENCHMARK 2: Depth Scoring Consistency
# ================================================================== #
def benchmark_depth_scoring() -> dict:
    from brain.cognitive_router import CognitiveRouter, RequestCategory

    router = CognitiveRouter()

    shallow = ["hi", "hello", "thanks", "ok", "yes", "no", "good", "bye", "cool", "nice"]
    deep = [
        "explain the theory of relativity in detail",
        "write a complete implementation of a neural network from scratch with backpropagation",
        "analyze the pros and cons of different cancer treatment approaches",
        "design a microservices architecture for a large-scale e-commerce platform",
        "compare and contrast reinforcement learning with supervised learning",
    ]

    shallow_depths = [router._compute_depth(RequestCategory.CHAT, q) for q in shallow]
    deep_depths = [router._compute_depth(RequestCategory.CODING, q) for q in deep]

    avg_shallow = sum(shallow_depths) / len(shallow_depths)
    avg_deep = sum(deep_depths) / len(deep_depths)
    well_separated = avg_deep > avg_shallow + 0.3

    return {
        "test": "Depth Scoring Consistency",
        "avg_shallow_depth": round(avg_shallow, 3),
        "avg_deep_depth": round(avg_deep, 3),
        "well_separated": well_separated,
        "result": "PASS" if well_separated else "FAIL",
    }


# ================================================================== #
# BENCHMARK 3: Memory Relevance Scoring
# ================================================================== #
def benchmark_memory_relevance() -> dict:
    from brain.memory_relevance import MemoryRelevanceEngine

    engine = MemoryRelevanceEngine()

    now = "2026-05-30T12:00:00"
    memories = [
        {"id": 1, "content": "Python project uses FastAPI for the backend API server with PostgreSQL database", "importance": 0.9, "created_at": now, "access_count": 10, "topics": ["programming", "python", "fastapi"]},
        {"id": 2, "content": "User mentioned they prefer dark mode in all applications", "importance": 0.2, "created_at": "2026-05-01T12:00:00", "access_count": 1, "topics": ["preferences"]},
        {"id": 3, "content": "Cancer simulation uses logistic growth model with angiogenesis parameters", "importance": 0.85, "created_at": "2026-05-29T12:00:00", "access_count": 5, "topics": ["simulation", "cancer", "research"]},
        {"id": 4, "content": "User's favorite color is blue and they like minimal design", "importance": 0.1, "created_at": "2026-04-15T12:00:00", "access_count": 0, "topics": ["personal"]},
        {"id": 5, "content": "Docker compose setup for the project with three services: web, db, cache", "importance": 0.7, "created_at": "2026-05-27T12:00:00", "access_count": 4, "topics": ["devops", "docker"]},
    ]

    ranked = engine.rank_memories(query="Tell me about the project architecture and simulation", semantic_results=memories)
    top_ids = [m["id"] for m in ranked[:3]]
    relevant_in_top = sum(1 for tid in top_ids if tid in (1, 3, 5))

    return {
        "test": "Memory Relevance Scoring",
        "num_memories": len(memories),
        "top_3_ids": top_ids,
        "relevant_in_top_3": relevant_in_top,
        "result": "PASS" if relevant_in_top >= 2 else "FAIL",
    }


# ================================================================== #
# BENCHMARK 4: Memory Selection with Token Budget
# ================================================================== #
def benchmark_memory_budget() -> dict:
    from brain.memory_relevance import MemoryRelevanceEngine

    engine = MemoryRelevanceEngine()

    memories = [
        {"id": i, "content": f"Memory entry number {i} with some text content for testing purposes", "importance": 0.5, "created_at": "2026-05-28T10:00:00", "access_count": 1, "topics": []}
        for i in range(20)
    ]
    ranked = engine.rank_memories(query="test query", semantic_results=memories)

    tight = engine.select_top(ranked, max_items=10, max_estimate_chars=200)
    tight_total_chars = sum(len(m["content"]) for m in tight)
    tight_size = len(tight)

    generous = engine.select_top(ranked, max_items=10, max_estimate_chars=2000)
    generous_size = len(generous)

    budget_respected = tight_total_chars <= 300
    more_with_bigger_budget = generous_size >= tight_size

    return {
        "test": "Memory Selection Budget",
        "tight_budget_size": tight_size,
        "tight_budget_chars": tight_total_chars,
        "generous_budget_size": generous_size,
        "budget_respected": budget_respected,
        "more_with_bigger_budget": more_with_bigger_budget,
        "result": "PASS" if budget_respected else "FAIL",
    }


# ================================================================== #
# BENCHMARK 5: SmartCache Performance
# ================================================================== #
def benchmark_cache_performance() -> dict:
    from brain.smart_cache import SmartCache

    cache = SmartCache()
    warmup = 10

    miss_times = []
    for i in range(warmup):
        _t0 = time.perf_counter()
        cache.get_project_context(f"miss_key_{i}")
        miss_times.append((time.perf_counter() - _t0) * 1000)

    for i in range(warmup):
        cache.set_project_context(f"hit_key_{i}", f"value_{i}")

    hit_times = []
    for i in range(warmup):
        _t0 = time.perf_counter()
        cache.get_project_context(f"hit_key_{i}")
        hit_times.append((time.perf_counter() - _t0) * 1000)

    avg_miss = sum(miss_times) / len(miss_times)
    avg_hit = sum(hit_times) / len(hit_times)

    cache.set_memory("mem_key", "mem_val")
    cache.set_project_context("proj_key", "proj_val")
    cache.set_research("res_key", "res_val")

    all_ok = (cache.get_memory("mem_key") == "mem_val"
              and cache.get_project_context("proj_key") == "proj_val"
              and cache.get_research("res_key") == "res_val")

    stats = cache.get_stats()

    return {
        "test": "SmartCache Performance",
        "avg_hit_latency_ms": round(avg_hit, 6),
        "avg_miss_latency_ms": round(avg_miss, 6),
        "all_pools_work": all_ok,
        "pool_stats": {k: {"hit_rate": v["hit_rate"], "size": v["size"]} for k, v in stats.items()},
        "result": "PASS" if all_ok else "FAIL",
    }


# ================================================================== #
# BENCHMARK 6: Quality Check Performance
# ================================================================== #
def benchmark_quality_check() -> dict:
    from brain.cognitive_router import quality_check

    responses = [
        ("The capital of France is Paris.", "What is the capital of France?"),
        ("Python is a programming language.", "What is Python?"),
        ("Short", "How are you?"),
        ("", "Hello"),
        ("A" * 1000, "Tell me everything."),
    ]

    times = []
    for response, query in responses * 20:
        _t0 = time.perf_counter()
        quality_check(response, query)
        times.append((time.perf_counter() - _t0) * 1000)

    avg_time = sum(times) / len(times)

    return {
        "test": "Quality Check Performance",
        "num_runs": len(times),
        "avg_time_ms": round(avg_time, 6),
        "throughput_per_sec": round(1000 / max(avg_time, 0.001), 0),
        "result": "PASS" if avg_time < 0.1 else "FAIL",
    }


# ================================================================== #
# BENCHMARK 7: Full Pipeline Latency Simulation
# ================================================================== #
def benchmark_pipeline_latency() -> dict:
    from brain.cognitive_router import CognitiveRouter, quality_check
    from brain.memory_relevance import MemoryRelevanceEngine
    from brain.smart_cache import SmartCache

    router = CognitiveRouter()
    relevance = MemoryRelevanceEngine()
    cache = SmartCache()

    test_inputs = [
        "hello",
        "write a python function",
        "research cancer treatments",
        "what did we do last session",
        "plan the next sprint",
        "explain quantum computing",
    ]

    stages = {"classification": [], "relevance": [], "cache_lookup": [], "quality_check": []}

    for user_input in test_inputs:
        _t0 = time.perf_counter()
        decision = router.classify(user_input)
        stages["classification"].append((time.perf_counter() - _t0) * 1000)

        _t0 = time.perf_counter()
        cached = cache.get_memory(f"bench:{user_input[:20]}")
        stages["cache_lookup"].append((time.perf_counter() - _t0) * 1000)

        memories = [
            {"id": 1, "content": "Test memory about project", "importance": 0.8, "created_at": "2026-05-28T10:00:00", "access_count": 5, "topics": ["test"]}
        ]
        _t0 = time.perf_counter()
        ranked = relevance.rank_memories(user_input, semantic_results=memories)
        stages["relevance"].append((time.perf_counter() - _t0) * 1000)

        _t0 = time.perf_counter()
        quality_check(f"Response to {user_input}", user_input)
        stages["quality_check"].append((time.perf_counter() - _t0) * 1000)

    avg_stages = {k: round(sum(v) / len(v), 4) for k, v in stages.items()}
    total_avg = round(sum(avg_stages.values()), 4)

    bottlenecks = sorted(avg_stages, key=avg_stages.get, reverse=True)[:2]

    return {
        "test": "Pipeline Latency Breakdown",
        "avg_stage_latency_ms": avg_stages,
        "total_pipeline_latency_ms": total_avg,
        "bottlenecks": bottlenecks,
        "result": "PASS" if total_avg < 20 else "FAIL",
    }


# ================================================================== #
# BENCHMARK 8: Context Assembly Token Savings
# ================================================================== #
def benchmark_context_savings() -> dict:
    from brain.memory_relevance import MemoryRelevanceEngine

    engine = MemoryRelevanceEngine()

    memories = [
        {"id": i, "content": f"Memory {i}: " + "useful content about the project " * 10, "importance": 0.1 + (i * 0.08), "created_at": "2026-05-28T10:00:00", "access_count": i, "topics": ["test"]}
        for i in range(15)
    ]
    ranked = engine.rank_memories(query="project", semantic_results=memories)

    without_mem = memories
    without_size = sum(len(m["content"]) for m in without_mem)

    selected = engine.select_top(ranked, max_items=5, max_estimate_chars=3000)
    with_size = sum(len(m["content"]) for m in selected)

    savings_pct = round((1 - with_size / without_size) * 100, 1)

    return {
        "test": "Context Assembly Token Savings",
        "without_relevance_chars": without_size,
        "with_relevance_chars": with_size,
        "savings_pct": savings_pct,
        "selected_count": len(selected),
        "total_count": len(memories),
        "result": "PASS" if savings_pct > 20 else "FAIL",
    }


# ================================================================== #
# Run All Benchmarks
# ================================================================== #
def run_all():
    print("=" * 70)
    print("PHASE X: INTELLIGENCE BENCHMARK SUITE")
    print("=" * 70)

    if not _check_imports():
        print("\n  FATAL: Phase X modules failed to import. Aborting.")
        return

    benchmarks = [
        benchmark_classification(),
        benchmark_depth_scoring(),
        benchmark_memory_relevance(),
        benchmark_memory_budget(),
        benchmark_cache_performance(),
        benchmark_quality_check(),
        benchmark_pipeline_latency(),
        benchmark_context_savings(),
    ]

    print("\n" + "-" * 70)
    print("RESULTS")
    print("-" * 70)

    passed = 0
    for b in benchmarks:
        status_text = f"{OK} PASS" if b["result"] == "PASS" else f"{FAIL} FAIL"
        if b["result"] == "PASS":
            passed += 1
        print(f"\n{status_text} | {b['test']}")
        for k, v in b.items():
            if k in ("test", "result"):
                continue
            if isinstance(v, dict):
                print(f"    {k}:")
                for sk, sv in v.items():
                    print(f"      {sk}: {sv}")
            elif isinstance(v, float):
                print(f"    {k}: {v}")
            else:
                print(f"    {k}: {v}")

    print("\n" + "=" * 70)
    print(f"OVERALL: {passed}/{len(benchmarks)} benchmarks passed")
    print("=" * 70)

    return benchmarks


if __name__ == "__main__":
    run_all()

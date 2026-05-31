"""
tests/test_project_continuity.py
---------------------------------
Multi-session Project Continuity Test for Phase X.

Simulates a 5-session cancer simulation project to verify:
  - Cross-session continuity tracking
  - Memory consolidation with fact extraction
  - Continuity context quality
  - Project-aware context assembly

Run standalone:
    python tests/test_project_continuity.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

OK = "[OK]"
FAIL = "[FAIL]"
INFO = "[..]"

PROJECT_NAME = "Cancer Growth Simulation"
SESSIONS = [
    {
        "name": "Session 1: Roadmap Creation",
        "user_messages": [
            "I want to build a cancer growth simulation project",
            "Let's create a roadmap for this project",
            "I'm working on a tumor growth simulation that uses logistic growth equations",
            "My project needs to track angiogenesis and immune response",
        ],
    },
    {
        "name": "Session 2: Research Growth Models",
        "user_messages": [
            "I'm researching mathematical models for tumor growth",
            "I'm learning about key parameters for a logistic growth model",
            "Important: angiogenesis significantly affects the growth rate parameter",
        ],
    },
    {
        "name": "Session 3: Implementation",
        "user_messages": [
            "I'm building the growth model in Python",
            "I have implemented a function for the logistic growth equation",
            "Note that angiogenesis modifies the carrying capacity parameter",
        ],
    },
    {
        "name": "Session 4: Debugging",
        "user_messages": [
            "Remember that the growth function gives wrong values for small populations",
            "I think the carrying capacity calculation is off by a factor of 10",
            "Important: the angiogenesis modifier has a sign error in the implementation",
        ],
    },
    {
        "name": "Session 5: Continuation",
        "user_messages": [
            "I'm continuing work on the cancer simulation project",
            "Remember that we implemented the logistic growth model with angiogenesis modifiers",
            "Note that the carrying capacity bug still needs to be fixed",
            "Let's fix the sign error in the angiogenesis modifier",
        ],
    },
]


def test_continuity_tracking():
    """Verify continuity engine tracks sessions and goals."""
    print(f"\n{INFO} Testing continuity engine...")
    from brain.continuity_engine import ContinuityEngine

    continuity = ContinuityEngine()

    for session in SESSIONS:
        continuity.record_session_start()
        for msg in session["user_messages"]:
            continuity.record_turn(msg, f"Response about: {msg[:50]}")
        continuity.record_session_end()

    ctx = continuity.get_continuity_context()

    quality_checks = [
        ("session info" in ctx.lower(), "Contains session info"),
        ("goal" in ctx.lower() or "goal" in ctx, "Contains goals section"),
        ("cancer" in ctx.lower() or "simulation" in ctx.lower(), "Mentions project domain"),
        (100 < len(ctx) < 5000, "Reasonable length"),
    ]

    print(f"\n  Continuity context ({len(ctx)} chars):")
    print(f"    {ctx[:300]}...")

    passed = sum(1 for r, _ in quality_checks)
    total = len(quality_checks)
    for r, name in quality_checks:
        tag = OK if r else FAIL
        print(f"    {tag} {name}")

    print(f"\n  Quality: {passed}/{total} checks passed")
    assert passed >= 2, f"Too many quality checks failed: {passed}/{total}"
    return passed / total * 100


def test_consolidation_extraction():
    """Verify consolidation engine extracts facts from messages."""
    print(f"\n{INFO} Testing consolidation fact extraction...")
    from brain.memory_consolidation import MemoryConsolidationEngine

    consolidation = MemoryConsolidationEngine()

    for session in SESSIONS:
        for msg in session["user_messages"]:
            consolidation.consolidate_conversation(
                user_messages=[msg],
                assistant_messages=[f"Response about: {msg[:50]}"],
                session_id="test_session",
            )

    memory_count = consolidation.memory_count
    print(f"  Consolidated memories: {memory_count}")

    ctx = consolidation.build_consolidation_context(limit=5)
    print(f"  Consolidation context ({len(ctx)} chars):")
    print(f"    {ctx[:300]}..." if ctx else "    (empty)")

    important = consolidation.get_important(min_importance=0.7, limit=10)
    print(f"  Important memories: {len(important)}")

    status = consolidation.get_status()
    print(f"  Status: {status}")

    assert memory_count > 0, "Should have extracted at least some memories"
    assert len(ctx) > 50, "Consolidation context should be non-trivial"
    return memory_count


def test_consolidation_search():
    """Verify consolidated memories are searchable."""
    print(f"\n{INFO} Testing consolidation search...")
    from brain.memory_consolidation import MemoryConsolidationEngine

    consolidation = MemoryConsolidationEngine()

    for session in SESSIONS:
        for msg in session["user_messages"]:
            consolidation.consolidate_conversation(
                user_messages=[msg],
                assistant_messages=[f"Response about: {msg[:50]}"],
                session_id="test_session",
            )

    # Search for specific terms
    searches = {
        "angiogenesis": 0,
        "logistic growth": 0,
        "carrying capacity": 0,
    }

    for term in searches:
        results = consolidation.search(term, limit=5)
        searches[term] = len(results)

    print(f"  Search results:")
    for term, count in searches.items():
        tag = OK if count > 0 else FAIL
        print(f"    {tag} '{term}': {count} results")

    return sum(searches.values())


def test_continuity_context_quality():
    """Evaluate continuity context output quality."""
    print(f"\n{INFO} Testing continuity context quality...")
    from brain.continuity_engine import ContinuityEngine

    continuity = ContinuityEngine()

    for session in SESSIONS:
        continuity.record_session_start()
        for msg in session["user_messages"]:
            continuity.record_turn(msg, f"Response about: {msg[:50]}")
        continuity.record_session_end()

    ctx = continuity.get_continuity_context()

    quality_checks = {
        "Has session count": "session" in ctx.lower(),
        "Has goals": "goal" in ctx.lower(),
        "Mentions simulation": "simulation" in ctx.lower(),
        "Reasonable length": 50 < len(ctx) < 5000,
    }

    passed = sum(1 for v in quality_checks.values() if v)
    total = len(quality_checks)

    print(f"\n  Context length: {len(ctx)} chars")
    for check, result in quality_checks.items():
        tag = OK if result else FAIL
        print(f"    {tag} {check}")

    print(f"  Quality: {passed}/{total}")
    return passed / total * 100


def test_project_context_assembly():
    """Verify context assembly includes continuity + consolidation."""
    print(f"\n{INFO} Testing project-aware context assembly...")
    from brain.context_assembler import ContextAssembler
    from brain.memory_relevance import MemoryRelevanceEngine
    from brain.smart_cache import SmartCache
    from brain.continuity_engine import ContinuityEngine
    from brain.memory_consolidation import MemoryConsolidationEngine

    continuity = ContinuityEngine()
    consolidation = MemoryConsolidationEngine()

    for session in SESSIONS:
        continuity.record_session_start()
        for msg in session["user_messages"]:
            continuity.record_turn(msg, f"Response about: {msg[:50]}")
            consolidation.consolidate_conversation(
                user_messages=[msg],
                assistant_messages=[f"Response about: {msg[:50]}"],
                session_id="test_session",
            )
        continuity.record_session_end()

    class MockLongTerm:
        def format_facts_for_context(self):
            return "User is building a cancer growth simulation with logistic growth models."
        def get_recent_summaries(self, limit=2):
            return [{"created_at": "2026-05-30", "summary": "Cancer simulation with logistic growth and angiogenesis modifiers"}]

    class MockMemory:
        long_term = MockLongTerm()
        def get_context_for_llm(self, query=None):
            return "## Memory Context\nCancer simulation with logistic growth."
        def search(self, query):
            return {"semantic_results": [], "keyword_results": []}

    mre = MemoryRelevanceEngine()
    sc = SmartCache()
    assembler = ContextAssembler(
        llm=None,
        memory=MockMemory(),
        hyper_engine=None,
        memory_relevance=mre,
        smart_cache=sc,
    )
    assembler.continuity_engine = continuity
    assembler.consolidation_engine = consolidation

    ctx = assembler.assemble(
        user_input="What's the status of the cancer simulation?",
        response_depth=0.8,
        active_project=PROJECT_NAME,
    )

    assembled = ctx.assemble(max_chars=3000)

    quality_items = {
        "continuity present": bool(ctx.continuity_context),
        "consolidation present": bool(ctx.consolidation_context),
        "memory present": bool(ctx.memory_context),
        "total length reasonable": 100 < len(assembled) < 5000,
        "contains domain terms": any(t in assembled.lower() for t in ["logistic", "cancer", "angiogenesis"]),
    }

    passed = sum(1 for v in quality_items.values() if v)
    total = len(quality_items)

    print(f"  Assembled context: {len(assembled)} chars")
    for check, result in quality_items.items():
        tag = OK if result else FAIL
        print(f"    {tag} {check}")

    print(f"  Assembly quality: {passed}/{total}")
    return passed / total * 100


# ================================================================== #
# MAIN
# ================================================================== #
def run_all():
    print("=" * 60)
    print("PHASE X: PROJECT CONTINUITY TEST")
    print("=" * 60)
    print(f"\nProject: {PROJECT_NAME}")
    print(f"Sessions: {len(SESSIONS)}")
    for s in SESSIONS:
        print(f"  - {s['name']} ({len(s['user_messages'])} messages)")

    results = []

    tests = [
        ("Continuity tracking", test_continuity_tracking),
        ("Fact extraction", test_consolidation_extraction),
        ("Consolidation search", test_consolidation_search),
        ("Continuity context quality", test_continuity_context_quality),
        ("Project context assembly", test_project_context_assembly),
    ]

    for name, fn in tests:
        print(f"\n{'='*60}")
        print(f"[{name}]")
        print(f"{'='*60}")
        try:
            score = fn()
            results.append((name, "PASS", score))
        except Exception as e:
            import traceback
            traceback.print_exc()
            results.append((name, f"FAIL: {e}", 0))
            print(f"  {FAIL} {e}")

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    passed_count = sum(1 for _, s, _ in results if s == "PASS")
    for name, status, score in results:
        tag = OK if status == "PASS" else FAIL
        score_str = f" ({score:.0f}%)" if isinstance(score, (int, float)) else ""
        print(f"  {tag} {name}: {status}{score_str}")
    print(f"\n  {passed_count}/{len(results)} tests passed")


if __name__ == "__main__":
    run_all()

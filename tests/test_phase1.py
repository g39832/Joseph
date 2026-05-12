"""
tests/test_phase1.py
---------------------
Basic tests for Phase 1 components.

Run with:
    python -m pytest tests/ -v

Or without pytest:
    python tests/test_phase1.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_settings_load():
    """Settings should load without errors."""
    from configs.settings import settings
    assert settings.JOSEPH_NAME == "Joseph"
    assert settings.OLLAMA_BASE_URL.startswith("http")
    print("✓ Settings load correctly")


def test_short_term_memory():
    """Short-term memory should store and retrieve messages."""
    from memory.short_term import ShortTermMemory

    stm = ShortTermMemory(limit=5)
    stm.add("user", "Hello Joseph")
    stm.add("assistant", "Hello! How can I help?")

    messages = stm.get_messages()
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello Joseph"
    assert messages[1]["role"] == "assistant"
    print("✓ Short-term memory works correctly")


def test_short_term_memory_limit():
    """Short-term memory should respect the limit."""
    from memory.short_term import ShortTermMemory

    stm = ShortTermMemory(limit=3)
    for i in range(5):
        stm.add("user", f"Message {i}")

    # Should only keep last 3
    assert len(stm) == 3
    messages = stm.get_messages()
    assert messages[-1]["content"] == "Message 4"
    print("✓ Short-term memory limit works correctly")


def test_long_term_memory():
    """Long-term memory should persist facts and memories."""
    import tempfile
    from pathlib import Path
    from memory.long_term import LongTermMemory

    # Use a temp database for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_memory.db"
        ltm = LongTermMemory(db_path=db_path)

        # Test facts
        ltm.save_fact("test_key", "test_value")
        value = ltm.get_fact("test_key")
        assert value == "test_value", f"Expected 'test_value', got '{value}'"

        # Test memories
        memory_id = ltm.save_memory("Test memory content", importance=7)
        assert memory_id > 0

        memories = ltm.get_recent_memories(limit=5)
        assert len(memories) == 1
        assert memories[0]["content"] == "Test memory content"

        # Test facts dict
        facts = ltm.get_all_facts()
        assert "test_key" in facts

        print("✓ Long-term memory works correctly")


def test_personality_engine():
    """Personality engine should return valid responses."""
    from brain.personality import PersonalityEngine

    pe = PersonalityEngine()

    greeting = pe.get_greeting()
    assert isinstance(greeting, str)
    assert len(greeting) > 0

    wake = pe.get_wake_response()
    assert isinstance(wake, str)

    # Test robotic opener removal
    raw = "As an AI language model, I can help you with that."
    formatted = pe.format_response(raw)
    assert "As an AI language model" not in formatted
    assert formatted[0].isupper()  # Should start with capital letter

    print("✓ Personality engine works correctly")


def test_cli_command_parsing():
    """CLI should correctly parse special commands."""
    from ui.cli_interface import CLIInterface

    cli = CLIInterface()

    # Test command parsing
    cmd, arg = cli.parse_command("/help")
    assert cmd == "help"
    assert arg is None

    cmd, arg = cli.parse_command("/remember my dog is Max")
    assert cmd == "remember"
    assert arg == "my dog is Max"

    cmd, arg = cli.parse_command("/search outdoor activities")
    assert cmd == "search"
    assert arg == "outdoor activities"

    # Non-command should return None, None
    cmd, arg = cli.parse_command("Hello Joseph")
    assert cmd is None
    assert arg is None

    print("✓ CLI command parsing works correctly")


def test_permissions_system():
    """Permissions system should correctly classify risk levels."""
    from automation.safety.permissions import PermissionsManager, RiskLevel

    # Use a mock callback that always approves
    perms = PermissionsManager(confirm_callback=lambda action, risk: True)

    # Low risk should auto-approve
    result = perms.request_permission("open website", RiskLevel.LOW)
    assert result is True

    # High risk with mock approval
    result = perms.request_permission("delete file", RiskLevel.HIGH)
    assert result is True

    # High risk with mock denial
    perms_deny = PermissionsManager(confirm_callback=lambda action, risk: False)
    result = perms_deny.request_permission("delete file", RiskLevel.HIGH)
    assert result is False

    print("✓ Permissions system works correctly")


def test_prompts():
    """Prompts should generate non-empty strings."""
    from brain.prompts import (
        get_system_prompt,
        get_summarization_prompt,
        get_memory_extraction_prompt,
    )

    system = get_system_prompt(user_name="TestUser")
    assert "Joseph" in system
    assert "TestUser" in system
    assert len(system) > 100

    summary_prompt = get_summarization_prompt("User: Hello\nJoseph: Hi there")
    assert len(summary_prompt) > 20

    extract_prompt = get_memory_extraction_prompt("My favorite color is blue")
    assert len(extract_prompt) > 20

    print("✓ Prompts generate correctly")


if __name__ == "__main__":
    print("\nRunning Phase 1 Tests\n" + "=" * 40)
    tests = [
        test_settings_load,
        test_short_term_memory,
        test_short_term_memory_limit,
        test_long_term_memory,
        test_personality_engine,
        test_cli_command_parsing,
        test_permissions_system,
        test_prompts,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} FAILED: {e}")
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("All tests passed! Joseph Phase 1 is ready.")
    else:
        print("Some tests failed. Check the errors above.")

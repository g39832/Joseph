"""
tests/test_phase3.py
---------------------
Tests for Phase 3 automation components.

Run with:
    python tests/test_phase3.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_command_router_intent_classification():
    """Router should correctly classify intents via fast regex."""
    from automation.command_router import CommandRouter, QUICK_BROWSER, QUICK_DESKTOP, QUICK_SEARCH

    router = CommandRouter()

    # Test browser patterns
    browser_inputs = [
        "open YouTube",
        "open GitHub",
        "open Netflix",
        "pull up Spotify",
    ]
    for text in browser_inputs:
        assert QUICK_BROWSER.search(text), f"Expected BROWSER match for: '{text}'"

    # Test desktop patterns
    desktop_inputs = [
        "open Notepad",
        "launch calculator",
        "open VS Code",
        "start Chrome",
    ]
    for text in desktop_inputs:
        assert QUICK_DESKTOP.search(text), f"Expected DESKTOP match for: '{text}'"

    # Test search patterns
    search_inputs = [
        "search for Python tutorials",
        "look up the weather",
        "google machine learning",
    ]
    for text in search_inputs:
        assert QUICK_SEARCH.search(text), f"Expected SEARCH match for: '{text}'"

    print("✓ Intent classification works correctly")


def test_search_query_extraction():
    """Router should extract clean search queries."""
    from automation.command_router import CommandRouter

    router = CommandRouter()

    cases = [
        ("search Google for Python tutorials", "Python tutorials"),
        ("search for the best pizza recipe", "the best pizza recipe"),
        ("google machine learning", "machine learning"),
    ]

    for input_text, expected in cases:
        result = router._extract_search_query(input_text)
        assert expected.lower() in result.lower(), (
            f"Expected '{expected}' in result '{result}' for input '{input_text}'"
        )

    print("✓ Search query extraction works correctly")


def test_app_controller_known_apps():
    """AppController should have a populated app map."""
    from automation.desktop.app_control import AppController

    app = AppController()
    known = app.list_known_apps()
    assert len(known) > 10
    assert "notepad" in known
    assert "chrome" in known
    print(f"✓ AppController knows {len(known)} apps")


def test_app_controller_clipboard():
    """AppController should read/write clipboard."""
    from automation.desktop.app_control import AppController

    app = AppController()
    test_text = "JOSEPH clipboard test 12345"
    app.write_clipboard(test_text)
    result = app.read_clipboard()
    assert test_text in result, f"Expected '{test_text}' in clipboard, got '{result}'"
    print("✓ Clipboard read/write works")


def test_mouse_keyboard_available():
    """MouseKeyboardController should initialize."""
    from automation.desktop.mouse_keyboard import MouseKeyboardController

    mk = MouseKeyboardController()
    assert mk.is_available
    size = mk.get_screen_size()
    assert size[0] > 0 and size[1] > 0
    print(f"✓ MouseKeyboard ready, screen: {size[0]}x{size[1]}")


def test_playwright_import():
    """Playwright should be importable."""
    from automation.browser.playwright_controller import PlaywrightController
    pc = PlaywrightController()
    print("✓ PlaywrightController imports OK")


def test_open_notepad():
    """AppController should open Notepad."""
    import time
    from automation.desktop.app_control import AppController

    app = AppController()
    success, msg = app.open_app("notepad")
    assert success, f"Failed to open Notepad: {msg}"
    time.sleep(1)
    print(f"✓ Notepad opened: {msg}")


if __name__ == "__main__":
    print("\nRunning Phase 3 Automation Tests\n" + "=" * 40)

    tests = [
        test_command_router_intent_classification,
        test_search_query_extraction,
        test_app_controller_known_apps,
        test_app_controller_clipboard,
        test_mouse_keyboard_available,
        test_playwright_import,
        test_open_notepad,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\nRunning: {test.__name__}")
            test()
            passed += 1
        except Exception as e:
            print(f"✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

    print(f"\n{'=' * 40}")
    print(f"Results: {passed} passed, {failed} failed")
    if failed == 0:
        print("All Phase 3 tests passed!")

"""
hyper/bootstrap.py
-------------------
Helper utilities for enabling the Hyper-Intelligence layer safely.

The hyper layer is optional and off by default. These helpers make it easy
for the existing app, API, and UI to attach the layer without changing the
default runtime behavior.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def hyper_enabled() -> bool:
    """Return True when the hyper layer is explicitly enabled."""
    value = os.getenv("ENABLE_HYPER_LAYER", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def create_hyper_engine(llm=None, memory=None, personality=None, enabled: Optional[bool] = None):
    """
    Create and start the hyper engine if feature flag is enabled.

    Returns:
        HyperIntelligenceEngine instance or None.
    """
    if enabled is None:
        enabled = hyper_enabled()
    if not enabled:
        return None

    try:
        from hyper.engine import HyperIntelligenceEngine

        engine = HyperIntelligenceEngine()
        engine.attach(llm=llm, memory=memory, personality=personality)
        engine.start()
        return engine
    except Exception as e:
        logger.warning(f"Hyper layer could not start: {e}")
        return None


def get_context_enhancement(hyper_engine, user_input: str = "") -> str:
    """Safely request extra system-prompt context from the hyper layer."""
    if not hyper_engine:
        return ""
    try:
        return hyper_engine.get_context_enhancement(user_input)
    except Exception as e:
        logger.debug(f"Hyper context enhancement failed: {e}")
        return ""


def enhance_response(hyper_engine, user_input: str, base_response: str, context: Optional[dict] = None) -> str:
    """Safely enhance a response using the hyper layer."""
    if not hyper_engine:
        return base_response
    try:
        return hyper_engine.enhance_response(user_input, base_response, context=context)
    except Exception as e:
        logger.debug(f"Hyper response enhancement failed: {e}")
        return base_response


def prepare_hyper_turn(hyper_engine, user_input: str, memory=None) -> dict:
    """Safely build the hyper pre-response packet."""
    if not hyper_engine:
        return {"enabled": False, "system_context": "", "trace": {}}
    try:
        return hyper_engine.prepare_turn(user_input, memory=memory)
    except Exception as e:
        logger.debug(f"Hyper turn preparation failed: {e}")
        return {"enabled": False, "system_context": "", "trace": {"error": str(e)}}


def finalize_hyper_turn(hyper_engine, user_input: str, response_text: str, elapsed_seconds: Optional[float] = None, memory=None) -> None:
    """Safely finalize a hyper-powered turn."""
    if not hyper_engine:
        return
    try:
        hyper_engine.finalize_turn(user_input, response_text, elapsed_seconds=elapsed_seconds, memory=memory)
    except Exception as e:
        logger.debug(f"Hyper turn finalization failed: {e}")


def get_hyper_dashboard_data(hyper_engine) -> dict:
    """Safely retrieve dashboard diagnostics."""
    if not hyper_engine:
        return {"system": {"hyper_enabled": False}}
    try:
        return hyper_engine.get_dashboard_data()
    except Exception as e:
        logger.debug(f"Hyper dashboard data failed: {e}")
        return {"system": {"hyper_enabled": True}, "error": str(e)}


def shutdown_hyper(hyper_engine) -> None:
    """Stop the hyper engine without raising errors."""
    if not hyper_engine:
        return
    try:
        hyper_engine.stop()
    except Exception:
        pass

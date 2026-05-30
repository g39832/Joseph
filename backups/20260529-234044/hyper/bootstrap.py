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


def shutdown_hyper(hyper_engine) -> None:
    """Stop the hyper engine without raising errors."""
    if not hyper_engine:
        return
    try:
        hyper_engine.stop()
    except Exception:
        pass

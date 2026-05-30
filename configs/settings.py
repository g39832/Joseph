"""
configs/settings.py
-------------------
Central settings loader for JOSEPH.

Reads from:
  1. .env file (via python-dotenv)
  2. joseph_config.json (for structured config)
  3. Environment variables (override everything)

All other modules import from here — never import dotenv elsewhere.
"""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file)
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

logger = logging.getLogger(__name__)


def _load_json_config() -> dict:
    """Load joseph_config.json and return as dict."""
    config_path = BASE_DIR / "configs" / "joseph_config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    logger.warning("joseph_config.json not found, using defaults.")
    return {}


# Load JSON config once at module level
_json_cfg = _load_json_config()


class Settings:
    """
    Single source of truth for all JOSEPH configuration.
    Attributes are read from environment variables with fallbacks
    to joseph_config.json values.
    """

    # --- Paths ---
    BASE_DIR: Path = BASE_DIR
    DATA_DIR: Path = BASE_DIR / "data"
    LOG_DIR: Path = BASE_DIR / "logs"
    EXPORTS_DIR: Path = BASE_DIR / "exports"

    # --- Assistant Identity ---
    JOSEPH_NAME: str = os.getenv("JOSEPH_NAME", "Joseph")
    USER_NAME: str = os.getenv("USER_NAME", "Boss")

    # --- Ollama / LLM ---
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv(
        "OLLAMA_MODEL", _json_cfg.get("llm", {}).get("model", "llama3")
    )
    OLLAMA_FALLBACK_MODEL: str = _json_cfg.get("llm", {}).get(
        "fallback_model", "qwen2.5"
    )
    OLLAMA_TIMEOUT: int = int(os.getenv("OLLAMA_TIMEOUT", "120"))
    LLM_TEMPERATURE: float = float(
        _json_cfg.get("llm", {}).get("temperature", 0.65)
    )
    LLM_MAX_TOKENS: int = int(
        _json_cfg.get("llm", {}).get("max_tokens", 768)
    )
    LLM_STREAM: bool = _json_cfg.get("llm", {}).get("stream", True)

    # --- Memory ---
    MEMORY_DB_PATH: Path = BASE_DIR / os.getenv(
        "MEMORY_DB_PATH", "data/memory.db"
    ).lstrip("./")
    CHROMA_DB_PATH: Path = BASE_DIR / os.getenv(
        "CHROMA_DB_PATH", "data/chroma"
    ).lstrip("./")
    SHORT_TERM_LIMIT: int = int(
        os.getenv(
            "SHORT_TERM_LIMIT",
            str(_json_cfg.get("memory", {}).get("short_term_limit", 20)),
        )
    )
    CHROMA_COLLECTION: str = _json_cfg.get("memory", {}).get(
        "chroma_collection", "joseph_memory"
    )
    SUMMARIZE_AFTER_TURNS: int = _json_cfg.get("memory", {}).get(
        "summarize_after_turns", 10
    )

    # --- Logging ---
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    LOG_FILE: Path = BASE_DIR / os.getenv("LOG_FILE", "logs/joseph.log").lstrip(
        "./"
    )

    # --- API ---
    API_HOST: str = os.getenv("API_HOST", "127.0.0.1")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))

    # --- Voice ---
    WAKE_WORD: str = os.getenv("WAKE_WORD", "joseph").lower()
    MIC_DEVICE_INDEX: Optional[int] = (
        int(os.getenv("MIC_DEVICE_INDEX", "0"))
        if os.getenv("MIC_DEVICE_INDEX")
        else None
    )
    WHISPER_MODEL: str = os.getenv("WHISPER_MODEL", "base.en")
    TTS_MODEL: str = os.getenv(
        "TTS_MODEL", "tts_models/en/ljspeech/tacotron2-DDC"
    )

    # --- Safety ---
    REQUIRE_CONFIRMATION_FOR_SHELL: bool = (
        os.getenv("REQUIRE_CONFIRMATION_FOR_SHELL", "true").lower() == "true"
    )
    REQUIRE_CONFIRMATION_FOR_FILES: bool = (
        os.getenv("REQUIRE_CONFIRMATION_FOR_FILES", "true").lower() == "true"
    )
    REQUIRE_CONFIRMATION_FOR_EMAIL: bool = (
        os.getenv("REQUIRE_CONFIRMATION_FOR_EMAIL", "true").lower() == "true"
    )

    # --- UI ---
    SHOW_TIMESTAMPS: bool = _json_cfg.get("ui", {}).get("show_timestamps", True)
    SHOW_MEMORY_STATUS: bool = _json_cfg.get("ui", {}).get(
        "show_memory_status", True
    )

    # --- Hyper Intelligence Layer ---
    ENABLE_HYPER_LAYER: bool = os.getenv("ENABLE_HYPER_LAYER", "false").lower() == "true"
    ENABLE_HYPER_LEARNING: bool = os.getenv("ENABLE_HYPER_LEARNING", "true").lower() == "true"
    ENABLE_HYPER_WEB: bool = os.getenv("ENABLE_HYPER_WEB", "true").lower() == "true"
    ENABLE_HYPER_GPU: bool = os.getenv("ENABLE_HYPER_GPU", "true").lower() == "true"
    ENABLE_HYPER_AGENT_ORCHESTRATION: bool = (
        os.getenv("ENABLE_HYPER_AGENT_ORCHESTRATION", "true").lower() == "true"
    )
    ENABLE_HYPER_GRAPH: bool = os.getenv("ENABLE_HYPER_GRAPH", "true").lower() == "true"
    ENABLE_HYPER_DASHBOARD: bool = os.getenv("ENABLE_HYPER_DASHBOARD", "true").lower() == "true"
    ENABLE_HYPER_ANALYZER: bool = os.getenv("ENABLE_HYPER_ANALYZER", "true").lower() == "true"
    HYPER_RESEARCH_TIMEOUT: int = int(os.getenv("HYPER_RESEARCH_TIMEOUT", "12"))
    HYPER_MONITOR_INTERVAL: float = float(os.getenv("HYPER_MONITOR_INTERVAL", "5.0"))

    def ensure_directories(self) -> None:
        """Create all required data/log directories if they don't exist."""
        for directory in [self.DATA_DIR, self.LOG_DIR, self.EXPORTS_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        # Ensure chroma parent exists
        self.CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)

    def __repr__(self) -> str:
        return (
            f"Settings(model={self.OLLAMA_MODEL}, "
            f"user={self.USER_NAME}, "
            f"log_level={self.LOG_LEVEL})"
        )


# Singleton instance — import this everywhere
settings = Settings()

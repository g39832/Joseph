"""
hyper/monitor.py
----------------
System metrics and diagnostics collection for the hyper layer.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections import deque
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class SystemMonitor:
    """Collects lightweight metrics and health signals without crashing."""

    def __init__(self, sample_interval: float = 5.0, history_size: int = 200):
        self.sample_interval = sample_interval
        self.session_id: Optional[str] = None
        self.started_at = datetime.now()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._history = deque(maxlen=history_size)
        self._tool_failures = deque(maxlen=history_size)
        self._api_latencies = deque(maxlen=history_size)
        self._response_times = deque(maxlen=history_size)
        self._tokens_per_second = deque(maxlen=history_size)
        self._model_quality = deque(maxlen=history_size)
        self._response_quality = deque(maxlen=history_size)
        self._gpu_usage = deque(maxlen=history_size)
        self._vram_usage = deque(maxlen=history_size)
        self._last_snapshot = {}
        self._psutil = None
        try:
            import psutil  # type: ignore

            self._psutil = psutil
        except Exception:
            self._psutil = None

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="SystemMonitor")
        self._thread.start()
        logger.info("System monitor started")

    def stop(self) -> None:
        self._running = False

    def set_session(self, session_id: Optional[str]) -> None:
        self.session_id = session_id

    def _loop(self) -> None:
        while self._running:
            try:
                self._last_snapshot = self._collect_snapshot()
                self._history.append(self._last_snapshot)
            except Exception as e:
                logger.debug(f"Monitor loop error: {e}")
            time.sleep(self.sample_interval)

    def _collect_snapshot(self) -> dict:
        cpu = 0.0
        memory = 0.0

        if self._psutil:
            try:
                cpu = float(self._psutil.cpu_percent(interval=None))
                memory = float(self._psutil.virtual_memory().percent)
            except Exception:
                pass
        else:
            try:
                if hasattr(os, "getloadavg"):
                    cpu = round(min(100.0, (os.getloadavg()[0] / max(1, os.cpu_count() or 1)) * 100.0), 2)
            except Exception:
                pass

        return {
            "timestamp": datetime.now().isoformat(),
            "cpu_usage": round(cpu, 2),
            "memory_usage": round(memory, 2),
            "gpu_usage": self._avg(self._gpu_usage),
            "vram_usage": self._avg(self._vram_usage),
            "api_latency_ms": self._avg(self._api_latencies),
            "response_time_ms": self._avg(self._response_times),
            "tokens_per_second": self._avg(self._tokens_per_second),
            "tool_failures": len(self._tool_failures),
            "model_performance": self._avg(self._model_quality),
            "response_quality": self._avg(self._response_quality),
            "session_id": self.session_id,
            "uptime_seconds": round((datetime.now() - self.started_at).total_seconds(), 1),
        }

    def _avg(self, values) -> float:
        values = list(values)
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    def record_api_latency(self, latency_ms: float) -> None:
        self._api_latencies.append(float(latency_ms))

    def record_response_metrics(self, elapsed_seconds: float, response_text: str = "") -> None:
        elapsed_seconds = max(0.001, float(elapsed_seconds))
        response_text = response_text or ""
        token_estimate = max(1, len(response_text.split()))
        self._response_times.append(elapsed_seconds * 1000.0)
        self._tokens_per_second.append(token_estimate / elapsed_seconds)

    def record_tool_failure(self, tool_name: str, error: str = "") -> None:
        self._tool_failures.append(
            {"tool": tool_name, "error": error, "timestamp": datetime.now().isoformat()}
        )

    def record_model_performance(self, score: float) -> None:
        self._model_quality.append(float(score))

    def record_response_quality(self, score: float) -> None:
        self._response_quality.append(float(score))

    def record_gpu_metrics(self, gpu_usage: float = 0.0, vram_usage: float = 0.0) -> None:
        self._gpu_usage.append(float(gpu_usage))
        self._vram_usage.append(float(vram_usage))

    def get_metrics_snapshot(self) -> dict:
        if not self._last_snapshot:
            self._last_snapshot = self._collect_snapshot()
        snapshot = dict(self._last_snapshot)
        snapshot["api_latency_ms"] = self._avg(self._api_latencies)
        snapshot["response_time_ms"] = self._avg(self._response_times)
        snapshot["tokens_per_second"] = self._avg(self._tokens_per_second)
        snapshot["tool_failures"] = len(self._tool_failures)
        snapshot["model_performance"] = self._avg(self._model_quality)
        snapshot["response_quality"] = self._avg(self._response_quality)
        snapshot["gpu_usage"] = self._avg(self._gpu_usage)
        snapshot["vram_usage"] = self._avg(self._vram_usage)
        snapshot["uptime_hint"] = len(self._history)
        return snapshot

    def get_health_summary(self) -> dict:
        snapshot = self.get_metrics_snapshot()
        warnings = []

        if snapshot["cpu_usage"] > 85:
            warnings.append("High CPU usage")
        if snapshot["memory_usage"] > 85:
            warnings.append("High memory usage")
        if snapshot["api_latency_ms"] > 1500:
            warnings.append("High API latency")
        if snapshot["response_time_ms"] > 6000:
            warnings.append("Slow response time")
        if snapshot["tool_failures"] > 5:
            warnings.append("Repeated tool failures")
        if snapshot["response_quality"] and snapshot["response_quality"] < 0.4:
            warnings.append("Low response quality")

        return {
            "ok": not warnings,
            "warnings": warnings,
            "metrics": snapshot,
        }

    def get_diagnostics(self) -> dict:
        return {
            "health": self.get_health_summary(),
            "history_count": len(self._history),
            "recent_history": list(self._history)[-10:],
            "tool_failures": list(self._tool_failures)[-10:],
            "session_id": self.session_id,
            "uptime_seconds": round((datetime.now() - self.started_at).total_seconds(), 1),
        }

    def __repr__(self) -> str:
        summary = self.get_health_summary()
        return f"SystemMonitor(ok={summary['ok']}, warnings={len(summary['warnings'])})"

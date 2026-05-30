"""
hyper/gpu_manager.py
--------------------
Best-effort GPU capability detection and acceleration routing.

This manager never hard-fails. If GPU support is missing or partially broken,
it falls back to CPU mode and records the failure for diagnostics.
"""

from __future__ import annotations

import logging
import platform
from dataclasses import dataclass, asdict
from typing import Any, Optional
import subprocess
import time
import statistics

logger = logging.getLogger(__name__)


@dataclass
class GPUCapabilitySnapshot:
    backend: str = "cpu"
    nvidia: bool = False
    cuda: bool = False
    tensorrt: bool = False
    directml: bool = False
    rocm: bool = False
    opencl: bool = False
    device_name: Optional[str] = None
    memory_gb: Optional[float] = None
    torch_available: bool = False
    torch_version: Optional[str] = None
    notes: str = "CPU fallback"


class GPUComputeManager:
    """Detects available GPU backends and exposes safe fallback helpers."""

    def __init__(self):
        self.snapshot = GPUCapabilitySnapshot()
        self.initialized = False
        self._error: Optional[str] = None
        self._benchmarks: dict[str, Any] = {}

    def initialize(self) -> bool:
        """Detect hardware acceleration capabilities."""
        try:
            self.snapshot = self._detect()
            self.initialized = True
            logger.info(f"GPU manager initialized: {self.snapshot.backend}")
            return True
        except Exception as e:
            self._error = str(e)
            self.snapshot = GPUCapabilitySnapshot(notes=f"GPU init failed: {e}")
            self.initialized = False
            logger.warning(f"GPU manager failed, using CPU: {e}")
            return False

    def _detect(self) -> GPUCapabilitySnapshot:
        snap = GPUCapabilitySnapshot()

        try:
            import torch

            snap.torch_available = True
            snap.torch_version = getattr(torch, "__version__", None)
            snap.cuda = bool(torch.cuda.is_available())
            if snap.cuda:
                snap.backend = "cuda"
                snap.nvidia = True
                try:
                    snap.device_name = torch.cuda.get_device_name(0)
                    props = torch.cuda.get_device_properties(0)
                    snap.memory_gb = round(props.total_memory / 1024**3, 1)
                except Exception:
                    pass
                snap.notes = "CUDA available"
                return snap
        except Exception:
            pass

        # ONNX Runtime providers can expose DirectML / TensorRT / CUDA.
        try:
            import onnxruntime as ort

            providers = [p.lower() for p in ort.get_available_providers()]
            if any("tensorrt" in p for p in providers):
                snap.backend = "tensorrt"
                snap.tensorrt = True
            elif any("directml" in p for p in providers):
                snap.backend = "directml"
                snap.directml = True
            elif any("rocm" in p for p in providers):
                snap.backend = "rocm"
                snap.rocm = True
            elif any("opencl" in p for p in providers):
                snap.backend = "opencl"
                snap.opencl = True

            if snap.backend != "cpu":
                snap.notes = f"ONNX Runtime providers: {', '.join(providers)}"
                return snap
        except Exception:
            pass

        # Optional OpenCL detection.
        try:
            import pyopencl  # type: ignore

            platforms = pyopencl.get_platforms()
            if platforms:
                snap.backend = "opencl"
                snap.opencl = True
                snap.notes = f"OpenCL available on {platform.system()}"
                return snap
        except Exception:
            pass

        snap.notes = "No GPU backend detected"
        return snap

    def get_utilization(self) -> dict:
        """
        Return a best-effort utilization snapshot.
        """
        usage = {
            "gpu_usage": 0.0,
            "vram_used_mb": 0.0,
            "vram_total_mb": 0.0,
            "device_name": self.snapshot.device_name,
            "backend": self.snapshot.backend,
        }
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
                timeout=3,
                check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                line = result.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 4:
                    usage["device_name"] = parts[0]
                    usage["gpu_usage"] = float(parts[1])
                    usage["vram_used_mb"] = float(parts[2])
                    usage["vram_total_mb"] = float(parts[3])
                    return usage
        except Exception:
            pass

        try:
            import torch
            if torch.cuda.is_available():
                usage["device_name"] = torch.cuda.get_device_name(0)
                usage["vram_used_mb"] = round(torch.cuda.memory_allocated(0) / 1024**2, 1)
                usage["vram_total_mb"] = round(torch.cuda.get_device_properties(0).total_memory / 1024**2, 1)
        except Exception:
            pass
        return usage

    def benchmark(self, size: int = 1024, repeats: int = 3) -> dict:
        """
        Compare simple CPU vs GPU execution time when available.
        """
        results = {
            "backend": self.snapshot.backend,
            "size": size,
            "repeats": repeats,
            "cpu_ms": None,
            "gpu_ms": None,
            "speedup": None,
        }

        try:
            import numpy as np

            cpu_times = []
            for _ in range(repeats):
                a = np.random.rand(size, size).astype("float32")
                b = np.random.rand(size, size).astype("float32")
                start = time.perf_counter()
                _ = a @ b
                cpu_times.append((time.perf_counter() - start) * 1000.0)
            results["cpu_ms"] = round(statistics.mean(cpu_times), 2)
        except Exception as e:
            results["cpu_error"] = str(e)

        try:
            if self.snapshot.cuda:
                import torch

                device = torch.device("cuda")
                gpu_times = []
                for _ in range(repeats):
                    a = torch.rand((size, size), device=device)
                    b = torch.rand((size, size), device=device)
                    torch.cuda.synchronize()
                    start = time.perf_counter()
                    _ = a @ b
                    torch.cuda.synchronize()
                    gpu_times.append((time.perf_counter() - start) * 1000.0)
                results["gpu_ms"] = round(statistics.mean(gpu_times), 2)
        except Exception as e:
            results["gpu_error"] = str(e)

        if results["cpu_ms"] and results["gpu_ms"]:
            results["speedup"] = round(results["cpu_ms"] / max(0.001, results["gpu_ms"]), 2)

        self._benchmarks = results
        return results

    def is_available(self) -> bool:
        return self.snapshot.backend != "cpu"

    def get_best_backend(self) -> str:
        return self.snapshot.backend

    def accelerate(self, operation: str, fallback=None, *args, **kwargs):
        """
        Run a callable with GPU preference and safe CPU fallback.
        """
        if callable(operation):
            try:
                return operation(*args, **kwargs)
            except Exception as e:
                logger.debug(f"GPU path failed, using fallback: {e}")
                if callable(fallback):
                    return fallback(*args, **kwargs)
                raise
        if callable(fallback):
            return fallback(*args, **kwargs)
        return None

    def get_status(self) -> dict[str, Any]:
        data = asdict(self.snapshot)
        data["initialized"] = self.initialized
        data["error"] = self._error
        data["utilization"] = self.get_utilization()
        data["benchmark"] = self._benchmarks or None
        return data

    def __repr__(self) -> str:
        return f"GPUComputeManager(backend={self.snapshot.backend}, initialized={self.initialized})"

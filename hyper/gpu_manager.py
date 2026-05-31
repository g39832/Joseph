"""
hyper/gpu_manager.py
---------------------
GPUComputeManager — Phase 6: GPU Acceleration Layer.

Detects and manages GPU resources for JOSEPH.
Provides acceleration for inference, embeddings, and processing.
Falls back gracefully to CPU — never crashes on GPU failure.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class GPUComputeManager:
    """
    Manages GPU acceleration for JOSEPH.

    Detects available GPU backends and configures
    the system to use the best available option.

    Never crashes — always falls back to CPU.
    """

    def __init__(self):
        self._available = False
        self._backend = "cpu"
        self._device_name = "CPU"
        self._vram_gb = 0.0
        self._cuda_version = None
        self._initialized = False

    def initialize(self) -> bool:
        """
        Detect GPU and initialize acceleration.

        Returns:
            True if GPU acceleration is available.
        """
        try:
            import torch

            if torch.cuda.is_available():
                self._backend = "cuda"
                self._device_name = torch.cuda.get_device_name(0)
                vram = torch.cuda.get_device_properties(0).total_memory
                self._vram_gb = round(vram / 1024**3, 1)
                self._cuda_version = torch.version.cuda
                self._available = True
                logger.info(
                    f"GPU acceleration: {self._device_name} "
                    f"({self._vram_gb}GB VRAM, CUDA {self._cuda_version})"
                )
            else:
                logger.info("GPU not available — using CPU")

        except ImportError:
            logger.debug("PyTorch not available for GPU detection")
        except Exception as e:
            logger.warning(f"GPU init error (falling back to CPU): {e}")

        self._initialized = True
        return self._available

    def get_optimal_device(self) -> str:
        """Return the optimal device string for PyTorch."""
        return "cuda" if self._available else "cpu"

    def get_optimal_dtype(self) -> str:
        """Return optimal compute dtype based on VRAM."""
        if not self._available:
            return "int8"
        if self._vram_gb >= 6:
            return "float16"
        elif self._vram_gb >= 3:
            return "float16"
        return "int8"

    def get_status(self) -> dict:
        """Return GPU status information."""
        status = {
            "available": self._available,
            "backend": self._backend,
            "device": self._device_name,
            "vram_gb": self._vram_gb,
        }
        if self._available:
            try:
                import torch
                allocated = torch.cuda.memory_allocated(0) / 1024**3
                reserved = torch.cuda.memory_reserved(0) / 1024**3
                status["vram_used_gb"] = round(allocated, 2)
                status["vram_reserved_gb"] = round(reserved, 2)
            except Exception:
                pass
        return status

    def clear_cache(self) -> None:
        """Clear GPU memory cache."""
        if self._available:
            try:
                import torch
                torch.cuda.empty_cache()
                logger.debug("GPU cache cleared")
            except Exception:
                pass

    @property
    def is_available(self) -> bool:
        return self._available

    @property
    def device_name(self) -> str:
        return self._device_name

    def __repr__(self) -> str:
        return (
            f"GPUComputeManager(backend={self._backend}, "
            f"device={self._device_name}, "
            f"vram={self._vram_gb}GB)"
        )

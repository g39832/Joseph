"""
voice/gpu_setup.py
-------------------
GPU acceleration setup for JOSEPH voice system.

Your RTX 3050 can run Whisper 5-10x faster than CPU.
This module handles CUDA detection and configuration.

To enable GPU voice:
  1. Run: python voice/gpu_setup.py
  2. Follow the printed instructions
  3. Restart Joseph

The setup script will:
  - Detect your GPU
  - Check if CUDA is installed
  - Install the correct PyTorch version
  - Reconfigure Whisper to use GPU
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def check_cuda_available() -> bool:
    """Check if CUDA is available via torch."""
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False


def check_torch_installed() -> bool:
    """Check if PyTorch is installed."""
    try:
        import torch
        return True
    except ImportError:
        return False


def get_gpu_info() -> dict:
    """Get GPU information."""
    info = {
        "name": "Unknown",
        "cuda_available": False,
        "torch_installed": False,
        "torch_version": None,
        "cuda_version": None,
        "vram_gb": None,
    }

    # Check torch
    info["torch_installed"] = check_torch_installed()
    if info["torch_installed"]:
        import torch
        info["torch_version"] = torch.__version__
        info["cuda_available"] = torch.cuda.is_available()
        if info["cuda_available"]:
            info["cuda_version"] = torch.version.cuda
            info["name"] = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory
            info["vram_gb"] = round(vram / 1024**3, 1)

    return info


def get_recommended_whisper_config() -> dict:
    """
    Get the recommended Whisper configuration based on available hardware.

    Returns:
        Dict with device, compute_type, model_size recommendations.
    """
    info = get_gpu_info()

    if info["cuda_available"] and info["vram_gb"]:
        vram = info["vram_gb"]
        if vram >= 6:
            return {
                "device": "cuda",
                "compute_type": "float16",
                "model_size": "medium.en",
                "reason": f"GPU ({info['name']}, {vram}GB VRAM) — high accuracy",
            }
        elif vram >= 3:
            return {
                "device": "cuda",
                "compute_type": "float16",
                "model_size": "small.en",
                "reason": f"GPU ({info['name']}, {vram}GB VRAM) — good balance",
            }
        else:
            return {
                "device": "cuda",
                "compute_type": "int8",
                "model_size": "base.en",
                "reason": f"GPU ({info['name']}, {vram}GB VRAM) — limited VRAM",
            }
    else:
        return {
            "device": "cpu",
            "compute_type": "int8",
            "model_size": "small.en",
            "reason": "CPU mode (no CUDA available)",
        }


def print_setup_instructions():
    """Print step-by-step GPU setup instructions."""
    info = get_gpu_info()

    print("\n" + "=" * 60)
    print("JOSEPH — GPU Voice Setup")
    print("=" * 60)

    print(f"\nGPU Detection:")
    print(f"  PyTorch installed: {info['torch_installed']}")
    print(f"  CUDA available:    {info['cuda_available']}")
    if info["torch_installed"]:
        print(f"  PyTorch version:   {info['torch_version']}")
    if info["cuda_available"]:
        print(f"  GPU:               {info['name']}")
        print(f"  VRAM:              {info['vram_gb']}GB")
        print(f"  CUDA version:      {info['cuda_version']}")

    if info["cuda_available"]:
        config = get_recommended_whisper_config()
        print(f"\n✓ GPU is ready!")
        print(f"  Recommended config: {config['reason']}")
        print(f"  Model: {config['model_size']}")
        print(f"  Device: {config['device']}")
        print(f"  Compute type: {config['compute_type']}")
        print(f"\nTo apply this config, update your .env:")
        print(f"  WHISPER_MODEL={config['model_size']}")
        print(f"\nAnd update voice/speech_to_text.py:")
        print(f"  device=\"{config['device']}\"")
        print(f"  compute_type=\"{config['compute_type']}\"")
    else:
        print(f"\n⚠ CUDA not available. Steps to enable GPU voice:")
        print(f"\nStep 1 — Install CUDA Toolkit 12.1:")
        print(f"  Download: https://developer.nvidia.com/cuda-12-1-0-download-archive")
        print(f"  Select: Windows > x86_64 > 11 > exe (local)")
        print(f"  Install with default settings")
        print(f"  Restart your computer after install")
        print(f"\nStep 2 — Install PyTorch with CUDA:")
        print(f"  Run this command:")
        print(f"  pip install torch --index-url https://download.pytorch.org/whl/cu121")
        print(f"\nStep 3 — Verify:")
        print(f"  python -c \"import torch; print(torch.cuda.is_available())\"")
        print(f"  Should print: True")
        print(f"\nStep 4 — Run this script again to get your config.")

    print("\n" + "=" * 60)


def apply_gpu_config_to_stt():
    """
    Automatically update speech_to_text.py to use GPU if available.
    Only runs if CUDA is confirmed available.
    """
    if not check_cuda_available():
        print("CUDA not available — keeping CPU config.")
        return False

    config = get_recommended_whisper_config()
    stt_path = Path(__file__).parent / "speech_to_text.py"

    if not stt_path.exists():
        print(f"speech_to_text.py not found at {stt_path}")
        return False

    content = stt_path.read_text(encoding="utf-8")

    # Update device
    content = content.replace(
        'device="cpu"',
        f'device="{config["device"]}"',
    )
    # Update compute_type
    content = content.replace(
        'compute_type="int8",  # int8 is fastest on CPU',
        f'compute_type="{config["compute_type"]}",  # GPU accelerated',
    )

    stt_path.write_text(content, encoding="utf-8")
    print(f"✓ speech_to_text.py updated for GPU ({config['device']}, {config['compute_type']})")

    # Update .env
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        env_content = env_path.read_text(encoding="utf-8")
        # Update model size
        import re
        env_content = re.sub(
            r"WHISPER_MODEL=\S+",
            f"WHISPER_MODEL={config['model_size']}",
            env_content,
        )
        env_path.write_text(env_content, encoding="utf-8")
        print(f"✓ .env updated: WHISPER_MODEL={config['model_size']}")

    return True


if __name__ == "__main__":
    print_setup_instructions()

    if check_cuda_available():
        print("\nApply GPU configuration automatically? (yes/no): ", end="")
        answer = input().strip().lower()
        if answer in ("yes", "y"):
            apply_gpu_config_to_stt()
            print("\n✓ Done. Restart Joseph to use GPU voice.")
        else:
            print("Skipped. Apply manually using the config above.")

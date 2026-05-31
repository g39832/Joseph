"""
brain/vision_engine.py
------------------------
Vision Engine — provides image understanding capabilities.

Supports image description, diagram analysis, screenshot understanding,
UI analysis, graph interpretation, and chart interpretation.

Uses Ollama multimodal API (llava/bakllava) when available, with
graceful fallback to basic image metadata extraction.

Usage:
    ve = VisionEngine(llm=llm)
    result = ve.describe("path/to/image.png")
    result.description  # text description
"""

import base64
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VisionResult:
    path: str
    description: str = ""
    objects: list[str] = field(default_factory=list)
    text_detected: str = ""
    image_size: tuple = (0, 0)
    format: str = ""
    error: str = ""
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()


class VisionEngine:
    """
    Image analysis using Ollama multimodal API with fallback.

    Lightweight — vision model is NOT loaded at startup.
    Analysis happens via API call to Ollama's /api/chat endpoint
    which supports multimodal models like llava, bakllava, etc.
    """

    def __init__(self, llm=None, base_url: str = "http://localhost:11434"):
        self._llm = llm
        self._base_url = base_url.rstrip("/")
        self._multimodal_available = None

    def check_multimodal(self) -> bool:
        """Check if a multimodal model is available in Ollama."""
        if self._multimodal_available is not None:
            return self._multimodal_available
        try:
            import urllib.request
            url = f"{self._base_url}/api/tags"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            multimodal_keywords = ["llava", "bakllava", "moondream", "cogvlm",
                                   "minicpm-v", "qwen2-vl", "internvl"]
            for model in models:
                for kw in multimodal_keywords:
                    if kw in model.lower():
                        self._multimodal_available = True
                        logger.info(f"Multimodal model found: {model}")
                        return True
            self._multimodal_available = False
            return False
        except Exception:
            self._multimodal_available = False
            return False

    def describe(self, image_path: str, prompt: str = "") -> VisionResult:
        """Analyze an image and return a description."""
        path = os.path.abspath(image_path)
        if not os.path.exists(path):
            return VisionResult(path=path, error=f"File not found: {path}")

        ext = os.path.splitext(path)[1].lower()
        supported = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"}
        if ext not in supported:
            return VisionResult(
                path=path,
                error=f"Unsupported format: {ext}. Supported: {', '.join(supported)}"
            )

        # Get basic image info
        size, fmt = self._get_image_info(path)

        # Try multimodal analysis
        if self.check_multimodal():
            description = self._multimodal_analyze(path, prompt)
            if description:
                return VisionResult(
                    path=path,
                    description=description,
                    image_size=size,
                    format=fmt,
                )

        # Fallback: basic analysis via LLM with metadata
        fallback_desc = self._fallback_analysis(path, fmt)
        return VisionResult(
            path=path,
            description=fallback_desc,
            image_size=size,
            format=fmt,
        )

    def _get_image_info(self, path: str) -> tuple:
        """Get basic image dimensions and format."""
        try:
            from PIL import Image
            with Image.open(path) as img:
                return img.size, img.format or ""
        except ImportError:
            return (0, 0), ""
        except Exception:
            return (0, 0), ""

    def _multimodal_analyze(self, path: str, user_prompt: str = "") -> str:
        """Analyze image using Ollama multimodal API."""
        try:
            import urllib.request

            # Read and encode image
            with open(path, "rb") as f:
                img_base64 = base64.b64encode(f.read()).decode("utf-8")

            # Find multimodal model
            multimodal_model = self._find_multimodal_model()
            if not multimodal_model:
                return ""

            prompt = user_prompt or "Describe this image in detail. What do you see?"

            payload = json.dumps({
                "model": multimodal_model,
                "messages": [{
                    "role": "user",
                    "content": prompt,
                    "images": [img_base64],
                }],
                "stream": False,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._base_url}/api/chat",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read())
            return result.get("message", {}).get("content", "").strip()

        except Exception as e:
            logger.warning(f"Multimodal analysis failed: {e}")
            return ""

    def _find_multimodal_model(self) -> Optional[str]:
        try:
            import urllib.request
            url = f"{self._base_url}/api/tags"
            resp = urllib.request.urlopen(url, timeout=5)
            data = json.loads(resp.read())
            models = [m["name"] for m in data.get("models", [])]
            # Prefer llava, then any multimodal model
            for model in models:
                name = model.lower()
                if "llava" in name:
                    return model
            for model in models:
                name = model.lower()
                for kw in ["bakllava", "moondream", "minicpm-v", "qwen2-vl"]:
                    if kw in name:
                        return model
            return models[0] if models else None
        except Exception:
            return None

    def _fallback_analysis(self, path: str, fmt: str) -> str:
        """Generate a basic description from file metadata."""
        size = os.path.getsize(path)
        try:
            from PIL import Image
            with Image.open(path) as img:
                w, h = img.size
                mode = img.mode
                return (
                    f"Image file: {os.path.basename(path)}\n"
                    f"Format: {fmt or 'Unknown'}\n"
                    f"Dimensions: {w}x{h} pixels\n"
                    f"Color mode: {mode}\n"
                    f"File size: {self._format_size(size)}\n\n"
                    "Note: No multimodal model available. "
                    "Install llava or bakllava via 'ollama pull llava' "
                    "for detailed image understanding."
                )
        except ImportError:
            return (
                f"Image file: {os.path.basename(path)}\n"
                f"Format: {fmt or 'Unknown'}\n"
                f"File size: {self._format_size(size)}\n\n"
                "Install Pillow for image metadata extraction and "
                "ollama pull llava for detailed analysis."
            )

    def analyze_screenshot(self, image_path: str) -> VisionResult:
        """Specialized screenshot analysis with UI focus."""
        return self.describe(
            image_path,
            prompt="This is a screenshot. Describe what application is shown, "
                   "what elements are visible, and what the user might be doing. "
                   "Include any error messages, code, or important text visible.",
        )

    def analyze_diagram(self, image_path: str) -> VisionResult:
        """Specialized diagram analysis."""
        return self.describe(
            image_path,
            prompt="This is a diagram. Describe its structure, components, "
                   "relationships, labels, and overall meaning. "
                   "Identify the type of diagram if possible.",
        )

    def analyze_chart(self, image_path: str) -> VisionResult:
        """Specialized chart/graph analysis."""
        return self.describe(
            image_path,
            prompt="This is a chart or graph. Describe what it shows, "
                   "the axes, data trends, key values, and conclusions. "
                   "Include any labels, legends, or annotations.",
        )

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB"):
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}GB"

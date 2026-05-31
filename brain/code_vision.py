"""
brain/code_vision.py
----------------------
Code Screen Analysis — specialized mode for analyzing code from screenshots.

Extracts code from images, detects bugs, provides explanations,
and suggests refactoring.

Usage:
    cv = CodeVision(llm=llm, vision_engine=ve)
    result = cv.analyze_code_image("path/to/code_screenshot.png")
    result.code  # extracted code
    result.explanation
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class CodeAnalysis:
    path: str
    code: str = ""
    language: str = ""
    explanation: str = ""
    bugs: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    error: str = ""
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()


# Common language keywords for detection
LANGUAGE_KEYWORDS = {
    "python": ["def ", "import ", "class ", "print", "if __name__", "lambda", "yield"],
    "javascript": ["function", "const ", "let ", "var ", "=>", "console.log"],
    "typescript": [": string", ": number", "interface ", "type ", "as "],
    "rust": ["fn ", "let mut", "impl ", "struct ", "enum ", "match "],
    "c": ["printf", "#include", "int main", "void ", "malloc"],
    "cpp": ["std::", "cout", "template", "class ", "virtual"],
    "java": ["public class", "public static", "System.out", "@Override"],
    "go": ["func ", "package ", "import (", "defer "],
}


class CodeVision:
    """
    Analyze code from screenshots using Vision Engine + LLM.

    Pipeline: screenshot → vision description → LLM code extraction → analysis.
    """

    def __init__(self, llm=None, vision_engine=None):
        self._llm = llm
        self._ve = vision_engine

    def analyze_code_image(self, image_path: str) -> CodeAnalysis:
        """Analyze code from a screenshot image."""
        path = os.path.abspath(image_path)
        if not os.path.exists(path):
            return CodeAnalysis(path=path, error=f"File not found: {path}")

        analysis = CodeAnalysis(path=path)

        # Step 1: Get image description with code focus
        code_text = ""
        if self._ve:
            result = self._ve.describe(
                path,
                prompt="This is a screenshot of code. Extract ALL the code text "
                       "exactly as it appears. Include all characters, indentation, "
                       "and syntax. Return ONLY the code, no explanation.",
            )
            if result.description:
                code_text = result.description
        else:
            analysis.error = "Vision engine not available."
            return analysis

        if not code_text:
            analysis.error = "Could not extract code from image."
            return analysis

        # Step 2: Clean up the extracted text
        code_text = self._clean_code(code_text)
        analysis.code = code_text

        # Step 3: Detect language
        analysis.language = self._detect_language(code_text)

        # Step 4: LLM analysis
        if self._llm and len(code_text) > 10:
            self._analyze_code(analysis)

        return analysis

    def analyze_code_text(self, code_text: str, language: str = "") -> CodeAnalysis:
        """Analyze code directly from text (not from image)."""
        analysis = CodeAnalysis(
            path="",
            code=code_text,
            language=language or self._detect_language(code_text),
        )
        if self._llm and len(code_text) > 10:
            self._analyze_code(analysis)
        return analysis

    def _clean_code(self, text: str) -> str:
        """Clean up extracted code text."""
        # Remove common vision model artifacts
        text = re.sub(r"Here['']?s the code extracted from the image:?", "", text, flags=re.I)
        text = re.sub(r"The code in the screenshot is:?", "", text, flags=re.I)
        text = re.sub(r"```\w*\n?", "", text)  # Remove markdown code fences
        text = re.sub(r"\n{4,}", "\n\n", text)  # Normalize whitespace
        return text.strip()

    def _detect_language(self, code: str) -> str:
        """Detect programming language from code keywords."""
        code_lower = code.lower()
        scores = {}
        for lang, keywords in LANGUAGE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in code_lower)
            if score > 0:
                scores[lang] = score
        if scores:
            return max(scores, key=scores.get)
        return "unknown"

    def _analyze_code(self, analysis: CodeAnalysis) -> None:
        """Run LLM-based code analysis."""
        code = analysis.code[:4000]
        lang = analysis.language

        try:
            # Explanation
            expl_prompt = (
                f"Explain what this {lang} code does in simple terms:\n\n{code}"
            )
            explanation = self._ask(expl_prompt, max_tokens=300)
            if explanation:
                analysis.explanation = explanation.strip()[:500]

            # Bug detection
            bug_prompt = (
                f"Analyze this {lang} code for bugs, errors, or potential issues. "
                f"List each issue on a new line starting with '-'. "
                f"If none found, say 'No obvious bugs detected':\n\n{code}"
            )
            bug_text = self._ask(bug_prompt, max_tokens=300)
            if bug_text and "no obvious bugs" not in bug_text.lower():
                analysis.bugs = [
                    b.strip().lstrip("-* ") for b in bug_text.split("\n")
                    if b.strip().startswith(("-", "*"))
                ]

            # Suggestions
            sug_prompt = (
                f"Suggest 2-3 improvements or refactoring suggestions for this "
                f"{lang} code. List each on a new line starting with '-':\n\n{code}"
            )
            sug_text = self._ask(sug_prompt, max_tokens=300)
            if sug_text:
                analysis.suggestions = [
                    s.strip().lstrip("-* ") for s in sug_text.split("\n")
                    if s.strip().startswith(("-", "*"))
                ]

        except Exception as e:
            logger.warning(f"Code analysis failed: {e}")

    def _ask(self, prompt: str, max_tokens: int = 200) -> str:
        if not self._llm:
            return ""
        try:
            response = ""
            for chunk in self._llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a code analysis assistant.",
            ):
                response += chunk
                if len(response) > max_tokens:
                    break
            return response.strip()
        except Exception:
            return ""

"""
brain/document_intelligence.py
--------------------------------
Document Intelligence Engine — extracts and analyzes text from
PDF, DOCX, TXT, Markdown, and code files.

Supports summarization, key points, topic extraction, citation
extraction, and question answering. Integrates with Research Workspace,
Memory, and Knowledge Graph.

Usage:
    di = DocumentIntelligence(llm=llm)
    result = di.analyze("path/to/file.pdf")
    result.summary  # generated summary
    result.key_points  # extracted key points
    result.topics  # detected topics
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DocumentResult:
    path: str
    file_type: str
    file_size_bytes: int
    text_preview: str = ""
    full_text: str = ""
    summary: str = ""
    key_points: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    word_count: int = 0
    error: str = ""
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()


SUPPORTED_TYPES = {
    ".pdf": "PDF",
    ".docx": "DOCX",
    ".txt": "TXT",
    ".md": "Markdown",
    ".py": "Code",
    ".js": "Code",
    ".ts": "Code",
    ".rs": "Code",
    ".c": "Code",
    ".cpp": "Code",
    ".h": "Code",
    ".java": "Code",
    ".html": "Code",
    ".css": "Code",
    ".json": "Code",
    ".yaml": "Code",
    ".toml": "Code",
    ".sql": "Code",
    ".sh": "Code",
    ".bat": "Code",
}


class DocumentIntelligence:
    """
    Extract and analyze document content.

    Uses lightweight extraction libraries with fallbacks.
    LLM analysis is optional and lazy.
    """

    def __init__(self, llm=None):
        self._llm = llm
        self._extractors = {}

    def analyze(self, file_path: str) -> DocumentResult:
        """Analyze a document file and return structured results."""
        path = os.path.abspath(file_path)
        ext = os.path.splitext(path)[1].lower()
        file_type = SUPPORTED_TYPES.get(ext, "Unknown")
        size = os.path.getsize(path) if os.path.exists(path) else 0

        if not os.path.exists(path):
            return DocumentResult(
                path=path, file_type=file_type, file_size_bytes=0,
                error=f"File not found: {path}",
            )

        text = self._extract_text(path, ext)
        if not text:
            return DocumentResult(
                path=path, file_type=file_type, file_size_bytes=size,
                error="Could not extract text from file",
            )

        preview = text[:500]
        word_count = len(text.split())

        result = DocumentResult(
            path=path,
            file_type=file_type,
            file_size_bytes=size,
            text_preview=preview,
            full_text=text,
            word_count=word_count,
        )

        # Run LLM analysis if available
        if self._llm and len(text) > 20:
            self._llm_analyze(result)

        return result

    def _extract_text(self, path: str, ext: str) -> str:
        """Extract text from a file based on its extension."""
        try:
            if ext == ".pdf":
                return self._extract_pdf(path)
            elif ext == ".docx":
                return self._extract_docx(path)
            elif ext in (".txt", ".md", ".py", ".js", ".ts", ".rs", ".c",
                         ".cpp", ".h", ".java", ".html", ".css", ".json",
                         ".yaml", ".toml", ".sql", ".sh", ".bat"):
                return self._extract_text_file(path)
            else:
                return self._extract_text_file(path)
        except Exception as e:
            logger.warning(f"Text extraction failed for {path}: {e}")
            return ""

    def _extract_pdf(self, path: str) -> str:
        """Extract text from PDF using available library."""
        # Try PyMuPDF (fitz) first, then pdfminer, then fallback
        try:
            import fitz
            doc = fitz.open(path)
            text = "\n".join(page.get_text() for page in doc)
            doc.close()
            if text.strip():
                return text
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"PyMuPDF failed: {e}")

        try:
            from pdfminer.high_level import extract_text as pdf_extract
            text = pdf_extract(path)
            if text.strip():
                return text
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pdfminer failed: {e}")

        # Last resort: try pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(path)
            text = "\n".join(page.extract_text() for page in reader.pages)
            return text
        except ImportError:
            pass
        except Exception as e:
            logger.debug(f"pypdf failed: {e}")

        return ""

    def _extract_docx(self, path: str) -> str:
        """Extract text from DOCX."""
        try:
            from docx import Document
            doc = Document(path)
            return "\n".join(p.text for p in doc.paragraphs)
        except ImportError:
            logger.debug("python-docx not available")
            return ""
        except Exception as e:
            logger.warning(f"DOCX extraction failed: {e}")
            return ""

    def _extract_text_file(self, path: str) -> str:
        """Read a plain text file with encoding detection."""
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(path, "r", encoding=enc) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.debug(f"Read failed with {enc}: {e}")
                continue
        return ""

    def _llm_analyze(self, result: DocumentResult) -> None:
        """Use LLM to analyze extracted text."""
        text = result.full_text
        # Truncate to avoid context limits
        if len(text) > 8000:
            text = text[:8000] + "\n\n[...truncated]"

        try:
            # Summary
            summary_prompt = (
                "Summarize the following document in 3-5 sentences:\n\n"
                f"{text[:4000]}"
            )
            summary = self._llm_ask(summary_prompt, max_tokens=200)
            if summary:
                result.summary = summary.strip()

            # Key points
            points_prompt = (
                "Extract the 3-5 most important key points from this document "
                "as a bullet list:\n\n" + text[:4000]
            )
            points_text = self._llm_ask(points_prompt, max_tokens=300)
            if points_text:
                result.key_points = [
                    p.strip().lstrip("-* ") for p in points_text.split("\n")
                    if p.strip().startswith(("-", "*")) or p.strip()
                ]
                if not result.key_points:
                    result.key_points = [points_text.strip()[:200]]

            # Topics
            topics_prompt = (
                "List the main topics or subject areas of this document "
                "as a comma-separated list:\n\n" + text[:3000]
            )
            topics_text = self._llm_ask(topics_prompt, max_tokens=100)
            if topics_text:
                result.topics = [
                    t.strip() for t in topics_text.split(",")
                    if t.strip()
                ]

            # Citations (for academic/technical docs)
            citations_prompt = (
                "Extract any citations or references from this document. "
                "List them one per line. If none, say 'None found':\n\n"
                + text[:4000]
            )
            citations_text = self._llm_ask(citations_prompt, max_tokens=300)
            if citations_text and "none found" not in citations_text.lower():
                result.citations = [
                    c.strip() for c in citations_text.split("\n")
                    if c.strip() and not c.lower().startswith("none")
                ]

        except Exception as e:
            logger.warning(f"LLM analysis failed: {e}")

    def answer_question(self, file_path: str, question: str) -> str:
        """Answer a question about a document using LLM."""
        if not self._llm:
            return "LLM not available for question answering."
        result = self.analyze(file_path)
        if result.error:
            return f"Error: {result.error}"
        if not result.full_text:
            return "Could not extract text from document."
        text = result.full_text[:6000]
        prompt = (
            f"Based on the following document, answer this question:\n"
            f"Question: {question}\n\n"
            f"Document:\n{text}\n\n"
            f"Answer concisely:"
        )
        return self._llm_ask(prompt, max_tokens=300) or "Could not generate answer."

    def generate_research_notes(self, file_path: str) -> str:
        """Generate research notes from a document for the Research Workspace."""
        result = self.analyze(file_path)
        if result.error:
            return f"Error: {result.error}"
        lines = [
            f"# Document Analysis: {os.path.basename(file_path)}",
            f"Type: {result.file_type} | Words: {result.word_count}",
            "",
        ]
        if result.summary:
            lines.append("## Summary")
            lines.append(result.summary)
            lines.append("")
        if result.key_points:
            lines.append("## Key Points")
            for p in result.key_points:
                lines.append(f"- {p}")
            lines.append("")
        if result.topics:
            lines.append("## Topics")
            lines.append(", ".join(result.topics))
            lines.append("")
        if result.citations:
            lines.append("## References")
            for c in result.citations:
                lines.append(f"- {c}")
        return "\n".join(lines)

    def _llm_ask(self, prompt: str, max_tokens: int = 200) -> str:
        """Send a prompt to the LLM and get the response."""
        if not self._llm:
            return ""
        try:
            response = ""
            for chunk in self._llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a document analysis assistant.",
            ):
                response += chunk
                if len(response) > max_tokens:
                    break
            return response.strip()
        except Exception as e:
            logger.debug(f"LLM ask failed: {e}")
            return ""

    def is_available(self) -> dict:
        """Check which extraction libraries are available."""
        available = {"text": True}
        for lib, name in [
            ("fitz", "PyMuPDF"),
            ("pdfminer", "pdfminer"),
            ("pypdf", "pypdf"),
            ("docx", "python-docx"),
        ]:
            try:
                __import__(lib)
                available[name] = True
            except ImportError:
                available[name] = False
        return available

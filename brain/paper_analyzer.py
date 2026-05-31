"""
brain/paper_analyzer.py
-------------------------
Research Paper Analyzer — specialized document analysis for academic papers.

Extracts abstract, methodology, results, limitations, citations, and
generates follow-up questions. Integrates findings with Research Workspace.

Usage:
    pa = PaperAnalyzer(llm=llm, document_intelligence=di)
    result = pa.analyze("path/to/paper.pdf")
    result.abstract, result.methodology, result.results, ...
"""

import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PaperAnalysis:
    path: str
    title: str = ""
    authors: str = ""
    abstract: str = ""
    methodology: str = ""
    results: str = ""
    limitations: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    key_contributions: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    summary: str = ""
    error: str = ""
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()


class PaperAnalyzer:
    """
    Academic paper analysis using DocumentIntelligence + LLM.

    Pure LLM-based — no ML models required.
    """

    def __init__(self, llm=None, document_intelligence=None, research_workspace=None):
        self._llm = llm
        self._di = document_intelligence
        self._rw = research_workspace

    def analyze(self, file_path: str) -> PaperAnalysis:
        """Analyze an academic paper file."""
        path = os.path.abspath(file_path)
        if not os.path.exists(path):
            return PaperAnalysis(path=path, error=f"File not found: {path}")

        # Extract text using DocumentIntelligence
        text = ""
        if self._di:
            result = self._di.analyze(path)
            text = result.full_text
            if result.error:
                return PaperAnalysis(path=path, error=result.error)

        if not text:
            # Fallback: try direct extraction
            try:
                import fitz
                doc = fitz.open(path)
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
            except Exception:
                pass

        if not text:
            return PaperAnalysis(
                path=path,
                error="Could not extract text from paper."
            )

        analysis = PaperAnalysis(path=path)

        if not self._llm:
            analysis.error = "LLM not available for paper analysis."
            analysis.summary = text[:500]
            return analysis

        # Truncate for context limits
        text_sample = text[:8000]

        try:
            # Extract title
            title_prompt = (
                "Extract the title of this academic paper. Return ONLY the title:\n\n"
                + text_sample[:2000]
            )
            title = self._ask(title_prompt, max_tokens=100)
            if title:
                analysis.title = title.strip().strip('"\'')[:200]

            # Extract authors
            authors_prompt = (
                "Extract the authors of this paper as a comma-separated list. "
                "Return ONLY the names:\n\n" + text_sample[:2000]
            )
            authors = self._ask(authors_prompt, max_tokens=150)
            if authors:
                analysis.authors = authors.strip()[:300]

            # Extract abstract
            abstract_prompt = (
                "Extract the abstract of this paper. Return ONLY the abstract text:\n\n"
                + text_sample
            )
            abstract = self._ask(abstract_prompt, max_tokens=300)
            if abstract:
                analysis.abstract = abstract.strip()[:1000]

            # Extract methodology
            method_prompt = (
                "Describe the methodology used in this paper in 2-3 sentences:\n\n"
                + text_sample
            )
            methodology = self._ask(method_prompt, max_tokens=200)
            if methodology:
                analysis.methodology = methodology.strip()[:500]

            # Extract results
            results_prompt = (
                "Summarize the key results and findings of this paper in 2-3 sentences:\n\n"
                + text_sample
            )
            results = self._ask(results_prompt, max_tokens=200)
            if results:
                analysis.results = results.strip()[:500]

            # Extract limitations
            limits_prompt = (
                "List the limitations of this paper as a bullet list. "
                "If none are mentioned, say 'Not explicitly stated':\n\n"
                + text_sample
            )
            limits_text = self._ask(limits_prompt, max_tokens=200)
            if limits_text and "not explicitly stated" not in limits_text.lower():
                analysis.limitations = [
                    l.strip().lstrip("-* ") for l in limits_text.split("\n")
                    if l.strip().startswith(("-", "*"))
                ]

            # Extract citations
            citations_prompt = (
                "Extract the key references/citations from this paper. "
                "List them one per line:\n\n" + text_sample
            )
            citations_text = self._ask(citations_prompt, max_tokens=300)
            if citations_text:
                analysis.citations = [
                    c.strip() for c in citations_text.split("\n")
                    if c.strip() and not c.lower().startswith("none")
                ][:10]

            # Key contributions
            contrib_prompt = (
                "List the key contributions of this paper as a bullet list:\n\n"
                + text_sample
            )
            contrib_text = self._ask(contrib_prompt, max_tokens=200)
            if contrib_text:
                analysis.key_contributions = [
                    c.strip().lstrip("-* ") for c in contrib_text.split("\n")
                    if c.strip().startswith(("-", "*"))
                ]

            # Follow-up questions
            questions_prompt = (
                "Generate 3 follow-up research questions that this paper suggests:\n\n"
                + text_sample
            )
            questions_text = self._ask(questions_prompt, max_tokens=200)
            if questions_text:
                analysis.follow_up_questions = [
                    q.strip().lstrip("123456789. ") for q in questions_text.split("\n")
                    if q.strip() and len(q.strip()) > 10
                ][:5]

            # Overall summary
            summary_prompt = (
                "Summarize this paper in 3-4 sentences for a researcher:\n\n"
                + text_sample[:4000]
            )
            summary = self._ask(summary_prompt, max_tokens=200)
            if summary:
                analysis.summary = summary.strip()

        except Exception as e:
            logger.warning(f"Paper analysis failed: {e}")
            analysis.error = str(e)

        return analysis

    def create_research_entry(self, file_path: str) -> str:
        """Generate formatted research notes for the Research Workspace."""
        analysis = self.analyze(file_path)
        if analysis.error and not analysis.summary:
            return f"Error analyzing paper: {analysis.error}"

        lines = [
            f"# Paper Analysis: {analysis.title or os.path.basename(file_path)}",
        ]
        if analysis.authors:
            lines.append(f"Authors: {analysis.authors}")
        lines.append("")
        if analysis.abstract:
            lines.append("## Abstract")
            lines.append(analysis.abstract)
            lines.append("")
        if analysis.methodology:
            lines.append("## Methodology")
            lines.append(analysis.methodology)
            lines.append("")
        if analysis.results:
            lines.append("## Results")
            lines.append(analysis.results)
            lines.append("")
        if analysis.key_contributions:
            lines.append("## Key Contributions")
            for c in analysis.key_contributions:
                lines.append(f"- {c}")
            lines.append("")
        if analysis.limitations:
            lines.append("## Limitations")
            for l in analysis.limitations:
                lines.append(f"- {l}")
            lines.append("")
        if analysis.follow_up_questions:
            lines.append("## Follow-up Questions")
            for q in analysis.follow_up_questions:
                lines.append(f"- {q}")
            lines.append("")
        if analysis.citations:
            lines.append("## References")
            for c in analysis.citations[:5]:
                lines.append(f"- {c}")
        if analysis.summary and analysis.summary not in "\n".join(lines):
            lines.append("")
            lines.append("## Summary")
            lines.append(analysis.summary)
        return "\n".join(lines)

    def _ask(self, prompt: str, max_tokens: int = 200) -> str:
        if not self._llm:
            return ""
        try:
            response = ""
            for chunk in self._llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a research paper analysis assistant.",
            ):
                response += chunk
                if len(response) > max_tokens:
                    break
            return response.strip()
        except Exception as e:
            logger.debug(f"Paper analysis LLM call failed: {e}")
            return ""

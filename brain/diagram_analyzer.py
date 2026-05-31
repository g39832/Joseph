"""
brain/diagram_analyzer.py
---------------------------
Diagram Analysis — specialized analysis for flowcharts, architecture diagrams,
circuit diagrams, system diagrams, and UML diagrams.

Builds on Vision Engine with diagram-specific prompts.

Usage:
    da = DiagramAnalyzer(vision_engine=ve, llm=llm)
    result = da.analyze("path/to/diagram.png")
    result.type  # flowchart, architecture, circuit, etc.
    result.explanation
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class DiagramAnalysis:
    path: str
    diagram_type: str = ""
    components: list[str] = field(default_factory=list)
    relationships: list[str] = field(default_factory=list)
    explanation: str = ""
    error: str = ""
    analyzed_at: str = ""

    def __post_init__(self):
        if not self.analyzed_at:
            self.analyzed_at = datetime.now().isoformat()


DIAGRAM_PROMPTS = {
    "flowchart": (
        "This is a flowchart diagram. Describe the flow, decision points, "
        "processes, and start/end states. List the main steps in order."
    ),
    "architecture": (
        "This is an architecture diagram. Describe the system components, "
        "their relationships, data flow, and layer structure."
    ),
    "circuit": (
        "This is a circuit diagram. Describe the components, connections, "
        "power sources, and signal flow."
    ),
    "uml": (
        "This is a UML diagram. Identify the type (class, sequence, activity, etc.), "
        "describe the elements and their relationships."
    ),
    "general": (
        "This is a diagram. Describe its structure, components, labels, "
        "relationships, and overall purpose."
    ),
}


class DiagramAnalyzer:
    """
    Specialized diagram analysis.

    Auto-detects diagram type or accepts a hint.
    """

    def __init__(self, vision_engine=None, llm=None):
        self._ve = vision_engine
        self._llm = llm

    def analyze(
        self, image_path: str, diagram_type: str = "",
    ) -> DiagramAnalysis:
        """Analyze a diagram image."""
        path = os.path.abspath(image_path)
        if not os.path.exists(path):
            return DiagramAnalysis(path=path, error=f"File not found: {path}")

        result = DiagramAnalysis(path=path)

        if not self._ve:
            result.error = "Vision engine not available."
            return result

        # Auto-detect diagram type if not specified
        if not diagram_type:
            diagram_type = self._detect_type(path)
        result.diagram_type = diagram_type

        # Get description
        prompt = DIAGRAM_PROMPTS.get(diagram_type, DIAGRAM_PROMPTS["general"])
        vision_result = self._ve.describe(path, prompt=prompt)

        if vision_result.error:
            result.error = vision_result.error
            return result

        result.explanation = vision_result.description

        # Extract components and relationships via LLM
        if self._llm and vision_result.description:
            self._extract_structure(result)

        return result

    def _detect_type(self, path: str) -> str:
        """Try to detect diagram type from visual analysis."""
        if not self._ve:
            return "general"
        result = self._ve.describe(
            path,
            prompt="What type of diagram is this? Answer with one word: "
                   "flowchart, architecture, circuit, uml, or general.",
        )
        if result.description:
            desc = result.description.lower().strip()
            for dtype in DIAGRAM_PROMPTS:
                if dtype in desc:
                    return dtype
        return "general"

    def _extract_structure(self, result: DiagramAnalysis) -> None:
        """Use LLM to extract components and relationships."""
        if not self._llm or not result.explanation:
            return
        try:
            desc = result.explanation[:3000]
            prompt = (
                f"From this diagram description, extract:\n"
                f"1. Key components (list each on a new line starting with '-')"
                f"\n2. Relationships between them (list each on a new line starting with '-')"
                f"\n\nDescription:\n{desc}"
            )
            response = ""
            for chunk in self._llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a diagram analysis assistant.",
            ):
                response += chunk

            components = []
            relationships = []
            current = None
            for line in response.split("\n"):
                l = line.strip()
                if "components" in l.lower() or "key components" in l.lower():
                    current = "components"
                    continue
                elif "relationships" in l.lower() or "relations" in l.lower():
                    current = "relationships"
                    continue
                if current == "components" and l.startswith("-"):
                    components.append(l.lstrip("-* ").strip())
                elif current == "relationships" and l.startswith("-"):
                    relationships.append(l.lstrip("-* ").strip())

            result.components = components[:10]
            result.relationships = relationships[:10]

        except Exception as e:
            logger.debug(f"Structure extraction failed: {e}")

    def explain(self, image_path: str) -> str:
        """Generate a plain-language explanation of a diagram."""
        analysis = self.analyze(image_path)
        if analysis.error:
            return f"Error: {analysis.error}"
        lines = [
            f"Diagram Type: {analysis.diagram_type.title()}",
        ]
        if analysis.components:
            lines.append(f"\nComponents ({len(analysis.components)}):")
            for c in analysis.components:
                lines.append(f"  - {c}")
        if analysis.relationships:
            lines.append(f"\nRelationships ({len(analysis.relationships)}):")
            for r in analysis.relationships:
                lines.append(f"  - {r}")
        if analysis.explanation:
            lines.append(f"\nExplanation:\n{analysis.explanation}")
        return "\n".join(lines)

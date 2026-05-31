"""
engineer/engineering_assistant.py
---------------------------------
Orchestrator that ties together all engineering assistant modules.
Provides unified reports combining codebase analysis, architecture mapping,
dependency analysis, bug detection, refactoring suggestions, and
documentation generation. Optionally enhances results with LLM analysis.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engineer.codebase_analyzer import CodebaseAnalyzer, AnalysisResult
from engineer.architecture_mapper import ArchitectureMapper, ArchitectureMap
from engineer.dependency_analyzer import DependencyAnalyzer, DependencyGraph
from engineer.bug_detector import BugDetector, BugFinding
from engineer.refactoring_suggester import RefactoringSuggester, RefactoringSuggestion
from engineer.doc_generator import DocGenerator
from engineer.project_summarizer import ProjectSummarizer

logger = logging.getLogger(__name__)


@dataclass
class EngineeringReport:
    """Comprehensive engineering report combining all analyses."""

    project_name: str = ""
    directory: str = ""
    timestamp: str = ""

    analysis_result: Optional[AnalysisResult] = None
    architecture_map: Optional[ArchitectureMap] = None
    dependency_graph: Optional[DependencyGraph] = None
    bug_findings: List[BugFinding] = field(default_factory=list)
    refactoring_suggestions: List[RefactoringSuggestion] = field(default_factory=list)

    llm_enhanced: bool = False
    errors: List[str] = field(default_factory=list)


class EngineeringAssistant:
    """
    Engineering Assistant — the main orchestrator for codebase analysis.

    Combines all sub-analyzers into a single interface. Provides unified
    reports and optionally uses an LLM to enhance analysis results with
    contextual insights and recommendations.

    Args:
        llm: Optional callable LLM interface. Should accept a prompt string
             and return a response string. If None, LLM enhancement is skipped.
    """

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm
        self._analyzer = CodebaseAnalyzer()
        self._arch_mapper = ArchitectureMapper()
        self._dep_analyzer = DependencyAnalyzer()
        self._bug_detector = BugDetector()
        self._refactoring_suggester = RefactoringSuggester()
        self._doc_generator = DocGenerator()
        self._summarizer = ProjectSummarizer()

    def analyze_project(self, directory: str) -> Dict[str, Any]:
        """
        Run a full multi-stage analysis of the project.

        Executes all analysis modules sequentially and returns a
        dictionary of all results.

        Args:
            directory: Path to the project root.

        Returns:
            Dict with keys: analysis, architecture, dependencies, bugs,
            refactorings, summary, enhanced (if LLM available).
        """
        root = Path(directory)
        if not root.is_dir():
            return {"error": f"Directory not found: {directory}"}

        logger.info(f"Starting full analysis of {directory}")
        results: Dict[str, Any] = {
            "project_name": root.name,
            "directory": str(root.resolve()),
            "timestamp": datetime.now().isoformat(),
        }

        try:
            results["analysis"] = self._analyzer.analyze(directory)
            logger.info("Codebase analysis complete")
        except Exception as e:
            logger.error(f"Codebase analysis failed: {e}")
            results["analysis"] = {"error": str(e)}

        try:
            results["architecture"] = self._arch_mapper.map_architecture(directory)
            logger.info("Architecture mapping complete")
        except Exception as e:
            logger.error(f"Architecture mapping failed: {e}")
            results["architecture"] = {"error": str(e)}

        try:
            results["dependencies"] = self._dep_analyzer.analyze_dependencies(directory)
            logger.info("Dependency analysis complete")
        except Exception as e:
            logger.error(f"Dependency analysis failed: {e}")
            results["dependencies"] = {"error": str(e)}

        try:
            results["bugs"] = self._bug_detector.scan_for_bugs(directory)
            logger.info(f"Bug detection complete: {len(results['bugs'])} findings")
        except Exception as e:
            logger.error(f"Bug detection failed: {e}")
            results["bugs"] = {"error": str(e)}

        try:
            results["refactorings"] = self._refactoring_suggester.suggest_refactorings(directory)
            logger.info(f"Refactoring analysis complete: {len(results['refactorings'])} suggestions")
        except Exception as e:
            logger.error(f"Refactoring analysis failed: {e}")
            results["refactorings"] = {"error": str(e)}

        try:
            results["summary"] = self._summarizer.quick_summary(directory)
            logger.info("Summary generation complete")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            results["summary"] = {"error": str(e)}

        # LLM enhancement
        if self.llm is not None:
            try:
                enhanced = self._enhance_with_llm(results, directory)
                results["enhanced"] = enhanced
                results["llm_enhanced"] = True
                logger.info("LLM enhancement complete")
            except Exception as e:
                logger.error(f"LLM enhancement failed: {e}")
                results["llm_enhanced"] = False

        return results

    def get_architecture_report(self, directory: str) -> str:
        """
        Generate a text report of the project's architecture.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted architecture report string.
        """
        root = Path(directory)
        arch = self._arch_mapper.map_architecture(directory)
        analysis = self._analyzer.analyze(directory)

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  ARCHITECTURE REPORT: {root.name}")
        lines.append("=" * 60)
        lines.append("")

        if analysis.frameworks:
            lines.append("Frameworks:")
            for fw in analysis.frameworks:
                lines.append(f"  • {fw}")
            lines.append("")

        if arch.packages:
            lines.append("Package Structure:")
            for pkg in arch.packages:
                lines.append(f"  • {pkg['name']}")
                if pkg.get("modules"):
                    for mod in pkg["modules"]:
                        lines.append(f"      └── {mod}.py")
                if pkg.get("subpackages"):
                    for sub in pkg["subpackages"]:
                        lines.append(f"      ├── {sub}/")
            lines.append("")

        if arch.classes:
            lines.append(f"Classes ({len(arch.classes)}):")
            for cls in arch.classes[:15]:
                lines.append(f"  • {cls['name']} ({cls['file']}:{cls['line']})")
            if len(arch.classes) > 15:
                lines.append(f"  ... and {len(arch.classes) - 15} more")
            lines.append("")

        if arch.functions:
            lines.append(f"Functions ({len(arch.functions)}):")
            for func in arch.functions[:15]:
                lines.append(f"  • {func['name']}() ({func['file']}:{func['line']})")
            if len(arch.functions) > 15:
                lines.append(f"  ... and {len(arch.functions) - 15} more")
            lines.append("")

        if arch.diagram:
            lines.append("Directory Structure:")
            lines.append("")
            for diagram_line in arch.diagram.split("\n"):
                lines.append(f"  {diagram_line}")

        if self.llm:
            try:
                prompt = (
                    f"Summarize the architecture of the project at {directory}. "
                    f"Frameworks: {analysis.frameworks}. "
                    f"Classes: {len(arch.classes)}, Functions: {len(arch.functions)}. "
                    f"Provide a concise architectural overview."
                )
                llm_response = self.llm(prompt) if callable(self.llm) else ""
                if llm_response:
                    lines.append("")
                    lines.append("LLM Architecture Insight:")
                    lines.append(llm_response)
            except Exception:
                pass

        return "\n".join(lines)

    def get_bug_report(self, directory: str) -> str:
        """
        Generate a text report of bugs and issues found.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted bug report string.
        """
        root = Path(directory)
        findings = self._bug_detector.scan_for_bugs(directory)

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  BUG REPORT: {root.name}")
        lines.append("=" * 60)
        lines.append("")

        if not findings:
            lines.append("No issues found. ✨")
            return "\n".join(lines)

        # Group by severity
        by_severity: Dict[str, List[BugFinding]] = {}
        for f in findings:
            by_severity.setdefault(f.severity, []).append(f)

        severity_order = ["critical", "error", "warning", "info"]
        severity_labels = {
            "critical": "Critical Issues",
            "error": "Errors",
            "warning": "Warnings",
            "info": "Info",
        }
        severity_icons = {
            "critical": "🔴",
            "error": "🟠",
            "warning": "🟡",
            "info": "🔵",
        }

        total = len(findings)
        lines.append(f"Total findings: {total}")
        lines.append("")

        for sev in severity_order:
            if sev in by_severity:
                icon = severity_icons.get(sev, "•")
                label = severity_labels.get(sev, sev.capitalize())
                items = by_severity[sev]
                lines.append(f"  {icon} {label} ({len(items)}):")
                lines.append("")
                for finding in items[:30]:
                    rel_path = self._shorten_path(finding.file)
                    lines.append(f"    [{finding.category}] {rel_path}:{finding.line}")
                    lines.append(f"    {finding.message}")
                    if finding.suggestion:
                        lines.append(f"    Suggestion: {finding.suggestion}")
                    lines.append("")
                if len(items) > 30:
                    lines.append(f"    ... and {len(items) - 30} more {sev} issues")
                lines.append("")

        if self.llm:
            try:
                bug_summary = "\n".join(
                    f"- [{f.severity}] {f.file}:{f.line} {f.message}"
                    for f in findings[:10]
                )
                prompt = (
                    f"The following bugs/issues were found in the project at {directory}. "
                    f"Please provide a brief triage and remediation strategy:\n{bug_summary}"
                )
                llm_response = self.llm(prompt) if callable(self.llm) else ""
                if llm_response:
                    lines.append("LLM Bug Analysis:")
                    lines.append(llm_response)
                    lines.append("")
            except Exception:
                pass

        return "\n".join(lines)

    def get_refactoring_report(self, directory: str) -> str:
        """
        Generate a text report of refactoring suggestions.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted refactoring report string.
        """
        root = Path(directory)
        suggestions = self._refactoring_suggester.suggest_refactorings(directory)

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  REFACTORING REPORT: {root.name}")
        lines.append("=" * 60)
        lines.append("")

        if not suggestions:
            lines.append("No refactoring suggestions. Code looks clean! ✨")
            return "\n".join(lines)

        by_effort: Dict[str, List[RefactoringSuggestion]] = {}
        for s in suggestions:
            by_effort.setdefault(s.effort, []).append(s)

        effort_order = ["easy", "medium", "hard"]
        effort_labels = {
            "easy": "Easy Wins",
            "medium": "Medium Effort",
            "hard": "Significant Refactoring",
        }

        total = len(suggestions)
        lines.append(f"Total suggestions: {total}")
        lines.append("")

        for eff in effort_order:
            if eff in by_effort:
                label = effort_labels.get(eff, eff.capitalize())
                items = by_effort[eff]
                lines.append(f"  • {label} ({len(items)}):")
                lines.append("")
                for suggestion in items[:20]:
                    rel_path = self._shorten_path(suggestion.file)
                    lines.append(f"    [{suggestion.severity}] {rel_path}:{suggestion.line}")
                    lines.append(f"    {suggestion.issue}")
                    if suggestion.suggested_code:
                        lines.append(f"    → {suggestion.suggested_code[:120]}")
                    lines.append("")
                if len(items) > 20:
                    lines.append(f"    ... and {len(items) - 20} more suggestions")
                lines.append("")

        if self.llm:
            try:
                ref_summary = "\n".join(
                    f"- [{s.effort}] {s.file}:{s.line} {s.issue}"
                    for s in suggestions[:10]
                )
                prompt = (
                    f"The following refactoring opportunities were found in {directory}. "
                    f"Please prioritize and suggest an order of execution:\n{ref_summary}"
                )
                llm_response = self.llm(prompt) if callable(self.llm) else ""
                if llm_response:
                    lines.append("LLM Refactoring Strategy:")
                    lines.append(llm_response)
                    lines.append("")
            except Exception:
                pass

        return "\n".join(lines)

    def get_dependency_report(self, directory: str) -> str:
        """
        Generate a text report of project dependencies.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted dependency report string.
        """
        root = Path(directory)
        deps = self._dep_analyzer.analyze_dependencies(directory)

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  DEPENDENCY REPORT: {root.name}")
        lines.append("=" * 60)
        lines.append("")

        lines.append(f"Modules analyzed: {len(deps.nodes)}")
        lines.append(f"Internal edges:   {len(deps.edges)}")
        lines.append(f"External deps:    {len(deps.externals)}")
        lines.append(f"Circular deps:    {len(deps.circulars)}")
        lines.append("")

        if deps.externals:
            lines.append("External Dependencies:")
            for ext in sorted(deps.externals):
                lines.append(f"  • {ext}")
            lines.append("")

        if deps.circulars:
            lines.append("Circular Dependencies (!):")
            for cycle in deps.circulars:
                cycle_str = " → ".join(cycle)
                lines.append(f"  ⚠ {cycle_str}")
            lines.append("")
            lines.append("Consider refactoring to break these cycles.")
            lines.append("")

        if deps.nodes:
            lines.append("Modules with most dependencies:")
            sorted_modules = sorted(
                deps.nodes,
                key=lambda m: len(deps.adjacency.get(m, [])),
                reverse=True,
            )
            for module in sorted_modules[:10]:
                import_count = len(deps.adjacency.get(module, []))
                lines.append(f"  • {module} ({import_count} imports)")
            if len(sorted_modules) > 10:
                lines.append(f"  ... and {len(sorted_modules) - 10} more modules")
            lines.append("")

        if self.llm:
            try:
                circular_summary = ""
                if deps.circulars:
                    circular_summary = "\nCircular dependencies:\n" + "\n".join(
                        f"  {' → '.join(c)}" for c in deps.circulars
                    )
                prompt = (
                    f"Analyze the dependency graph for the project at {directory}. "
                    f"External dependencies: {', '.join(deps.externals[:15])}. "
                    f"Circular dependencies found: {len(deps.circulars)}."
                    f"{circular_summary}"
                    f"Provide dependency management recommendations."
                )
                llm_response = self.llm(prompt) if callable(self.llm) else ""
                if llm_response:
                    lines.append("LLM Dependency Analysis:")
                    lines.append(llm_response)
                    lines.append("")
            except Exception:
                pass

        return "\n".join(lines)

    def get_full_report(self, directory: str) -> str:
        """
        Generate a comprehensive report combining all analyses.

        Args:
            directory: Path to the project root.

        Returns:
            Combined formatted report string.
        """
        sections: List[str] = []
        sections.append(self._summarizer.quick_summary(directory))
        sections.append("")
        sections.append(self.get_architecture_report(directory))
        sections.append("")
        sections.append(self.get_dependency_report(directory))
        sections.append("")
        sections.append(self.get_bug_report(directory))
        sections.append("")
        sections.append(self.get_refactoring_report(directory))
        return "\n".join(sections)

    def get_project_summary(self, directory: str) -> str:
        """
        Get a quick project summary.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted summary string.
        """
        return self._summarizer.quick_summary(directory)

    def _enhance_with_llm(
        self, results: Dict[str, Any], directory: str
    ) -> Dict[str, str]:
        """
        Enhance analysis results with LLM-generated insights.

        Args:
            results: The analysis results dict.
            directory: Path to the project root.

        Returns:
            Dict of enhanced text sections.
        """
        if not callable(self.llm):
            return {}

        enhanced: Dict[str, str] = {}

        # Generate overall project insight
        analysis = results.get("analysis", {})
        if isinstance(analysis, dict) and "error" not in analysis:
            total_files = getattr(analysis, "total_files", 0) if not isinstance(analysis, dict) else analysis.get("total_files", 0)
            total_lines = getattr(analysis, "total_lines", 0) if not isinstance(analysis, dict) else analysis.get("total_lines", 0)
            frameworks = getattr(analysis, "frameworks", []) if not isinstance(analysis, dict) else analysis.get("frameworks", [])

            prompt = (
                f"Provide a brief 2-3 sentence overview of the project at {directory}. "
                f"It has {total_files} files and {total_lines} lines of code. "
                f"{'Frameworks: ' + ', '.join(frameworks) if frameworks else ''}"
            )
            try:
                enhanced["overview"] = self.llm(prompt)
            except Exception:
                pass

        # Generate architecture insight
        arch = results.get("architecture", {})
        if isinstance(arch, dict) and "error" not in arch:
            classes = getattr(arch, "classes", []) if not isinstance(arch, dict) else arch.get("classes", [])
            functions = getattr(arch, "functions", []) if not isinstance(arch, dict) else arch.get("functions", [])
            prompt = (
                f"Provide architectural observations for the project at {directory}. "
                f"Found {len(classes)} classes and {len(functions)} functions. "
                f"Comment on design patterns, modularity, and code organization."
            )
            try:
                enhanced["architecture"] = self.llm(prompt)
            except Exception:
                pass

        return enhanced

    def _shorten_path(self, filepath: str, max_parts: int = 3) -> str:
        """Shorten a file path for display by showing only the last parts."""
        path = Path(filepath)
        parts = path.parts
        if len(parts) <= max_parts:
            return str(path)
        return ".../" + "/".join(parts[-max_parts:])

    def __repr__(self) -> str:
        llm_status = "with LLM" if self.llm else "no LLM"
        return f"EngineeringAssistant({llm_status})"

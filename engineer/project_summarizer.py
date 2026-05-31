"""
engineer/project_summarizer.py
------------------------------
Creates both quick and deep summaries of projects. Provides comparative
analysis between two project directories.
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engineer.codebase_analyzer import CodebaseAnalyzer
from engineer.architecture_mapper import ArchitectureMapper

logger = logging.getLogger(__name__)


EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv",
    "venv", "env", ".tox", ".eggs", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


class ProjectSummarizer:
    """Generates project summaries at various levels of detail."""

    def __init__(self) -> None:
        self._analyzer = CodebaseAnalyzer()
        self._arch_mapper = ArchitectureMapper()

    def summarize(self, directory: str, depth: str = "quick") -> str:
        """
        Generate a project summary at the specified depth.

        Args:
            directory: Path to the project root.
            depth: Either 'quick' or 'deep'.

        Returns:
            Formatted summary string.
        """
        if depth == "deep":
            return self.deep_summary(directory)
        return self.quick_summary(directory)

    def quick_summary(self, directory: str) -> str:
        """
        Generate a quick overview of the project.

        Includes file count, languages, total size, and entry points.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted summary string.
        """
        root = Path(directory)
        if not root.is_dir():
            return f"Error: Not a valid directory: {directory}"

        result = self._analyzer.analyze(directory)
        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  PROJECT SUMMARY: {root.name}")
        lines.append("=" * 60)
        lines.append("")

        # Basic info
        lines.append(f"  Location:     {root.resolve()}")
        lines.append(f"  Total Files:  {result.total_files:,}")
        lines.append(f"  Total Lines:  {result.total_lines:,}")
        lines.append(f"  Analyzed:     {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append("")

        # Languages
        if result.languages:
            lines.append("  ── Languages ──")
            total = sum(result.languages.values())
            for lang, count in sorted(
                result.languages.items(), key=lambda x: x[1], reverse=True
            )[:8]:
                pct = count / total * 100 if total > 0 else 0
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"    {lang:20s} {count:8,} lines ({pct:5.1f}%) {bar}")
            if len(result.languages) > 8:
                lines.append(f"    ... and {len(result.languages) - 8} more languages")
            lines.append("")

        # Frameworks
        if result.frameworks:
            lines.append("  ── Frameworks ──")
            for fw in result.frameworks:
                lines.append(f"    • {fw}")
            lines.append("")

        # Entry points
        if result.entry_points:
            lines.append("  ── Entry Points ──")
            for ep in result.entry_points:
                lines.append(f"    • {ep}")
            lines.append("")

        # File types
        if result.file_types:
            lines.append("  ── File Types ──")
            for ext, count in sorted(
                result.file_types.items(), key=lambda x: x[1], reverse=True
            )[:10]:
                ext_name = ext if ext != "(no extension)" else "no ext"
                lines.append(f"    {ext_name:15s} {count:5,} files")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def deep_summary(self, directory: str) -> str:
        """
        Generate a detailed project summary with architecture breakdown.

        Args:
            directory: Path to the project root.

        Returns:
            Formatted detailed summary string.
        """
        root = Path(directory)
        if not root.is_dir():
            return f"Error: Not a valid directory: {directory}"

        result = self._analyzer.analyze(directory)
        arch = self._arch_mapper.map_architecture(directory)

        lines: List[str] = []
        lines.append("=" * 60)
        lines.append(f"  DEEP PROJECT ANALYSIS: {root.name}")
        lines.append("=" * 60)
        lines.append("")

        # Basic info
        lines.append(f"  Location:       {root.resolve()}")
        lines.append(f"  Total Files:    {result.total_files:,}")
        lines.append(f"  Total Lines:    {result.total_lines:,}")
        lines.append(f"  Python Files:   {result.file_types.get('.py', 0):,}")
        lines.append(f"  Analyzed:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")

        # Language breakdown
        if result.languages:
            lines.append("  ── Language Breakdown ──")
            total = sum(result.languages.values())
            max_lang_len = max(len(l) for l in result.languages.keys()) + 2
            for lang, count in sorted(
                result.languages.items(), key=lambda x: x[1], reverse=True
            ):
                pct = count / total * 100 if total > 0 else 0
                bar_count = int(pct / 2)
                bar = "█" * bar_count + "░" * (50 - bar_count)
                lines.append(f"    {lang:{max_lang_len}s} {count:8,} ({pct:5.1f}%) {bar}")
            lines.append("")

        # Frameworks
        if result.frameworks:
            lines.append("  ── Detected Frameworks ──")
            for fw in result.frameworks:
                lines.append(f"    • {fw}")
            lines.append("")

        # Package structure
        if arch.packages:
            lines.append("  ── Package Structure ──")
            for pkg in arch.packages:
                lines.append(f"    • {pkg['name']}")
                if pkg.get("modules"):
                    for mod in pkg["modules"]:
                        lines.append(f"        └── {mod}.py")
                if pkg.get("subpackages"):
                    for sub in pkg["subpackages"]:
                        lines.append(f"        ├── {sub}/")
                lines.append("")

        # Classes and functions
        if arch.classes:
            lines.append(f"  ── Classes ({len(arch.classes)}) ──")
            for cls in arch.classes[:20]:
                methods = cls.get("methods", [])
                method_str = f" ({len(methods)} methods)" if methods else ""
                lines.append(f"    • {cls['name']}{method_str} → {cls['file']}:{cls['line']}")
            if len(arch.classes) > 20:
                lines.append(f"    ... and {len(arch.classes) - 20} more classes")
            lines.append("")

        if arch.functions:
            lines.append(f"  ── Functions ({len(arch.functions)}) ──")
            for func in arch.functions[:20]:
                lines.append(f"    • {func['name']}() → {func['file']}:{func['line']}")
            if len(arch.functions) > 20:
                lines.append(f"    ... and {len(arch.functions) - 20} more functions")
            lines.append("")

        # Architecture diagram
        if arch.diagram:
            lines.append("  ── Project Structure ──")
            lines.append("")
            for diagram_line in arch.diagram.split("\n"):
                lines.append(f"    {diagram_line}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def compare_projects(self, dir1: str, dir2: str) -> str:
        """
        Compare two projects side by side.

        Args:
            dir1: Path to the first project.
            dir2: Path to the second project.

        Returns:
            Formatted comparison string.
        """
        root1 = Path(dir1)
        root2 = Path(dir2)

        if not root1.is_dir() or not root2.is_dir():
            missing = []
            if not root1.is_dir():
                missing.append(dir1)
            if not root2.is_dir():
                missing.append(dir2)
            return f"Error: Invalid directories: {', '.join(missing)}"

        result1 = self._analyzer.analyze(dir1)
        result2 = self._analyzer.analyze(dir2)

        lines: List[str] = []
        lines.append("=" * 80)
        lines.append(f"  PROJECT COMPARISON")
        lines.append("=" * 80)
        lines.append("")

        name1 = root1.name
        name2 = root2.name
        max_name_len = max(len(name1), len(name2)) + 2

        # Basic metrics
        metrics: List[Tuple[str, Any, Any, str]] = [
            ("Total Files", result1.total_files, result2.total_files, "{:,}"),
            ("Total Lines", result1.total_lines, result2.total_lines, "{:,}"),
            ("Frameworks", ", ".join(result1.frameworks) if result1.frameworks else "None",
                           ", ".join(result2.frameworks) if result2.frameworks else "None", "{}"),
            ("Entry Points", ", ".join(result1.entry_points) if result1.entry_points else "None",
                             ", ".join(result2.entry_points) if result2.entry_points else "None", "{}"),
        ]

        lines.append(f"  {'Metric':30s} {name1:{max_name_len}s} {name2}")
        lines.append(f"  {'─' * 30} {'─' * max_name_len} {'─' * max_name_len}")
        for metric, v1, v2, fmt in metrics:
            str1 = fmt.format(v1)
            str2 = fmt.format(v2)
            lines.append(f"  {metric:30s} {str1:{max_name_len}s} {str2}")
        lines.append("")

        # Language comparison
        all_langs = set(list(result1.languages.keys()) + list(result2.languages.keys()))
        if all_langs:
            lines.append(f"  {'Language':25s} {name1:{max_name_len}s} {name2}")
            lines.append(f"  {'─' * 25} {'─' * max_name_len} {'─' * max_name_len}")
            for lang in sorted(all_langs):
                v1 = result1.languages.get(lang, 0)
                v2 = result2.languages.get(lang, 0)
                lines.append(f"  {lang:25s} {v1:>{max_name_len},} {v2:>,}")
            lines.append("")

        # File type comparison
        all_types = set(list(result1.file_types.keys()) + list(result2.file_types.keys()))
        if all_types:
            lines.append(f"  {'File Type':25s} {name1:{max_name_len}s} {name2}")
            lines.append(f"  {'─' * 25} {'─' * max_name_len} {'─' * max_name_len}")
            for ext in sorted(all_types):
                v1 = result1.file_types.get(ext, 0)
                v2 = result2.file_types.get(ext, 0)
                ext_label = ext if ext != "(no extension)" else "no ext"
                lines.append(f"  {ext_label:25s} {v1:>{max_name_len},} {v2:>,}")
            lines.append("")

        # Size difference
        diff_files = result1.total_files - result2.total_files
        diff_lines = result1.total_lines - result2.total_lines
        lines.append("  ── Size Difference ──")
        if diff_files > 0:
            lines.append(f"    {name1} has {diff_files:,} more files")
        elif diff_files < 0:
            lines.append(f"    {name2} has {abs(diff_files):,} more files")
        else:
            lines.append("    Same number of files")

        if diff_lines > 0:
            lines.append(f"    {name1} has {diff_lines:,} more lines of code")
        elif diff_lines < 0:
            lines.append(f"    {name2} has {abs(diff_lines):,} more lines of code")
        else:
            lines.append("    Same number of lines")
        lines.append("")

        lines.append("=" * 80)
        return "\n".join(lines)

    def __repr__(self) -> str:
        return "ProjectSummarizer()"

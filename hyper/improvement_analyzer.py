"""
hyper/improvement_analyzer.py
-----------------------------
Static self-improvement reporting.

This analyzer never modifies code. It only reports opportunities and likely
bottlenecks so a human can approve any follow-up work.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ImprovementFinding:
    issue: str
    location: str
    suggested_fix: str
    estimated_improvement: str
    priority: str = "medium"


class ImprovementAnalyzer:
    """Finds likely bottlenecks and duplicate logic."""

    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else Path.cwd()

    def analyze_repository(self) -> list[dict]:
        findings: list[ImprovementFinding] = []
        for path in self._python_files():
            findings.extend(self._analyze_file(path))
        return [asdict(f) for f in findings]

    def _python_files(self) -> list[Path]:
        files = []
        for path in self.root.rglob("*.py"):
            if any(part in {"venv", "__pycache__", ".git"} for part in path.parts):
                continue
            files.append(path)
        return files

    def _analyze_file(self, path: Path) -> list[ImprovementFinding]:
        findings: list[ImprovementFinding] = []
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except Exception:
            return findings

        findings.extend(self._detect_duplicate_defs(path, tree))
        findings.extend(self._detect_repeated_sql(path, tree))
        findings.extend(self._detect_broad_except(path, tree))
        return findings

    def _detect_duplicate_defs(self, path: Path, tree: ast.AST) -> list[ImprovementFinding]:
        names = {}
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.setdefault(node.name, []).append(node.lineno)
        for name, lines in names.items():
            if len(lines) > 1:
                findings.append(
                    ImprovementFinding(
                        issue=f"Duplicate function definition: {name}",
                        location=f"{path}:{lines[1]}",
                        suggested_fix="Consolidate the repeated implementation and keep a single source of truth.",
                        estimated_improvement="Lower maintenance risk and reduce confusion around dispatch paths.",
                        priority="high",
                    )
                )
        return findings

    def _detect_repeated_sql(self, path: Path, tree: ast.AST) -> list[ImprovementFinding]:
        sql_literals = {}
        findings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                text = node.value.lower()
                if "select" in text or "insert into" in text or "update " in text:
                    sql_literals.setdefault(text.strip(), []).append(node.lineno)
        for query, lines in sql_literals.items():
            if len(lines) >= 3:
                findings.append(
                    ImprovementFinding(
                        issue="Repeated SQL query literal",
                        location=f"{path}:{lines[0]}",
                        suggested_fix="Wrap repeated queries in helper methods or cached accessors.",
                        estimated_improvement="Potentially 10-25% fewer redundant DB round trips on hot paths.",
                        priority="medium",
                    )
                )
        return findings

    def _detect_broad_except(self, path: Path, tree: ast.AST) -> list[ImprovementFinding]:
        findings = []
        broad_count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                broad_count += 1
        if broad_count >= 3:
            findings.append(
                ImprovementFinding(
                    issue="Heavy use of bare except blocks",
                    location=str(path),
                    suggested_fix="Narrow exception scopes and record the failure mode in logs.",
                    estimated_improvement="Better debuggability and fewer silent failures.",
                    priority="medium",
                )
            )
        return findings

    def summarize(self) -> dict:
        findings = self.analyze_repository()
        return {
            "finding_count": len(findings),
            "high_priority": sum(1 for f in findings if f["priority"] == "high"),
            "medium_priority": sum(1 for f in findings if f["priority"] == "medium"),
            "low_priority": sum(1 for f in findings if f["priority"] == "low"),
            "findings": findings[:50],
        }

    def __repr__(self) -> str:
        report = self.summarize()
        return f"ImprovementAnalyzer(findings={report['finding_count']})"

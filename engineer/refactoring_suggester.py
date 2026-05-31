"""
engineer/refactoring_suggester.py
---------------------------------
Analyzes Python code for refactoring opportunities. Detects long functions,
high cyclomatic complexity, duplicate code blocks, missing docstrings,
and PEP8 naming convention violations.
"""

import ast
import logging
import re
import tokenize
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RefactoringSuggestion:
    """A suggestion for refactoring code."""

    file: str
    line: int
    issue: str
    severity: str  # info, warning, suggestion
    current_code: str = ""
    suggested_code: str = ""
    effort: str = "medium"  # easy, medium, hard


EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv",
    "venv", "env", ".tox", ".eggs", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}

# PEP8 naming patterns
PEP8_PATTERNS = {
    "module": re.compile(r'^[a-z][a-z0-9_]*$'),
    "class": re.compile(r'^[A-Z][a-zA-Z0-9]*$'),
    "function": re.compile(r'^[a-z_][a-z0-9_]*$'),
    "method": re.compile(r'^[a-z_][a-z0-9_]*$'),
    "variable": re.compile(r'^[a-z_][a-z0-9_]*$'),
    "constant": re.compile(r'^[A-Z][A-Z0-9_]*$'),
}


class RefactoringSuggester:
    """Analyzes code and suggests refactoring improvements."""

    def suggest_refactorings(self, directory: str) -> List[RefactoringSuggestion]:
        """
        Analyze an entire project for refactoring opportunities.

        Args:
            directory: Path to the project root.

        Returns:
            List of RefactoringSuggestion instances.
        """
        all_suggestions: List[RefactoringSuggestion] = []
        root = Path(directory)

        if not root.is_dir():
            logger.warning(f"Not a valid directory: {directory}")
            return all_suggestions

        try:
            for py_file in sorted(root.rglob("*.py")):
                if self._should_exclude(py_file):
                    continue
                try:
                    suggestions = self.suggest_for_file(str(py_file))
                    all_suggestions.extend(suggestions)
                except Exception as e:
                    logger.error(f"Error analyzing {py_file}: {e}")

            # Cross-file analyses
            all_suggestions.extend(
                self.check_missing_docstrings(directory)
            )
            all_suggestions.extend(
                self.check_naming_conventions(directory)
            )
            all_suggestions.extend(
                self.check_duplicate_code(directory)
            )
        except Exception as e:
            logger.error(f"Refactoring analysis failed: {e}", exc_info=True)

        return all_suggestions

    def suggest_for_file(self, filepath: str) -> List[RefactoringSuggestion]:
        """
        Analyze a single file for refactoring opportunities.

        Args:
            filepath: Path to the file to analyze.

        Returns:
            List of RefactoringSuggestion instances.
        """
        suggestions: List[RefactoringSuggestion] = []

        try:
            suggestions.extend(self.check_long_functions(filepath))
            suggestions.extend(self.check_complex_functions(filepath))
        except Exception as e:
            logger.error(f"Error in file analysis for {filepath}: {e}")

        return suggestions

    def check_long_functions(self, filepath: str) -> List[RefactoringSuggestion]:
        """
        Find functions that exceed the recommended length (50 lines).

        Args:
            filepath: Path to the file to analyze.

        Returns:
            List of RefactoringSuggestion for long functions.
        """
        path = Path(filepath)
        suggestions: List[RefactoringSuggestion] = []

        if not path.is_file():
            return suggestions

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, Exception) as e:
            logger.debug(f"Cannot parse {filepath}: {e}")
            return suggestions

        lines = source.splitlines()
        res_path = str(path.resolve())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Calculate function line count
                if hasattr(node, "end_lineno") and node.end_lineno:
                    func_lines = node.end_lineno - node.lineno + 1
                else:
                    func_lines = self._count_node_lines(node, lines)

                if func_lines > 50:
                    # Extract the function source for display
                    func_source = self._extract_source_snippet(lines, node)

                    suggestions.append(
                        RefactoringSuggestion(
                            file=res_path,
                            line=node.lineno or 0,
                            issue=f"Long function '{node.name}': {func_lines} lines (max 50)",
                            severity="warning",
                            current_code=func_source,
                            suggested_code=f"Consider breaking '{node.name}' into smaller functions",
                            effort="hard" if func_lines > 100 else "medium",
                        )
                    )

        return suggestions

    def check_complex_functions(self, filepath: str) -> List[RefactoringSuggestion]:
        """
        Find functions with high cyclomatic complexity.

        Cyclomatic complexity = 1 + number of decision points:
        if, elif, for, while, and, or, except, with, assert.

        Args:
            filepath: Path to the file to analyze.

        Returns:
            List of RefactoringSuggestion for complex functions.
        """
        path = Path(filepath)
        suggestions: List[RefactoringSuggestion] = []

        if not path.is_file():
            return suggestions

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, Exception) as e:
            logger.debug(f"Cannot parse {filepath}: {e}")
            return suggestions

        lines = source.splitlines()
        res_path = str(path.resolve())

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                complexity = self._calculate_complexity(node)

                if complexity >= 10:
                    func_source = self._extract_source_snippet(lines, node)

                    effort = "medium"
                    if complexity >= 20:
                        effort = "hard"

                    suggestions.append(
                        RefactoringSuggestion(
                            file=res_path,
                            line=node.lineno or 0,
                            issue=f"Complex function '{node.name}': cyclomatic complexity {complexity} (recommended <= 10)",
                            severity="warning",
                            current_code=func_source,
                            suggested_code=f"Reduce complexity by extracting conditionals into helper functions or using early returns",
                            effort=effort,
                        )
                    )

        return suggestions

    def check_duplicate_code(self, directory: str) -> List[RefactoringSuggestion]:
        """
        Find similar code blocks across the project (basic clone detection).

        Uses normalized line fingerprints to find function bodies that
        share a high proportion of identical lines.

        Args:
            directory: Path to the project root.

        Returns:
            List of RefactoringSuggestion for duplicate code.
        """
        suggestions: List[RefactoringSuggestion] = []
        root = Path(directory)

        # Collect all function bodies with their normalized content
        function_bodies: List[Dict[str, Any]] = []

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            rel_path = str(py_file.resolve())

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    body_lines = []
                    for stmt in node.body:
                        try:
                            start = stmt.lineno or 0
                            end = getattr(stmt, "end_lineno", start) or start
                            body_lines.append(
                                ast.unparse(stmt) if hasattr(ast, "unparse") else ""
                            )
                        except Exception:
                            continue

                    normalized = "\n".join(body_lines)
                    # Normalize whitespace for comparison
                    normalized = re.sub(r'\s+', ' ', normalized).strip()

                    if len(normalized) > 50:  # Only consider non-trivial bodies
                        function_bodies.append({
                            "name": node.name,
                            "file": rel_path,
                            "line": node.lineno or 0,
                            "normalized": normalized,
                            "length": len(normalized),
                        })

        # Compare function bodies for similarity
        threshold = 0.8  # 80% similarity threshold
        compared: Set[Tuple[int, int]] = set()

        for i, f1 in enumerate(function_bodies):
            for j, f2 in enumerate(function_bodies):
                if i >= j:
                    continue
                key = (i, j)
                if key in compared:
                    continue
                compared.add(key)

                if f1["file"] == f2["file"]:
                    continue  # Skip functions in the same file

                similarity = self._compute_similarity(
                    f1["normalized"], f2["normalized"]
                )

                if similarity >= threshold:
                    n1 = f1["name"]
                    f1_path = f1["file"]
                    l1 = f1["line"]
                    n2 = f2["name"]
                    f2_path = f2["file"]
                    l2 = f2["line"]
                    suggestions.append(
                        RefactoringSuggestion(
                            file=f1_path,
                            line=l1,
                            issue=f"Duplicate code: '{n1}' is {similarity:.0%} similar to '{n2}' in {f2_path}:{l2}",
                            severity="warning",
                            current_code=f"Function '{n1}' at {f1_path}:{l1}",
                            suggested_code="Consider extracting the common logic into a shared utility function",
                            effort="medium",
                        )
                    )

        return suggestions

    def check_missing_docstrings(self, directory: str) -> List[RefactoringSuggestion]:
        """
        Find public functions and classes without docstrings.

        Args:
            directory: Path to the project root.

        Returns:
            List of RefactoringSuggestion for missing docstrings.
        """
        suggestions: List[RefactoringSuggestion] = []
        root = Path(directory)

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            rel_path = str(py_file.resolve())

            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private methods (starting with _)
                    if node.name.startswith("_"):
                        continue
                    # Skip dunder methods
                    if node.name.startswith("__") and node.name.endswith("__"):
                        continue
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        suggestions.append(
                            RefactoringSuggestion(
                                file=rel_path,
                                line=node.lineno or 0,
                                issue=f"Missing docstring for function '{node.name}'",
                                severity="info",
                                current_code=f"def {node.name}(...):",
                                suggested_code=f"Add a docstring describing what '{node.name}' does, its arguments, and return value",
                                effort="easy",
                            )
                        )

                elif isinstance(node, ast.ClassDef):
                    docstring = ast.get_docstring(node)
                    if not docstring:
                        suggestions.append(
                            RefactoringSuggestion(
                                file=rel_path,
                                line=node.lineno or 0,
                                issue=f"Missing docstring for class '{node.name}'",
                                severity="info",
                                current_code=f"class {node.name}:",
                                suggested_code=f"Add a docstring describing the class's purpose and usage",
                                effort="easy",
                            )
                        )

        return suggestions

    def check_naming_conventions(self, directory: str) -> List[RefactoringSuggestion]:
        """
        Check for PEP8 naming convention violations.

        Args:
            directory: Path to the project root.

        Returns:
            List of RefactoringSuggestion for naming violations.
        """
        suggestions: List[RefactoringSuggestion] = []
        root = Path(directory)

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            rel_path = str(py_file.resolve())

            for node in ast.walk(tree):
                # Check class names
                if isinstance(node, ast.ClassDef):
                    if not PEP8_PATTERNS["class"].match(node.name):
                        suggestions.append(
                            RefactoringSuggestion(
                                file=rel_path,
                                line=node.lineno or 0,
                                issue=f"Class name '{node.name}' does not follow PEP8 (should be PascalCase)",
                                severity="info",
                                current_code=f"class {node.name}:",
                                suggested_code=self._suggest_pascal_case(node.name),
                                effort="easy",
                            )
                        )

                # Check function names (including methods)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name.startswith("__") and node.name.endswith("__"):
                        continue  # Skip dunders
                    if node.name.startswith("_"):
                        continue  # Skip private methods (can be lowercase)
                    if not PEP8_PATTERNS["function"].match(node.name):
                        suggestions.append(
                            RefactoringSuggestion(
                                file=rel_path,
                                line=node.lineno or 0,
                                issue=f"Function name '{node.name}' does not follow PEP8 (should be snake_case)",
                                severity="info",
                                current_code=f"def {node.name}(...):",
                                suggested_code=self._suggest_snake_case(node.name),
                                effort="easy",
                            )
                        )

        return suggestions

    def _calculate_complexity(self, node: ast.AST) -> int:
        """
        Calculate cyclomatic complexity of a function.

        Args:
            node: The AST node of the function.

        Returns:
            Integer complexity score.
        """
        complexity = 1  # Base complexity

        for child in ast.walk(node):
            if isinstance(child, ast.If):
                complexity += 1
            elif isinstance(child, ast.While):
                complexity += 1
            elif isinstance(child, ast.For):
                complexity += 1
            elif isinstance(child, ast.AsyncFor):
                complexity += 1
            elif isinstance(child, ast.ExceptHandler):
                complexity += 1
            elif isinstance(child, ast.With):
                complexity += 1
            elif isinstance(child, ast.AsyncWith):
                complexity += 1
            elif isinstance(child, ast.Assert):
                complexity += 1
            elif isinstance(child, ast.BoolOp):
                # Each 'and'/'or' adds complexity
                complexity += len(child.values) - 1

        return complexity

    def _count_node_lines(
        self, node: ast.AST, lines: List[str]
    ) -> int:
        """Count the number of lines a node spans."""
        if hasattr(node, "end_lineno") and node.end_lineno:
            return node.end_lineno - node.lineno + 1
        # Fallback: count lines of source
        start = node.lineno or 0
        end = start
        for child in ast.walk(node):
            if hasattr(child, "lineno") and child.lineno:
                end = max(end, child.lineno)
        return end - start + 1

    def _extract_source_snippet(
        self, lines: List[str], node: ast.AST, context: int = 0
    ) -> str:
        """Extract a source code snippet for a given AST node."""
        start = max(0, (node.lineno or 1) - 1 - context)
        if hasattr(node, "end_lineno") and node.end_lineno:
            end = node.end_lineno
        else:
            end = (node.lineno or 1) + 10
        snippet = lines[start:end]
        return "\n".join(snippet)

    def _compute_similarity(self, s1: str, s2: str) -> float:
        """Compute similarity between two strings using token overlap."""
        tokens1 = set(s1.split())
        tokens2 = set(s2.split())
        if not tokens1 or not tokens2:
            return 0.0
        intersection = tokens1 & tokens2
        union = tokens1 | tokens2
        return len(intersection) / len(union) if union else 0.0

    def _suggest_snake_case(self, name: str) -> str:
        """Suggest a snake_case version of a name."""
        # Convert CamelCase or mixedCase to snake_case
        s1 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        s2 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s1)
        return s2.lower()

    def _suggest_pascal_case(self, name: str) -> str:
        """Suggest a PascalCase version of a name."""
        # Convert snake_case to PascalCase
        return "".join(word.capitalize() for word in name.split("_"))

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from analysis."""
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            if part in EXCLUDED_DIRS:
                return True
        return False

    def __repr__(self) -> str:
        return "RefactoringSuggester()"

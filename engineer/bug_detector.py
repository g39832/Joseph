"""
engineer/bug_detector.py
------------------------
Static bug detection for Python code. Scans for syntax errors, common
bug patterns, and potential vulnerabilities including bare except clauses,
dangerous eval/exec usage, hardcoded secrets, SQL injection patterns,
path traversal, None dereferences, unused imports, and mutable defaults.
"""

import ast
import logging
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class BugFinding:
    """A single bug or issue found during static analysis."""

    file: str
    line: int
    severity: str  # info, warning, error, critical
    message: str
    category: str
    suggestion: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "message": self.message,
            "category": self.category,
            "suggestion": self.suggestion,
        }


EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv",
    "venv", "env", ".tox", ".eggs", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}

# Patterns for hardcoded secrets
SECRET_PATTERNS: List[Tuple[str, str]] = [
    (r'(?i)(password|passwd|pwd)\s*[=:]\s*["\'].+["\']', "Hardcoded password detected"),
    (r'(?i)(secret|api_key|apikey|api[-_]?key)\s*[=:]\s*["\'].+["\']', "Hardcoded API key/secret detected"),
    (r'(?i)(token|auth_token|access_token)\s*[=:]\s*["\'].+["\']', "Hardcoded token detected"),
    (r'(?i)(connection_string|connstr)\s*[=:]\s*["\'].+["\']', "Hardcoded connection string detected"),
]

# SQL injection patterns
SQL_INJECTION_PATTERNS: List[Tuple[str, str, str]] = [
    (r'execute\(.*["\'].*%.*["\']', "SQL injection via string formatting in execute()", "Use parameterized queries instead of string formatting"),
    (r'execute\(.*f["\'].*\{.*\}.*["\']', "SQL injection via f-string in execute()", "Use parameterized queries instead of f-strings"),
    (r'raw\(.*["\'].*%.*["\']', "SQL injection via string formatting in raw()", "Use parameterized queries instead of string formatting"),
    (r'raw\(.*f["\'].*\{.*\}.*["\']', "SQL injection via f-string in raw()", "Use parameterized queries instead of f-strings"),
]

# Path traversal patterns
PATH_TRAVERSAL_PATTERNS: List[Tuple[str, str, str]] = [
    (r'open\(.*["\'].*\+.*["\']', "Path traversal risk in open()", "Use os.path.join() and validate paths"),
    (r'open\(.*f["\'].*\{.*\}.*["\']', "Path traversal risk in open() with f-string", "Validate and sanitize file paths"),
]


@dataclass
class _VariableState:
    """Tracks variable assignment state for None-dereference detection."""
    name: str
    assigned_to_none: bool
    line: int


class BugDetector:
    """Static bug detection for Python source code."""

    def scan_for_bugs(self, directory: str) -> List[BugFinding]:
        """
        Scan an entire project for bugs.

        Args:
            directory: Path to the project root.

        Returns:
            List of BugFinding instances across all files.
        """
        all_findings: List[BugFinding] = []
        root = Path(directory)

        if not root.is_dir():
            logger.warning(f"Not a valid directory: {directory}")
            return all_findings

        for py_file in sorted(root.rglob("*.py")):
            if self._should_exclude(py_file):
                continue
            try:
                findings = self.scan_file(str(py_file))
                all_findings.extend(findings)
            except Exception as e:
                logger.error(f"Error scanning {py_file}: {e}")

        return all_findings

    def scan_file(self, filepath: str) -> List[BugFinding]:
        """
        Scan a single file for all detectable issues.

        Args:
            filepath: Path to the file to scan.

        Returns:
            List of BugFinding instances.
        """
        findings: List[BugFinding] = []

        # Syntax check
        syntax_findings = self.check_syntax(filepath)
        findings.extend(syntax_findings)

        # If there are syntax errors, skip deeper analysis
        if any(f.category == "syntax" for f in syntax_findings):
            return findings

        # Common bug patterns
        bug_findings = self.check_common_bugs(filepath)
        findings.extend(bug_findings)

        return findings

    def check_syntax(self, filepath: str) -> List[BugFinding]:
        """
        Check a file for syntax errors.

        Args:
            filepath: Path to the file to check.

        Returns:
            List of BugFinding for syntax errors.
        """
        path = Path(filepath)
        findings: List[BugFinding] = []

        if not path.is_file():
            return findings

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            ast.parse(source)
        except SyntaxError as e:
            findings.append(
                BugFinding(
                    file=str(path.resolve()),
                    line=e.lineno or 0,
                    severity="error",
                    message=f"Syntax error: {e.msg}",
                    category="syntax",
                    suggestion=f"Fix the syntax at line {e.lineno}: {e.text.strip() if e.text else ''}",
                )
            )
        except Exception as e:
            findings.append(
                BugFinding(
                    file=str(path.resolve()),
                    line=0,
                    severity="error",
                    message=f"Cannot read file: {e}",
                    category="syntax",
                    suggestion="Check file encoding and permissions",
                )
            )

        return findings

    def check_common_bugs(self, filepath: str) -> List[BugFinding]:
        """
        Scan a file for common bug patterns using AST analysis
        and regex patterns.

        Args:
            filepath: Path to the file to scan.

        Returns:
            List of BugFinding instances.
        """
        path = Path(filepath)
        findings: List[BugFinding] = []

        if not path.is_file():
            return findings

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, Exception) as e:
            logger.debug(f"Cannot parse {filepath}: {e}")
            return findings

        res_path = str(path.resolve())

        # 1. Bare except clauses
        findings.extend(self._check_bare_except(tree, res_path))

        # 2. Dangerous eval/exec usage
        findings.extend(self._check_dangerous_calls(tree, res_path))

        # 3. Mutable default arguments
        findings.extend(self._check_mutable_defaults(tree, res_path))

        # 4. Unused imports
        findings.extend(self._check_unused_imports(tree, res_path))

        # 5. None dereference potential
        findings.extend(self._check_none_dereference(tree, res_path))

        # Regex-based checks on source
        findings.extend(self._check_secrets(source, res_path))
        findings.extend(self._check_sql_injection(source, res_path))
        findings.extend(self._check_path_traversal(source, res_path))
        findings.extend(self._check_assert_usage(source, res_path))
        findings.extend(self._check_debug_prints(source, res_path))

        return findings

    def _check_bare_except(
        self, tree: ast.AST, filepath: str
    ) -> List[BugFinding]:
        """Detect bare except clauses."""
        findings: List[BugFinding] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    findings.append(
                        BugFinding(
                            file=filepath,
                            line=node.lineno or 0,
                            severity="warning",
                            message="Bare except clause: catches all exceptions",
                            category="bare_except",
                            suggestion="Specify the exception type(s) to catch, e.g. 'except ValueError:' or 'except Exception:'",
                        )
                    )
        return findings

    def _check_dangerous_calls(
        self, tree: ast.AST, filepath: str
    ) -> List[BugFinding]:
        """Detect eval(), exec(), compile() with arbitrary input."""
        findings: List[BugFinding] = []
        dangerous = {"eval", "exec", "compile"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in dangerous:
                    findings.append(
                        BugFinding(
                            file=filepath,
                            line=node.lineno or 0,
                            severity="critical",
                            message=f"Dangerous function '{node.func.id}()' detected",
                            category="dangerous_call",
                            suggestion=f"Avoid using {node.func.id}() with untrusted input. Consider using ast.literal_eval() or safe alternatives.",
                        )
                    )
        return findings

    def _check_mutable_defaults(
        self, tree: ast.AST, filepath: str
    ) -> List[BugFinding]:
        """Detect mutable default argument values."""
        findings: List[BugFinding] = []
        mutable_types = (ast.List, ast.Dict, ast.Set)

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in node.args.defaults:
                    if isinstance(default, mutable_types):
                        findings.append(
                            BugFinding(
                                file=filepath,
                                line=default.lineno or 0,
                                severity="warning",
                                message="Mutable default argument: will be shared across all calls",
                                category="mutable_default",
                                suggestion="Use '= None' and initialize inside the function instead",
                            )
                        )
                # Handle keyword-only defaults
                for default in node.args.kw_defaults:
                    if default is not None and isinstance(default, mutable_types):
                        findings.append(
                            BugFinding(
                                file=filepath,
                                line=default.lineno or 0,
                                severity="warning",
                                message="Mutable default argument (keyword-only): will be shared across all calls",
                                category="mutable_default",
                                suggestion="Use '= None' and initialize inside the function instead",
                            )
                        )
        return findings

    def _check_unused_imports(
        self, tree: ast.AST, filepath: str
    ) -> List[BugFinding]:
        """Detect imports that are not used in the file body."""
        findings: List[BugFinding] = []
        imports: Dict[int, Tuple[str, str]] = {}  # line -> (name, alias)
        used_names: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[node.lineno] = ("import", name)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    name = alias.asname or alias.name
                    imports[node.lineno] = ("from", name)
            elif isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):
                    used_names.add(node.id)

        for line, (imp_type, name) in imports.items():
            base_name = name.split(".")[0]
            if base_name not in used_names:
                findings.append(
                    BugFinding(
                        file=filepath,
                        line=line,
                        severity="info",
                        message=f"Unused import: '{name}'",
                        category="unused_import",
                        suggestion=f"Remove the unused import '{name}'",
                    )
                )

        return findings

    def _check_none_dereference(
        self, tree: ast.AST, filepath: str
    ) -> List[BugFinding]:
        """
        Detect potential None dereferences where a variable assigned
        None is then used with attribute access without a None check.
        """
        findings: List[BugFinding] = []
        none_vars: Dict[str, int] = {}  # var_name -> line assigned

        for node in ast.walk(tree):
            # Track assignments of None
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and isinstance(
                        node.value, ast.Constant
                    ):
                        if node.value.value is None:
                            none_vars[target.id] = node.lineno

            # Track attribute access on variables that could be None
            if isinstance(node, ast.Attribute) and isinstance(
                node.value, ast.Name
            ):
                if node.value.id in none_vars:
                    findings.append(
                        BugFinding(
                            file=filepath,
                            line=node.lineno or 0,
                            severity="warning",
                            message=f"Possible None dereference: '{node.value.id}' was assigned None at line {none_vars[node.value.id]}",
                            category="none_dereference",
                            suggestion=f"Check if '{node.value.id}' is None before accessing its attributes",
                        )
                    )

        return findings

    def _check_secrets(
        self, source: str, filepath: str
    ) -> List[BugFinding]:
        """Detect hardcoded secrets using regex patterns."""
        findings: List[BugFinding] = []
        for pattern, message in SECRET_PATTERNS:
            for match in re.finditer(pattern, source):
                line_number = source[: match.start()].count("\n") + 1
                findings.append(
                    BugFinding(
                        file=filepath,
                        line=line_number,
                        severity="critical",
                        message=message,
                        category="hardcoded_secret",
                        suggestion="Move secrets to environment variables or a .env file",
                    )
                )
        return findings

    def _check_sql_injection(
        self, source: str, filepath: str
    ) -> List[BugFinding]:
        """Detect potential SQL injection patterns."""
        findings: List[BugFinding] = []
        for pattern, message, suggestion in SQL_INJECTION_PATTERNS:
            for match in re.finditer(pattern, source):
                line_number = source[: match.start()].count("\n") + 1
                findings.append(
                    BugFinding(
                        file=filepath,
                        line=line_number,
                        severity="error",
                        message=message,
                        category="sql_injection",
                        suggestion=suggestion,
                    )
                )
        return findings

    def _check_path_traversal(
        self, source: str, filepath: str
    ) -> List[BugFinding]:
        """Detect potential path traversal patterns."""
        findings: List[BugFinding] = []
        for pattern, message, suggestion in PATH_TRAVERSAL_PATTERNS:
            for match in re.finditer(pattern, source):
                line_number = source[: match.start()].count("\n") + 1
                findings.append(
                    BugFinding(
                        file=filepath,
                        line=line_number,
                        severity="warning",
                        message=message,
                        category="path_traversal",
                        suggestion=suggestion,
                    )
                )
        return findings

    def _check_assert_usage(
        self, source: str, filepath: str
    ) -> List[BugFinding]:
        """
        Detect assert statements used for validation (assertions can be
        disabled with -O flag).
        """
        findings: List[BugFinding] = []
        pattern = r'^\s*assert\s+'
        for match in re.finditer(pattern, source, re.MULTILINE):
            line_number = source[: match.start()].count("\n") + 1
            findings.append(
                BugFinding(
                    file=filepath,
                    line=line_number,
                    severity="info",
                    message="Assert statement used for validation; assertions are disabled with -O",
                    category="assert_usage",
                    suggestion="Use proper if/raise validation instead of assert for production code",
                )
            )
        return findings

    def _check_debug_prints(
        self, source: str, filepath: str
    ) -> List[BugFinding]:
        """
        Detect print statements left in production code (heuristic:
        prints outside of scripts and CLI tools).
        """
        findings: List[BugFinding] = []
        pattern = r'^\s*print\('
        count = 0
        for match in re.finditer(pattern, source, re.MULTILINE):
            count += 1
            if count > 5:
                break
            line_number = source[: match.start()].count("\n") + 1
            findings.append(
                BugFinding(
                    file=filepath,
                    line=line_number,
                    severity="info",
                    message="Print statement detected; may be debug code",
                    category="debug_print",
                    suggestion="Replace with logging.debug() or remove debug print statements",
                )
            )
        return findings

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from scanning."""
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            if part in EXCLUDED_DIRS:
                return True
        return False

    def __repr__(self) -> str:
        return "BugDetector()"

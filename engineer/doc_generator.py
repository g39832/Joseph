"""
engineer/doc_generator.py
-------------------------
Generates documentation for codebases. Produces markdown-formatted
file-level docs, module docs, API documentation, README files, and
changelogs from git history.
"""

import ast
import logging
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv",
    "venv", "env", ".tox", ".eggs", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache",
}


class DocGenerator:
    """Generates markdown documentation for codebases."""

    def generate_docs(
        self, directory: str, output_dir: str
    ) -> Dict[str, str]:
        """
        Generate documentation for the entire project.

        Args:
            directory: Path to the project root.
            output_dir: Path where documentation files will be written.

        Returns:
            Dict mapping output filenames to their content.
        """
        root = Path(directory)
        out_path = Path(output_dir)
        docs: Dict[str, str] = {}

        if not root.is_dir():
            logger.warning(f"Not a valid directory: {directory}")
            return docs

        try:
            out_path.mkdir(parents=True, exist_ok=True)

            # Generate README
            docs["README.md"] = self.generate_readme(directory)

            # Generate API docs
            docs["API.md"] = self.generate_api_docs(directory)

            # Generate module docs for each Python file
            module_docs: List[str] = []
            for py_file in sorted(root.rglob("*.py")):
                if self._should_exclude(py_file):
                    continue
                try:
                    file_docs = self.generate_file_docs(str(py_file))
                    module_docs.append(file_docs)
                except Exception as e:
                    logger.error(f"Error generating docs for {py_file}: {e}")

            docs["MODULES.md"] = "\n\n---\n\n".join(module_docs)

            # Generate changelog
            changelog = self.generate_changelog(directory)
            if changelog:
                docs["CHANGELOG.md"] = changelog

            # Write files to disk
            for filename, content in docs.items():
                filepath = out_path / filename
                filepath.write_text(content, encoding="utf-8")
                logger.info(f"Written: {filepath}")

        except Exception as e:
            logger.error(f"Documentation generation failed: {e}", exc_info=True)

        return docs

    def generate_file_docs(self, filepath: str) -> str:
        """
        Generate markdown documentation for a single Python file.

        Args:
            filepath: Path to the Python file.

        Returns:
            Markdown string documenting the file.
        """
        path = Path(filepath)
        if not path.is_file():
            return f"# File not found: {filepath}"

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, Exception) as e:
            return f"# {path.name}\n\n_Cannot parse: {e}_\n"

        rel_path = str(path.relative_to(path.anchor)) if path.is_absolute() else str(path)
        lines: List[str] = []
        lines.append(f"# {path.name}")
        lines.append("")
        lines.append(f"**Path:** `{rel_path}`")
        lines.append("")

        # Module docstring
        module_doc = ast.get_docstring(tree)
        if module_doc:
            lines.append("## Overview")
            lines.append("")
            lines.append(module_doc)
            lines.append("")

        # Imports
        imports = self._extract_imports(tree)
        if imports:
            lines.append("## Imports")
            lines.append("")
            lines.append("| Module | Names |")
            lines.append("|--------|-------|")
            for imp in imports:
                lines.append(f"| `{imp['module']}` | {', '.join(f'`{n}`' for n in imp['names'])} |")
            lines.append("")

        # Classes
        classes = [n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
        if classes:
            lines.append("## Classes")
            lines.append("")
            for cls in classes:
                lines.append(f"### `class {cls.name}`")
                lines.append("")
                cls_doc = ast.get_docstring(cls)
                if cls_doc:
                    lines.append(cls_doc)
                    lines.append("")

                # Bases
                if cls.bases:
                    bases = []
                    for base in cls.bases:
                        if isinstance(base, ast.Name):
                            bases.append(f"`{base.id}`")
                        elif isinstance(base, ast.Attribute):
                            bases.append(f"`{self._format_attribute(base)}`")
                    if bases:
                        lines.append(f"**Bases:** {', '.join(bases)}")
                        lines.append("")

                # Methods
                methods = [
                    n for n in cls.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                if methods:
                    lines.append("| Method | Description |")
                    lines.append("|--------|-------------|")
                    for method in methods:
                        doc = ast.get_docstring(method) or ""
                        first_line = doc.split("\n")[0] if doc else ""
                        lines.append(f"| `{method.name}()` | {first_line} |")
                    lines.append("")

        # Top-level functions
        functions = [
            n for n in ast.iter_child_nodes(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]
        if functions:
            lines.append("## Functions")
            lines.append("")
            for func in functions:
                lines.append(f"### `{func.name}()`")
                lines.append("")
                func_doc = ast.get_docstring(func)
                if func_doc:
                    lines.append(func_doc)
                    lines.append("")

                # Parse args from docstring or signature
                args = [arg.arg for arg in func.args.args]
                if args:
                    lines.append(f"**Parameters:** `{', '.join(f'{a}' for a in args)}`")
                    lines.append("")

        return "\n".join(lines)

    def generate_module_docs(self, module_path: str) -> str:
        """
        Generate documentation for a Python module (directory with __init__.py).

        Args:
            module_path: Path to the module directory.

        Returns:
            Markdown string documenting the module.
        """
        path = Path(module_path)
        if not path.is_dir():
            return self.generate_file_docs(module_path)

        init_file = path / "__init__.py"
        lines: List[str] = []
        lines.append(f"# Module: {path.name}")
        lines.append("")

        if init_file.is_file():
            try:
                source = init_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
                doc = ast.get_docstring(tree)
                if doc:
                    lines.append(doc)
                    lines.append("")
            except Exception:
                pass

        lines.append("## Contents")
        lines.append("")

        for item in sorted(path.iterdir()):
            if item.name.startswith(".") or item.name.startswith("__pycache__"):
                continue
            if item.is_dir():
                sub_init = item / "__init__.py"
                if sub_init.exists():
                    lines.append(f"- **{item.name}/** (package)")
                else:
                    lines.append(f"- {item.name}/")
            elif item.suffix == ".py":
                name = item.stem
                lines.append(f"- `{name}.py`")
            elif item.suffix in (".md", ".txt", ".yaml", ".yml", ".json", ".toml"):
                lines.append(f"- {item.name}")
            else:
                lines.append(f"- {item.name}")

        return "\n".join(lines)

    def generate_api_docs(self, directory: str) -> str:
        """
        Generate API documentation for all public classes and functions.

        Args:
            directory: Path to the project root.

        Returns:
            Markdown string containing API documentation.
        """
        root = Path(directory)
        lines: List[str] = []
        project_name = root.name
        lines.append(f"# {project_name} API Reference")
        lines.append("")
        lines.append(f"_Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_")
        lines.append("")
        lines.append("---")
        lines.append("")

        for py_file in sorted(root.rglob("*.py")):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            rel_path = str(py_file.relative_to(root)).replace("\\", "/")
            module_name = rel_path.replace("/", ".").replace(".py", "")
            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]

            file_api: List[str] = []
            for node in ast.iter_child_nodes(tree):
                if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                    file_api.append(self._render_class_api(node, module_name))
                elif isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not node.name.startswith("_"):
                    file_api.append(self._render_function_api(node, module_name))

            if file_api:
                lines.append(f"## Module: `{module_name}`")
                lines.append("")
                lines.extend(file_api)
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def generate_readme(self, directory: str) -> str:
        """
        Generate a README.md for the project based on its analysis.

        Args:
            directory: Path to the project root.

        Returns:
            Markdown string for a project README.
        """
        from engineer.codebase_analyzer import CodebaseAnalyzer

        root = Path(directory)
        project_name = root.name
        lines: List[str] = []
        lines.append(f"# {project_name}")
        lines.append("")

        # Project description from module docstrings
        first_doc = self._find_first_docstring(directory)
        if first_doc:
            lines.append(first_doc)
            lines.append("")

        analyzer = CodebaseAnalyzer()
        result = analyzer.analyze(directory)

        if result.languages:
            lines.append("## Languages")
            lines.append("")
            lines.append("| Language | Lines of Code |")
            lines.append("|----------|---------------|")
            total = sum(result.languages.values())
            for lang, count in sorted(
                result.languages.items(), key=lambda x: x[1], reverse=True
            ):
                pct = count / total * 100 if total > 0 else 0
                lines.append(f"| {lang} | {count:,} ({pct:.1f}%) |")
            lines.append("")

        if result.frameworks:
            lines.append("## Frameworks")
            lines.append("")
            for fw in result.frameworks:
                lines.append(f"- {fw}")
            lines.append("")

        if result.entry_points:
            lines.append("## Quick Start")
            lines.append("")
            lines.append("```bash")
            # Suggest a run command based on entry point
            for ep in result.entry_points:
                ep_path = Path(ep)
                if ep_path.suffix == ".py":
                    lines.append(f"python {ep_path.name}")
                elif ep_path.suffix in (".js", ".ts"):
                    lines.append(f"node {ep_path.name}")
                elif ep_path.name == "index.html":
                    lines.append(f"# Open {ep_path.name} in a browser")
            lines.append("```")
            lines.append("")

        lines.append("## Structure")
        lines.append("")
        lines.append("```")
        lines.append(f"{project_name}/")
        self._render_structure_text(result.structure, lines, indent="    ")
        lines.append("```")
        lines.append("")

        lines.append("---")
        lines.append(
            f"_Generated by [JOSEPH Engineering Assistant](https://joseph.ai) on "
            f"{datetime.now().strftime('%Y-%m-%d')}_"
        )
        lines.append("")

        return "\n".join(lines)

    def generate_changelog(self, directory: str) -> str:
        """
        Generate a CHANGELOG from git log history.

        Args:
            directory: Path to the project root.

        Returns:
            Markdown changelog string, or empty string if no git history.
        """
        root = Path(directory)
        git_dir = root / ".git"

        if not git_dir.exists():
            return "# CHANGELOG\n\n_No git history found._\n"

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "--decorate", "--no-merges", "-50"],
                capture_output=True,
                text=True,
                cwd=directory,
                timeout=30,
            )
            if result.returncode != 0:
                return "# CHANGELOG\n\n_Error reading git log._\n"

            log_lines = [l for l in result.stdout.strip().split("\n") if l.strip()]
            if not log_lines:
                return "# CHANGELOG\n\n_No commits found._\n"

            lines: List[str] = []
            lines.append("# CHANGELOG")
            lines.append("")

            # Try to get the first commit date for context
            try:
                date_result = subprocess.run(
                    ["git", "log", "--reverse", "--format=%ad", "--date=short"],
                    capture_output=True,
                    text=True,
                    cwd=directory,
                    timeout=30,
                )
                if date_result.stdout.strip():
                    dates = date_result.stdout.strip().split("\n")
                    lines.append(f"_Commits from {dates[0]} to {dates[-1]}_")
                    lines.append("")
            except Exception:
                pass

            # Group by version tags if available
            try:
                tag_result = subprocess.run(
                    ["git", "tag", "--sort=-version:refname"],
                    capture_output=True,
                    text=True,
                    cwd=directory,
                    timeout=30,
                )
                tags = [t.strip() for t in tag_result.stdout.strip().split("\n") if t.strip()]
            except Exception:
                tags = []

            if tags:
                lines.append("## Releases")
                lines.append("")
                for tag in tags[:10]:
                    try:
                        tag_log = subprocess.run(
                            ["git", "log", f"{tag}~1..{tag}", "--oneline"],
                            capture_output=True,
                            text=True,
                            cwd=directory,
                            timeout=30,
                        )
                        tag_commits = tag_log.stdout.strip()
                        if tag_commits:
                            lines.append(f"### {tag}")
                            lines.append("")
                            for commit_line in tag_commits.split("\n"):
                                if commit_line.strip():
                                    lines.append(f"- {commit_line.strip()}")
                            lines.append("")
                    except Exception:
                        pass

            lines.append("## Recent Commits")
            lines.append("")
            for commit_line in log_lines[:30]:
                lines.append(f"- {commit_line.strip()}")

            lines.append("")
            return "\n".join(lines)

        except subprocess.TimeoutExpired:
            return "# CHANGELOG\n\n_Git log timed out._\n"
        except FileNotFoundError:
            return "# CHANGELOG\n\n_Git not found on system._\n"
        except Exception as e:
            logger.error(f"Error generating changelog: {e}")
            return "# CHANGELOG\n\n_Error reading git history._\n"

    def _extract_imports(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract imports from an AST."""
        imports: List[Dict[str, Any]] = []
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                imports.append({
                    "module": ", ".join(a.name for a in node.names),
                    "names": [a.name for a in node.names],
                })
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.append({
                    "module": module,
                    "names": [a.name for a in node.names],
                })
        return imports

    def _format_attribute(self, node: ast.Attribute) -> str:
        """Format an attribute access chain."""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _render_class_api(
        self, node: ast.ClassDef, module_name: str
    ) -> str:
        """Render a class API entry in markdown."""
        lines: List[str] = []
        full_name = f"{module_name}.{node.name}"
        lines.append(f"### `{full_name}`")
        lines.append("")

        doc = ast.get_docstring(node)
        if doc:
            lines.append(doc)
            lines.append("")

        if node.bases:
            bases = []
            for base in node.bases:
                if isinstance(base, ast.Name):
                    bases.append(f"`{base.id}`")
                elif isinstance(base, ast.Attribute):
                    bases.append(f"`{self._format_attribute(base)}`")
            lines.append(f"**Bases:** {', '.join(bases)}")
            lines.append("")

        methods = [
            n for n in node.body
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and not n.name.startswith("_")
        ]
        if methods:
            lines.append("#### Methods")
            lines.append("")
            for m in methods:
                doc = ast.get_docstring(m) or ""
                first_line = doc.split("\n")[0] if doc else ""
                lines.append(f"- **{m.name}()**: {first_line}")
            lines.append("")

        return "\n".join(lines)

    def _render_function_api(
        self, node: ast.AST, module_name: str
    ) -> str:
        """Render a function API entry in markdown."""
        lines: List[str] = []
        name = node.name if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) else "unknown"
        full_name = f"{module_name}.{name}"
        lines.append(f"### `{full_name}()`")
        lines.append("")

        doc = ast.get_docstring(node)
        if doc:
            lines.append(doc)
            lines.append("")

        return "\n".join(lines)

    def _find_first_docstring(self, directory: str) -> Optional[str]:
        """Find the first module-level docstring for project description."""
        root = Path(directory)
        # Check __init__.py first
        for candidate in [root / "__init__.py", root / "main.py", root / "app.py"]:
            if candidate.is_file():
                try:
                    tree = ast.parse(
                        candidate.read_text(encoding="utf-8", errors="replace")
                    )
                    doc = ast.get_docstring(tree)
                    if doc:
                        return doc.split("\n")[0]
                except Exception:
                    continue
        return None

    def _render_structure_text(
        self, structure: Dict[str, Any], lines: List[str], indent: str = ""
    ) -> None:
        """Render structure tree as ASCII text."""
        children = structure.get("children", {})
        items = sorted(children.items(), key=lambda x: (x[1].get("type") != "directory", x[0].lower()))
        for i, (name, info) in enumerate(items):
            is_last = i == len(items) - 1
            prefix = "└── " if is_last else "├── "
            next_indent = "    " if is_last else "│   "

            if info.get("type") == "directory":
                lines.append(f"{indent}{prefix}{name}/")
                self._render_structure_text(info, lines, indent + next_indent)
            else:
                lines.append(f"{indent}{prefix}{name}")

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from analysis."""
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            if part in EXCLUDED_DIRS:
                return True
        return False

    def __repr__(self) -> str:
        return "DocGenerator()"

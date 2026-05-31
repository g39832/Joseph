"""
engineer/architecture_mapper.py
--------------------------------
Maps project architecture including package structure, class/function hierarchy,
and module dependency graphs. Generates ASCII architecture diagrams.
"""

import ast
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ArchitectureMap:
    """Complete architecture map of a project."""

    packages: List[Dict[str, Any]] = field(default_factory=list)
    modules: List[Dict[str, Any]] = field(default_factory=list)
    classes: List[Dict[str, Any]] = field(default_factory=list)
    functions: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)
    diagram: str = ""


EXCLUDED_DIRS = {
    "__pycache__", ".git", ".svn", ".hg", "node_modules", ".venv",
    "venv", "env", ".env", ".tox", ".eggs", "dist", "build",
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".idea", ".vscode",
}


class ArchitectureMapper:
    """Maps and analyzes project architecture."""

    def map_architecture(self, directory: str) -> ArchitectureMap:
        """
        Build a full architecture map of the project.

        Args:
            directory: Path to the project root.

        Returns:
            ArchitectureMap containing packages, modules, classes,
            functions, dependencies, and an ASCII diagram.
        """
        result = ArchitectureMap()
        root = Path(directory)

        if not root.is_dir():
            logger.warning(f"Not a valid directory: {directory}")
            return result

        try:
            result.packages = self.map_package_structure(directory)
            classes_and_functions = self.find_classes_and_functions(directory)
            result.classes = [cf for cf in classes_and_functions if cf["type"] == "class"]
            result.functions = [cf for cf in classes_and_functions if cf["type"] == "function"]
            result.dependencies = self.build_module_dependency_graph(directory)
            result.modules = self._build_module_list(directory)
            result.diagram = self.generate_architecture_diagram(directory)
        except Exception as e:
            logger.error(f"Architecture mapping failed: {e}", exc_info=True)

        return result

    def map_package_structure(self, directory: str) -> List[Dict[str, Any]]:
        """
        Map the Python package hierarchy by locating __init__.py files.

        Args:
            directory: Path to the project root.

        Returns:
            List of dicts representing the package tree, each with
            'name', 'path', 'subpackages', and 'modules' keys.
        """
        root = Path(directory)
        packages: List[Dict[str, Any]] = []

        for init_file in root.rglob("__init__.py"):
            if self._should_exclude(init_file):
                continue
            pkg_dir = init_file.parent
            rel_path = pkg_dir.relative_to(root)
            parts = list(rel_path.parts)

            pkg_info: Dict[str, Any] = {
                "name": ".".join(parts) if parts else pkg_dir.name,
                "path": str(init_file),
                "module_path": str(rel_path),
                "modules": [],
                "subpackages": [],
            }

            # Find modules in this package
            for item in sorted(pkg_dir.iterdir()):
                if item.is_file() and item.suffix == ".py":
                    if item.name != "__init__.py":
                        pkg_info["modules"].append(item.stem)
                elif item.is_dir() and (item / "__init__.py").exists():
                    if item.name not in EXCLUDED_DIRS:
                        pkg_info["subpackages"].append(item.name)

            packages.append(pkg_info)

        return sorted(packages, key=lambda p: p["name"])

    def find_classes_and_functions(self, directory: str) -> List[Dict[str, Any]]:
        """
        Extract all classes and functions with their locations.

        Args:
            directory: Path to the project root.

        Returns:
            List of dicts with keys: type, name, file, line, parent_class.
        """
        results: List[Dict[str, Any]] = []
        root = Path(directory)

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception) as e:
                logger.debug(f"Skipping {py_file}: {e}")
                continue

            rel_path = py_file.relative_to(root)
            file_str = str(rel_path).replace("\\", "/")

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Collect methods
                    methods = [
                        n.name
                        for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    base_classes = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            base_classes.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            base_classes.append(
                                f"{self._get_attribute_chain(base)}"
                            )

                    results.append(
                        {
                            "type": "class",
                            "name": node.name,
                            "file": file_str,
                            "line": node.lineno,
                            "methods": methods,
                            "bases": base_classes,
                            "docstring": ast.get_docstring(node),
                        }
                    )

                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip if it's a method (nested inside class)
                    parent_class = self._find_parent_class(tree, node)
                    results.append(
                        {
                            "type": "function",
                            "name": node.name,
                            "file": file_str,
                            "line": node.lineno,
                            "parent_class": parent_class,
                            "docstring": ast.get_docstring(node),
                        }
                    )

        return results

    def build_module_dependency_graph(self, directory: str) -> Dict[str, List[str]]:
        """
        Map which modules import what within the project.

        Args:
            directory: Path to the project root.

        Returns:
            Dict mapping module paths (relative) to lists of imported modules.
        """
        graph: Dict[str, List[str]] = {}
        root = Path(directory)

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            rel_path = str(py_file.relative_to(root)).replace("\\", "/")
            imports = self._extract_imports(tree)
            if imports:
                graph[rel_path] = imports

        return graph

    def generate_architecture_diagram(
        self, directory: str, output_path: Optional[str] = None
    ) -> str:
        """
        Generate an ASCII architecture diagram of the project.

        Args:
            directory: Path to the project root.
            output_path: Optional file path to write the diagram to.

        Returns:
            String containing the ASCII architecture diagram.
        """
        root = Path(directory)
        lines: List[str] = []
        project_name = root.name
        lines.append(f"Project: {project_name}")
        lines.append(f"{'=' * (len(project_name) + 9)}")
        lines.append("")

        self._render_tree(root, lines, prefix="")
        diagram = "\n".join(lines)

        if output_path:
            try:
                out = Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(diagram, encoding="utf-8")
                logger.info(f"Architecture diagram written to {output_path}")
            except Exception as e:
                logger.error(f"Failed to write diagram: {e}")

        return diagram

    def _build_module_list(self, directory: str) -> List[Dict[str, Any]]:
        """Build a list of all Python modules in the project."""
        modules: List[Dict[str, Any]] = []
        root = Path(directory)

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            rel_path = str(py_file.relative_to(root)).replace("\\", "/")
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            modules.append(
                {
                    "path": rel_path,
                    "name": py_file.stem,
                    "classes": [
                        n.name
                        for n in ast.walk(tree)
                        if isinstance(n, ast.ClassDef)
                    ],
                    "functions": [
                        n.name
                        for n in ast.walk(tree)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ],
                    "imports": self._extract_imports(tree),
                }
            )

        return modules

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import names from an AST node."""
        imports: List[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    if module:
                        imports.append(f"{module}.{alias.name}")
                    else:
                        imports.append(alias.name)
        return imports

    def _find_parent_class(
        self, tree: ast.AST, func_node: ast.FunctionDef
    ) -> Optional[str]:
        """Find the parent class name of a function definition."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for child in node.body:
                    if child is func_node:
                        return node.name
        return None

    def _get_attribute_chain(self, node: ast.Attribute) -> str:
        """Convert an attribute access chain to a dotted string."""
        parts: List[str] = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))

    def _render_tree(
        self,
        path: Path,
        lines: List[str],
        prefix: str = "",
        max_depth: int = 4,
        depth: int = 0,
    ) -> None:
        """
        Recursively render an ASCII directory tree.

        Args:
            path: Current path to render.
            lines: List of string lines being built.
            prefix: Current line prefix for indentation.
            max_depth: Maximum recursion depth.
            depth: Current depth level.
        """
        if depth > max_depth:
            return

        try:
            entries = sorted(
                path.iterdir(),
                key=lambda p: (p.is_file(), p.name.lower()),
            )
        except PermissionError:
            return

        # Filter hidden/excluded
        entries = [
            e
            for e in entries
            if not e.name.startswith(".")
            and e.name not in EXCLUDED_DIRS
            and e.name != "node_modules"
        ]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            continuation = "    " if is_last else "│   "

            if entry.is_dir():
                lines.append(f"{prefix}{connector}{entry.name}/")
                self._render_tree(
                    entry, lines, prefix + continuation, max_depth, depth + 1
                )
            else:
                lines.append(f"{prefix}{connector}{entry.name}")

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from analysis."""
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            if part in EXCLUDED_DIRS:
                return True
        return False

    def __repr__(self) -> str:
        return "ArchitectureMapper()"

"""
engineer/codebase_analyzer.py
-----------------------------
Analyzes a codebase directory to extract structural information.
Provides file-level and project-level analysis including language statistics,
entry point detection, and framework identification.
"""

import ast
import json
import logging
import os
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Result of a full codebase analysis."""

    total_files: int = 0
    total_lines: int = 0
    languages: Dict[str, int] = field(default_factory=dict)
    frameworks: List[str] = field(default_factory=list)
    entry_points: List[str] = field(default_factory=list)
    structure: Dict[str, Any] = field(default_factory=dict)
    file_types: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


LANGUAGE_MAP: Dict[str, str] = {
    ".py": "Python",
    ".js": "JavaScript",
    ".jsx": "React JSX",
    ".ts": "TypeScript",
    ".tsx": "React TSX",
    ".html": "HTML",
    ".htm": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".less": "LESS",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".h": "C Header",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".go": "Go",
    ".rs": "Rust",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".kt": "Kotlin",
    ".kts": "Kotlin Script",
    ".sql": "SQL",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".xml": "XML",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".sh": "Shell",
    ".bat": "Batch",
    ".ps1": "PowerShell",
    ".tf": "Terraform",
    ".toml": "TOML",
    ".ini": "INI",
    ".cfg": "Config",
    ".svg": "SVG",
    ".txt": "Text",
    ".env": "Env",
    ".lock": "Lockfile",
}

FRAMEWORK_PATTERNS: Dict[str, List[str]] = {
    "Flask": ["flask", "from flask", "import flask"],
    "Django": ["django", "from django", "import django", "DJANGO_SETTINGS_MODULE"],
    "FastAPI": ["fastapi", "from fastapi", "import fastapi"],
    "React": ["react", "from react", "import React", "react-dom"],
    "Vue": ["vue", "from vue", "import Vue", "vue-router"],
    "Angular": ["@angular", "angular/core", "angular/platform-browser"],
    "Express": ["express", "require('express')", "from 'express'"],
    "PyTorch": ["torch", "from torch", "import torch"],
    "TensorFlow": ["tensorflow", "from tensorflow", "import tensorflow", "tf.keras"],
    "Scikit-learn": ["sklearn", "from sklearn", "import sklearn"],
    "SQLAlchemy": ["sqlalchemy", "from sqlalchemy", "import sqlalchemy"],
    "Pandas": ["pandas", "import pandas"],
    "NumPy": ["numpy", "import numpy"],
    "Pytest": ["pytest", "import pytest"],
    "Selenium": ["selenium", "from selenium", "import selenium"],
    "Next.js": ["next", "next/link", "next/image", "next/document"],
    "Discord.py": ["discord", "import discord", "from discord.ext"],
    "Tkinter": ["tkinter", "from tkinter", "import tkinter"],
    "PyQt": ["PyQt5", "PyQt6", "PySide2", "PySide6"],
    "Flet": ["flet", "import flet", "from flet"],
    "Django REST": ["rest_framework", "from rest_framework"],
    "OpenCV": ["cv2", "from cv2", "import cv2"],
    "Requests": ["requests", "import requests"],
    "BeautifulSoup": ["bs4", "from bs4", "import bs4"],
    "Celery": ["celery", "from celery", "import celery"],
    "Aiohttp": ["aiohttp", "from aiohttp", "import aiohttp"],
    "Click": ["click", "import click", "from click"],
    "Typer": ["typer", "import typer", "from typer"],
    "Rich": ["rich", "from rich", "import rich"],
}

ENTRY_POINT_NAMES = [
    "main.py",
    "app.py",
    "run.py",
    "server.py",
    "cli.py",
    "start.py",
    "__main__.py",
    "manage.py",
    "wsgi.py",
    "asgi.py",
    "index.js",
    "index.ts",
    "server.js",
    "server.ts",
    "app.js",
    "app.ts",
    "index.html",
]

EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".svn",
    ".hg",
    "node_modules",
    ".venv",
    "venv",
    "env",
    ".env",
    ".tox",
    ".eggs",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    ".idea",
    ".vscode",
}

EXCLUDED_EXTS = {
    ".pyc",
    ".pyo",
    ".pyd",
    ".so",
    ".dll",
    ".dylib",
    ".exe",
    ".bin",
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".whl",
    ".egg",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".ico",
    ".webp",
    ".mp3",
    ".mp4",
    ".wav",
    ".ogg",
    ".avi",
    ".mov",
    ".mkv",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".xz",
    ".7z",
    ".rar",
    ".woff",
    ".woff2",
    ".ttf",
    ".eot",
    ".otf",
}


class CodebaseAnalyzer:
    """Provides comprehensive analysis of a codebase directory."""

    def analyze(self, directory: str) -> AnalysisResult:
        """
        Perform a full analysis of the codebase at the given directory.

        Args:
            directory: Path to the codebase root directory.

        Returns:
            AnalysisResult dataclass with all analysis data.
        """
        result = AnalysisResult()
        root = Path(directory)

        if not root.exists():
            result.errors.append(f"Directory does not exist: {directory}")
            return result
        if not root.is_dir():
            result.errors.append(f"Path is not a directory: {directory}")
            return result

        try:
            result.file_types = self.count_files_by_type(directory)
            result.total_files = sum(v for k, v in result.file_types.items() if k not in EXCLUDED_EXTS)
            result.languages = self.get_language_breakdown(directory)
            result.entry_points = self.find_entry_points(directory)
            result.frameworks = self.detect_framework(directory)
            result.structure = self._build_structure_tree(root)
            result.total_lines = sum(result.languages.values())
        except Exception as e:
            logger.error(f"Analysis failed for {directory}: {e}", exc_info=True)
            result.errors.append(str(e))

        return result

    def count_files_by_type(self, directory: str) -> Dict[str, int]:
        """
        Count files grouped by file extension.

        Args:
            directory: Path to the directory to scan.

        Returns:
            Dictionary mapping extensions (e.g. '.py') to file counts.
        """
        counts: Dict[str, int] = defaultdict(int)
        root = Path(directory)

        try:
            for filepath in root.rglob("*"):
                if not filepath.is_file():
                    continue
                if self._should_exclude(filepath):
                    continue
                ext = filepath.suffix.lower() if filepath.suffix else "(no extension)"
                counts[ext] += 1
        except PermissionError as e:
            logger.warning(f"Permission error scanning {directory}: {e}")

        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    def analyze_file(self, filepath: str) -> Dict[str, Any]:
        """
        Analyze a single file and return its statistics.

        Args:
            filepath: Path to the file to analyze.

        Returns:
            Dictionary with keys: path, extension, lines, code_lines,
            comment_lines, blank_lines, classes, functions, imports.
        """
        path = Path(filepath)
        if not path.is_file():
            return {"error": f"File not found: {filepath}"}

        stats: Dict[str, Any] = {
            "path": str(path.resolve()),
            "extension": path.suffix,
            "lines": 0,
            "code_lines": 0,
            "comment_lines": 0,
            "blank_lines": 0,
            "classes": [],
            "functions": [],
            "imports": [],
        }

        if path.suffix == ".py":
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                stats["error"] = str(e)
                return stats

            lines = source.splitlines()
            stats["lines"] = len(lines)

            in_multiline_comment = False
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    stats["blank_lines"] += 1
                    continue
                if stripped.startswith('"""') or stripped.startswith("'''"):
                    stats["comment_lines"] += 1
                    if stripped.count('"""') == 1 and stripped.count("'''") == 1:
                        in_multiline_comment = not in_multiline_comment
                    continue
                if in_multiline_comment:
                    stats["comment_lines"] += 1
                    if '"""' in stripped or "'''" in stripped:
                        in_multiline_comment = False
                    continue
                if stripped.startswith("#"):
                    stats["comment_lines"] += 1
                    continue
                stats["code_lines"] += 1

            try:
                tree = ast.parse(source)
                stats["classes"] = [
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ClassDef)
                ]
                stats["functions"] = [
                    node.name
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                ]
                stats["imports"] = self._extract_imports(tree)
            except SyntaxError as e:
                stats["syntax_error"] = str(e)

            if stats["classes"]:
                stats["class_count"] = len(stats["classes"])
            if stats["functions"]:
                stats["function_count"] = len(stats["functions"])
        else:
            try:
                source = path.read_text(encoding="utf-8", errors="replace")
                lines = source.splitlines()
            except (UnicodeDecodeError, Exception):
                stats["error"] = "Binary or non-unicode file"
                return stats

            stats["lines"] = len(lines)
            for line in lines:
                if not line.strip():
                    stats["blank_lines"] += 1
                else:
                    stats["code_lines"] += 1

        return stats

    def find_entry_points(self, directory: str) -> List[str]:
        """
        Find common entry point files in the project.

        Args:
            directory: Path to the project root.

        Returns:
            List of paths to discovered entry point files.
        """
        found: List[str] = []
        root = Path(directory)

        for entry in ENTRY_POINT_NAMES:
            candidate = root / entry
            if candidate.is_file():
                found.append(str(candidate.resolve()))

        # Also check one level deep in src/ or app/ directories
        for subdir in root.iterdir():
            if subdir.is_dir() and subdir.name in ("src", "app", "source", "lib"):
                for entry in ENTRY_POINT_NAMES:
                    candidate = subdir / entry
                    if candidate.is_file():
                        found.append(str(candidate.resolve()))

        return found

    def detect_framework(self, directory: str) -> List[str]:
        """
        Detect frameworks used in the project by scanning configuration
        files and source code imports.

        Args:
            directory: Path to the project root.

        Returns:
            Sorted list of detected framework names.
        """
        detected: set = set()
        root = Path(directory)

        self._check_package_json(root, detected)
        self._check_requirements_files(root, detected)
        self._check_source_imports(root, detected)

        return sorted(detected)

    def get_language_breakdown(self, directory: str) -> Dict[str, int]:
        """
        Count total lines of code per programming language.

        Args:
            directory: Path to the project root.

        Returns:
            Dictionary mapping language names to total line counts.
        """
        total_lines: Dict[str, int] = defaultdict(int)
        root = Path(directory)

        for filepath in root.rglob("*"):
            if not filepath.is_file():
                continue
            if self._should_exclude(filepath):
                continue

            ext = filepath.suffix.lower()
            lang = LANGUAGE_MAP.get(ext)

            if lang is None:
                name_lower = filepath.name.lower()
                if name_lower == "dockerfile":
                    lang = "Dockerfile"
                elif name_lower == "makefile":
                    lang = "Makefile"
                elif "dockerfile" in name_lower:
                    lang = "Dockerfile"
                else:
                    lang = ext[1:].upper() if ext else "Unknown"

            try:
                with open(
                    filepath, "r", encoding="utf-8", errors="replace"
                ) as f:
                    line_count = sum(1 for _ in f)
                total_lines[lang] += line_count
            except Exception:
                continue

        return dict(sorted(total_lines.items(), key=lambda x: x[1], reverse=True))

    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import names from an AST."""
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

    def _check_package_json(self, root: Path, detected: set) -> None:
        """Check package.json for JavaScript framework dependencies."""
        pkg = root / "package.json"
        if not pkg.is_file():
            return
        try:
            data = json.loads(pkg.read_text(encoding="utf-8", errors="replace"))
            deps = {
                **data.get("dependencies", {}),
                **data.get("devDependencies", {}),
                **data.get("peerDependencies", {}),
            }
            framework_packages = {
                "react": "React",
                "vue": "Vue",
                "angular": "Angular",
                "express": "Express",
                "next": "Next.js",
                "gatsby": "Gatsby",
                "svelte": "Svelte",
                "nuxt": "Nuxt.js",
                "@nestjs/core": "NestJS",
                "electron": "Electron",
                "jquery": "jQuery",
                "bootstrap": "Bootstrap",
                "tailwindcss": "Tailwind CSS",
                "socket.io": "Socket.io",
                "three": "Three.js",
                "d3": "D3.js",
                "axios": "Axios",
                "redux": "Redux",
                "mobx": "MobX",
                "styled-components": "Styled Components",
                "material-ui": "Material UI",
                "@mui/material": "Material UI",
                "@angular/core": "Angular",
                "chakra-ui": "Chakra UI",
                "primereact": "PrimeReact",
                "antd": "Ant Design",
            }
            for pkg_name, framework_name in framework_packages.items():
                if pkg_name in deps:
                    detected.add(framework_name)
        except Exception:
            pass

    def _check_requirements_files(self, root: Path, detected: set) -> None:
        """Scan requirements files and pyproject.toml for framework hints."""
        req_files = [
            "requirements.txt",
            "Pipfile",
            "pyproject.toml",
            "setup.py",
            "setup.cfg",
        ]

        for req_file in req_files:
            req_path = root / req_file
            if not req_path.is_file():
                continue
            try:
                content = req_path.read_text(
                    encoding="utf-8", errors="replace"
                ).lower()
                for framework, patterns in FRAMEWORK_PATTERNS.items():
                    if any(p.lower() in content for p in patterns):
                        detected.add(framework)
            except Exception:
                continue

            # Parse pyproject.toml for structured dependencies
            if req_file == "pyproject.toml":
                try:
                    import tomllib

                    data = tomllib.loads(content)
                    for key in ("dependencies", "optional-dependencies"):
                        deps_section = data.get("project", {}).get(key, {})
                        if isinstance(deps_section, dict):
                            for group_name, group_deps in deps_section.items():
                                dep_str = " ".join(group_deps).lower()
                                self._match_framework_patterns(
                                    dep_str, detected
                                )
                        elif isinstance(deps_section, list):
                            dep_str = " ".join(deps_section).lower()
                            self._match_framework_patterns(dep_str, detected)
                except (ImportError, Exception):
                    pass

    def _match_framework_patterns(
        self, text: str, detected: set
    ) -> None:
        """Match framework patterns against a text string."""
        for framework, patterns in FRAMEWORK_PATTERNS.items():
            if any(p.lower() in text for p in patterns):
                detected.add(framework)

    def _check_source_imports(
        self, root: Path, detected: set
    ) -> None:
        """Scan source files for import-based framework detection."""
        max_files = 200
        scanned = 0

        for ext in ("*.py", "*.js", "*.jsx", "*.ts", "*.tsx"):
            for filepath in root.rglob(ext):
                if scanned >= max_files:
                    return
                if self._should_exclude(filepath):
                    continue
                try:
                    content = filepath.read_text(
                        encoding="utf-8", errors="replace"
                    )
                    content_lower = content.lower()
                    for framework, patterns in FRAMEWORK_PATTERNS.items():
                        if framework in detected:
                            continue
                        if any(
                            p.lower() in content_lower for p in patterns
                        ):
                            detected.add(framework)
                    scanned += 1
                except Exception:
                    continue

    def _build_structure_tree(
        self, root: Path, max_depth: int = 4
    ) -> Dict[str, Any]:
        """
        Build a nested dictionary representing the project's directory tree.

        Args:
            root: The root directory path.
            max_depth: Maximum depth to recurse into.

        Returns:
            Nested dict with 'type', 'name', 'children' keys.
        """

        def _recurse(path: Path, depth: int = 0) -> Dict[str, Any]:
            if depth > max_depth:
                return {"type": "truncated", "name": path.name}

            if path.is_file():
                return {
                    "type": "file",
                    "name": path.name,
                    "size": path.stat().st_size,
                }

            result: Dict[str, Any] = {
                "type": "directory",
                "name": path.name,
                "children": {},
            }

            try:
                entries = sorted(
                    path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())
                )
                for entry in entries:
                    if entry.name.startswith("."):
                        continue
                    if entry.name in EXCLUDED_DIRS:
                        continue
                    if entry.name == "node_modules":
                        continue
                    result["children"][entry.name] = _recurse(entry, depth + 1)
            except PermissionError:
                pass

            return result

        return _recurse(root)

    def _should_exclude(self, path: Path) -> bool:
        """
        Determine whether a path should be excluded from analysis.

        Args:
            path: The file path to check.

        Returns:
            True if the path should be skipped.
        """
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            if part in EXCLUDED_DIRS:
                return True
        if path.suffix.lower() in EXCLUDED_EXTS:
            return True
        return False

    def __repr__(self) -> str:
        return "CodebaseAnalyzer()"

"""
tools/search_tools.py
----------------------
Project search and indexing tools.

Provides content search, filename search, regex grep,
and directory indexing using only Python stdlib.
"""

import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from tools.registry import ToolResult

logger = logging.getLogger(__name__)

SEARCHABLE_EXTENSIONS: set[str] = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".csv", ".html", ".css", ".xml", ".log", ".ini", ".cfg", ".env",
    ".bat", ".ps1", ".sh", ".sql", ".toml", ".rst", ".conf",
    ".jsx", ".tsx", ".vue", ".svelte", ".rb", ".java", ".c", ".cpp",
    ".h", ".hpp", ".go", ".rs", ".swift", ".kt", ".scala", ".php",
    ".r", ".m", ".mm", ".gradle", ".cmake", ".makefile", ".dockerfile",
    ".yml", ".yaml", ".jsonc",
}


class SearchTools:
    """
    Project search and indexing using only Python stdlib.

    Features:
      - Content + filename combined search
      - Regex pattern grep
      - File type filtering
      - Build searchable in-memory index
    """

    def __init__(self):
        self._index: dict[str, list[dict]] = {}
        self._indexed_dir: Optional[Path] = None
        self._last_indexed: Optional[str] = None

    def search_files(
        self,
        query: str,
        directory: str = ".",
        search_content: bool = True,
        max_results: int = 30,
        case_sensitive: bool = False,
    ) -> ToolResult:
        """
        Search files by name and/or content.

        Args:
            query: Search term.
            directory: Root directory to search.
            search_content: Also search file contents.
            max_results: Maximum results to return.
            case_sensitive: Case-sensitive search.

        Returns:
            ToolResult with formatted file list.
        """
        root = Path(directory).expanduser().resolve()
        if not root.exists():
            return ToolResult(
                success=False, output="",
                error=f"Directory not found: {directory}",
            )
        if not root.is_dir():
            return ToolResult(
                success=False, output="",
                error=f"Not a directory: {directory}",
            )

        query_lower = query.lower() if not case_sensitive else query
        results: list[dict] = []

        try:
            for item in root.rglob("*"):
                if not item.is_file():
                    continue

                if not case_sensitive:
                    name_match = query_lower in item.name.lower()
                else:
                    name_match = query in item.name

                if name_match:
                    results.append({
                        "path": str(item.relative_to(root)),
                        "type": "name_match",
                        "line": None,
                        "context": None,
                    })

                if search_content and item.suffix.lower() in SEARCHABLE_EXTENSIONS:
                    try:
                        content = item.read_text(
                            encoding="utf-8", errors="ignore"
                        )
                        lines = content.split("\n")
                        for i, line in enumerate(lines, 1):
                            if not case_sensitive:
                                match = query_lower in line.lower()
                            else:
                                match = query in line

                            if match:
                                context = line.strip()[:200]
                                results.append({
                                    "path": str(item.relative_to(root)),
                                    "type": "content_match",
                                    "line": i,
                                    "context": context,
                                })
                                if len(results) >= max_results:
                                    break
                    except Exception:
                        pass

                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No results found for '{query}' in {root}",
                )

            lines = [
                f"Search results for '{query}' in {root}:",
                f"Found {len(results)} match(es):\n",
            ]
            for r in results[:max_results]:
                if r["type"] == "name_match":
                    lines.append(f"  {r['path']} (filename match)")
                else:
                    lines.append(
                        f"  {r['path']}:{r['line']}  {r['context'][:120]}"
                    )

            if len(results) > max_results:
                lines.append(f"\n  ... and {len(results) - max_results} more results")

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Search error: {e}",
            )

    def grep_pattern(
        self,
        pattern: str,
        directory: str = ".",
        file_pattern: Optional[str] = None,
        max_results: int = 50,
        context_lines: int = 0,
    ) -> ToolResult:
        """
        Regex search across files.

        Args:
            pattern: Regular expression pattern.
            directory: Root directory to search.
            file_pattern: Optional glob for file filtering (e.g. "*.py").
            max_results: Maximum matches to return.
            context_lines: Number of context lines around each match.

        Returns:
            ToolResult with matched lines.
        """
        root = Path(directory).expanduser().resolve()
        if not root.exists():
            return ToolResult(
                success=False, output="",
                error=f"Directory not found: {directory}",
            )

        try:
            regex = re.compile(pattern, re.MULTILINE)
        except re.error as e:
            return ToolResult(
                success=False, output="", error=f"Invalid regex: {e}",
            )

        results: list[dict] = []
        file_count = 0

        try:
            for item in root.rglob("*"):
                if not item.is_file():
                    continue

                if file_pattern and not item.match(file_pattern):
                    continue

                if item.suffix.lower() not in SEARCHABLE_EXTENSIONS:
                    continue

                file_count += 1

                try:
                    content = item.read_text(encoding="utf-8", errors="ignore")
                    lines = content.split("\n")

                    for i, line in enumerate(lines, 1):
                        if regex.search(line):
                            entry = {
                                "path": str(item.relative_to(root)),
                                "line": i,
                                "content": line.strip()[:300],
                            }

                            if context_lines > 0:
                                start = max(0, i - 1 - context_lines)
                                end = min(len(lines), i + context_lines)
                                ctx = []
                                for ci in range(start, end):
                                    prefix = ">" if ci == i - 1 else " "
                                    ctx.append(f"{prefix} {ci + 1}:{lines[ci].strip()[:200]}")
                                entry["context"] = "\n".join(ctx)

                            results.append(entry)

                            if len(results) >= max_results:
                                break
                except Exception:
                    continue

                if len(results) >= max_results:
                    break

            if not results:
                return ToolResult(
                    success=True,
                    output=f"No matches for pattern '{pattern}' in {root}",
                )

            lines = [
                f"Grep results for /{pattern}/ in {root}:",
                f"Scanned {file_count} files, found {len(results)} match(es):\n",
            ]
            for r in results[:max_results]:
                if context_lines > 0 and r.get("context"):
                    lines.append(f"  {r['path']}:{r['line']}")
                    lines.append(f"  {r['context']}")
                else:
                    lines.append(f"  {r['path']}:{r['line']}: {r['content'][:150]}")
                lines.append("")

            return ToolResult(success=True, output="\n".join(lines))

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Grep error: {e}",
            )

    def find_by_type(
        self,
        extension: str,
        directory: str = ".",
        max_results: int = 50,
    ) -> ToolResult:
        """
        Find files by extension.

        Args:
            extension: File extension (e.g. ".py", ".md", "py").
            directory: Root directory to search.
            max_results: Maximum results.

        Returns:
            ToolResult with file list.
        """
        if not extension.startswith("."):
            extension = f".{extension}"

        root = Path(directory).expanduser().resolve()
        if not root.exists():
            return ToolResult(
                success=False, output="",
                error=f"Directory not found: {directory}",
            )

        ext_lower = extension.lower()
        results: list[Path] = []

        try:
            for item in root.rglob(f"*{extension}"):
                if item.is_file() and item.suffix.lower() == ext_lower:
                    results.append(item)
                    if len(results) >= max_results:
                        break
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Find error: {e}",
            )

        if not results:
            return ToolResult(
                success=True,
                output=f"No *{extension} files found in {root}",
            )

        lines = [
            f"Found {len(results)} *{extension} file(s) in {root}:",
        ]
        for r in results:
            try:
                rel = r.relative_to(root)
            except ValueError:
                rel = r
            size = r.stat().st_size
            modified = datetime.fromtimestamp(r.stat().st_mtime).strftime("%Y-%m-%d")
            lines.append(f"  {rel} ({self._format_size(size)}, {modified})")

        if len(results) >= max_results:
            lines.append(f"\n(Showing first {max_results} of {len(results)} files)")

        return ToolResult(success=True, output="\n".join(lines))

    def index_directory(self, directory: str) -> ToolResult:
        """
        Build a searchable index of a directory's text files.

        Stores file paths, sizes, and first 200 chars of each file
        for fast in-memory searching.

        Args:
            directory: Directory to index.

        Returns:
            ToolResult with index stats.
        """
        root = Path(directory).expanduser().resolve()
        if not root.exists():
            return ToolResult(
                success=False, output="",
                error=f"Directory not found: {directory}",
            )

        indexed = 0
        skipped = 0
        errors = 0
        self._index = {}
        self._indexed_dir = root

        try:
            for item in root.rglob("*"):
                if not item.is_file():
                    continue

                if item.suffix.lower() not in SEARCHABLE_EXTENSIONS:
                    skipped += 1
                    continue

                try:
                    content = item.read_text(encoding="utf-8", errors="ignore")
                    rel_path = str(item.relative_to(root))
                    self._index[rel_path] = {
                        "path": rel_path,
                        "size": len(content),
                        "modified": datetime.fromtimestamp(
                            item.stat().st_mtime
                        ).isoformat(),
                        "preview": content[:200],
                        "lines": content.count("\n") + 1,
                    }
                    indexed += 1
                except Exception:
                    errors += 1

            self._last_indexed = datetime.now().isoformat()
            summary = (
                f"Indexed {root}: {indexed} files indexed, "
                f"{skipped} skipped, {errors} errors"
            )
            logger.info(summary)
            return ToolResult(success=True, output=summary)

        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Index error: {e}",
            )

    def search_index(self, query: str, case_sensitive: bool = False) -> ToolResult:
        """
        Search previously built index.

        Args:
            query: Search term.
            case_sensitive: Case-sensitive search.

        Returns:
            ToolResult with matching indexed files.
        """
        if not self._index:
            return ToolResult(
                success=False, output="",
                error="No index available. Run index_directory first.",
            )

        query_lower = query.lower() if not case_sensitive else query
        results: list[tuple[str, str]] = []

        for rel_path, info in self._index.items():
            if not case_sensitive:
                name_match = query_lower in rel_path.lower()
                content_match = query_lower in info["preview"].lower()
            else:
                name_match = query in rel_path
                content_match = query in info["preview"]

            if name_match:
                results.append((rel_path, "filename"))
            elif content_match:
                results.append((rel_path, "content"))

        if not results:
            return ToolResult(
                success=True,
                output=f"No results in index for '{query}'",
            )

        lines = [
            f"Index search for '{query}' ({self._indexed_dir}):",
            f"Found {len(results)} match(es):\n",
        ]
        for path, match_type in results[:30]:
            info = self._index.get(path, {})
            preview = info.get("preview", "")[:100].replace("\n", " ")
            lines.append(f"  [{match_type}] {path}")
            if preview:
                lines.append(f"             {preview}")

        return ToolResult(success=True, output="\n".join(lines))

    def get_index_stats(self) -> ToolResult:
        """Return statistics about the current index."""
        if not self._index:
            return ToolResult(
                success=True,
                output="No index loaded.",
            )

        total_size = sum(i["size"] for i in self._index.values())
        total_lines = sum(i["lines"] for i in self._index.values())

        ext_counts: dict[str, int] = {}
        for path in self._index:
            ext = Path(path).suffix.lower()
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        ext_summary = ", ".join(
            f"{ext}: {count}" for ext, count in
            sorted(ext_counts.items(), key=lambda x: -x[1])[:10]
        )

        stats = (
            f"Index: {self._indexed_dir}\n"
            f"Files: {len(self._index)}\n"
            f"Total size: {self._format_size(total_size)}\n"
            f"Total lines: {total_lines}\n"
            f"Last indexed: {self._last_indexed}\n"
            f"Extensions: {ext_summary}"
        )
        return ToolResult(success=True, output=stats)

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / 1024 ** 2:.1f}MB"
        else:
            return f"{size_bytes / 1024 ** 3:.1f}GB"

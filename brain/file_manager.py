"""
brain/file_manager.py
----------------------
Safe file management for JOSEPH.

Allows Joseph to:
- List files in allowed directories
- Read text files
- Create/write files (with confirmation)
- Search for files by name or content
- Organize files (move, rename) — with confirmation
- Open files in default application

SAFETY: All destructive operations require explicit confirmation.
Only operates within allowed directories defined in settings.
"""

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

from automation.safety.permissions import permissions, RiskLevel
from configs.settings import settings

logger = logging.getLogger(__name__)

# Directories Joseph is allowed to work in
ALLOWED_DIRS = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    settings.DATA_DIR,
    settings.EXPORTS_DIR,
]

# File types Joseph can read
READABLE_EXTENSIONS = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".csv", ".html", ".css", ".xml", ".log", ".ini", ".cfg", ".env",
    ".bat", ".ps1", ".sh", ".sql", ".toml",
}

# File types to never touch
FORBIDDEN_EXTENSIONS = {
    ".exe", ".dll", ".sys", ".bat" ".msi", ".reg",
}


class FileManager:
    """
    Safe file operations for JOSEPH.

    All paths are validated against allowed directories.
    Destructive operations require user confirmation.

    Usage:
        fm = FileManager()
        files = fm.list_directory("~/Desktop")
        content = fm.read_file("~/Desktop/notes.txt")
        fm.create_file("~/Desktop/new_note.txt", "Hello world")
    """

    def __init__(self):
        self._allowed_dirs = ALLOWED_DIRS
        logger.info(f"FileManager initialized with {len(self._allowed_dirs)} allowed dirs")

    def _resolve_path(self, path_str: str) -> Optional[Path]:
        """
        Resolve a path string to an absolute Path.
        Expands ~ and validates against allowed directories.

        Returns:
            Resolved Path, or None if not allowed.
        """
        try:
            path = Path(path_str).expanduser().resolve()

            # Check if path is within an allowed directory
            for allowed in self._allowed_dirs:
                allowed_resolved = allowed.expanduser().resolve()
                try:
                    path.relative_to(allowed_resolved)
                    return path
                except ValueError:
                    continue

            logger.warning(f"Path not in allowed directories: {path}")
            return None

        except Exception as e:
            logger.error(f"Path resolution error: {e}")
            return None

    def list_directory(
        self,
        directory: str = "~/Desktop",
        show_hidden: bool = False,
    ) -> str:
        """
        List files in a directory.

        Args:
            directory: Directory path to list.
            show_hidden: Whether to show hidden files.

        Returns:
            Formatted file listing string.
        """
        path = self._resolve_path(directory)
        if not path:
            return f"I don't have access to that directory."

        if not path.exists():
            return f"Directory not found: {directory}"

        if not path.is_dir():
            return f"That's a file, not a directory."

        try:
            items = sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
            lines = [f"Contents of {path}:"]

            dirs = []
            files = []

            for item in items:
                if not show_hidden and item.name.startswith("."):
                    continue
                if item.is_dir():
                    dirs.append(f"  📁 {item.name}/")
                else:
                    size = self._format_size(item.stat().st_size)
                    modified = datetime.fromtimestamp(
                        item.stat().st_mtime
                    ).strftime("%Y-%m-%d")
                    files.append(f"  📄 {item.name} ({size}, {modified})")

            lines.extend(dirs)
            lines.extend(files)

            if len(lines) == 1:
                lines.append("  (empty)")

            lines.append(f"\n{len(dirs)} folders, {len(files)} files")
            return "\n".join(lines)

        except PermissionError:
            return f"Permission denied: {directory}"
        except Exception as e:
            return f"Error listing directory: {e}"

    def read_file(self, file_path: str, max_chars: int = 3000) -> str:
        """
        Read the contents of a text file.

        Args:
            file_path: Path to the file.
            max_chars: Maximum characters to return.

        Returns:
            File contents as string.
        """
        path = self._resolve_path(file_path)
        if not path:
            return "I don't have access to that file."

        if not path.exists():
            return f"File not found: {file_path}"

        if path.suffix.lower() in FORBIDDEN_EXTENSIONS:
            return f"I can't read that file type ({path.suffix})."

        if path.suffix.lower() not in READABLE_EXTENSIONS and path.suffix != "":
            return f"I can only read text files. That file type ({path.suffix}) isn't supported."

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                return content[:max_chars] + f"\n\n[... truncated at {max_chars} chars. File is {len(content)} chars total]"
            return content

        except PermissionError:
            return f"Permission denied: {file_path}"
        except Exception as e:
            return f"Error reading file: {e}"

    def create_file(self, file_path: str, content: str = "") -> str:
        """
        Create a new file with optional content.
        Requires confirmation if file already exists.

        Args:
            file_path: Where to create the file.
            content: Initial file content.

        Returns:
            Success/failure message.
        """
        path = self._resolve_path(file_path)
        if not path:
            return "I don't have access to that location."

        if path.exists():
            if not permissions.request_permission(
                f"overwrite existing file: {path.name}",
                RiskLevel.HIGH,
            ):
                return "File creation cancelled."

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            logger.info(f"File created: {path}")
            return f"File created: {path.name}"

        except Exception as e:
            return f"Error creating file: {e}"

    def append_to_file(self, file_path: str, content: str) -> str:
        """
        Append content to an existing file.

        Args:
            file_path: Path to the file.
            content: Content to append.

        Returns:
            Success/failure message.
        """
        path = self._resolve_path(file_path)
        if not path:
            return "I don't have access to that file."

        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"Content appended to {path.name}."

        except Exception as e:
            return f"Error appending to file: {e}"

    def search_files(
        self,
        query: str,
        directory: str = "~/Desktop",
        search_content: bool = False,
    ) -> str:
        """
        Search for files by name or content.

        Args:
            query: Search term.
            directory: Where to search.
            search_content: Also search inside file contents.

        Returns:
            Formatted search results.
        """
        path = self._resolve_path(directory)
        if not path:
            return "I don't have access to that directory."

        try:
            results = []
            query_lower = query.lower()

            for item in path.rglob("*"):
                if item.is_file():
                    # Name match
                    if query_lower in item.name.lower():
                        results.append(f"  📄 {item.relative_to(path)} (name match)")
                        continue

                    # Content match
                    if search_content and item.suffix.lower() in READABLE_EXTENSIONS:
                        try:
                            content = item.read_text(encoding="utf-8", errors="ignore")
                            if query_lower in content.lower():
                                results.append(
                                    f"  📄 {item.relative_to(path)} (content match)"
                                )
                        except Exception:
                            pass

            if not results:
                return f"No files found matching '{query}' in {directory}."

            lines = [f"Found {len(results)} file(s) matching '{query}':"]
            lines.extend(results[:20])  # Limit to 20 results
            if len(results) > 20:
                lines.append(f"  ... and {len(results) - 20} more")
            return "\n".join(lines)

        except Exception as e:
            return f"Search error: {e}"

    def open_file(self, file_path: str) -> str:
        """
        Open a file in its default application.

        Args:
            file_path: Path to the file.

        Returns:
            Success/failure message.
        """
        path = self._resolve_path(file_path)
        if not path:
            return "I don't have access to that file."

        if not path.exists():
            return f"File not found: {file_path}"

        try:
            os.startfile(str(path))
            return f"Opening {path.name}."
        except Exception as e:
            return f"Error opening file: {e}"

    def delete_file(self, file_path: str) -> str:
        """
        Delete a file — ALWAYS requires confirmation.

        Args:
            file_path: Path to delete.

        Returns:
            Success/failure message.
        """
        path = self._resolve_path(file_path)
        if not path:
            return "I don't have access to that file."

        if not path.exists():
            return f"File not found: {file_path}"

        if not permissions.request_permission(
            f"permanently delete file: {path.name}",
            RiskLevel.HIGH,
        ):
            return "File deletion cancelled."

        try:
            path.unlink()
            logger.info(f"File deleted: {path}")
            return f"Deleted: {path.name}"
        except Exception as e:
            return f"Error deleting file: {e}"

    def get_file_info(self, file_path: str) -> str:
        """Get metadata about a file."""
        path = self._resolve_path(file_path)
        if not path or not path.exists():
            return f"File not found: {file_path}"

        stat = path.stat()
        return (
            f"File: {path.name}\n"
            f"Path: {path}\n"
            f"Size: {self._format_size(stat.st_size)}\n"
            f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M')}\n"
            f"Type: {path.suffix or 'no extension'}"
        )

    def _format_size(self, size_bytes: int) -> str:
        """Format file size as human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / 1024**2:.1f}MB"
        else:
            return f"{size_bytes / 1024**3:.1f}GB"

    def get_allowed_dirs(self) -> list[str]:
        """Return list of directories Joseph can access."""
        return [str(d.expanduser()) for d in self._allowed_dirs]


# Module-level singleton
file_manager = FileManager()

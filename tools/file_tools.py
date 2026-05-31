"""
tools/file_tools.py
--------------------
File operations with safety and rollback support.

All modifying operations back up original data for undo capability.
Operations are restricted to allowed directories (Desktop, Documents, project).
"""

import json
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from configs.settings import settings
from tools.registry import ToolResult

logger = logging.getLogger(__name__)

ALLOWED_DIRS: list[Path] = [
    Path.home() / "Desktop",
    Path.home() / "Documents",
    Path.home() / "Downloads",
    settings.DATA_DIR,
    settings.EXPORTS_DIR,
    settings.BASE_DIR,
]

READABLE_EXTENSIONS: set[str] = {
    ".txt", ".md", ".py", ".js", ".ts", ".json", ".yaml", ".yml",
    ".csv", ".html", ".css", ".xml", ".log", ".ini", ".cfg", ".env",
    ".bat", ".ps1", ".sh", ".sql", ".toml", ".rst", ".ini",
    ".conf", ".yml", ".yaml", ".jsonc", ".jsx", ".tsx", ".vue",
    ".svelte", ".rb", ".java", ".c", ".cpp", ".h", ".hpp",
    ".go", ".rs", ".swift", ".kt", ".scala", ".php",
}

FORBIDDEN_EXTENSIONS: set[str] = {
    ".exe", ".dll", ".sys", ".msi", ".reg", ".bat",
    ".com", ".scr", ".pif", ".vbs", ".ps1", ".bin",
}


class FileTools:
    """
    Safe file operations with automatic backup/rollback.

    All operations validate paths against ALLOWED_DIRS.
    Modifying operations create backups before making changes.
    """

    BACKUP_DIR = settings.DATA_DIR / "file_backups"

    def __init__(self):
        self.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        self._operation_log: list[dict] = []

    def read_file(self, path: str, max_chars: int = 50000) -> ToolResult:
        """Read the contents of a text file."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")

        if resolved.suffix.lower() in FORBIDDEN_EXTENSIONS:
            return ToolResult(
                success=False, output="",
                error=f"Cannot read forbidden file type: {resolved.suffix}",
            )

        try:
            content = resolved.read_text(encoding="utf-8", errors="replace")
            if len(content) > max_chars:
                content = content[:max_chars] + f"\n\n[... truncated at {max_chars} chars]"
            self._log_op("read", path)
            return ToolResult(success=True, output=content)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Read error: {e}")

    def write_file(
        self,
        path: str,
        content: str,
        max_chars: int = 100000,
    ) -> ToolResult:
        """Write content to a file, backing up the original first."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if len(content) > max_chars:
            return ToolResult(
                success=False, output="",
                error=f"Content too large ({len(content)} chars, max {max_chars})",
            )

        rollback_data = None
        if resolved.exists():
            try:
                backup = self._backup_file(resolved)
                rollback_data = {
                    "path": str(resolved),
                    "backup_path": str(backup),
                    "operation": "write_file",
                }
            except Exception as e:
                return ToolResult(
                    success=False, output="",
                    error=f"Backup failed: {e}",
                )

        try:
            resolved.parent.mkdir(parents=True, exist_ok=True)
            resolved.write_text(content, encoding="utf-8")
            self._log_op("write", path)
            logger.info(f"File written: {resolved}")
            return ToolResult(
                success=True,
                output=f"File written: {resolved.name} ({len(content)} chars)",
                rollback_data=rollback_data,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Write error: {e}")

    def move_file(self, src: str, dst: str) -> ToolResult:
        """Move a file from source to destination with rollback."""
        src_resolved = self._resolve_path(src)
        dst_resolved = self._resolve_path(dst)

        if not src_resolved:
            return ToolResult(success=False, output="", error=f"Access denied source: {src}")
        if not dst_resolved:
            return ToolResult(success=False, output="", error=f"Access denied destination: {dst}")

        if not src_resolved.exists():
            return ToolResult(success=False, output="", error=f"Source not found: {src}")

        if dst_resolved.exists():
            return ToolResult(
                success=False, output="",
                error=f"Destination already exists: {dst}",
            )

        try:
            dst_resolved.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_resolved), str(dst_resolved))
            self._log_op("move", f"{src} -> {dst}")

            rollback_data = {
                "src": str(dst_resolved),
                "dst": str(src_resolved),
                "operation": "move_file",
            }
            return ToolResult(
                success=True,
                output=f"Moved: {src_resolved.name} -> {dst_resolved.name}",
                rollback_data=rollback_data,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Move error: {e}")

    def copy_file(self, src: str, dst: str) -> ToolResult:
        """Copy a file from source to destination."""
        src_resolved = self._resolve_path(src)
        dst_resolved = self._resolve_path(dst)

        if not src_resolved:
            return ToolResult(success=False, output="", error=f"Access denied source: {src}")
        if not dst_resolved:
            return ToolResult(success=False, output="", error=f"Access denied destination: {dst}")

        if not src_resolved.exists():
            return ToolResult(success=False, output="", error=f"Source not found: {src}")

        if dst_resolved.exists():
            return ToolResult(
                success=False, output="",
                error=f"Destination already exists: {dst}",
            )

        try:
            dst_resolved.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src_resolved), str(dst_resolved))
            self._log_op("copy", f"{src} -> {dst}")
            return ToolResult(
                success=True,
                output=f"Copied: {src_resolved.name} -> {dst_resolved.name}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Copy error: {e}")

    def delete_file(self, path: str) -> ToolResult:
        """Move a file to trash/backup instead of permanent deletion."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")

        if resolved.is_dir():
            return ToolResult(success=False, output="", error=f"Use delete_directory for folders")

        try:
            backup = self._backup_file(resolved)
            resolved.unlink()
            self._log_op("delete", path)

            rollback_data = {
                "path": str(resolved),
                "backup_path": str(backup),
                "operation": "delete_file",
            }
            return ToolResult(
                success=True,
                output=f"Moved to trash: {resolved.name}",
                rollback_data=rollback_data,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Delete error: {e}")

    def list_directory(
        self,
        path: str,
        show_hidden: bool = False,
        max_items: int = 100,
    ) -> ToolResult:
        """List files and directories in a path."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"Directory not found: {path}")

        if not resolved.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")

        try:
            items = list(resolved.iterdir())
            if not show_hidden:
                items = [i for i in items if not i.name.startswith(".")]
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))

            lines = [f"Contents of {resolved}:"]
            dirs = []
            files = []

            for item in items[:max_items]:
                if item.is_dir():
                    dirs.append(f"  {item.name}/")
                else:
                    size = self._format_size(item.stat().st_size)
                    modified = datetime.fromtimestamp(
                        item.stat().st_mtime
                    ).strftime("%Y-%m-%d %H:%M")
                    files.append(f"  {item.name} ({size}, {modified})")

            lines.extend(dirs)
            lines.extend(files)
            if len(items) > max_items:
                lines.append(f"  ... and {len(items) - max_items} more")

            if len(lines) == 1:
                lines.append("  (empty)")

            lines.append(f"\n{len(dirs)} directories, {len(files)} files")
            self._log_op("list", path)
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"List error: {e}")

    def get_file_info(self, path: str) -> ToolResult:
        """Get metadata about a file or directory."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"Not found: {path}")

        try:
            stat = resolved.stat()
            info_parts = [
                f"Name: {resolved.name}",
                f"Path: {resolved}",
                f"Size: {self._format_size(stat.st_size)}",
                f"Created: {datetime.fromtimestamp(stat.st_ctime).strftime('%Y-%m-%d %H:%M:%S')}",
                f"Modified: {datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')}",
                f"Type: {'Directory' if resolved.is_dir() else 'File'}",
            ]
            if resolved.is_file():
                info_parts.append(f"Extension: {resolved.suffix or '(none)'}")
            return ToolResult(success=True, output="\n".join(info_parts))
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Info error: {e}")

    def create_directory(self, path: str) -> ToolResult:
        """Create a new directory."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if resolved.exists():
            return ToolResult(success=False, output="", error=f"Already exists: {path}")

        try:
            resolved.mkdir(parents=True, exist_ok=True)
            self._log_op("mkdir", path)
            return ToolResult(success=True, output=f"Directory created: {resolved}")
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Mkdir error: {e}")

    def append_to_file(self, path: str, content: str) -> ToolResult:
        """Append content to an existing file."""
        resolved = self._resolve_path(path)
        if not resolved:
            return ToolResult(success=False, output="", error=f"Access denied: {path}")

        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")

        rollback_data = None
        try:
            backup = self._backup_file(resolved)
            rollback_data = {
                "path": str(resolved),
                "backup_path": str(backup),
                "operation": "write_file",
            }
            with open(resolved, "a", encoding="utf-8") as f:
                f.write(content)
            self._log_op("append", path)
            return ToolResult(
                success=True,
                output=f"Appended {len(content)} chars to {resolved.name}",
                rollback_data=rollback_data,
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Append error: {e}")

    def rollback_write(self, path: str, backup_path: str) -> ToolResult:
        """Restore a file from backup."""
        backup = Path(backup_path)
        target = Path(path)

        if not backup.exists():
            return ToolResult(
                success=False, output="",
                error=f"Backup not found: {backup_path}",
            )

        try:
            shutil.copy2(str(backup), str(target))
            backup.unlink()
            return ToolResult(
                success=True,
                output=f"Restored: {target.name} from backup",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Rollback error: {e}")

    def rollback_move(self, src: str, dst: str) -> ToolResult:
        """Undo a file move operation."""
        src_path = Path(src)
        dst_path = Path(dst)

        if not src_path.exists():
            return ToolResult(
                success=False, output="",
                error=f"Source not found: {src}",
            )

        try:
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            return ToolResult(
                success=True,
                output=f"Moved back: {src_path.name} -> {dst_path.name}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Rollback move error: {e}")

    def rollback_delete(self, path: str, backup_path: str) -> ToolResult:
        """Restore a deleted file from backup."""
        backup = Path(backup_path)
        target = Path(path)

        if not backup.exists():
            return ToolResult(
                success=False, output="",
                error=f"Backup not found: {backup_path}",
            )

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(backup), str(target))
            return ToolResult(
                success=True,
                output=f"Restored: {target.name}",
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Restore error: {e}")

    def _resolve_path(self, path_str: str) -> Optional[Path]:
        """Resolve and validate a path against allowed directories."""
        try:
            path = Path(path_str).expanduser().resolve()

            for allowed in ALLOWED_DIRS:
                allowed_resolved = allowed.expanduser().resolve()
                try:
                    path.relative_to(allowed_resolved)
                    return path
                except ValueError:
                    continue

            logger.warning(f"Path outside allowed dirs: {path}")
            return None
        except Exception as e:
            logger.error(f"Path resolution error: {e}")
            return None

    def _backup_file(self, path: Path) -> Path:
        """Create a timestamped backup of a file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        backup_name = f"{path.name}.backup_{timestamp}"
        backup_path = self.BACKUP_DIR / backup_name
        shutil.copy2(str(path), str(backup_path))
        logger.debug(f"Backup created: {backup_path}")
        return backup_path

    def _format_size(self, size_bytes: int) -> str:
        """Format size in human-readable form."""
        if size_bytes < 1024:
            return f"{size_bytes}B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f}KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / 1024 ** 2:.1f}MB"
        else:
            return f"{size_bytes / 1024 ** 3:.1f}GB"

    def _log_op(self, operation: str, path: str) -> None:
        """Record an operation in the log."""
        self._operation_log.append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "path": path,
        })

    def get_operation_log(self, limit: int = 50) -> list[dict]:
        """Return recent file operations."""
        return self._operation_log[-limit:]

    def get_allowed_directories(self) -> list[str]:
        """Return list of directories this module can access."""
        return [str(p.expanduser().resolve()) for p in ALLOWED_DIRS]

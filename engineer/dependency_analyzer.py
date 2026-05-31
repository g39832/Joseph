"""
engineer/dependency_analyzer.py
-------------------------------
Analyzes project dependencies including import graphs, external package
detection, circular dependency detection, and dependency tree generation.
Optionally generates Graphviz DOT output for visualization.
"""

import ast
import logging
import sys
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DependencyGraph:
    """Complete dependency graph for a project."""

    nodes: List[str] = field(default_factory=list)
    edges: List[Tuple[str, str]] = field(default_factory=list)
    externals: List[str] = field(default_factory=list)
    circulars: List[List[str]] = field(default_factory=list)
    adjacency: Dict[str, List[str]] = field(default_factory=dict)


# Python standard library modules (common ones used in detection)
STDLIB_MODULES: Set[str] = {
    "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio",
    "asyncore", "atexit", "audioop", "base64", "bdb", "binascii", "binhex",
    "bisect", "builtins", "bz2", "calendar", "cgi", "cgitb", "chunk",
    "cmath", "cmd", "code", "codecs", "codeop", "collections", "colorsys",
    "compileall", "concurrent", "configparser", "contextlib", "contextvars",
    "copy", "copyreg", "cProfile", "crypt", "csv", "ctypes", "curses",
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis",
    "distutils", "doctest", "email", "encodings", "enum", "errno",
    "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob",
    "graphlib", "grp", "gzip", "hashlib", "heapq", "hmac", "html", "http",
    "idlelib", "imaplib", "imghdr", "imp", "importlib", "inspect", "io",
    "ipaddress", "itertools", "json", "keyword", "lib2to3", "linecache",
    "locale", "logging", "lzma", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "multiprocessing", "netrc", "nis",
    "nntplib", "numbers", "operator", "optparse", "os", "ossaudiodev",
    "pathlib", "pdb", "pickle", "pickletools", "pipes", "pkgutil",
    "platform", "plistlib", "poplib", "posix", "posixpath", "pprint",
    "profile", "pstats", "pty", "pwd", "py_compile", "pyclbr",
    "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "resource", "rlcompleter", "runpy", "sched", "secrets", "select",
    "selectors", "shelve", "shlex", "shutil", "signal", "site", "smtpd",
    "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3",
    "ssl", "stat", "statistics", "string", "stringprep", "struct",
    "subprocess", "sunau", "symtable", "sys", "sysconfig", "syslog",
    "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test",
    "textwrap", "threading", "time", "timeit", "tkinter", "token",
    "tokenize", "tomllib", "trace", "traceback", "tracemalloc", "tty",
    "turtle", "turtledemo", "types", "typing", "unicodedata",
    "unittest", "urllib", "uu", "uuid", "venv", "warnings", "wave",
    "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib",
    "xml", "xmlrpc", "zipapp", "zipfile", "zipimport", "zlib",
    "__future__", "__main__",
}


class DependencyAnalyzer:
    """Analyzes project dependencies, imports, and dependency graphs."""

    def analyze_dependencies(self, directory: str) -> DependencyGraph:
        """
        Perform a full dependency analysis of the project.

        Args:
            directory: Path to the project root.

        Returns:
            DependencyGraph with nodes, edges, external dependencies,
            and circular dependencies.
        """
        graph = DependencyGraph()
        root = Path(directory)

        if not root.is_dir():
            logger.warning(f"Not a valid directory: {directory}")
            return graph

        try:
            graph.adjacency = self.build_import_graph(directory)
            graph.nodes = list(graph.adjacency.keys())
            graph.edges = self._build_edge_list(graph.adjacency)
            graph.externals = self.find_external_dependencies(directory)
            graph.circulars = self.check_circular_dependencies(directory)
        except Exception as e:
            logger.error(f"Dependency analysis failed: {e}", exc_info=True)

        return graph

    def find_imports_in_file(self, filepath: str) -> List[Dict[str, Any]]:
        """
        Extract all import statements from a single file.

        Args:
            filepath: Path to the file to analyze.

        Returns:
            List of dicts with keys: type (import/from), module, names, line.
        """
        path = Path(filepath)
        if not path.is_file():
            return []

        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (SyntaxError, Exception) as e:
            logger.debug(f"Cannot parse {filepath}: {e}")
            return []

        imports: List[Dict[str, Any]] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
                imports.append(
                    {
                        "type": "import",
                        "module": names[0] if names else "",
                        "names": names,
                        "line": node.lineno,
                    }
                )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                names = [alias.name for alias in node.names]
                imports.append(
                    {
                        "type": "from",
                        "module": module,
                        "names": names,
                        "line": node.lineno,
                    }
                )

        return imports

    def build_import_graph(self, directory: str) -> Dict[str, List[str]]:
        """
        Build a mapping of each module to the modules it imports.

        Only includes relative project imports for the graph edges;
        all imports (including external) are listed in the values.

        Args:
            directory: Path to the project root.

        Returns:
            Dict mapping relative module paths to lists of imported modules.
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
            imports: List[str] = []

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
                    for alias in node.names:
                        pass  # We track the module, not individual names

            if imports:
                graph[rel_path] = imports

        return graph

    def find_external_dependencies(self, directory: str) -> List[str]:
        """
        Find third-party (non-stdlib, non-project) package dependencies.

        Args:
            directory: Path to the project root.

        Returns:
            Sorted list of unique external package names.
        """
        externals: Set[str] = set()
        root = Path(directory)

        # Collect all project module names for relative import detection
        project_modules: Set[str] = set()
        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            rel = py_file.relative_to(root)
            module_path = str(rel).replace("\\", "/").replace("/", ".").replace(".py", "")
            if module_path.endswith(".__init__"):
                module_path = module_path[:-9]  # Remove .__init__
            project_modules.add(module_path)
            # Also add parent packages
            parts = module_path.split(".")
            for i in range(1, len(parts)):
                project_modules.add(".".join(parts[:i]))

        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            try:
                source = py_file.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(source)
            except (SyntaxError, Exception):
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top_level = alias.name.split(".")[0]
                        if (
                            top_level not in STDLIB_MODULES
                            and top_level not in project_modules
                            and not top_level.startswith("_")
                        ):
                            externals.add(top_level)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top_level = node.module.split(".")[0]
                        if (
                            top_level not in STDLIB_MODULES
                            and top_level not in project_modules
                            and not top_level.startswith("_")
                        ):
                            externals.add(top_level)

        return sorted(externals)

    def check_circular_dependencies(self, directory: str) -> List[List[str]]:
        """
        Detect circular dependencies between modules.

        Uses DFS with cycle detection on the import graph considering
        only internal project imports.

        Args:
            directory: Path to the project root.

        Returns:
            List of cycles, each cycle being a list of module paths.
        """
        root = Path(directory)

        # Build full import map
        import_map = self.build_import_graph(directory)

        # Build a reverse map: project module path -> its file path
        file_to_module: Dict[str, str] = {}
        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            rel = str(py_file.relative_to(root)).replace("\\", "/")
            module_name = rel.replace("/", ".").replace(".py", "")
            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]
            file_to_module[rel] = module_name

        # Convert file paths to module names and filter internal edges
        adj: Dict[str, List[str]] = defaultdict(list)
        for filepath, imports in import_map.items():
            module = file_to_module.get(filepath, filepath)
            for imp in imports:
                # Check if the import is an internal module
                for proj_file, proj_module in file_to_module.items():
                    if imp == proj_module or imp.startswith(proj_module + "."):
                        adj[module].append(proj_module)
                        break

        # Find cycles using DFS
        cycles: List[List[str]] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        parent: Dict[str, Optional[str]] = {}

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in adj.get(node, []):
                if neighbor not in visited:
                    parent[neighbor] = node
                    dfs(neighbor, path)
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    # Normalize to avoid duplicates
                    if cycle not in cycles and list(reversed(cycle)) not in cycles:
                        cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for module in adj:
            if module not in visited:
                dfs(module, [])

        return cycles

    def get_dependency_tree(
        self, module_name: str, directory: str
    ) -> Dict[str, Any]:
        """
        Build a recursive dependency tree for a given module.

        Args:
            module_name: Name of the module to analyze.
            directory: Path to the project root.

        Returns:
            Nested dict representing the dependency tree.
        """
        root = Path(directory)
        import_map = self.build_import_graph(directory)

        # Map module names to file paths
        module_to_file: Dict[str, str] = {}
        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            rel = str(py_file.relative_to(root)).replace("\\", "/")
            mod = rel.replace("/", ".").replace(".py", "")
            if mod.endswith(".__init__"):
                mod = mod[:-9]
            module_to_file[mod] = rel

        # Find the file for the given module
        target_file = None
        for mod, filepath in module_to_file.items():
            if module_name == mod or module_name in mod:
                target_file = filepath
                break

        if not target_file or target_file not in import_map:
            return {"module": module_name, "dependencies": []}

        def _build_tree(
            filepath: str, visited: Optional[Set[str]] = None
        ) -> Dict[str, Any]:
            if visited is None:
                visited = set()
            if filepath in visited:
                return {"module": filepath, "dependencies": [], "circular": True}

            visited.add(filepath)
            imports = import_map.get(filepath, [])
            children = []

            for imp in imports:
                # Find which project file this import resolves to
                for mod, fpath in module_to_file.items():
                    if imp == mod or imp.startswith(mod + "."):
                        child = _build_tree(fpath, visited.copy())
                        children.append(child)
                        break

            return {"module": filepath, "dependencies": children}

        return _build_tree(target_file)

    def generate_graphviz_output(
        self, directory: str, output_path: str
    ) -> str:
        """
        Generate a Graphviz DOT format file for the dependency graph.

        Args:
            directory: Path to the project root.
            output_path: Path where the .dot file will be written.

        Returns:
            The DOT content as a string.
        """
        import_map = self.build_import_graph(directory)
        root = Path(directory)

        # Map files to short module names
        module_to_file: Dict[str, str] = {}
        for py_file in root.rglob("*.py"):
            if self._should_exclude(py_file):
                continue
            rel = str(py_file.relative_to(root)).replace("\\", "/")
            mod = rel.replace("/", ".").replace(".py", "")
            if mod.endswith(".__init__"):
                mod = mod[:-9]
            module_to_file[mod] = rel

        # Build DOT content
        lines = ["digraph Dependencies {", "    node [shape=box, style=rounded, fontname=Arial];", "    rankdir=LR;", ""]

        # Add nodes
        node_ids: Dict[str, str] = {}
        for i, filepath in enumerate(import_map.keys()):
            node_id = f"n{i}"
            # Use a short label
            rel = filepath.replace("\\", "/")
            label = rel.replace("/", ".").replace(".py", "")
            if label.endswith(".__init__"):
                label = label[:-9]
            lines.append(f'    {node_id} [label="{label}"];')
            node_ids[filepath] = node_id

        # Add edges for internal dependencies
        file_to_module = {v: k for k, v in module_to_file.items()}
        for filepath, imports in import_map.items():
            src_id = node_ids.get(filepath)
            if src_id is None:
                continue
            for imp in imports:
                for mod, fpath in module_to_file.items():
                    if imp == mod or imp.startswith(mod + "."):
                        dst_id = node_ids.get(fpath)
                        if dst_id:
                            lines.append(f"    {src_id} -> {dst_id};")
                        break

        lines.append("}")
        dot_content = "\n".join(lines)

        try:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(dot_content, encoding="utf-8")
            logger.info(f"Graphviz DOT file written to {output_path}")
        except Exception as e:
            logger.error(f"Failed to write Graphviz output: {e}")

        return dot_content

    def _build_edge_list(
        self, graph: Dict[str, List[str]]
    ) -> List[Tuple[str, str]]:
        """Convert adjacency dict to a list of (from, to) edges."""
        edges: List[Tuple[str, str]] = []
        for source, targets in graph.items():
            for target in targets:
                edges.append((source, target))
        return edges

    def _should_exclude(self, path: Path) -> bool:
        """Check if a path should be excluded from analysis."""
        excluded = {
            "__pycache__", ".git", ".svn", ".hg", "node_modules",
            ".venv", "venv", "env", ".tox", ".eggs", "dist", "build",
            ".mypy_cache", ".pytest_cache",
        }
        for part in path.parts:
            if part.startswith(".") and part not in (".", ".."):
                return True
            if part in excluded:
                return True
        return False

    def __repr__(self) -> str:
        return "DependencyAnalyzer()"

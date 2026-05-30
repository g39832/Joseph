"""
hyper/knowledge_graph.py
------------------------
Persistent knowledge graph for users, projects, topics, technologies, tasks,
and research.

The graph is stored locally and used as an additive reasoning aid. It does not
replace the existing memory system.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import networkx as nx

from configs.settings import settings

logger = logging.getLogger(__name__)

DB_PATH = settings.DATA_DIR / "hyper_knowledge_graph.db"


@dataclass
class GraphNode:
    node_id: str
    label: str
    node_type: str = "topic"
    importance: float = 0.5
    properties: Optional[dict] = None


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relation: str
    weight: float = 1.0
    evidence: str = ""


class KnowledgeGraph:
    """Persistent graph of semantic relationships."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._use_memory_store = False
        self._memory_conn = None
        self.graph = nx.DiGraph()
        self._init_db()
        self._load_graph()

    @contextmanager
    def _conn(self):
        try:
            if self._use_memory_store:
                if self._memory_conn is None:
                    self._memory_conn = sqlite3.connect(":memory:")
                    self._memory_conn.row_factory = sqlite3.Row
                conn = self._memory_conn
            else:
                conn = sqlite3.connect(str(self.db_path))
                conn.row_factory = sqlite3.Row
        except Exception:
            self._use_memory_store = True
            if self._memory_conn is None:
                self._memory_conn = sqlite3.connect(":memory:")
                self._memory_conn.row_factory = sqlite3.Row
            conn = self._memory_conn
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if not self._use_memory_store:
                conn.close()

    def _init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS graph_nodes (
                    node_id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    node_type TEXT DEFAULT 'topic',
                    importance REAL DEFAULT 0.5,
                    properties_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS graph_edges (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation TEXT NOT NULL,
                    weight REAL DEFAULT 1.0,
                    evidence TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_graph_nodes_type
                    ON graph_nodes(node_type);
                CREATE INDEX IF NOT EXISTS idx_graph_edges_source
                    ON graph_edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_graph_edges_target
                    ON graph_edges(target_id);
            """)

    def _load_graph(self) -> None:
        try:
            with self._conn() as conn:
                nodes = conn.execute("SELECT * FROM graph_nodes").fetchall()
                edges = conn.execute("SELECT * FROM graph_edges").fetchall()
            self.graph.clear()
            for row in nodes:
                props = {}
                try:
                    props = json.loads(row["properties_json"] or "{}")
                except Exception:
                    props = {}
                self.graph.add_node(
                    row["node_id"],
                    label=row["label"],
                    node_type=row["node_type"],
                    importance=row["importance"],
                    properties=props,
                )
            for row in edges:
                self.graph.add_edge(
                    row["source_id"],
                    row["target_id"],
                    relation=row["relation"],
                    weight=row["weight"],
                    evidence=row["evidence"],
                )
        except Exception as e:
            logger.debug(f"Knowledge graph load skipped: {e}")

    def _slug(self, label: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
        return slug or "node"

    def add_node(
        self,
        label: str,
        node_type: str = "topic",
        importance: float = 0.5,
        properties: Optional[dict] = None,
        node_id: Optional[str] = None,
    ) -> str:
        node_id = node_id or self._slug(label)
        props = properties or {}
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO graph_nodes (node_id, label, node_type, importance, properties_json, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(node_id) DO UPDATE SET
                     label = excluded.label,
                     node_type = excluded.node_type,
                     importance = excluded.importance,
                     properties_json = excluded.properties_json,
                     updated_at = CURRENT_TIMESTAMP""",
                (node_id, label, node_type, importance, json.dumps(props, ensure_ascii=False)),
            )
        self.graph.add_node(node_id, label=label, node_type=node_type, importance=importance, properties=props)
        return node_id

    def add_relation(
        self,
        source_label: str,
        target_label: str,
        relation: str,
        source_type: str = "topic",
        target_type: str = "topic",
        weight: float = 1.0,
        evidence: str = "",
    ) -> tuple[str, str]:
        source_id = self.add_node(source_label, node_type=source_type)
        target_id = self.add_node(target_label, node_type=target_type)
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO graph_edges (source_id, target_id, relation, weight, evidence, updated_at)
                   VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)""",
                (source_id, target_id, relation, weight, evidence),
            )
        self.graph.add_edge(source_id, target_id, relation=relation, weight=weight, evidence=evidence)
        return source_id, target_id

    def ingest_from_text(self, text: str, source_type: str = "text") -> int:
        """
        Heuristic ingestion from text into the knowledge graph.
        """
        if not text:
            return 0
        tokens = [t.strip(" ,.;:!?") for t in text.split()]
        entities = [t for t in tokens if len(t) > 3 and t[:1].isupper()]
        if not entities:
            entities = [t for t in tokens if len(t) > 5][:5]
        count = 0
        for left, right in zip(entities, entities[1:]):
            self.add_relation(left, right, "related_to", source_type=source_type, target_type=source_type)
            count += 1
        return count

    def link_user_interest(self, user_label: str, topic: str, relation: str = "interested_in") -> None:
        self.add_relation(user_label, topic, relation, source_type="user", target_type="topic", weight=1.2)

    def get_related(self, label: str, depth: int = 2, limit: int = 10) -> list[dict]:
        node_id = self._slug(label)
        if node_id not in self.graph:
            return []
        results = []
        try:
            lengths = nx.single_source_shortest_path_length(self.graph.to_undirected(), node_id, cutoff=depth)
            for target_id, dist in sorted(lengths.items(), key=lambda item: (item[1], item[0])):
                if target_id == node_id:
                    continue
                node_data = self.graph.nodes.get(target_id, {})
                results.append(
                    {
                        "node_id": target_id,
                        "label": node_data.get("label", target_id),
                        "node_type": node_data.get("node_type", "topic"),
                        "distance": dist,
                        "importance": node_data.get("importance", 0.5),
                    }
                )
                if len(results) >= limit:
                    break
        except Exception as e:
            logger.debug(f"Knowledge graph traversal failed: {e}")
        return results

    def build_context(self, query: str, limit: int = 5) -> str:
        if not query:
            return ""
        query_lower = query.lower()
        scores = []
        for node_id, data in self.graph.nodes(data=True):
            label = str(data.get("label", node_id))
            score = 0.0
            if label.lower() in query_lower:
                score += 2.0
            if any(word in label.lower() for word in query_lower.split()):
                score += 1.0
            score += float(data.get("importance", 0.5))
            if score > 0:
                scores.append((score, node_id, data))

        scores.sort(reverse=True, key=lambda item: item[0])
        if not scores:
            return ""

        lines = ["Knowledge graph context:"]
        for score, node_id, data in scores[:limit]:
            lines.append(f"- {data.get('label', node_id)} [{data.get('node_type', 'topic')}]")
            neighbors = self.get_related(data.get("label", node_id), depth=1, limit=3)
            for neighbor in neighbors[:3]:
                lines.append(f"  -> {neighbor['label']} ({neighbor['node_type']})")
        return "\n".join(lines)

    def summarize(self) -> dict:
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "types": self._type_counts(),
            "persistent": not self._use_memory_store,
        }

    def _type_counts(self) -> dict:
        counts = {}
        for _, data in self.graph.nodes(data=True):
            node_type = data.get("node_type", "topic")
            counts[node_type] = counts.get(node_type, 0) + 1
        return counts

    def __repr__(self) -> str:
        stats = self.summarize()
        return f"KnowledgeGraph(nodes={stats['nodes']}, edges={stats['edges']})"

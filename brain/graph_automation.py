"""
brain/graph_automation.py
--------------------------
Knowledge graph auto-maintenance — Phase 6.

Automatically creates nodes and edges in the knowledge graph based on
conversation topics, user interests, project activity, and research.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class GraphAutomation:
    """
    Automatically maintains the knowledge graph from conversation context.

    Creates nodes for:
    - Topics mentioned in conversation
    - User interests extracted from messages
    - Projects and their technologies
    - Research topics

    Creates edges for:
    - User → interest relationships
    - Project → technology relationships
    - Topic → topic co-occurrence
    """

    def __init__(self, llm=None):
        self.llm = llm
        self._graph = None
        self._last_updates: list[dict] = []

    def _lazy_graph(self):
        if self._graph is None:
            try:
                from hyper.knowledge_graph import KnowledgeGraph
                self._graph = KnowledgeGraph()
            except Exception as e:
                logger.debug(f"KnowledgeGraph unavailable: {e}")
        return self._graph

    def extract_and_store(self, user_input: str, response: str, user_name: str = "User") -> list[dict]:
        """
        Analyze a conversation turn and update the knowledge graph.

        Returns:
            List of update dicts describing what was added.
        """
        updates = []
        graph = self._lazy_graph()
        if not graph:
            return updates

        # 1. Extract named entities from the turn
        entities = self._extract_entities(user_input, response)
        for entity in entities:
            try:
                node_id = graph.add_node(
                    label=entity["label"],
                    node_type=entity.get("type", "topic"),
                    importance=entity.get("importance", 0.5),
                    properties={"extracted_at": datetime.now().isoformat()},
                )
                updates.append({
                    "action": "add_node",
                    "label": entity["label"],
                    "type": entity.get("type", "topic"),
                    "node_id": node_id,
                })
            except Exception as e:
                logger.debug(f"Graph node error: {e}")

        # 2. Link user to extracted topics
        for entity in entities[:5]:
            try:
                graph.add_relation(
                    source_label=user_name,
                    target_label=entity["label"],
                    relation="interested_in",
                    source_type="user",
                    target_type=entity.get("type", "topic"),
                    weight=entity.get("importance", 0.5),
                    evidence=f"Mentioned in conversation at {datetime.now().isoformat()}",
                )
                updates.append({
                    "action": "add_edge",
                    "source": user_name,
                    "target": entity["label"],
                    "relation": "interested_in",
                })
            except Exception as e:
                logger.debug(f"Graph edge error: {e}")

        # 3. Link co-occurring entities
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                try:
                    graph.add_relation(
                        source_label=entities[i]["label"],
                        target_label=entities[j]["label"],
                        relation="related_to",
                        source_type=entities[i].get("type", "topic"),
                        target_type=entities[j].get("type", "topic"),
                        weight=0.3,
                        evidence="Co-occurred in conversation",
                    )
                    updates.append({
                        "action": "add_edge",
                        "source": entities[i]["label"],
                        "target": entities[j]["label"],
                        "relation": "related_to",
                    })
                except Exception as e:
                    pass

        self._last_updates = updates
        return updates

    def _extract_entities(self, user_input: str, response: str) -> list[dict]:
        """Use LLM to extract named entities from the conversation turn."""
        if not self.llm:
            return self._heuristic_entities(user_input, response)

        text = f"User: {user_input}\nAssistant: {response}"[:2000]
        prompt = (
            "Extract key topics, technologies, concepts, and interests from this conversation turn.\n"
            "Return a JSON list of objects with keys: label, type (topic|technology|concept|project), importance (0.0-1.0).\n\n"
            f"Conversation:\n{text}\n\n"
            "JSON list:"
        )
        try:
            raw = self.llm.generate(prompt, temperature=0.2).strip()
            json_match = re.search(r"\[.*\]", raw, re.DOTALL)
            if json_match:
                entities = json.loads(json_match.group())
                if isinstance(entities, list):
                    return [
                        {
                            "label": str(e.get("label", "Unknown"))[:60],
                            "type": str(e.get("type", "topic"))[:20],
                            "importance": float(e.get("importance", 0.5)),
                        }
                        for e in entities
                        if e.get("label")
                    ]
        except Exception as e:
            logger.debug(f"Entity extraction error: {e}")

        return self._heuristic_entities(user_input, response)

    def _heuristic_entities(self, user_input: str, response: str) -> list[dict]:
        """Fallback entity extraction without LLM."""
        combined = user_input + " " + response
        words = re.findall(r"\b[A-Z][a-z]+\b", combined)
        seen = set()
        entities = []
        for word in words:
            lower = word.lower()
            if lower not in seen and len(word) > 3:
                seen.add(lower)
                entities.append({
                    "label": word,
                    "type": "topic",
                    "importance": 0.3,
                })
        return entities[:10]

    def link_project_to_tech(self, project_name: str, technologies: list[str]) -> list[dict]:
        """Link a project to its technologies in the graph."""
        updates = []
        graph = self._lazy_graph()
        if not graph:
            return updates

        for tech in technologies:
            try:
                graph.add_relation(
                    source_label=project_name,
                    target_label=tech,
                    relation="uses",
                    source_type="project",
                    target_type="technology",
                    weight=1.0,
                    evidence="Project dependency",
                )
                updates.append({
                    "action": "add_edge",
                    "source": project_name,
                    "target": tech,
                    "relation": "uses",
                })
            except Exception as e:
                logger.debug(f"Project-tech link error: {e}")

        self._last_updates.extend(updates)
        return updates

    def get_last_updates(self) -> list[dict]:
        return self._last_updates

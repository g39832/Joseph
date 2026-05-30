"""
memory/chroma_store.py
----------------------
Semantic (vector) memory for JOSEPH using ChromaDB.

ChromaDB stores memories as vector embeddings, enabling
semantic search — finding memories by meaning, not just keywords.

Example:
  You store: "I love hiking in the mountains"
  You search: "outdoor activities"
  ChromaDB finds it because the meanings are similar.

This is what makes Joseph feel like he truly "remembers" things
rather than just doing keyword lookups.

ChromaDB runs 100% locally — no API keys, no internet needed.
"""

import logging
from typing import Optional

from configs.settings import settings

logger = logging.getLogger(__name__)


class ChromaMemoryStore:
    """
    Vector-based semantic memory using ChromaDB.

    Stores text as embeddings for similarity search.
    Falls back gracefully if ChromaDB is unavailable.

    Usage:
        store = ChromaMemoryStore()
        store.add_memory("I prefer dark mode in all my editors")
        results = store.search("editor preferences")
    """

    def __init__(self):
        self._client = None
        self._collection = None
        self._available = False
        self._initialize()

    def _initialize(self) -> None:
        """
        Initialize ChromaDB client and collection.
        Fails gracefully — Joseph still works without it.
        """
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            # Persistent client — data saved to disk
            self._client = chromadb.PersistentClient(
                path=str(settings.CHROMA_DB_PATH),
                settings=ChromaSettings(
                    anonymized_telemetry=False,  # No data sent anywhere
                    allow_reset=True,
                ),
            )

            # Get or create the memory collection
            self._collection = self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},  # Cosine similarity
            )

            self._available = True
            count = self._collection.count()
            logger.info(
                f"ChromaDB ready: collection='{settings.CHROMA_COLLECTION}', "
                f"documents={count}"
            )

        except ImportError:
            logger.warning(
                "ChromaDB not installed. Semantic search disabled. "
                "Install with: pip install chromadb"
            )
        except Exception as e:
            logger.warning(
                f"ChromaDB initialization failed: {e}. "
                "Semantic search disabled. SQLite memory still works."
            )

    @property
    def is_available(self) -> bool:
        """Check if ChromaDB is ready to use."""
        return self._available and self._collection is not None

    def add_memory(
        self,
        content: str,
        memory_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Add a memory to the vector store.

        Args:
            content: The text to store and embed.
            memory_id: Optional unique ID (auto-generated if not provided).
            metadata: Optional dict of metadata to store alongside the embedding.

        Returns:
            True if stored successfully, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            import uuid
            from datetime import datetime

            doc_id = memory_id or str(uuid.uuid4())
            meta = metadata or {}
            meta["timestamp"] = datetime.now().isoformat()
            meta["source"] = meta.get("source", "conversation")

            self._collection.add(
                documents=[content],
                ids=[doc_id],
                metadatas=[meta],
            )
            logger.debug(f"ChromaDB: stored memory id={doc_id}")
            return True

        except Exception as e:
            logger.error(f"ChromaDB add_memory error: {e}")
            return False

    def search(
        self,
        query: str,
        n_results: int = 5,
        min_relevance: float = 0.3,
    ) -> list[dict]:
        """
        Search for semantically similar memories.

        Args:
            query: The search query text.
            n_results: Maximum number of results to return.
            min_relevance: Minimum similarity score (0-1, higher = more similar).

        Returns:
            List of dicts with keys: content, id, metadata, distance, relevance
        """
        if not self.is_available:
            return []

        try:
            # Don't search if collection is empty
            if self._collection.count() == 0:
                return []

            results = self._collection.query(
                query_texts=[query],
                n_results=min(n_results, self._collection.count()),
                include=["documents", "metadatas", "distances"],
            )

            memories = []
            if results and results["documents"] and results["documents"][0]:
                for doc, meta, dist in zip(
                    results["documents"][0],
                    results["metadatas"][0],
                    results["distances"][0],
                ):
                    # Convert cosine distance to similarity score (0-1)
                    relevance = 1 - dist
                    if relevance >= min_relevance:
                        memories.append(
                            {
                                "content": doc,
                                "metadata": meta,
                                "distance": dist,
                                "relevance": round(relevance, 3),
                            }
                        )

            logger.debug(
                f"ChromaDB search '{query[:30]}...': {len(memories)} results"
            )
            return memories

        except Exception as e:
            logger.error(f"ChromaDB search error: {e}")
            return []

    def format_search_results(self, results: list[dict]) -> str:
        """
        Format search results as readable text for LLM context injection.

        Args:
            results: Results from search().

        Returns:
            Formatted string of relevant memories.
        """
        if not results:
            return ""

        lines = ["Relevant memories:"]
        for i, result in enumerate(results, 1):
            relevance_pct = int(result["relevance"] * 100)
            lines.append(f"{i}. [{relevance_pct}% match] {result['content']}")

        return "\n".join(lines)

    def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a specific memory by ID.

        Args:
            memory_id: The ID of the memory to delete.

        Returns:
            True if deleted, False otherwise.
        """
        if not self.is_available:
            return False

        try:
            self._collection.delete(ids=[memory_id])
            logger.info(f"ChromaDB: deleted memory id={memory_id}")
            return True
        except Exception as e:
            logger.error(f"ChromaDB delete error: {e}")
            return False

    def upsert_memory(
        self,
        content: str,
        memory_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> bool:
        """
        Update an existing memory or insert it if it does not exist.

        This keeps the vector store aligned with edited long-term memories.
        """
        if not self.is_available:
            return False

        try:
            import uuid
            from datetime import datetime

            doc_id = memory_id or str(uuid.uuid4())
            meta = metadata or {}
            meta["timestamp"] = datetime.now().isoformat()
            meta["source"] = meta.get("source", "conversation")

            if hasattr(self._collection, "upsert"):
                self._collection.upsert(
                    documents=[content],
                    ids=[doc_id],
                    metadatas=[meta],
                )
            else:
                try:
                    self._collection.delete(ids=[doc_id])
                except Exception:
                    pass
                self._collection.add(
                    documents=[content],
                    ids=[doc_id],
                    metadatas=[meta],
                )
            logger.debug(f"ChromaDB: upserted memory id={doc_id}")
            return True
        except Exception as e:
            logger.error(f"ChromaDB upsert error: {e}")
            return False

    def get_count(self) -> int:
        """Return the number of stored memories."""
        if not self.is_available:
            return 0
        try:
            return self._collection.count()
        except Exception:
            return 0

    def reset(self) -> bool:
        """
        Clear all memories from the vector store.
        WARNING: This is irreversible.

        Returns:
            True if reset successfully.
        """
        if not self.is_available:
            return False

        try:
            self._client.delete_collection(settings.CHROMA_COLLECTION)
            self._collection = self._client.get_or_create_collection(
                name=settings.CHROMA_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            logger.warning("ChromaDB collection reset — all vector memories cleared")
            return True
        except Exception as e:
            logger.error(f"ChromaDB reset error: {e}")
            return False

    def __repr__(self) -> str:
        if self.is_available:
            return f"ChromaMemoryStore(available=True, count={self.get_count()})"
        return "ChromaMemoryStore(available=False)"

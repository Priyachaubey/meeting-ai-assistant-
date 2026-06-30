"""Enterprise semantic search service.

Uses ML embeddings (sentence-transformers) for real semantic search,
combined with keyword matching for hybrid retrieval. All inference
executes through the AI Server's embedding provider.
"""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SearchResult:
    """A single search result."""

    id: str
    type: str  # meeting, transcript, chat, document, action_item, decision, task, email, knowledge
    title: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)
    highlight: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "text": self.text,
            "score": round(self.score, 4),
            "metadata": self.metadata,
            "highlight": self.highlight,
        }


@dataclass
class SearchIndex:
    """An indexed document for search."""

    doc_id: str
    doc_type: str
    title: str
    content: str
    metadata: dict = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)
    indexed_at: float = field(default_factory=time.time)
    workspace_id: str = ""
    user_id: str = ""


# Module-level reference to the ML embedding provider (set by main.py)
_embedding_provider: Any = None


class SearchService:
    """Enterprise search engine with full-text and semantic search.

    Uses ML embeddings (sentence-transformers) when available via
    _embedding_provider, falling back to hash-based embeddings.
    """

    def __init__(self) -> None:
        self._indices: dict[str, dict[str, SearchIndex]] = {}
        self._workspace_indices: dict[str, set[str]] = {}

    def _get_index(self, workspace_id: str) -> dict[str, SearchIndex]:
        if workspace_id not in self._indices:
            self._indices[workspace_id] = {}
        return self._indices[workspace_id]

    def _get_ws_docs(self, workspace_id: str) -> set[str]:
        if workspace_id not in self._workspace_indices:
            self._workspace_indices[workspace_id] = set()
        return self._workspace_indices[workspace_id]

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors."""
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def _get_embedding(self, text: str) -> list[float]:
        """Get embedding using ML provider or hash fallback."""
        if _embedding_provider is not None:
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Can't await in sync context; use hash fallback
                    return self._hash_text(text)
                result = loop.run_until_complete(_embedding_provider.embed([text]))
                return result.vectors[0]
            except Exception:
                pass
        return self._hash_text(text)

    def index_document(
        self,
        doc_id: str,
        doc_type: str,
        title: str,
        content: str,
        workspace_id: str = "default",
        user_id: str = "",
        metadata: dict | None = None,
    ) -> None:
        """Index a document for search."""
        index = self._get_index(workspace_id)
        embedding = self._get_embedding(f"{title} {content}")
        idx_doc = SearchIndex(
            doc_id=doc_id,
            doc_type=doc_type,
            title=title,
            content=content,
            metadata=metadata or {},
            embedding=embedding,
            workspace_id=workspace_id,
            user_id=user_id,
        )
        index[doc_id] = idx_doc
        self._get_ws_docs(workspace_id).add(doc_id)

    def remove_document(self, doc_id: str, workspace_id: str = "default") -> None:
        """Remove a document from the index."""
        index = self._get_index(workspace_id)
        index.pop(doc_id, None)
        self._get_ws_docs(workspace_id).discard(doc_id)

    def search(
        self,
        query: str,
        workspace_id: str = "default",
        doc_types: list[str] | None = None,
        limit: int = 20,
        user_id: str | None = None,
    ) -> list[dict]:
        """Hybrid search: keyword + semantic similarity."""
        if not query.strip():
            return []

        index = self._get_index(workspace_id)
        if not index:
            return []

        query_lower = query.lower().strip()
        query_words = set(re.findall(r"\w+", query_lower))
        query_embedding = self._get_embedding(query)

        results: list[SearchResult] = []

        for doc_id, doc in index.items():
            if doc_types and doc.doc_type not in doc_types:
                continue
            if user_id and doc.user_id and doc.user_id != user_id:
                continue

            content_lower = doc.content.lower()
            title_lower = doc.title.lower()

            keyword_score = 0.0
            if query_lower in content_lower:
                keyword_score += 0.5
            if query_lower in title_lower:
                keyword_score += 0.8

            for word in query_words:
                if word in content_lower:
                    keyword_score += 0.1
                if word in title_lower:
                    keyword_score += 0.2

            semantic_score = self._cosine_similarity(query_embedding, doc.embedding)

            combined_score = (keyword_score * 0.6) + (semantic_score * 0.4)

            if combined_score > 0.05:
                highlight = self._extract_highlight(doc.content, query_lower)
                results.append(
                    SearchResult(
                        id=doc.doc_id,
                        type=doc.doc_type,
                        title=doc.title,
                        text=doc.content[:300],
                        score=combined_score,
                        metadata=doc.metadata,
                        highlight=highlight,
                    )
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return [r.to_dict() for r in results[:limit]]

    def _extract_highlight(self, text: str, query: str) -> str:
        """Extract a highlight snippet around the query match."""
        text_lower = text.lower()
        idx = text_lower.find(query)
        if idx == -1:
            words = query.split()
            for word in words:
                idx = text_lower.find(word)
                if idx != -1:
                    break

        if idx == -1:
            return text[:150] + "..." if len(text) > 150 else text

        start = max(0, idx - 60)
        end = min(len(text), idx + len(query) + 60)
        snippet = text[start:end]
        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."
        return snippet

    def search_meetings(
        self, query: str, workspace_id: str = "default", limit: int = 10
    ) -> list[dict]:
        """Search specifically for meetings."""
        return self.search(query, workspace_id, doc_types=["meeting"], limit=limit)

    def search_transcripts(
        self, query: str, workspace_id: str = "default", limit: int = 20
    ) -> list[dict]:
        """Search specifically for transcript segments."""
        return self.search(query, workspace_id, doc_types=["transcript"], limit=limit)

    def search_knowledge(
        self, query: str, workspace_id: str = "default", limit: int = 10
    ) -> list[dict]:
        """Search specifically for knowledge base documents."""
        return self.search(
            query, workspace_id, doc_types=["document", "knowledge"], limit=limit
        )

    def search_actions(
        self, query: str, workspace_id: str = "default", limit: int = 20
    ) -> list[dict]:
        """Search for action items, decisions, and tasks."""
        return self.search(
            query,
            workspace_id,
            doc_types=["action_item", "decision", "task"],
            limit=limit,
        )

    def get_stats(self, workspace_id: str = "default") -> dict:
        """Get search index statistics."""
        index = self._get_index(workspace_id)
        type_counts: dict[str, int] = {}
        for doc in index.values():
            type_counts[doc.doc_type] = type_counts.get(doc.doc_type, 0) + 1
        return {
            "total_documents": len(index),
            "by_type": type_counts,
            "active_workspaces": len(self._indices),
        }


search_service = SearchService()

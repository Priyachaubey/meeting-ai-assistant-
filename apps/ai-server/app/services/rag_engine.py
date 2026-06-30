"""RAG (Retrieval-Augmented Generation) Engine.

Production RAG pipeline: chunking → embedding → vector search →
context compression → LLM generation with citations.

All inference executes locally through the AI Server's
embedding and LLM providers.
"""

from __future__ import annotations

import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("convopilot.rag")


@dataclass
class Chunk:
    """A chunk of text with metadata."""

    chunk_id: str
    text: str
    embedding: list[float] = field(default_factory=list)
    source_id: str = ""
    source_type: str = ""  # meeting, document, transcript, knowledge
    title: str = ""
    metadata: dict = field(default_factory=dict)
    score: float = 0.0
    created_at: float = field(default_factory=time.time)


@dataclass
class RetrievalResult:
    """A single retrieval result with citation info."""

    chunk: Chunk
    score: float
    citation: str = ""


class RAGEngine:
    """Production RAG engine with vector retrieval and context compression.

    Features:
    - Semantic search via embedding provider
    - Hybrid retrieval (keyword + semantic)
    - Context compression for LLM
    - Citation tracking
    - Incremental indexing
    - Meeting and knowledge base integration
    """

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._source_chunks: dict[str, set[str]] = {}
        self._embedding_provider: Any = None
        self._llm_provider: Any = None

    def set_embedding_provider(self, provider: Any) -> None:
        self._embedding_provider = provider

    def set_llm_provider(self, provider: Any) -> None:
        self._llm_provider = provider

    # ── Chunking ────────────────────────────────────────────────────

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 512,
        overlap: int = 64,
        source_id: str = "",
        source_type: str = "document",
        title: str = "",
        metadata: dict | None = None,
    ) -> list[Chunk]:
        """Split text into overlapping chunks for indexing."""
        if not text.strip():
            return []

        words = text.split()
        chunks = []
        start = 0
        idx = 0

        while start < len(words):
            end = min(start + chunk_size, len(words))
            chunk_text = " ".join(words[start:end])
            chunk_id = hashlib.md5(
                f"{source_id}:{idx}:{chunk_text[:100]}".encode()
            ).hexdigest()[:16]

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
                    source_id=source_id,
                    source_type=source_type,
                    title=title,
                    metadata=metadata or {},
                )
            )
            start += chunk_size - overlap
            idx += 1

        return chunks

    # ── Indexing ────────────────────────────────────────────────────

    async def index(
        self,
        text: str,
        source_id: str,
        source_type: str = "document",
        title: str = "",
        metadata: dict | None = None,
    ) -> int:
        """Index a document by chunking, embedding, and storing."""
        chunks = self.chunk_text(
            text,
            source_id=source_id,
            source_type=source_type,
            title=title,
            metadata=metadata,
        )

        if not chunks:
            return 0

        # Remove old chunks for this source
        self._remove_source(source_id)

        # Generate embeddings
        if self._embedding_provider:
            texts = [c.text for c in chunks]
            result = await self._embedding_provider.embed(texts)
            for chunk, embedding in zip(chunks, result.vectors):
                chunk.embedding = embedding

        # Store chunks
        for chunk in chunks:
            self._chunks[chunk.chunk_id] = chunk
            self._source_chunks.setdefault(source_id, set()).add(chunk.chunk_id)

        logger.info(
            "rag_indexed",
            source_id=source_id,
            chunks=len(chunks),
            source_type=source_type,
        )
        return len(chunks)

    def _remove_source(self, source_id: str) -> None:
        """Remove all chunks for a source."""
        chunk_ids = self._source_chunks.pop(source_id, set())
        for cid in chunk_ids:
            self._chunks.pop(cid, None)

    # ── Retrieval ───────────────────────────────────────────────────

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
        min_score: float = 0.1,
    ) -> list[RetrievalResult]:
        """Retrieve relevant chunks for a query.

        Uses semantic search (cosine similarity on embeddings)
        combined with keyword matching for hybrid retrieval.
        """
        if not query.strip() or not self._chunks:
            return []

        # Get query embedding
        query_embedding: list[float] = []
        if self._embedding_provider:
            result = await self._embedding_provider.embed([query])
            query_embedding = result.vectors[0]

        results: list[RetrievalResult] = []

        for chunk in self._chunks.values():
            if source_types and chunk.source_type not in source_types:
                continue

            # Semantic score
            semantic_score = 0.0
            if query_embedding and chunk.embedding:
                semantic_score = self._cosine_similarity(
                    query_embedding, chunk.embedding
                )

            # Keyword score
            query_words = set(re.findall(r"\w+", query.lower()))
            chunk_words = set(re.findall(r"\w+", chunk.text.lower()))
            keyword_overlap = len(query_words & chunk_words) / max(len(query_words), 1)

            # Combined score (weighted)
            score = (semantic_score * 0.7) + (keyword_overlap * 0.3)

            if score >= min_score:
                citation = f"[{chunk.source_type}:{chunk.source_id}]"
                results.append(
                    RetrievalResult(chunk=chunk, score=score, citation=citation)
                )

        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    # ── Context Compression ─────────────────────────────────────────

    def compress_context(
        self,
        results: list[RetrievalResult],
        max_tokens: int = 2000,
    ) -> str:
        """Compress retrieval results into a context string for LLM.

        Deduplicates overlapping chunks and ranks by score.
        """
        if not results:
            return ""

        # Sort by score, deduplicate similar chunks
        seen_texts: set[str] = set()
        unique_results: list[RetrievalResult] = []

        for r in results:
            # Simple dedup: skip if we've seen very similar text
            text_key = r.chunk.text[:100].lower()
            if text_key in seen_texts:
                continue
            seen_texts.add(text_key)
            unique_results.append(r)

        # Build context with citations
        context_parts = []
        total_words = 0

        for r in unique_results:
            words = len(r.chunk.text.split())
            if total_words + words > max_tokens:
                # Truncate to fit
                remaining = max_tokens - total_words
                if remaining > 50:
                    truncated = " ".join(r.chunk.text.split()[:remaining])
                    context_parts.append(f"{r.citation} {truncated}...")
                break
            context_parts.append(f"{r.citation} {r.chunk.text}")
            total_words += words

        return "\n\n---\n\n".join(context_parts)

    # ── RAG Query ───────────────────────────────────────────────────

    async def query(
        self,
        question: str,
        top_k: int = 5,
        source_types: list[str] | None = None,
    ) -> dict:
        """Full RAG pipeline: retrieve → compress → generate.

        Returns answer with citations.
        """
        from app.providers.base import LLMMessage

        # Retrieve relevant chunks
        results = await self.retrieve(question, top_k=top_k, source_types=source_types)

        if not results:
            return {
                "answer": "No relevant information found in the knowledge base.",
                "citations": [],
                "sources_used": 0,
            }

        # Compress into context
        context = self.compress_context(results)

        # Generate answer with LLM
        if self._llm_provider:
            messages = [
                LLMMessage(
                    role="system",
                    content=(
                        "Answer the question using ONLY the provided context. "
                        "If the answer is not in the context, say so. "
                        "Include source citations in your answer."
                    ),
                ),
                LLMMessage(
                    role="user",
                    content=f"Context:\n{context}\n\nQuestion: {question}",
                ),
            ]
            response = await self._llm_provider.chat(messages, max_tokens=1000)
            answer = response.content
        else:
            answer = context

        citations = [
            {
                "source_id": r.chunk.source_id,
                "source_type": r.chunk.source_type,
                "text": r.chunk.text[:200],
                "score": round(r.score, 3),
                "citation": r.citation,
            }
            for r in results
        ]

        return {
            "answer": answer,
            "citations": citations,
            "sources_used": len(results),
        }

    # ── Utilities ───────────────────────────────────────────────────

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if len(a) != len(b) or not a:
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def get_stats(self) -> dict:
        total_chunks = len(self._chunks)
        type_counts: dict[str, int] = {}
        for c in self._chunks.values():
            type_counts[c.source_type] = type_counts.get(c.source_type, 0) + 1

        return {
            "total_chunks": total_chunks,
            "total_sources": len(self._source_chunks),
            "by_type": type_counts,
            "embedding_provider": (
                self._embedding_provider.provider_name
                if self._embedding_provider
                else "none"
            ),
            "llm_provider": (
                self._llm_provider.provider_name if self._llm_provider else "none"
            ),
        }


rag_engine = RAGEngine()

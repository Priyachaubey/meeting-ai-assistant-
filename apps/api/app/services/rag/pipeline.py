import logging
import time
import uuid
from dataclasses import dataclass

import httpx
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import settings
from app.core.security import create_access_token
from app.services.rag.chunking import chunk_text
from app.services.rag.embedding_cache import get_cached_embedding, store_embedding
from app.services.rag.loaders import DocumentLoadError, load_text
from app.services.usage import UsageEvent

logger = logging.getLogger("convopilot.rag")

# ── Embedding provider selection ────────────────────────────────────────────
# Resolved once at import time against settings.embedding_provider so that
# EMBEDDING_MODEL and EMBEDDING_DIM are always consistent, and Qdrant
# collections are always created with the right vector size for the current
# provider. If you switch providers on a deployment that already has data in
# Qdrant, you must delete the old collections and re-ingest — see config.py's
# `embedding_provider` comment for details.

if settings.embedding_provider == "openai":
    EMBEDDING_PROVIDER = "openai"
    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536
else:
    # "ai-server" (default) — sentence-transformers/all-MiniLM-L6-v2
    EMBEDDING_PROVIDER = "ai-server"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM = 384


class RagError(Exception):
    """Configuration or pipeline failure. ingest()/search() raise this rather than silently
    returning empty/fake results — consistent with this codebase's error handling elsewhere
    (LLMProviderError, TranscriptionProviderError, BillingError)."""


@dataclass
class RetrievedChunk:
    document_id: str
    text: str
    score: float
    source: str = "document"  # "document" (uploaded file) | "meeting" (indexed summary)
    meeting_id: str | None = None


def _collection_name(workspace_id: str) -> str:
    return f"knowledge_{workspace_id}"


def _point_id(workspace_id: str, identifier: str, chunk_index: int) -> str:
    # Deterministic UUID from (workspace, identifier, chunk index): re-ingesting the same
    # document/meeting overwrites its old chunks at the same points instead of duplicating
    # them. Qdrant point IDs must be an unsigned int or a real UUID string — uuid5 is exactly
    # the tool for a deterministic name-based UUID, not an arbitrary hex string.
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{workspace_id}:{identifier}:{chunk_index}"))


class RagPipeline:
    """NOTE: written against the documented qdrant-client 1.x synchronous API and the OpenAI
    embeddings endpoint from training knowledge — not exercised against a live Qdrant instance
    (no network access in this sandbox). Two things worth double-checking when you actually
    run this: (1) qdrant-client has been migrating `search()` towards `query_points()` across
    1.x releases — if the pinned 1.14.2 client warns or fails on `.search()`, switch to
    `.query_points()`, same arguments. (2) collection auto-creation here assumes the collection
    doesn't already exist with a different vector size from an earlier experiment — if you've
    manually created `knowledge_*` collections before, drop them first.

    One collection per WORKSPACE (not per individual user — changed from per-owner; see
    AUDIT.md for why) holds BOTH uploaded documents and indexed meeting summaries (tagged via
    RetrievedChunk.source) — "Knowledge Assistant" and "Universal Meeting Search" are the same
    search surface over the same data, not two separate systems, since asking "what did we
    decide about pricing" should be able to pull from a past meeting summary just as easily as
    an uploaded contract. Workspace-level scoping matches the shared-meeting-library model
    already established for Meeting (see models.Workspace) — a document one teammate uploads
    is visible to the whole workspace, the same way a meeting one teammate runs is. There's no
    "private to me" upload option yet — flagged as a real, deliberately-not-built nuance in
    AUDIT.md, not an oversight.

    ingest()/ingest_text()/search() return (result, list[UsageEvent]) — embedding calls cost
    real tokens just like chat completions, so they're tracked the same way. RagPipeline
    itself never touches a DB session (consistent with the rest of this codebase: providers
    and pipelines stay DB-agnostic, the route layer that already has a session persists usage
    events).
    """

    def __init__(self) -> None:
        self._qdrant: QdrantClient | None = None

    def _client(self) -> QdrantClient:
        if self._qdrant is None:
            self._qdrant = QdrantClient(url=settings.qdrant_url)
        return self._qdrant

    async def _embed(self, texts: list[str]) -> tuple[list[list[float]], UsageEvent]:
        # Per-text cache check before any I/O — same reasoning as before, now with the model
        # key correctly reflecting which provider/model was actually used.
        embeddings: list[list[float] | None] = [None] * len(texts)
        for i, text in enumerate(texts):
            embeddings[i] = await get_cached_embedding(EMBEDDING_MODEL, text)
        uncached_indices = [i for i, vec in enumerate(embeddings) if vec is None]

        if not uncached_indices:
            usage = UsageEvent(
                operation="embedding", provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL,
                prompt_tokens=0, completion_tokens=0, latency_ms=0.0, success=True,
            )
            return embeddings, usage  # type: ignore[return-value]

        uncached_texts = [texts[i] for i in uncached_indices]
        start = time.monotonic()

        if EMBEDDING_PROVIDER == "ai-server":
            fresh, usage = await self._embed_via_ai_server(uncached_texts, start)
        else:
            fresh, usage = await self._embed_via_openai(uncached_texts, start)

        for local_idx, original_idx in enumerate(uncached_indices):
            embeddings[original_idx] = fresh[local_idx]
            await store_embedding(EMBEDDING_MODEL, texts[original_idx], fresh[local_idx])

        return embeddings, usage  # type: ignore[return-value]

    async def _embed_via_ai_server(self, texts: list[str], start: float) -> tuple[list[list[float]], UsageEvent]:
        """Call apps/ai-server's /api/ai/embed — sentence-transformers, 384-dim vectors."""
        token = create_access_token(subject="api-service", minutes=5)
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    f"{settings.ai_server_url.rstrip('/')}/api/ai/embed",
                    json={"texts": texts},
                    headers={"Authorization": f"Bearer {token}"},
                )
        except httpx.RequestError as exc:
            usage = UsageEvent(
                operation="embedding", provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL,
                prompt_tokens=0, success=False, error_message=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
            )
            raise RagError(f"ai-server unreachable for embeddings: {exc}") from exc

        if resp.status_code != 200:
            err = resp.text[:200]
            usage = UsageEvent(
                operation="embedding", provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL,
                prompt_tokens=0, success=False, error_message=err,
                latency_ms=(time.monotonic() - start) * 1000,
            )
            raise RagError(f"ai-server /embed returned {resp.status_code}: {err}")

        try:
            data = resp.json()
            vectors: list[list[float]] = data["vectors"]
        except (ValueError, KeyError) as exc:
            raise RagError(f"ai-server /embed returned unexpected shape: {exc}") from exc

        usage = UsageEvent(
            operation="embedding", provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL,
            prompt_tokens=data.get("token_count", len(texts)), completion_tokens=0,
            latency_ms=(time.monotonic() - start) * 1000, success=True,
        )
        return vectors, usage

    async def _embed_via_openai(self, texts: list[str], start: float) -> tuple[list[list[float]], UsageEvent]:
        """Fall-back path: OpenAI text-embedding-3-small, 1536-dim vectors."""
        if not settings.openai_api_key:
            raise RagError(
                "OPENAI_API_KEY is not set — set embedding_provider=ai-server in .env "
                "to use the self-hosted engine instead."
            )
        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=settings.llm_timeout_seconds)
        try:
            response = await client.embeddings.create(model=EMBEDDING_MODEL, input=texts)
        except Exception as exc:
            usage = UsageEvent(
                operation="embedding", provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL,
                prompt_tokens=0, success=False, error_message=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
            )
            raise RagError(f"OpenAI embedding request failed: {exc}") from exc

        usage = UsageEvent(
            operation="embedding", provider=EMBEDDING_PROVIDER, model=EMBEDDING_MODEL,
            prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
            completion_tokens=0,
            latency_ms=(time.monotonic() - start) * 1000,
            success=True,
        )
        return [item.embedding for item in response.data], usage

    def _ensure_collection(self, name: str) -> None:
        client = self._client()
        try:
            existing = {c.name for c in client.get_collections().collections}
        except Exception as exc:
            raise RagError(f"Could not reach Qdrant at {settings.qdrant_url}: {exc}") from exc
        if name not in existing:
            client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
            )
            logger.info("Created Qdrant collection %s", name)

    async def _ingest_chunked_text(
        self, workspace_id: str, identifier: str, text: str, *, source: str, meeting_id: str | None = None
    ) -> tuple[str, list[UsageEvent]]:
        chunks = chunk_text(text)
        if not chunks:
            raise RagError(f"'{identifier}' produced no usable chunks after extraction.")

        embeddings, usage = await self._embed(chunks)
        collection = _collection_name(workspace_id)
        self._ensure_collection(collection)

        points = [
            PointStruct(
                id=_point_id(workspace_id, identifier, i),
                vector=embedding,
                payload={
                    "document_id": identifier,
                    "text": chunk,
                    "chunk_index": i,
                    "source": source,
                    "meeting_id": meeting_id,
                },
            )
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings))
        ]
        try:
            self._client().upsert(collection_name=collection, points=points)
        except Exception as exc:
            raise RagError(f"Qdrant upsert failed: {exc}") from exc

        logger.info("Ingested %s (%s): %d chunks into %s", identifier, source, len(points), collection)
        return collection, [usage]

    async def ingest(self, workspace_id: str, filename: str, content: bytes) -> tuple[str, list[UsageEvent]]:
        try:
            text = load_text(filename, content)
        except DocumentLoadError as exc:
            raise RagError(str(exc)) from exc
        return await self._ingest_chunked_text(workspace_id, filename, text, source="document")

    async def ingest_text(
        self, workspace_id: str, identifier: str, text: str, *, meeting_id: str
    ) -> tuple[str, list[UsageEvent]]:
        """For already-extracted text that isn't a file upload — specifically, meeting
        summaries (see routes/meetings.py's meeting_summary, which calls this after generating
        a fresh summary so it becomes searchable). Separate from ingest() because there's no
        file/extension to dispatch a loader on; this skips straight to chunking."""
        return await self._ingest_chunked_text(workspace_id, identifier, text, source="meeting", meeting_id=meeting_id)

    async def search(self, workspace_id: str, query: str, limit: int = 6) -> tuple[list[RetrievedChunk], list[UsageEvent]]:
        collection = _collection_name(workspace_id)
        client = self._client()
        try:
            existing = {c.name for c in client.get_collections().collections}
        except Exception as exc:
            raise RagError(f"Could not reach Qdrant at {settings.qdrant_url}: {exc}") from exc
        if collection not in existing:
            return [], []  # nothing uploaded yet for this user — not an error, just no results

        [query_embedding], usage = await self._embed([query])
        try:
            results = client.search(collection_name=collection, query_vector=query_embedding, limit=limit)
        except Exception as exc:
            raise RagError(f"Qdrant search failed: {exc}") from exc

        retrieved = [
            RetrievedChunk(
                document_id=r.payload.get("document_id", "unknown") if r.payload else "unknown",
                text=r.payload.get("text", "") if r.payload else "",
                score=r.score,
                source=r.payload.get("source", "document") if r.payload else "document",
                meeting_id=r.payload.get("meeting_id") if r.payload else None,
            )
            for r in results
        ]
        return retrieved, [usage]

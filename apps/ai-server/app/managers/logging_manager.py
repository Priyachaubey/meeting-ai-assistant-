"""Logging Manager – structured audit logging for AI operations."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class AuditEntry:
    timestamp: str
    operation: str
    provider: str
    model: str
    user_id: str | None = None
    session_id: str | None = None
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cost_usd: float | None = None
    success: bool = True
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class LoggingManager:
    """Structured audit log for all AI operations."""

    def __init__(self, max_entries: int = 10_000) -> None:
        self._entries: list[AuditEntry] = []
        self._max = max_entries

    def record(self, entry: AuditEntry) -> None:
        self._entries.append(entry)
        if len(self._entries) > self._max:
            self._entries = self._entries[-self._max :]
        logger.info(
            "ai_operation",
            operation=entry.operation,
            provider=entry.provider,
            model=entry.model,
            tokens_in=entry.tokens_in,
            tokens_out=entry.tokens_out,
            latency_ms=entry.latency_ms,
            success=entry.success,
        )

    def log_llm_call(
        self,
        *,
        operation: str,
        provider: str,
        model: str,
        tokens_in: int = 0,
        tokens_out: int = 0,
        latency_ms: float = 0.0,
        cost_usd: float | None = None,
        success: bool = True,
        error: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> None:
        self.record(
            AuditEntry(
                timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                operation=operation,
                provider=provider,
                model=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                latency_ms=latency_ms,
                cost_usd=cost_usd,
                success=success,
                error=error,
                user_id=user_id,
                session_id=session_id,
            )
        )

    def get_entries(
        self,
        *,
        limit: int = 100,
        operation: str | None = None,
        provider: str | None = None,
        success: bool | None = None,
    ) -> list[dict[str, Any]]:
        entries = self._entries
        if operation:
            entries = [e for e in entries if e.operation == operation]
        if provider:
            entries = [e for e in entries if e.provider == provider]
        if success is not None:
            entries = [e for e in entries if e.success == success]
        return [
            {
                "timestamp": e.timestamp,
                "operation": e.operation,
                "provider": e.provider,
                "model": e.model,
                "tokens_in": e.tokens_in,
                "tokens_out": e.tokens_out,
                "latency_ms": e.latency_ms,
                "cost_usd": e.cost_usd,
                "success": e.success,
                "error": e.error,
            }
            for e in entries[-limit:]
        ]

    def get_summary(self) -> dict[str, Any]:
        total = len(self._entries)
        successful = sum(1 for e in self._entries if e.success)
        total_tokens_in = sum(e.tokens_in for e in self._entries)
        total_tokens_out = sum(e.tokens_out for e in self._entries)
        total_cost = sum(e.cost_usd or 0 for e in self._entries)
        avg_latency = sum(e.latency_ms for e in self._entries) / total if total else 0
        return {
            "total_operations": total,
            "successful": successful,
            "failed": total - successful,
            "total_tokens_in": total_tokens_in,
            "total_tokens_out": total_tokens_out,
            "total_cost_usd": round(total_cost, 6),
            "avg_latency_ms": round(avg_latency, 2),
        }


logging_manager = LoggingManager()

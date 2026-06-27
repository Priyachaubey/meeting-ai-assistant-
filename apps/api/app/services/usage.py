from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.entities import AIUsageEvent
from app.services.llm.pricing import estimate_cost_usd


@dataclass
class UsageEvent:
    """Provider-agnostic usage record, produced by orchestrator/RAG calls and persisted by
    the route layer (which owns the DB session) via record_usage() below — providers and the
    orchestrator stay DB-agnostic, consistent with the rest of this codebase."""

    operation: str  # "chat_completion" | "embedding"
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int = 0
    latency_ms: float = 0.0
    success: bool = True
    error_message: str | None = None


def record_usage(
    db: Session,
    event: UsageEvent,
    *,
    owner_id: str | None = None,
    meeting_id: str | None = None,
) -> AIUsageEvent:
    cost = estimate_cost_usd(event.provider, event.model, event.prompt_tokens, event.completion_tokens)
    row = AIUsageEvent(
        owner_id=owner_id,
        meeting_id=meeting_id,
        operation=event.operation,
        provider=event.provider,
        model=event.model,
        prompt_tokens=event.prompt_tokens,
        completion_tokens=event.completion_tokens,
        cost_usd=cost,
        latency_ms=event.latency_ms,
        success=event.success,
        error_message=event.error_message,
    )
    db.add(row)
    db.commit()
    return row


@dataclass
class UsageSummary:
    total_events: int
    successful_events: int
    failed_events: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_cost_usd: float
    avg_latency_ms: float
    by_provider: dict[str, dict]


def get_usage_summary(db: Session, *, owner_id: str | None = None, since: datetime | None = None) -> UsageSummary:
    """Real SQL aggregation over ai_usage_events — this *is* the AI analytics backend.
    Pass owner_id to scope to one user's usage, or None for a workspace-wide view (only
    appropriate for an admin-facing endpoint — routes/ai.py restricts this, this function
    doesn't enforce authorization itself).

    Aggregates in Python after a single filtered query rather than SQL GROUP BY — fine at
    today's (zero) data volume, and simpler to read/test. Once this table has real rows in
    the hundreds of thousands, move the per-provider grouping to SQL (func.sum/func.count
    with group_by) instead of loading every row into memory — not worth the complexity
    before there's data that needs it."""
    query = db.query(AIUsageEvent)
    if owner_id is not None:
        query = query.filter(AIUsageEvent.owner_id == owner_id)
    if since is not None:
        query = query.filter(AIUsageEvent.created_at >= since)

    rows = query.all()
    total_events = len(rows)
    successful = [r for r in rows if r.success]
    failed = [r for r in rows if not r.success]
    total_cost = sum(r.cost_usd for r in rows if r.cost_usd is not None)
    avg_latency = sum(r.latency_ms for r in rows) / total_events if total_events else 0.0

    by_provider: dict[str, dict] = {}
    for r in rows:
        bucket = by_provider.setdefault(
            r.provider, {"events": 0, "successes": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0}
        )
        bucket["events"] += 1
        bucket["successes"] += int(r.success)
        bucket["prompt_tokens"] += r.prompt_tokens
        bucket["completion_tokens"] += r.completion_tokens
        bucket["cost_usd"] += r.cost_usd or 0.0

    return UsageSummary(
        total_events=total_events,
        successful_events=len(successful),
        failed_events=len(failed),
        total_prompt_tokens=sum(r.prompt_tokens for r in rows),
        total_completion_tokens=sum(r.completion_tokens for r in rows),
        total_cost_usd=total_cost,
        avg_latency_ms=avg_latency,
        by_provider=by_provider,
    )


def get_usage_summary_last_n_days(db: Session, *, owner_id: str | None, days: int) -> UsageSummary:
    return get_usage_summary(db, owner_id=owner_id, since=datetime.utcnow() - timedelta(days=days))

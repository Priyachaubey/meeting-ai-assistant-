"""Health Manager – aggregated health status for the AI Server."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import structlog

from app.managers.provider_manager import provider_manager
from app.managers.agent_manager import agent_manager
from app.managers.memory_manager import memory_manager
from app.managers.model_manager import model_manager

logger = structlog.get_logger()


@dataclass
class HealthStatus:
    status: str  # healthy | degraded | unhealthy
    version: str
    uptime_seconds: float
    components: dict[str, Any]
    timestamp: str


_start_time = time.monotonic()


class HealthManager:
    """Aggregates health from all subsystems."""

    async def check(self) -> HealthStatus:
        import datetime

        provider_health = await provider_manager.health_check_all()
        all_healthy = all(provider_health.values()) if provider_health else True

        components = {
            "providers": provider_health,
            "agents": agent_manager.get_stats(),
            "memory": memory_manager.get_status(),
            "models": {"count": len(model_manager.list_all())},
        }

        return HealthStatus(
            status="healthy" if all_healthy else "degraded",
            version="1.0.0",
            uptime_seconds=round(time.monotonic() - _start_time, 2),
            components=components,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        )


health_manager = HealthManager()

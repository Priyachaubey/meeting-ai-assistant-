"""Agent Manager – lifecycle and orchestration for AI agents.

Agents are reusable AI workflows (e.g., summarization, question detection,
action item extraction) that can be composed and invoked across products.
"""

from __future__ import annotations

import abc
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from app.providers.base import LLMMessage

logger = structlog.get_logger()


@dataclass
class AgentResult:
    """Result from an agent execution."""

    agent_name: str
    output: dict[str, Any]
    latency_ms: float = 0.0
    tokens_used: int = 0
    success: bool = True
    error: str | None = None


class BaseAgent(abc.ABC):
    """Abstract base for all AI agents."""

    @property
    @abc.abstractmethod
    def name(self) -> str: ...

    @property
    def description(self) -> str:
        return ""

    @abc.abstractmethod
    async def execute(self, context: dict[str, Any]) -> AgentResult: ...


class AgentManager:
    """Registry and orchestrator for AI agents."""

    def __init__(self) -> None:
        self._agents: dict[str, BaseAgent] = {}
        self._execution_log: list[dict[str, Any]] = []

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent
        logger.info("agent_registered", agent=agent.name)

    def get(self, name: str) -> BaseAgent | None:
        return self._agents.get(name)

    def list_agents(self) -> list[dict[str, str]]:
        return [
            {"name": a.name, "description": a.description}
            for a in self._agents.values()
        ]

    async def execute(self, agent_name: str, context: dict[str, Any]) -> AgentResult:
        agent = self._agents.get(agent_name)
        if agent is None:
            return AgentResult(
                agent_name=agent_name,
                output={},
                success=False,
                error=f"Agent '{agent_name}' not found",
            )

        start = time.monotonic()
        try:
            result = await agent.execute(context)
            result.latency_ms = (time.monotonic() - start) * 1000
            self._execution_log.append(
                {
                    "agent": agent_name,
                    "success": result.success,
                    "latency_ms": result.latency_ms,
                    "tokens": result.tokens_used,
                }
            )
            return result
        except Exception as exc:
            latency = (time.monotonic() - start) * 1000
            logger.error("agent_execution_failed", agent=agent_name, error=str(exc))
            return AgentResult(
                agent_name=agent_name,
                output={},
                latency_ms=latency,
                success=False,
                error=str(exc),
            )

    async def execute_many(
        self, agent_names: list[str], context: dict[str, Any]
    ) -> list[AgentResult]:
        """Execute multiple agents sequentially with shared context."""
        results = []
        for name in agent_names:
            result = await self.execute(name, context)
            results.append(result)
            # Merge output into context for downstream agents
            context.update(result.output)
        return results

    def get_stats(self) -> dict[str, Any]:
        total = len(self._execution_log)
        successful = sum(1 for e in self._execution_log if e["success"])
        avg_latency = (
            sum(e["latency_ms"] for e in self._execution_log) / total if total else 0
        )
        return {
            "registered_agents": len(self._agents),
            "total_executions": total,
            "successful": successful,
            "failed": total - successful,
            "avg_latency_ms": round(avg_latency, 2),
        }


agent_manager = AgentManager()

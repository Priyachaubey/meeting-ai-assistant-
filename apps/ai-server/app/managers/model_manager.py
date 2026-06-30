"""Model Manager – tracks available models and their capabilities.

This manager maintains a registry of models across all providers,
their capabilities, pricing, and rate limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass
class ModelInfo:
    """Metadata for a single model."""

    model_id: str
    provider: str
    capability: str  # llm | embedding | speech | translation | vision | ocr | tts
    display_name: str = ""
    max_tokens: int = 4096
    input_cost_per_1k: float = 0.0
    output_cost_per_1k: float = 0.0
    rate_limit_rpm: int = 60
    capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelManager:
    """Registry of all available AI models."""

    def __init__(self) -> None:
        self._models: dict[str, ModelInfo] = {}

    def register(self, info: ModelInfo) -> None:
        key = f"{info.provider}:{info.model_id}"
        self._models[key] = info
        logger.info(
            "model_registered",
            model=info.model_id,
            provider=info.provider,
            capability=info.capability,
        )

    def get(self, provider: str, model_id: str) -> ModelInfo | None:
        return self._models.get(f"{provider}:{model_id}")

    def list_by_capability(self, capability: str) -> list[ModelInfo]:
        return [m for m in self._models.values() if m.capability == capability]

    def list_all(self) -> list[ModelInfo]:
        return list(self._models.values())

    def get_status(self) -> list[dict[str, Any]]:
        return [
            {
                "model_id": m.model_id,
                "provider": m.provider,
                "capability": m.capability,
                "display_name": m.display_name or m.model_id,
                "max_tokens": m.max_tokens,
            }
            for m in self._models.values()
        ]


model_manager = ModelManager()

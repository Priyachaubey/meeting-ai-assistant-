"""AI Server API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    messages: list[dict[str, str]]
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = False
    session_id: str | None = None


class ChatResponse(BaseModel):
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0


class EmbedRequest(BaseModel):
    texts: list[str]


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    model: str
    provider: str
    token_count: int = 0
    latency_ms: float = 0.0


class TranslateRequest(BaseModel):
    text: str
    source_language: str = "auto"
    target_language: str = "en"


class TranslateResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    provider: str
    model: str
    latency_ms: float = 0.0


class TranscribeRequest(BaseModel):
    language: str = "en"


class TranscribeResponse(BaseModel):
    text: str
    segments: list[dict]
    provider: str
    model: str
    duration_seconds: float = 0.0
    latency_ms: float = 0.0


class VisionRequest(BaseModel):
    prompt: str = "Describe this image in detail."


class VisionResponse(BaseModel):
    description: str
    labels: list[str] = []
    provider: str
    model: str
    latency_ms: float = 0.0


class OCRRequest(BaseModel):
    language: str = "en"


class OCRResponse(BaseModel):
    text: str
    blocks: list[dict] = []
    provider: str
    model: str
    latency_ms: float = 0.0


class AgentExecuteRequest(BaseModel):
    agent_name: str
    context: dict = Field(default_factory=dict)


class AgentExecuteResponse(BaseModel):
    agent_name: str
    output: dict
    latency_ms: float = 0.0
    success: bool = True
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    components: dict


class ProviderStatusResponse(BaseModel):
    providers: dict


class ModelListResponse(BaseModel):
    models: list[dict]


class AuditLogResponse(BaseModel):
    entries: list[dict]
    summary: dict


class MemorySessionRequest(BaseModel):
    session_id: str
    max_entries: int = 100


class MemoryAddRequest(BaseModel):
    session_id: str
    role: str = "user"
    content: str
    metadata: dict = {}


class MemoryGetRequest(BaseModel):
    session_id: str
    limit: int | None = None

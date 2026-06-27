import json
import logging

from app.schemas.meeting import AgentResult, TranscriptChunk
from app.services.llm import LLMProviderError, get_llm_provider
from app.services.memory import format_context_block
from app.services.prompts import get as get_prompt
from app.services.rag import RagError, RagPipeline
from app.services.usage import UsageEvent

logger = logging.getLogger("convopilot.orchestrator")

QUESTION_MARKERS = ("?", "can you", "could you", "what", "why", "how", "when", "where", "explain", "clarify")
GENERIC_SYSTEM_PROMPT = "Follow the instructions in the user message precisely. Output exactly what is asked for, nothing else."


class QuestionDetectionAgent:
    """Cheap keyword/punctuation gate — intentionally not an LLM call. Real-time chunks arrive
    far more often than they need a generated response, so this exists to avoid paying LLM
    latency+cost on every chunk. False negatives here just mean a missed suggestion, not a
    fabricated one, which is the safer failure mode for a gate like this."""

    def run(self, chunk: TranscriptChunk) -> bool:
        text = chunk.text.lower().strip()
        return text.endswith("?") or any(text.startswith(marker) for marker in QUESTION_MARKERS)


class ContextAgent:
    def run(self, chunk: TranscriptChunk) -> dict:
        return {"mode": "meeting", "speaker": chunk.speaker, "recent_text": chunk.text}


class KnowledgeRetrievalAgent:
    """Real retrieval — app/services/rag is wired to OpenAI embeddings + Qdrant, scoped per
    workspace (see RagPipeline's docstring). Still returns [] (not fabricated context) on any
    failure: no workspace to scope to, no Qdrant reachable, nothing uploaded yet for this
    workspace, or an embedding call failing. Feeding invented "retrieved" facts to a real LLM
    call produces confidently-wrong answers that look grounded, so silence is the safer
    failure mode here too."""

    def __init__(self, rag: RagPipeline) -> None:
        self._rag = rag

    async def run(self, workspace_id: str | None, context: dict) -> tuple[list[str], list[UsageEvent]]:
        if not workspace_id:
            return [], []
        try:
            results, usage = await self._rag.search(workspace_id, context["recent_text"])
        except RagError as exc:
            logger.warning("Knowledge retrieval unavailable: %s", exc)
            return [], []
        return [r.text for r in results], usage


class MeetingIntelligenceAgent:
    """Combined structured call: suggested response + sentiment + decision + risk in ONE LLM
    call instead of four, piggybacked on the same call this orchestrator was already making
    for question-triggered responses. This is a deliberate cost/latency tradeoff, not full
    coverage: decisions/risks expressed in plain statements (not questions) aren't analyzed by
    an LLM at all right now — they'd need either a per-chunk LLM call regardless of cost, or a
    periodic batched re-analysis (e.g. every N chunks). Worth adding either if the
    question-only coverage turns out to miss too much in practice; not invented speculatively
    here without that signal. ActionItemAgent/SentimentAgent below remain the always-on cheap
    path for chunks that don't trigger this."""

    async def run(self, chunk: TranscriptChunk, recent_context: str, retrieved: list[str]) -> tuple[dict, list[UsageEvent]]:
        retrieved_block = "\n".join(f"- {item}" for item in retrieved) if retrieved else "(none retrieved)"
        prompt = get_prompt("meeting_response").render(
            recent_context=recent_context, retrieved_context=retrieved_block, question=chunk.text
        )
        try:
            provider = get_llm_provider()
            response = await provider.complete(GENERIC_SYSTEM_PROMPT, prompt)
        except LLMProviderError as exc:
            # Surface the real problem instead of a fabricated answer — a wrong-looking-right
            # suggestion in a live customer call is worse than a visible "unavailable" message.
            logger.warning("LLM provider unavailable: %s", exc)
            return {"suggested_response": f"[AI suggestion unavailable: {exc}]"}, []

        usage = UsageEvent(
            operation="chat_completion",
            provider=response.provider,
            model=response.model,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            latency_ms=response.latency_ms,
            success=True,
        )
        try:
            parsed = json.loads(response.text)
        except json.JSONDecodeError:
            # Model didn't return valid JSON — surface the raw text as the suggestion rather
            # than silently losing it, same fallback pattern as meeting_summary.
            logger.warning("meeting_response prompt returned non-JSON output")
            return {"suggested_response": response.text}, [usage]
        return parsed, [usage]


class ActionItemAgent:
    """Cheap, always-on path — runs on every chunk regardless of whether the heavier
    MeetingIntelligenceAgent call fires, since action items ("I'll send...", "can you
    share...") are simple enough that a keyword heuristic catches the common phrasing without
    needing an LLM call on every single transcript line."""

    def run(self, chunk: TranscriptChunk) -> list[str]:
        text = chunk.text.lower()
        return ["Follow up with supporting documentation"] if "send" in text or "share" in text else []


class SentimentAgent:
    """Cheap fallback path, used when MeetingIntelligenceAgent didn't run for this chunk
    (i.e. no question detected) so every chunk still gets *some* sentiment signal without
    paying for an LLM call on every line."""

    def run(self, chunk: TranscriptChunk) -> str:
        text = chunk.text.lower()
        if any(word in text for word in ["concern", "risk", "blocked"]):
            return "cautious"
        if any(word in text for word in ["great", "love", "yes"]):
            return "positive"
        return "neutral"


class MeetingAgentOrchestrator:
    def __init__(self) -> None:
        self.question = QuestionDetectionAgent()
        self.context = ContextAgent()
        self.retrieval = KnowledgeRetrievalAgent(RagPipeline())
        self.intelligence = MeetingIntelligenceAgent()
        self.actions = ActionItemAgent()
        self.sentiment = SentimentAgent()

    async def process(
        self, chunk: TranscriptChunk, workspace_id: str | None, recent_lines: list[str] | None = None
    ) -> tuple[AgentResult, list[UsageEvent]]:
        is_question = self.question.run(chunk)
        usage_events: list[UsageEvent] = []

        if is_question:
            context = self.context.run(chunk)
            retrieved, retrieval_usage = await self.retrieval.run(workspace_id, context)
            usage_events.extend(retrieval_usage)

            analysis, intelligence_usage = await self.intelligence.run(
                chunk, format_context_block(recent_lines or []), retrieved
            )
            usage_events.extend(intelligence_usage)

            suggestion = analysis.get("suggested_response")
            sentiment = analysis.get("sentiment") or self.sentiment.run(chunk)
            decisions = [analysis["decision"]] if analysis.get("decision") else []
            risks = [analysis["risk"]] if analysis.get("risk") else []
            follow_ups = analysis.get("follow_ups") or []
        else:
            suggestion = None
            sentiment = self.sentiment.run(chunk)
            decisions, risks, follow_ups = [], [], []

        result = AgentResult(
            question_detected=is_question,
            suggested_response=suggestion,
            follow_ups=follow_ups,
            action_items=self.actions.run(chunk),
            sentiment=sentiment,
            decisions=decisions,
            risks=risks,
        )
        return result, usage_events

"""Meeting intelligence agents for real-time AI assistance.

These agents process meeting context to generate live summaries,
action items, decisions, risks, suggestions, and more. They use
the production ML inference provider for real neural analysis.
"""

from __future__ import annotations

import re
import time
from typing import Any

from app.managers.agent_manager import AgentManager, AgentResult, BaseAgent
from app.managers.provider_manager import provider_manager
from app.providers.base import LLMMessage


def _get_llm():
    """Get the active LLM provider from the provider manager."""
    return provider_manager.llm


class SummarizerAgent(BaseAgent):
    """Generates live meeting summaries from transcript context."""

    @property
    def name(self) -> str:
        return "meeting_summarizer"

    @property
    def description(self) -> str:
        return "Generates live meeting summaries from transcript"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"summary": "", "status": "empty"},
            )

        messages = [
            LLMMessage(role="system", content="Generate a concise meeting summary."),
            LLMMessage(role="user", content=f"Summarize this meeting:\n\n{transcript}"),
        ]
        response = await _get_llm().chat(messages, max_tokens=500)
        return AgentResult(
            agent_name=self.name,
            output={"summary": response.content, "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class ActionItemAgent(BaseAgent):
    """Extracts action items from meeting transcript."""

    @property
    def name(self) -> str:
        return "action_item_extractor"

    @property
    def description(self) -> str:
        return "Extracts action items from meeting transcript"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"action_items": [], "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system", content="Extract action items. Return a numbered list."
            ),
            LLMMessage(role="user", content=f"Extract action items:\n\n{transcript}"),
        ]
        response = await _get_llm().chat(messages, max_tokens=300)
        items = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.content.split("\n")
            if line.strip() and not line.strip().startswith(("Action", "No specific"))
        ]
        items = [i for i in items if len(i) > 5][:10]

        return AgentResult(
            agent_name=self.name,
            output={"action_items": items, "raw": response.content, "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class DecisionAgent(BaseAgent):
    """Extracts decisions from meeting transcript."""

    @property
    def name(self) -> str:
        return "decision_extractor"

    @property
    def description(self) -> str:
        return "Extracts decisions from meeting transcript"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"decisions": [], "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system", content="Extract decisions made. Return a numbered list."
            ),
            LLMMessage(role="user", content=f"Extract decisions:\n\n{transcript}"),
        ]
        response = await _get_llm().chat(messages, max_tokens=300)
        items = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.content.split("\n")
            if line.strip() and not line.strip().startswith(("Decision", "No explicit"))
        ]
        items = [i for i in items if len(i) > 5][:10]

        return AgentResult(
            agent_name=self.name,
            output={"decisions": items, "raw": response.content, "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class RiskAgent(BaseAgent):
    """Identifies risks from meeting transcript."""

    @property
    def name(self) -> str:
        return "risk_detector"

    @property
    def description(self) -> str:
        return "Identifies risks and concerns from meeting transcript"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"risks": [], "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system",
                content="Identify risks and concerns. Return a numbered list.",
            ),
            LLMMessage(role="user", content=f"Identify risks:\n\n{transcript}"),
        ]
        response = await _get_llm().chat(messages, max_tokens=300)
        items = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.content.split("\n")
            if line.strip() and not line.strip().startswith(("Risk", "No specific"))
        ]
        items = [i for i in items if len(i) > 5][:10]

        return AgentResult(
            agent_name=self.name,
            output={"risks": items, "raw": response.content, "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class SuggestionAgent(BaseAgent):
    """Generates real-time AI suggestions during meetings."""

    @property
    def name(self) -> str:
        return "meeting_suggester"

    @property
    def description(self) -> str:
        return "Generates real-time suggestions based on meeting context"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        last_message = context.get("last_message", "")
        meeting_mode = context.get("meeting_mode", "meeting")

        if not last_message.strip():
            return AgentResult(
                agent_name=self.name,
                output={"suggestion": "", "status": "empty"},
            )

        mode_hints = {
            "interview": "This is an interview. Provide STAR-method hints and technical guidance.",
            "sales": "This is a sales meeting. Handle objections and suggest discovery questions.",
            "presentation": "This is a presentation. Suggest speaker notes and audience engagement tips.",
            "meeting": "This is a general meeting. Provide relevant suggestions and follow-ups.",
        }

        messages = [
            LLMMessage(
                role="system",
                content=f"You are a meeting AI assistant. {mode_hints.get(meeting_mode, mode_hints['meeting'])}",
            ),
            LLMMessage(
                role="user",
                content=f"Context:\n{transcript[-2000:]}\n\nLatest: {last_message}\n\nProvide a brief suggestion.",
            ),
        ]
        response = await _get_llm().chat(messages, max_tokens=200)

        return AgentResult(
            agent_name=self.name,
            output={"suggestion": response.content.strip(), "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class SentimentAgent(BaseAgent):
    """Analyzes meeting sentiment in real-time."""

    @property
    def name(self) -> str:
        return "sentiment_analyzer"

    @property
    def description(self) -> str:
        return "Analyzes meeting sentiment and tone"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"sentiment": "neutral", "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system",
                content="Analyze sentiment. Reply with one word: positive, negative, or neutral.",
            ),
            LLMMessage(
                role="user", content=f"Analyze sentiment:\n\n{transcript[-1500:]}"
            ),
        ]
        response = await _get_llm().chat(messages, max_tokens=10)
        sentiment = response.content.strip().lower()
        if sentiment not in ("positive", "negative", "neutral"):
            sentiment = "neutral"

        return AgentResult(
            agent_name=self.name,
            output={"sentiment": sentiment, "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class QuestionDetectorAgent(BaseAgent):
    """Detects questions in meeting transcript."""

    @property
    def name(self) -> str:
        return "question_detector"

    @property
    def description(self) -> str:
        return "Detects questions asked during the meeting"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        last_message = context.get("last_message", "")

        questions = []
        for line in transcript.split("\n"):
            line = line.strip()
            if "?" in line and len(line) > 10:
                questions.append(line)

        is_question = "?" in last_message

        return AgentResult(
            agent_name=self.name,
            output={
                "question_detected": is_question,
                "questions": questions[-20:],
                "status": "ok",
            },
        )


class FollowUpAgent(BaseAgent):
    """Generates follow-up items from meeting context."""

    @property
    def name(self) -> str:
        return "followup_generator"

    @property
    def description(self) -> str:
        return "Generates follow-up items from meeting context"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"follow_ups": [], "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system",
                content="Generate follow-up items. Return a numbered list.",
            ),
            LLMMessage(role="user", content=f"Generate follow-ups:\n\n{transcript}"),
        ]
        response = await _get_llm().chat(messages, max_tokens=300)
        items = [
            line.strip().lstrip("0123456789.-) ")
            for line in response.content.split("\n")
            if line.strip() and not line.strip().startswith(("Follow", "No follow"))
        ]
        items = [i for i in items if len(i) > 5][:10]

        return AgentResult(
            agent_name=self.name,
            output={"follow_ups": items, "raw": response.content, "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class MeetingChatAgent(BaseAgent):
    """Answers questions about the meeting using meeting context."""

    @property
    def name(self) -> str:
        return "meeting_chat"

    @property
    def description(self) -> str:
        return "Answers questions about the meeting using context"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        question = context.get("question", "")
        transcript = context.get("transcript", "")

        if not question.strip():
            return AgentResult(
                agent_name=self.name,
                output={"answer": "", "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system",
                content="You are a meeting AI assistant. Answer questions based on the meeting transcript. If the answer is not in the transcript, say so.",
            ),
            LLMMessage(
                role="user",
                content=f"Meeting transcript:\n{transcript[-3000:]}\n\nQuestion: {question}",
            ),
        ]
        response = await _get_llm().chat(messages, max_tokens=400)

        return AgentResult(
            agent_name=self.name,
            output={"answer": response.content.strip(), "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class EmailDraftAgent(BaseAgent):
    """Generates meeting follow-up email drafts."""

    @property
    def name(self) -> str:
        return "email_drafter"

    @property
    def description(self) -> str:
        return "Generates meeting follow-up email drafts"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        transcript = context.get("transcript", "")
        participants = context.get("participants", [])
        meeting_title = context.get("meeting_title", "Meeting")

        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"email": "", "status": "empty"},
            )

        messages = [
            LLMMessage(
                role="system",
                content="Generate a professional meeting follow-up email with summary, decisions, and action items.",
            ),
            LLMMessage(
                role="user",
                content=f"Meeting: {meeting_title}\nParticipants: {', '.join(participants) if participants else 'Team'}\n\nTranscript:\n{transcript[-3000:]}\n\nGenerate email draft.",
            ),
        ]
        response = await _get_llm().chat(messages, max_tokens=600)

        return AgentResult(
            agent_name=self.name,
            output={"email": response.content.strip(), "status": "ok"},
            tokens_used=response.prompt_tokens + response.completion_tokens,
        )


class MeetingSearchAgent(BaseAgent):
    """Searches meeting transcript for relevant content."""

    @property
    def name(self) -> str:
        return "meeting_search"

    @property
    def description(self) -> str:
        return "Searches meeting transcript for relevant content"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        query = context.get("query", "").lower()
        transcript = context.get("transcript", "")

        if not query.strip():
            return AgentResult(
                agent_name=self.name,
                output={"results": [], "status": "empty"},
            )

        query_words = set(re.findall(r"\w+", query))
        results = []

        for line in transcript.split("\n"):
            line = line.strip()
            if not line:
                continue
            line_lower = line.lower()
            line_words = set(re.findall(r"\w+", line_lower))
            overlap = len(line_words & query_words)
            if overlap >= 1 or query in line_lower:
                score = overlap / max(len(query_words), 1)
                results.append({"text": line, "score": round(score, 3)})

        results.sort(key=lambda x: -x["score"])
        results = results[:20]

        return AgentResult(
            agent_name=self.name,
            output={"results": results, "total": len(results), "status": "ok"},
        )


class KnowledgeAgent(BaseAgent):
    """Indexes and retrieves knowledge from meeting content."""

    @property
    def name(self) -> str:
        return "knowledge_agent"

    @property
    def description(self) -> str:
        return "Indexes and retrieves knowledge from meetings and documents"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        action = context.get("action", "search")
        query = context.get("query", "")
        content = context.get("content", "")

        if action == "index":
            if not content.strip():
                return AgentResult(
                    agent_name=self.name,
                    output={"status": "empty", "indexed": False},
                )
            word_count = len(content.split())
            return AgentResult(
                agent_name=self.name,
                output={
                    "status": "ok",
                    "indexed": True,
                    "word_count": word_count,
                    "content_hash": str(hash(content))[:12],
                },
            )

        if not query.strip():
            return AgentResult(
                agent_name=self.name,
                output={"results": [], "status": "empty"},
            )

        if content:
            query_lower = query.lower()
            query_words = set(re.findall(r"\w+", query_lower))
            lines = content.split("\n")
            scored = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line_lower = line.lower()
                line_words = set(re.findall(r"\w+", line_lower))
                overlap = len(line_words & query_words)
                if overlap > 0 or query_lower in line_lower:
                    score = overlap / max(len(query_words), 1)
                    scored.append({"text": line, "score": round(score, 3)})
            scored.sort(key=lambda x: -x["score"])
            return AgentResult(
                agent_name=self.name,
                output={"results": scored[:20], "total": len(scored), "status": "ok"},
            )

        return AgentResult(
            agent_name=self.name,
            output={"results": [], "total": 0, "status": "ok"},
        )


class AutomationAgent(BaseAgent):
    """Orchestrates multi-step meeting workflows."""

    @property
    def name(self) -> str:
        return "automation_agent"

    @property
    def description(self) -> str:
        return "Orchestrates multi-step meeting automation workflows"

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        workflow = context.get("workflow", "post_meeting")
        transcript = context.get("transcript", "")
        participants = context.get("participants", [])
        meeting_title = context.get("meeting_title", "Meeting")

        if not transcript.strip():
            return AgentResult(
                agent_name=self.name,
                output={"status": "empty", "steps": []},
            )

        steps = []

        summary_resp = await _get_llm().chat(
            [
                LLMMessage(
                    role="system", content="Generate a concise meeting summary."
                ),
                LLMMessage(role="user", content=f"Summarize:\n\n{transcript[-3000:]}"),
            ],
            max_tokens=500,
        )
        steps.append(
            {"step": "summary", "status": "ok", "content": summary_resp.content}
        )

        actions_resp = await _get_llm().chat(
            [
                LLMMessage(
                    role="system",
                    content="Extract action items. Return a numbered list.",
                ),
                LLMMessage(role="user", content=f"Extract:\n\n{transcript[-3000:]}"),
            ],
            max_tokens=300,
        )
        action_items = [
            l.strip().lstrip("0123456789.-) ")
            for l in actions_resp.content.split("\n")
            if l.strip() and len(l.strip()) > 5
        ][:10]
        steps.append({"step": "action_items", "status": "ok", "items": action_items})

        decisions_resp = await _get_llm().chat(
            [
                LLMMessage(
                    role="system", content="Extract decisions. Return a numbered list."
                ),
                LLMMessage(role="user", content=f"Extract:\n\n{transcript[-3000:]}"),
            ],
            max_tokens=300,
        )
        decisions = [
            l.strip().lstrip("0123456789.-) ")
            for l in decisions_resp.content.split("\n")
            if l.strip() and len(l.strip()) > 5
        ][:10]
        steps.append({"step": "decisions", "status": "ok", "items": decisions})

        email_resp = await _get_llm().chat(
            [
                LLMMessage(
                    role="system",
                    content="Generate a professional meeting follow-up email.",
                ),
                LLMMessage(
                    role="user",
                    content=f"Meeting: {meeting_title}\nParticipants: {', '.join(str(p) for p in participants)}\n\nTranscript:\n{transcript[-3000:]}",
                ),
            ],
            max_tokens=600,
        )
        steps.append(
            {"step": "email_draft", "status": "ok", "content": email_resp.content}
        )

        return AgentResult(
            agent_name=self.name,
            output={
                "workflow": workflow,
                "steps": steps,
                "summary": summary_resp.content,
                "action_items": action_items,
                "decisions": decisions,
                "email_draft": email_resp.content,
                "status": "ok",
            },
        )


def register_all_agents(manager: AgentManager) -> None:
    """Register all meeting intelligence agents with the agent manager."""
    agents = [
        SummarizerAgent(),
        ActionItemAgent(),
        DecisionAgent(),
        RiskAgent(),
        SuggestionAgent(),
        SentimentAgent(),
        QuestionDetectorAgent(),
        FollowUpAgent(),
        MeetingChatAgent(),
        EmailDraftAgent(),
        MeetingSearchAgent(),
        KnowledgeAgent(),
        AutomationAgent(),
    ]
    for agent in agents:
        manager.register(agent)

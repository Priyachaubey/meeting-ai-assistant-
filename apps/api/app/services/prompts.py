"""Prompt template registry with versioning.

Deliberately a code-level registry, not a DB-backed CMS. A DB-backed prompt manager (editable
at runtime, audit-logged changes, a UI for non-engineers to tweak wording) is real
infrastructure that's premature here: nobody on this team edits prompts except by changing
code, there's no non-engineer prompt-editing workflow to support, and no A/B-testing
infrastructure to route between versions yet. Building that CMS now would be exactly the
speculative-infrastructure problem this whole project started from — scaffolding for a
workflow that doesn't exist. What's real and worth having now: every prompt is named,
versioned, and rendered through one function, so (a) changing a prompt is a one-line diff
with a version bump instead of hunting for a string literal in agent code, and (b) every
AI call recorded in ai_usage_events could be joined back to which prompt version produced it,
once that's wired (not yet — see TODO at the bottom).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: int
    template: str

    def render(self, **kwargs: str) -> str:
        try:
            return self.template.format(**kwargs)
        except KeyError as exc:
            raise ValueError(f"Prompt '{self.name}' v{self.version} missing variable: {exc}") from exc


_REGISTRY: dict[str, PromptTemplate] = {}


def register(name: str, version: int, template: str) -> PromptTemplate:
    prompt = PromptTemplate(name=name, version=version, template=template)
    _REGISTRY[name] = prompt
    return prompt


def get(name: str) -> PromptTemplate:
    if name not in _REGISTRY:
        raise KeyError(f"No prompt template registered under '{name}'. Registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


# --- Registered prompts -----------------------------------------------------------------
# Bump `version` whenever you change a template's wording in a way worth tracking — it
# costs nothing and means "which prompt version generated this AI usage event" is answerable
# later instead of lost.

MEETING_RESPONSE_V1 = register(
    "meeting_response",
    version=2,
    template=(
        "You are a live meeting co-pilot. The user is in a real-time call and a question was "
        "just asked of them.\n\n"
        "Respond with ONLY a JSON object — no markdown, no commentary — matching exactly:\n"
        '{{"suggested_response": "<2-3 sentence answer they could say next>", '
        '"sentiment": "<positive|neutral|cautious>", '
        '"decision": "<a concrete decision just made in this exchange, or null>", '
        '"risk": "<a concrete risk/blocker just raised in this exchange, or null>", '
        '"follow_ups": ["<a natural follow-up question the user could ask next, grounded in '
        'this specific exchange>", ...]}}\n\n'
        "Ground suggested_response in the retrieved context if any is given, and don't "
        "contradict it. If no context is given, answer generally and do not invent specific "
        "company facts, numbers, or policies you weren't given. Only set decision/risk if one "
        "was actually expressed in the conversation below — leave them null otherwise, don't "
        "manufacture one to fill the field. follow_ups must be specific to what was actually "
        "discussed — 0 to 2 items, empty list if nothing natural follows, never generic "
        "filler questions unrelated to this exchange.\n\n"
        "Recent conversation:\n{recent_context}\n\n"
        "Retrieved context:\n{retrieved_context}\n\n"
        "Question just asked: {question}"
    ),
)

MEETING_SUMMARY_V1 = register(
    "meeting_summary",
    version=1,
    template=(
        "You are summarizing a meeting transcript. Respond with ONLY a JSON object — no "
        'markdown, no commentary — matching exactly: {{"summary": "<2-4 sentence summary>", '
        '"decisions": ["<decision>", ...], "risks": ["<risk>", ...]}}. Use only information '
        "present in the transcript. If there are no clear decisions or risks, return empty "
        "lists rather than inventing any.\n\n"
        "Transcript:\n{transcript}"
    ),
)

TEXT_TRANSLATION_V1 = register(
    "text_translation",
    version=1,
    template=(
        "Translate the following text into {target_language}. Respond with ONLY the "
        "translated text — no preamble, no notes, no quotation marks around it, no "
        "explanation of your translation choices. Preserve the original meaning and tone "
        "exactly; do not summarize, expand, or add information that wasn't in the source.\n\n"
        "Text:\n{text}"
    ),
)

AI_EMAIL_GENERATOR_V1 = register(
    "ai_email_generator",
    version=1,
    template=(
        "Write a follow-up email based on this meeting. Respond with ONLY a JSON object: "
        '{{"subject": "<email subject>", "body": "<email body, plain text, no markdown>"}}. '
        "Use a professional, concise tone. Reference specific points from the transcript/"
        "summary below — do not invent commitments, numbers, or names that aren't in it.\n\n"
        "Meeting summary:\n{summary}\n\nKey decisions:\n{decisions}\n\nAction items:\n{action_items}"
    ),
)

AI_FOLLOWUP_MESSAGE_V1 = register(
    "ai_followup_message",
    version=1,
    template=(
        "Write a short, casual follow-up message (Slack/chat style, not a formal email — "
        "2-4 sentences) based on this meeting. Respond with ONLY the message text, no "
        "subject line, no preamble. Reference specific points from the summary/action items "
        "below — do not invent commitments, numbers, or names that aren't in it.\n\n"
        "Meeting summary:\n{summary}\n\nAction items:\n{action_items}"
    ),
)

AI_RESEARCH_ASSISTANT_V1 = register(
    "ai_research_assistant",
    version=1,
    template=(
        "Answer the question using ONLY the retrieved context below. If the context doesn't "
        "contain enough information to answer, say so explicitly rather than guessing or "
        "using outside knowledge — this answer is being presented as grounded in the user's "
        "own documents, so it must actually be grounded in them.\n\n"
        "Retrieved context:\n{retrieved_context}\n\nQuestion: {question}"
    ),
)

# TODO once there's a real need: thread prompt name+version through LLMResponse/UsageEvent
# so ai_usage_events can answer "which prompt version generated this call" — straightforward
# to add (one more column) but not worth it until something is actually comparing prompt
# versions against each other, which nothing does yet.

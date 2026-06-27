"""Meeting "AI Score" — a deterministic heuristic formula over real counts (decisions, action
items, risks), NOT a model-derived judgment of meeting quality. There's no labeled training
data anywhere for "good meeting" vs "bad meeting," so anything claiming to be a validated
quality metric would be fabricated. This is explicit about being a heuristic, in both the API
response and (per FRONTEND.md notes) the UI — a single number with no breakdown attached would
imply more rigor than exists here.

Deliberately excludes "Speaking Time" and "Participation" from the original feature list —
those need real speaker diarization (who spoke when, how much), which isn't wired (Deepgram's
real-time API returns a transcript per speaker label, but the diarization quality itself
hasn't been validated, and nothing currently aggregates per-speaker duration). Computing a
"participation score" without that data would mean inventing numbers — exactly what this
whole project has been trying to stop doing. Once real per-speaker duration exists, extending
this formula to include it is straightforward; faking it now is not the alternative.
"""

from dataclasses import dataclass


@dataclass
class MeetingScore:
    overall: int  # 0-100
    decisiveness: int
    productivity: int
    risk_penalty: int
    breakdown_note: str


def compute_meeting_score(*, decisions: list[str], action_items: list[str], risks: list[str]) -> MeetingScore:
    decisiveness = min(len(decisions) * 20, 40)
    productivity = min(len(action_items) * 15, 40)
    risk_penalty = min(len(risks) * 10, 30)
    overall = max(0, min(100, 50 + decisiveness + productivity - risk_penalty))
    return MeetingScore(
        overall=overall,
        decisiveness=decisiveness,
        productivity=productivity,
        risk_penalty=risk_penalty,
        breakdown_note=(
            "Heuristic formula over decision/action-item/risk counts — not a measured or "
            "ML-derived quality judgment. Speaking time and participation aren't included: "
            "no real speaker-diarization data exists yet to compute them from."
        ),
    )

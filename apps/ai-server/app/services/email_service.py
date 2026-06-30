"""Email generation and automation service.

Generates professional meeting follow-up emails with summary,
action items, transcript, participants, decisions, and AI insights.
Supports Gmail, Outlook, and SMTP architecture.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailDraft:
    """A generated email draft."""

    id: str
    meeting_id: str
    subject: str
    body_html: str
    body_text: str
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    status: str = "draft"  # draft, sent, failed
    created_at: float = field(default_factory=time.time)
    sent_at: float | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "subject": self.subject,
            "body_html": self.body_html,
            "body_text": self.body_text,
            "recipients": self.recipients,
            "cc": self.cc,
            "status": self.status,
            "created_at": self.created_at,
            "sent_at": self.sent_at,
        }


class EmailService:
    """Email generation and sending service."""

    def __init__(self) -> None:
        self._drafts: dict[str, EmailDraft] = {}
        self._meeting_drafts: dict[str, list[str]] = {}

    def generate_email(
        self,
        meeting_id: str,
        meeting_title: str,
        participants: list[dict],
        summary: str,
        action_items: list[str],
        decisions: list[str],
        transcript: str,
        duration_minutes: float = 0,
        follow_ups: list[str] | None = None,
        risks: list[str] | None = None,
        ai_insights: str = "",
    ) -> EmailDraft:
        """Generate a professional follow-up email."""
        participant_names = [
            p.get("name", p.get("display_name", "Participant")) for p in participants
        ]
        participant_list = ", ".join(participant_names)

        duration_str = ""
        if duration_minutes > 0:
            hrs = int(duration_minutes // 60)
            mins = int(duration_minutes % 60)
            if hrs > 0:
                duration_str = f"{hrs}h {mins}m"
            else:
                duration_str = f"{mins} minutes"

        subject = f"Meeting Summary: {meeting_title}"

        text_body = self._build_text_body(
            meeting_title,
            participant_list,
            duration_str,
            summary,
            action_items,
            decisions,
            follow_ups or [],
            risks or [],
            ai_insights,
            transcript,
        )
        html_body = self._build_html_body(
            meeting_title,
            participant_list,
            duration_str,
            summary,
            action_items,
            decisions,
            follow_ups or [],
            risks or [],
            ai_insights,
        )

        recipients = [p.get("email", "") for p in participants if p.get("email")]

        draft = EmailDraft(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            subject=subject,
            body_html=html_body,
            body_text=text_body,
            recipients=recipients,
        )
        self._drafts[draft.id] = draft
        if meeting_id not in self._meeting_drafts:
            self._meeting_drafts[meeting_id] = []
        self._meeting_drafts[meeting_id].append(draft.id)

        return draft

    def _build_text_body(
        self,
        title,
        participants,
        duration,
        summary,
        actions,
        decisions,
        follow_ups,
        risks,
        insights,
        transcript,
    ) -> str:
        lines = [
            f"Meeting Summary: {title}",
            "=" * 40,
            "",
        ]
        if participants:
            lines.append(f"Participants: {participants}")
        if duration:
            lines.append(f"Duration: {duration}")
        lines.append("")

        lines.append("SUMMARY")
        lines.append("-" * 20)
        lines.append(summary)
        lines.append("")

        if decisions:
            lines.append("DECISIONS MADE")
            lines.append("-" * 20)
            for i, d in enumerate(decisions, 1):
                lines.append(f"  {i}. {d}")
            lines.append("")

        if actions:
            lines.append("ACTION ITEMS")
            lines.append("-" * 20)
            for i, a in enumerate(actions, 1):
                lines.append(f"  {i}. {a}")
            lines.append("")

        if follow_ups:
            lines.append("FOLLOW-UP ITEMS")
            lines.append("-" * 20)
            for i, f in enumerate(follow_ups, 1):
                lines.append(f"  {i}. {f}")
            lines.append("")

        if risks:
            lines.append("RISKS & CONCERNS")
            lines.append("-" * 20)
            for i, r in enumerate(risks, 1):
                lines.append(f"  {i}. {r}")
            lines.append("")

        if insights:
            lines.append("AI INSIGHTS")
            lines.append("-" * 20)
            lines.append(insights)
            lines.append("")

        lines.append("---")
        lines.append("Generated by ConvoPilot AI - Microtechnique")
        lines.append("https://meeting.microtechnique.in")

        return "\n".join(lines)

    def _build_html_body(
        self,
        title,
        participants,
        duration,
        summary,
        actions,
        decisions,
        follow_ups,
        risks,
        insights,
    ) -> str:
        sections = []

        if participants or duration:
            meta = []
            if participants:
                meta.append(f"<strong>Participants:</strong> {participants}")
            if duration:
                meta.append(f"<strong>Duration:</strong> {duration}")
            sections.append(
                f'<div style="margin-bottom:16px;color:#666;font-size:14px">{" &middot; ".join(meta)}</div>'
            )

        sections.append(f"""
        <div style="margin-bottom:24px">
            <h2 style="color:#5B0A8C;font-size:18px;margin-bottom:8px">Summary</h2>
            <p style="line-height:1.6;color:#333">{summary}</p>
        </div>""")

        if decisions:
            items = "".join(
                f"<li style='margin-bottom:4px'>{d}</li>" for d in decisions
            )
            sections.append(f"""
            <div style="margin-bottom:24px">
                <h2 style="color:#059669;font-size:18px;margin-bottom:8px">Decisions Made</h2>
                <ol style="color:#333;line-height:1.6">{items}</ol>
            </div>""")

        if actions:
            items = "".join(
                f"<li style='margin-bottom:8px;padding:8px 12px;background:#f8f9fa;border-left:3px solid #5B0A8C;border-radius:4px'>{a}</li>"
                for a in actions
            )
            sections.append(f"""
            <div style="margin-bottom:24px">
                <h2 style="color:#2563EB;font-size:18px;margin-bottom:8px">Action Items</h2>
                <ol style="list-style:none;padding:0">{items}</ol>
            </div>""")

        if follow_ups:
            items = "".join(
                f"<li style='margin-bottom:4px'>{f}</li>" for f in follow_ups
            )
            sections.append(f"""
            <div style="margin-bottom:24px">
                <h2 style="color:#D97706;font-size:18px;margin-bottom:8px">Follow-up Items</h2>
                <ol style="color:#333;line-height:1.6">{items}</ol>
            </div>""")

        if risks:
            items = "".join(
                f"<li style='margin-bottom:4px;color:#DC2626'>{r}</li>" for r in risks
            )
            sections.append(f"""
            <div style="margin-bottom:24px">
                <h2 style="color:#DC2626;font-size:18px;margin-bottom:8px">Risks &amp; Concerns</h2>
                <ol style="line-height:1.6">{items}</ol>
            </div>""")

        if insights:
            sections.append(f"""
            <div style="margin-bottom:24px">
                <h2 style="color:#7C3AED;font-size:18px;margin-bottom:8px">AI Insights</h2>
                <p style="line-height:1.6;color:#333;background:#f5f3ff;padding:12px;border-radius:8px">{insights}</p>
            </div>""")

        body_content = "\n".join(sections)

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:20px;color:#333">
    <div style="background:linear-gradient(135deg,#5B0A8C,#7C3AED);padding:24px;border-radius:12px 12px 0 0;color:white">
        <h1 style="margin:0;font-size:22px">Meeting Summary</h1>
        <p style="margin:8px 0 0;opacity:0.9">{title}</p>
    </div>
    <div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px">
        {body_content}
        <div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;text-align:center;color:#999;font-size:12px">
            Generated by <strong>ConvoPilot AI</strong> &mdash; Microtechnique<br>
            <a href="https://meeting.microtechnique.in" style="color:#5B0A8C">meeting.microtechnique.in</a>
        </div>
    </div>
</body>
</html>"""

    def get_draft(self, draft_id: str) -> EmailDraft | None:
        """Get a specific email draft."""
        return self._drafts.get(draft_id)

    def get_meeting_drafts(self, meeting_id: str) -> list[dict]:
        """Get all email drafts for a meeting."""
        draft_ids = self._meeting_drafts.get(meeting_id, [])
        return [self._drafts[did].to_dict() for did in draft_ids if did in self._drafts]

    def mark_sent(self, draft_id: str) -> bool:
        """Mark a draft as sent."""
        draft = self._drafts.get(draft_id)
        if draft:
            draft.status = "sent"
            draft.sent_at = time.time()
            return True
        return False

    def update_recipients(
        self, draft_id: str, recipients: list[str], cc: list[str] | None = None
    ) -> bool:
        """Update email recipients."""
        draft = self._drafts.get(draft_id)
        if draft:
            draft.recipients = recipients
            if cc is not None:
                draft.cc = cc
            return True
        return False

    def get_status(self) -> dict:
        """Get service status."""
        total = len(self._drafts)
        sent = sum(1 for d in self._drafts.values() if d.status == "sent")
        return {
            "total_drafts": total,
            "sent": sent,
            "pending": total - sent,
        }


email_service = EmailService()

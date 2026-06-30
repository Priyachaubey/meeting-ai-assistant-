"""Meeting export service.

Exports meetings in multiple formats: JSON, TXT, HTML, and Markdown.
Includes transcript, summary, action items, decisions, participants,
and AI analysis.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExportResult:
    """Result of a meeting export."""

    id: str
    meeting_id: str
    format: str
    content: str
    content_type: str
    filename: str
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "meeting_id": self.meeting_id,
            "format": self.format,
            "content_type": self.content_type,
            "filename": self.filename,
            "size_bytes": len(self.content.encode("utf-8")),
            "created_at": self.created_at,
        }


class ExportService:
    """Meeting export service supporting multiple formats."""

    def export_json(
        self,
        meeting_id: str,
        meeting_title: str,
        data: dict,
    ) -> ExportResult:
        """Export meeting as structured JSON."""
        export_data = {
            "meeting_id": meeting_id,
            "title": meeting_title,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "participants": data.get("participants", []),
            "transcript": data.get("transcript", []),
            "ai_analysis": {
                "summary": data.get("summary", ""),
                "action_items": data.get("action_items", []),
                "decisions": data.get("decisions", []),
                "risks": data.get("risks", []),
                "follow_ups": data.get("follow_ups", []),
                "sentiment": data.get("sentiment", ""),
            },
            "chat_messages": data.get("chat_messages", []),
            "duration_minutes": data.get("duration_minutes", 0),
            "metadata": data.get("metadata", {}),
        }
        content = json.dumps(export_data, indent=2, ensure_ascii=False)
        safe_title = meeting_title.replace(" ", "_").replace("/", "-")[:50]
        return ExportResult(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            format="json",
            content=content,
            content_type="application/json",
            filename=f"{safe_title}_export.json",
        )

    def export_txt(
        self,
        meeting_id: str,
        meeting_title: str,
        data: dict,
    ) -> ExportResult:
        """Export meeting as plain text."""
        lines = [
            f"MEETING: {meeting_title}",
            f"DATE: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            "=" * 60,
            "",
        ]

        participants = data.get("participants", [])
        if participants:
            names = [
                p.get("display_name", p.get("name", "Unknown")) for p in participants
            ]
            lines.append(f"PARTICIPANTS: {', '.join(names)}")
            lines.append("")

        duration = data.get("duration_minutes", 0)
        if duration:
            lines.append(f"DURATION: {duration:.0f} minutes")
            lines.append("")

        summary = data.get("summary", "")
        if summary:
            lines.append("SUMMARY")
            lines.append("-" * 40)
            lines.append(summary)
            lines.append("")

        decisions = data.get("decisions", [])
        if decisions:
            lines.append("DECISIONS")
            lines.append("-" * 40)
            for i, d in enumerate(decisions, 1):
                lines.append(f"  {i}. {d}")
            lines.append("")

        actions = data.get("action_items", [])
        if actions:
            lines.append("ACTION ITEMS")
            lines.append("-" * 40)
            for i, a in enumerate(actions, 1):
                lines.append(f"  {i}. {a}")
            lines.append("")

        transcript = data.get("transcript", [])
        if transcript:
            lines.append("TRANSCRIPT")
            lines.append("-" * 40)
            for entry in transcript:
                speaker = entry.get("speaker_name", "Unknown")
                text = entry.get("text", "")
                ts = entry.get("timestamp_ms", 0)
                mins = int(ts / 60000)
                secs = int((ts % 60000) / 1000)
                lines.append(f"[{mins:02d}:{secs:02d}] {speaker}: {text}")
            lines.append("")

        lines.append("---")
        lines.append("Exported by ConvoPilot AI - Microtechnique")

        content = "\n".join(lines)
        safe_title = meeting_title.replace(" ", "_").replace("/", "-")[:50]
        return ExportResult(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            format="txt",
            content=content,
            content_type="text/plain",
            filename=f"{safe_title}_transcript.txt",
        )

    def export_markdown(
        self,
        meeting_id: str,
        meeting_title: str,
        data: dict,
    ) -> ExportResult:
        """Export meeting as Markdown."""
        lines = [
            f"# {meeting_title}",
            "",
            f"*Exported: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}*",
            "",
        ]

        participants = data.get("participants", [])
        if participants:
            names = [
                p.get("display_name", p.get("name", "Unknown")) for p in participants
            ]
            lines.append(f"**Participants:** {', '.join(names)}")
            lines.append("")

        duration = data.get("duration_minutes", 0)
        if duration:
            lines.append(f"**Duration:** {duration:.0f} minutes")
            lines.append("")

        summary = data.get("summary", "")
        if summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(summary)
            lines.append("")

        decisions = data.get("decisions", [])
        if decisions:
            lines.append("## Decisions")
            lines.append("")
            for d in decisions:
                lines.append(f"- {d}")
            lines.append("")

        actions = data.get("action_items", [])
        if actions:
            lines.append("## Action Items")
            lines.append("")
            for a in actions:
                lines.append(f"- [ ] {a}")
            lines.append("")

        follow_ups = data.get("follow_ups", [])
        if follow_ups:
            lines.append("## Follow-up Items")
            lines.append("")
            for f in follow_ups:
                lines.append(f"- {f}")
            lines.append("")

        risks = data.get("risks", [])
        if risks:
            lines.append("## Risks & Concerns")
            lines.append("")
            for r in risks:
                lines.append(f"- :warning: {r}")
            lines.append("")

        transcript = data.get("transcript", [])
        if transcript:
            lines.append("## Transcript")
            lines.append("")
            for entry in transcript:
                speaker = entry.get("speaker_name", "Unknown")
                text = entry.get("text", "")
                ts = entry.get("timestamp_ms", 0)
                mins = int(ts / 60000)
                secs = int((ts % 60000) / 1000)
                lines.append(f"**{speaker}** [{mins:02d}:{secs:02d}]:")
                lines.append(f"> {text}")
                lines.append("")

        lines.append("---")
        lines.append("*Generated by ConvoPilot AI - Microtechnique*")

        content = "\n".join(lines)
        safe_title = meeting_title.replace(" ", "-").replace("/", "-").lower()[:50]
        return ExportResult(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            format="markdown",
            content=content,
            content_type="text/markdown",
            filename=f"{safe_title}-meeting.md",
        )

    def export_html(
        self,
        meeting_id: str,
        meeting_title: str,
        data: dict,
    ) -> ExportResult:
        """Export meeting as standalone HTML."""
        from app.services.email_service import EmailService

        email_svc = EmailService()

        html = email_svc._build_html_body(
            title=meeting_title,
            participants=", ".join(
                p.get("display_name", p.get("name", ""))
                for p in data.get("participants", [])
            ),
            duration=f"{data.get('duration_minutes', 0):.0f} min"
            if data.get("duration_minutes")
            else "",
            summary=data.get("summary", ""),
            actions=data.get("action_items", []),
            decisions=data.get("decisions", []),
            follow_ups=data.get("follow_ups", []),
            risks=data.get("risks", []),
            insights=data.get("insights", ""),
        )

        safe_title = meeting_title.replace(" ", "_").replace("/", "-")[:50]
        return ExportResult(
            id=str(uuid.uuid4()),
            meeting_id=meeting_id,
            format="html",
            content=html,
            content_type="text/html",
            filename=f"{safe_title}_meeting.html",
        )


export_service = ExportService()

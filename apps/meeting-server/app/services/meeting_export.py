"""Meeting export service (meeting server side).

Exports meetings in multiple formats: JSON, TXT, Markdown, HTML.
"""

from __future__ import annotations

import json
import time
from typing import Any


def export_meeting(
    room_id: str,
    meeting_title: str,
    format: str,
    data: dict,
) -> dict:
    """Export a meeting in the specified format."""
    safe_title = meeting_title.replace(" ", "_").replace("/", "-")[:50]

    if format == "json":
        return _export_json(room_id, meeting_title, safe_title, data)
    elif format == "txt":
        return _export_txt(room_id, meeting_title, safe_title, data)
    elif format == "markdown":
        return _export_markdown(room_id, meeting_title, safe_title, data)
    elif format == "html":
        return _export_html(room_id, meeting_title, safe_title, data)
    else:
        return {"content": "", "filename": "export.txt", "data": {}}


def _export_json(room_id: str, title: str, safe_title: str, data: dict) -> dict:
    export_data = {
        "meeting_id": room_id,
        "title": title,
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
    return {
        "content": json.dumps(export_data, indent=2, ensure_ascii=False),
        "filename": f"{safe_title}_export.json",
        "data": export_data,
    }


def _export_txt(room_id: str, title: str, safe_title: str, data: dict) -> dict:
    lines = [
        f"MEETING: {title}",
        f"DATE: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "=" * 60,
        "",
    ]
    participants = data.get("participants", [])
    if participants:
        names = [p.get("display_name", p.get("name", "Unknown")) for p in participants]
        lines.append(f"PARTICIPANTS: {', '.join(names)}")
        lines.append("")

    summary = data.get("summary", "")
    if summary:
        lines.extend(["SUMMARY", "-" * 40, summary, ""])

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

    lines.extend(["---", "Exported by ConvoPilot AI - Microtechnique"])
    return {
        "content": "\n".join(lines),
        "filename": f"{safe_title}_transcript.txt",
        "data": {},
    }


def _export_markdown(room_id: str, title: str, safe_title: str, data: dict) -> dict:
    lines = [
        f"# {title}",
        "",
        f"*Exported: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}*",
        "",
    ]
    participants = data.get("participants", [])
    if participants:
        names = [p.get("display_name", p.get("name", "Unknown")) for p in participants]
        lines.extend([f"**Participants:** {', '.join(names)}", ""])

    summary = data.get("summary", "")
    if summary:
        lines.extend(["## Summary", "", summary, ""])

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
            lines.extend([f"**{speaker}** [{mins:02d}:{secs:02d}]:", f"> {text}", ""])

    lines.extend(["---", "*Generated by ConvoPilot AI - Microtechnique*"])
    safe_md = safe_title.replace("_", "-").lower()
    return {
        "content": "\n".join(lines),
        "filename": f"{safe_md}-meeting.md",
        "data": {},
    }


def _export_html(room_id: str, title: str, safe_title: str, data: dict) -> dict:
    summary = data.get("summary", "")
    actions = data.get("action_items", [])
    decisions = data.get("decisions", [])
    follow_ups = data.get("follow_ups", [])
    risks = data.get("risks", [])
    participants = data.get("participants", [])

    sections = []
    if participants:
        names = ", ".join(
            p.get("display_name", p.get("name", "")) for p in participants
        )
        sections.append(
            f'<div style="color:#666;margin-bottom:16px"><strong>Participants:</strong> {names}</div>'
        )

    if summary:
        sections.append(
            f'<div style="margin-bottom:24px"><h2 style="color:#5B0A8C">Summary</h2><p style="line-height:1.6">{summary}</p></div>'
        )

    if decisions:
        items = "".join(f"<li>{d}</li>" for d in decisions)
        sections.append(
            f'<div style="margin-bottom:24px"><h2 style="color:#059669">Decisions</h2><ol>{items}</ol></div>'
        )

    if actions:
        items = "".join(
            f"<li style='padding:8px;background:#f8f9fa;border-left:3px solid #5B0A8C;margin-bottom:4px'>{a}</li>"
            for a in actions
        )
        sections.append(
            f'<div style="margin-bottom:24px"><h2 style="color:#2563EB">Action Items</h2><ol style="list-style:none;padding:0">{items}</ol></div>'
        )

    if risks:
        items = "".join(f"<li style='color:#DC2626'>{r}</li>" for r in risks)
        sections.append(
            f'<div style="margin-bottom:24px"><h2 style="color:#DC2626">Risks</h2><ol>{items}</ol></div>'
        )

    body = "\n".join(sections)
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head>
<body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;max-width:680px;margin:0 auto;padding:20px">
<div style="background:linear-gradient(135deg,#5B0A8C,#7C3AED);padding:24px;border-radius:12px 12px 0 0;color:white">
<h1 style="margin:0">Meeting Summary</h1><p style="opacity:0.9">{title}</p></div>
<div style="padding:24px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 12px 12px">{body}
<div style="margin-top:24px;padding-top:16px;border-top:1px solid #e5e7eb;text-align:center;color:#999;font-size:12px">Generated by ConvoPilot AI - Microtechnique</div></div>
</body></html>"""

    return {
        "content": html,
        "filename": f"{safe_title}_meeting.html",
        "data": {},
    }

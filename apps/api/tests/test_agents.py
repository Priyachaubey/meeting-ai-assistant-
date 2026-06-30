import pytest
from app.agents.orchestrator import MeetingAgentOrchestrator
from app.schemas.meeting import TranscriptChunk
@pytest.mark.asyncio
async def test_question_detection_generates_response():
    result, usage_events = await MeetingAgentOrchestrator().process(
        TranscriptChunk(text="Can you explain security?", timestamp_ms=1), "test-owner"
    )
    assert result.question_detected is True
    assert result.suggested_response
    assert isinstance(usage_events, list)

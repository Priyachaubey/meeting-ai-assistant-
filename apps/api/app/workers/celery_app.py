from celery import Celery
from app.core.config import settings

celery_app = Celery("convopilot", broker=settings.redis_url, backend=settings.redis_url)


@celery_app.task
def summarize_meeting(meeting_id: str) -> dict:
    return {"meeting_id": meeting_id, "status": "queued"}

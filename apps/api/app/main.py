# configure_logging() must run before any other app.* module is imported below — several of
# them call logging.getLogger(name) at module level, and structlog's stdlib integration needs
# to be configured before the first log line of the process, not after.
from app.core.logging_config import configure_logging  # noqa: E402

configure_logging()

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.routes import auth, guest, knowledge, meetings, notifications, storage, workspaces, ws  # noqa: E402
from app.api.routes import ai as ai_routes  # noqa: E402
from app.billing.routes import billing  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.core.security import get_current_user_id  # noqa: E402
from app.database.session import get_db  # noqa: E402
from app.limiter import limiter  # noqa: E402
from app.services.health import get_detailed_health  # noqa: E402

app = FastAPI(title="Microtechnique AI Meeting API", version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router, prefix="/api")
app.include_router(meetings.router, prefix="/api")
app.include_router(knowledge.router, prefix="/api")
app.include_router(billing.router, prefix="/api")
app.include_router(ai_routes.router, prefix="/api")
app.include_router(workspaces.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(guest.router, prefix="/api")
app.include_router(storage.router, prefix="/api")
app.include_router(ws.router)


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "service": "microtechnique-ai-meeting-api"}


@app.get("/api/health/detailed")
async def health_detailed(db: Session = Depends(get_db), user_id: str = Depends(get_current_user_id)) -> dict:
    # Authenticated, not public — this exposes infra topology (Qdrant URL, which providers
    # are configured) that a load-balancer ping shouldn't, and real connectivity checks are
    # too slow to be the thing a probe hits every few seconds anyway (see services/health.py).
    return get_detailed_health(db)

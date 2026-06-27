# Microtechnique AI Meeting

*(formerly ConvoPilot AI — see AUDIT.md for rename history. Internal package names, env vars, and the Celery app namespace were left unchanged for compatibility.)*

Your Real-Time AI Meeting Copilot.

Microtechnique AI Meeting is a production-oriented SaaS monorepo for local-first meeting intelligence. The client captures system audio, streams transcript events to the FastAPI backend, runs agent orchestration for question detection and response generation, and stores meetings locally or in cloud infrastructure.

## Stack

- Web: Next.js 15, React 19, TypeScript, Tailwind CSS, Framer Motion, Zustand, TanStack Query, Recharts, Lucide Icons
- API: FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis, Qdrant, Celery, WebSockets
- AI: OpenAI-compatible, Claude/Gemini provider abstractions, Deepgram/Whisper transcript adapters, RAG pipeline
- Mobile: Flutter scaffold
- DevOps: Docker Compose, GitHub Actions, Kubernetes manifests, Prometheus/Grafana/Sentry-ready hooks

## Quick Start

```bash
cp .env.example .env
pnpm install
pnpm dev
```

API only:

```bash
cd apps/api
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Docker:

```bash
docker compose up --build
```

## Troubleshooting: "Something went wrong. Is the API running?" on login/register

That message means the browser's `fetch()` call never got a response at all —
not "the backend returned an error," but "nothing came back to compare." There
are exactly three real causes, and the browser console tells you which:

1. **Open the browser DevTools console** (F12) and try login/register again.
   Look at the *exact* error text:
   - `Failed to fetch` / `ERR_CONNECTION_REFUSED` → the backend genuinely isn't
     running, or is running on a different port than `NEXT_PUBLIC_API_URL`
     points to. Fix: confirm `uvicorn` is actually up (`curl http://localhost:8000/health`
     should return `{"ok":true,...}` — try this in a plain browser tab first,
     before even touching the login form), and that `apps/web/.env.local` has
     the right `NEXT_PUBLIC_API_URL`.
   - **A message mentioning "CORS"** → the backend IS running and IS
     responding, but the browser is blocking the response because the
     frontend's origin isn't in the backend's allowed list. The single most
     common real-world cause: Next.js silently shifts to port 3001 (or
     higher) if 3000 is already taken — `npm run dev` prints this, but it's
     easy to miss. `core/config.py`'s `cors_allowed_origins` already covers
     `localhost:3000` *and* `3001` in development automatically; if you're on
     a different port or domain, set `CORS_ALLOWED_ORIGINS_EXTRA` (comma-
     separated) in the API's `.env`.
   - **No console error, request just hangs** → check `DATABASE_URL`/Postgres
     connectivity — a route handler stuck waiting on a dead DB connection can
     look like "no response" from the frontend's perspective, though this
     usually surfaces as a timeout rather than an immediate `fetch` rejection.

2. **If you edited `apps/web/.env.local` while `next dev` was already
   running**, restart it. Next.js only reads `NEXT_PUBLIC_*` vars at server
   start — editing the file doesn't take effect on a running dev server.

3. **Test the backend directly, independent of the frontend**, before
   assuming the bug is in either layer:
   ```bash
   curl -i http://localhost:8000/health
   curl -i -X POST http://localhost:8000/api/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email":"test@example.com","password":"test12345"}'
   ```
   If both of those work from `curl` but the browser still fails, it's CORS —
   `curl` doesn't enforce CORS, only browsers do, so a `curl` success with a
   browser failure is close to definitive.

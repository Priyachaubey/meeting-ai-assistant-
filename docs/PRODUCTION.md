# Production Setup

1. Create managed PostgreSQL, Redis and Qdrant clusters.
2. Configure provider keys for OpenAI, Claude, Gemini, Deepgram and AssemblyAI as needed.
3. Set strong JWT_SECRET and ENCRYPTION_KEY values.
4. Run Alembic migrations before first release.
5. Deploy API and web services behind HTTPS.
6. Configure Sentry, Prometheus and Grafana dashboards.
7. Enable audit logging and retention policies per workspace.
8. Document regional storage and deletion flows for GDPR readiness.


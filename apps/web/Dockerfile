FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN corepack enable && pnpm install --filter @convopilot/web --frozen-lockfile=false
FROM deps AS build
# ── Root cause fix ──────────────────────────────────────────────────────
# Next.js inlines every NEXT_PUBLIC_* env var into the static JS bundle at
# `next build` time — not at container-run time. `docker-compose.yml`'s
# `env_file: .env` for the web service only injects runtime env vars into
# the *running* container's process; it does nothing for the build step
# above, which happens in a separate, earlier image layer entirely. With
# no ARG/ENV here, every NEXT_PUBLIC_* reference in the frontend source
# (apps/web/src/lib/api.ts's API_URL/WS_URL/meetingServerUrl/
# meetingServerSocketUrl) silently fell back to its hardcoded
# `localhost:800x` default, and that fallback got permanently baked into
# the production bundle — explaining errors like "Could not reach the API
# at http://localhost:8002/api/meetings/rooms" on a deployed site where
# nothing is or should be listening on the visitor's own localhost.
# docker-compose.yml passes these as `build.args` (see its `web:` service);
# without Compose (e.g. `docker build` by hand), pass them explicitly:
#   docker build --build-arg NEXT_PUBLIC_API_URL=https://api.example.com ...
ARG NEXT_PUBLIC_API_URL
ARG NEXT_PUBLIC_WS_URL
ARG NEXT_PUBLIC_MEETING_SERVER_URL
ARG NEXT_PUBLIC_MEETING_WS_URL
ARG NEXT_PUBLIC_TURN_URL
ARG NEXT_PUBLIC_TURN_USERNAME
ARG NEXT_PUBLIC_TURN_CREDENTIAL
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
ENV NEXT_PUBLIC_WS_URL=${NEXT_PUBLIC_WS_URL}
ENV NEXT_PUBLIC_MEETING_SERVER_URL=${NEXT_PUBLIC_MEETING_SERVER_URL}
ENV NEXT_PUBLIC_MEETING_WS_URL=${NEXT_PUBLIC_MEETING_WS_URL}
ENV NEXT_PUBLIC_TURN_URL=${NEXT_PUBLIC_TURN_URL}
ENV NEXT_PUBLIC_TURN_USERNAME=${NEXT_PUBLIC_TURN_USERNAME}
ENV NEXT_PUBLIC_TURN_CREDENTIAL=${NEXT_PUBLIC_TURN_CREDENTIAL}
COPY . .
RUN pnpm --filter @convopilot/web build
FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/apps/web/.next/standalone ./
COPY --from=build /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=build /app/apps/web/public ./apps/web/public
EXPOSE 3000
CMD ["node", "apps/web/server.js"]

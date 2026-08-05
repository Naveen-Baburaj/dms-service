# Railway production deployment plan

This repository is an isolated monorepo containing a Next.js frontend and a Frappe v15 custom app. Deploy the frontend and Frappe stack as separate Railway services. Do not run Frappe with `bench start` in production.

## Required Railway services

1. `dms-frontend` — public Next.js service, root directory `/frontend`.
2. `dms-backend` — public Frappe web service from a custom Frappe v15 image.
3. `dms-websocket` — private Frappe Socket.IO service using the same backend image.
4. `dms-worker-short` — private short/default queue worker.
5. `dms-worker-long` — private long queue worker.
6. `dms-scheduler` — private scheduler service.
7. MariaDB — managed database or Railway MySQL-compatible service with persistent storage and backups.
8. Redis cache and Redis queue — separate Railway Redis services, private only.
9. A one-shot/configurator migration service for site creation, app installation, and `bench migrate`.

Use Railway private networking (`<service>.railway.internal`) for database, Redis, workers, scheduler, and websocket traffic. Only frontend and backend need public domains.

## Backend secrets

Set these only on backend-derived services:

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=<Railway secret>
OPENAI_MODEL=gpt-5.4-mini
OPENAI_TIMEOUT_SECONDS=75
OPENAI_MAX_OUTPUT_TOKENS=1400
OPENAI_MAX_RETRIES=2
FRAPPE_SITE_NAME=<api-domain>
DB_HOST=<mariadb private host>
DB_PORT=3306
DB_NAME=<database>
DB_USER=<database user>
DB_PASSWORD=<Railway secret>
REDIS_CACHE=redis://<cache-service>.railway.internal:<port>
REDIS_QUEUE=redis://<queue-service>.railway.internal:<port>
SOCKETIO_PORT=9000
```

Never put the OpenAI key, database password, administrator password, or encryption key in GitHub, Docker build arguments, or `NEXT_PUBLIC_*` variables.

## Frontend variables

Set before the Next.js build:

```env
NEXT_PUBLIC_API_URL=https://<backend-public-domain>
NEXT_PUBLIC_APP_NAME=DMS
NODE_ENV=production
NEXT_TELEMETRY_DISABLED=1
```

## Production controls

- Replace development mock headers and `allow_guest=True` with real Frappe session/JWT authentication before public launch.
- Restrict CORS to the exact frontend production domain; never use `*` in production.
- Run migrations as a release/configurator step before web and worker rollout.
- Add a backend health check at `/api/method/ping` and a frontend health check at `/`.
- Add database backups and a persistent volume for Frappe `sites` files/private uploads.
- Use at least two backend web replicas only after shared Redis, database, and persistent file storage are confirmed.
- Configure deployment draining and graceful shutdown for workers/web.
- Monitor OpenAI latency/error rate without logging prompts containing customer PII.

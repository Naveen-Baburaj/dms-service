# Railway Deployment — DMS

This repository is deployed as an isolated monorepo with two application services plus MariaDB and Redis.

## Pinned application stack

- Frappe: `v15.113.1`
- DMS app: `1.0.0`
- Python: `3.11`
- Node.js: `20.20.2`
- MariaDB: `11.8`

## Services

### dms-frontend

- Repository: `Naveen-Baburaj/dms-service`
- Branch: `main`
- Root directory: `/frontend`
- Railway config: `/frontend/railway.toml`
- Dockerfile: `/frontend/Dockerfile.railway`
- Public service

Required variables:

```text
DMS_INTERNAL_API_URL=http://dms-backend.railway.internal:<PORT>
DMS_FRAPPE_SITE=dms.localhost
NODE_ENV=production
```

Do not set `NEXT_PUBLIC_API_URL` in production. Browser requests intentionally use the same-origin `/api` proxy.

### dms-backend

- Repository: `Naveen-Baburaj/dms-service`
- Branch: `main`
- Root directory: `/backend`
- Railway config: `/backend/railway.toml`
- Dockerfile: `/backend/Dockerfile.railway`
- Private service

Required variables:

```text
DMS_FRAPPE_SITE=dms.localhost
DB_HOST=<MariaDB private host>
DB_PORT=3306
DB_NAME=<database name>
DB_PASSWORD=<database password>
REDIS_CACHE=redis://<Redis private host>:6379
REDIS_QUEUE=redis://<Redis private host>:6379
REDIS_SOCKETIO=redis://<Redis private host>:6379
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-5.4-mini
OPENAI_API_KEY=<Railway secret; never commit>
DMS_IGNORE_CSRF=1
```

The backend runtime creates only Railway-specific site/common configuration files at container startup. Application source, Vividity behavior, Cadence, permissions, and business logic remain in the DMS app.

## MariaDB

Use MariaDB `11.8` with a persistent volume mounted at `/var/lib/mysql`.

The current local Frappe backup must be imported into the Railway database before the backend is considered ready. Do not commit backup files to this repository.

After import, run the backend once with:

```text
RUN_MIGRATE=1
```

After a successful migration, set it back to `0` (or remove it) and redeploy.

## Redis

A single Redis service is sufficient for the current demo. It can supply cache, queue, and socketio Redis URLs. Dedicated workers/scheduler can be added later if scheduled/background workloads become part of the public demo.

## Public routing

The browser communicates only with the frontend domain.

```text
Browser -> dms-frontend -> /api proxy -> dms-backend (Railway private network)
```

The proxy injects `X-Frappe-Site-Name: dms.localhost` and forwards Frappe session cookies. This preserves the current `sid`-based login/session model without cross-domain cookie handling.

## Expected migrated data checks

- DMS Company: 3
- DMS Lead: 339
- DMS Customer: 45
- DMS Vehicle: 104
- DMS Vehicle Sale: 339
- DMS Test Drive: 222
- DMS Booking: 222
- DMS Service Job: 1571
- DMS Invoice: 330

Inventory scope checks:

- Total: 104
- Honda: 38
- NEXA: 33
- Jaguar: 33

## Security

- Never commit `.env`, Frappe `site_config.json`, backup site-config files, database dumps, or API keys.
- Store the company OpenAI key only as a Railway service variable.
- Rotate any API key that has been exposed outside the intended secret store before public deployment.

# Railway Deployment — DMS

This repository deploys as two application services from the same GitHub root, plus MariaDB and Redis.

## Pinned application stack

- Frappe: `v15.113.1`
- DMS app: `1.0.0`
- Python: `3.11`
- Node.js: `20.20.2`
- MariaDB: `11.8`

## Application services

Both `dms-frontend` and `dms-backend` connect to `Naveen-Baburaj/dms-service`, branch `main`, with repository root `/` as the build context. The services are distinguished only by their Dockerfile path.

### dms-frontend

Set:

```text
RAILWAY_DOCKERFILE_PATH=frontend/Dockerfile.railway
PORT=3000
DMS_FRAPPE_SITE=dms.localhost
DMS_INTERNAL_API_URL=http://dms-backend.railway.internal:8000
NODE_ENV=production
```

Do not set `NEXT_PUBLIC_API_URL` in production. Browser requests intentionally use the same-origin `/api` proxy.

Expose only this service with a Railway HTTP domain.

### dms-backend

Set:

```text
RAILWAY_DOCKERFILE_PATH=backend/Dockerfile.railway
PORT=8000
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
RUN_MIGRATE=0
```

Keep this service private. The frontend proxy and Next.js middleware call it over Railway private networking and inject `X-Frappe-Site-Name: dms.localhost`.

The backend runtime creates Railway-specific site/common configuration files at container startup. Application source, Vividity behavior, Cadence, permissions, and business logic remain in the DMS app.

## MariaDB

Deploy `mariadb:11.8` with a persistent volume mounted at:

```text
/var/lib/mysql
```

Use a dedicated database/user for the Frappe site. Import the existing local Frappe SQL backup before the backend is considered ready.

After import, temporarily set on `dms-backend`:

```text
RUN_MIGRATE=1
```

Redeploy once, confirm migration succeeds, then return it to `0` and redeploy.

## Redis

A single Redis service is sufficient for the current demo. It supplies cache, queue, and socketio Redis URLs. Dedicated queue workers/scheduler services can be added later if asynchronous workloads become part of the public demo.

## Public routing

```text
Browser
  -> dms-frontend public Railway domain
      -> /api same-origin proxy
          -> dms-backend.railway.internal:8000
              -> MariaDB + Redis on Railway private network
```

The proxy forwards Frappe session cookies, preserving the current `sid`-based login/session model without cross-domain cookie handling.

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

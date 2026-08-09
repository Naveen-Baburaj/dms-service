# DMS Railway Deployment

This runbook applies only to the GitHub branch `Railway-hosting`. The protected
`main` branch is the local/demo baseline and must not receive these deployment
files or Railway-specific runtime changes.

## Fixed deployment target

| Resource | Value |
|---|---|
| GitHub repository | `Naveen-Baburaj/dms-service` |
| Railway source branch | `Railway-hosting` |
| Railway project | `DMS` |
| Railway project ID | `fd1f817a-1071-4457-a57c-0b8fc7d6d5ef` |
| Railway environment | `production` |
| Railway environment ID | `6c556f7d-f9a3-4bf2-b8d6-55c682c21355` |
| Frappe site | `dms.localhost` |

Never let a Railway GitHub service default to `main`. Every application service
must show `Railway-hosting` as its connected source branch before deployment.

## Architecture

```text
Browser
  -> dms-frontend (public HTTPS, Next.js 15)
      -> same-origin /api proxy
          -> dms-backend.railway.internal:8000 (private Frappe/Gunicorn)
              -> mariadb.railway.internal:3306 (persistent)
              -> redis.railway.internal:6379 (private)
```

The frontend proxy forwards Frappe's `sid` cookie. Do not set
`NEXT_PUBLIC_API_URL` in Railway production; browser JavaScript cannot reach a
Railway private hostname and cross-origin cookies would break the login flow.

## Pinned application stack

- Frappe: `v15.113.1`
- Bench image: `frappe/bench:v5.31.0`
- Python: `3.11`
- Node.js: `20.20.2`
- MariaDB: `11.8`
- Redis: `7-alpine`
- OpenAI model: `gpt-5.4-mini`

## Required services

### `mariadb`

- Image: `mariadb:11.8`
- Persistent volume mount: `/var/lib/mysql`
- Database/user: `dms` / `dms`
- Keep the existing generated passwords in Railway secrets.

Required variable names:

```text
MARIADB_ROOT_PASSWORD
MARIADB_DATABASE=dms
MARIADB_USER=dms
MARIADB_PASSWORD
MYSQLDATABASE=dms
MYSQLUSER=dms
MYSQLPASSWORD=${{MARIADB_PASSWORD}}
MYSQLPORT=3306
MYSQLHOST=${{RAILWAY_PRIVATE_DOMAIN}}
MYSQL_URL=mysql://${{MARIADB_USER}}:${{MARIADB_PASSWORD}}@${{RAILWAY_PRIVATE_DOMAIN}}:3306/${{MARIADB_DATABASE}}
```

### `redis`

- Image: `redis:7-alpine`
- Public domain: none
- Private URL: `redis://redis.railway.internal:6379`

### `dms-backend`

- Repository: `Naveen-Baburaj/dms-service`
- Branch: `Railway-hosting`
- Build context/root: `/`
- Dockerfile: `backend/Dockerfile.railway`
- Public domain: none
- Health check: `/api/method/ping`

Variables:

```text
PORT=8000
DMS_FRAPPE_SITE=dms.localhost
DB_HOST=${{mariadb.RAILWAY_PRIVATE_DOMAIN}}
DB_PORT=3306
DB_NAME=${{mariadb.MARIADB_USER}}
DB_PASSWORD=${{mariadb.MARIADB_PASSWORD}}
REDIS_CACHE=redis://redis.railway.internal:6379
REDIS_QUEUE=redis://redis.railway.internal:6379
REDIS_SOCKETIO=redis://redis.railway.internal:6379
LLM_PROVIDER=openai
OPENAI_MODEL=gpt-5.4-mini
OPENAI_API_KEY=<Railway secret>
DMS_IGNORE_CSRF=1
RUN_MIGRATE=1
FRAPPE_ENCRYPTION_KEY=<local site encryption_key, when present>
```

Use `RUN_MIGRATE=1` only for the first post-import deployment. After a successful
migration, set it to `0` and redeploy. Optional runtime tuning:

```text
DMS_AGENTIC_ENABLED=1
DMS_AGENTIC_FALLBACK_ENABLED=1
DMS_AGENTIC_MAX_STEPS=8
DMS_AGENTIC_MAX_TOOL_CALLS=16
DMS_AGENTIC_REASONING_EFFORT=high
OPENAI_TIMEOUT_SECONDS=75
OPENAI_MAX_RETRIES=2
OPENAI_MAX_OUTPUT_TOKENS=2400
WEB_CONCURRENCY=2
GUNICORN_THREADS=4
GUNICORN_TIMEOUT=120
```

### `dms-frontend`

- Repository: `Naveen-Baburaj/dms-service`
- Branch: `Railway-hosting`
- Build context/root: `/`
- Dockerfile: `frontend/Dockerfile.railway`
- Health check: `/login`
- Public Railway HTTPS domain: required

Variables:

```text
PORT=3000
NODE_ENV=production
DMS_FRAPPE_SITE=dms.localhost
DMS_INTERNAL_API_URL=http://dms-backend.railway.internal:8000
```

Do not define `NEXT_PUBLIC_API_URL` on this service.

After the public frontend domain is known, set the backend variable to the exact
origin (without a trailing slash), then redeploy the backend:

```text
DMS_PUBLIC_ORIGIN=https://<frontend-domain>.up.railway.app
```

## Database migration gate

The local Frappe database is the source of truth. Import the newest verified
`dms.localhost` SQL gzip into the Railway `dms` database before the first backend
migration. Database dumps and site configuration backups must never be committed.

Required post-import census:

| DocType | Count |
|---|---:|
| DMS Company | 3 |
| DMS Lead | 339 |
| DMS Customer | 45 |
| DMS Vehicle | 104 |
| DMS Vehicle Sale | 339 |
| DMS Test Drive | 222 |
| DMS Booking | 222 |
| DMS Service Job | 1571 |
| DMS Invoice | 330 |

Inventory must total `104`: Honda `38`, NEXA `33`, Jaguar `33`.

## Acceptance gate

Hosting is complete only after all of the following pass through the public
frontend URL:

- `/login` returns HTTP 200.
- Admin login redirects to `/admin` without a cookie redirect loop.
- Honda, NEXA, and Jaguar manager logins reach only their own dashboards.
- Dashboard, leads, inventory, sales analytics, and test-drive data render.
- Vividity answers a first-turn analytics question and a same-conversation chart
  follow-up without `backend_llm_error`.
- Manager cross-tenant requests, including follow-ups, return no foreign data.
- GitHub `main` remains at its protected handoff SHA.

## Redeployment

Push application deployment fixes only to `Railway-hosting`. Railway services
must remain connected to that branch. Redeploy only the affected service after
checking its latest build/runtime logs; do not merge the deployment branch into
`main` unless the user separately authorizes it.

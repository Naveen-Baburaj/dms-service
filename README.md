# DMS — Dealer Management System

Enterprise multi-brand dealer management system for **Honda**, **NEXA**, and **Jaguar** with a unified Group Admin view and the **Vividity** AI assistant.

## Current Architecture

```text
frontend/   Next.js 15 dashboard
backend/    Frappe Framework app named dms
deploy/     Local operations/systemd assets and deployment examples
docs/       Architecture, API, operations, and security notes
```

The Frappe site is `dms.localhost`. The AI endpoint lives inside the Frappe app:

```text
POST /api/method/dms.api.ai_agent.query
```

The AI agent reads DMS DocTypes including:

```text
DMS Company
DMS Customer
DMS Vehicle
DMS Vehicle Sale
DMS Service Job
DMS Lead
DMS Booking
DMS Test Drive
DMS Invoice
```

No separate FastAPI AI backend is required.

## Working Local URLs

Use the `dms.localhost` hostname for both frontend and backend. Do **not** use `localhost:3000` for login because the Frappe `sid` session cookie must be visible to the Next.js middleware on the same hostname.

```text
Frontend: http://dms.localhost:3000/login
Backend:  http://dms.localhost:8000
AI API:   http://dms.localhost:8000/api/method/dms.api.ai_agent.query
Socket.IO: http://dms.localhost:9000
```

## Local Development / Demo Mode

For local testing, run the backend and frontend in **two visible terminals**. Do not run the hidden systemd frontend/runtime at the same time.

### 1. Repository and runtime paths

The current local setup uses:

```text
Repository: /home/navbc/projects/dms-service
Frontend:   /home/navbc/projects/dms-service/frontend
Bench:      /home/navbc/frappe/dms-frappe-bench
Site:       dms.localhost
Conda env:  dms-frappe
Node:       20.20.2
```

If your paths differ, substitute them in the commands below.

### 2. Stop hidden/supervised runtime before visible development

If the systemd runtime is installed, stop it before using `bench start` and the visible Next.js dev server:

```bash
sudo systemctl stop dms-dashboard-health.timer 2>/dev/null || true
sudo systemctl stop dms-dashboard-health.service 2>/dev/null || true
sudo systemctl stop dms-dashboard-recover.service 2>/dev/null || true
sudo systemctl stop dms-dashboard.target 2>/dev/null || true
```

For a machine dedicated to visible local development, prevent those units from starting automatically:

```bash
sudo systemctl disable dms-dashboard-health.timer 2>/dev/null || true
sudo systemctl disable dms-dashboard.target 2>/dev/null || true
```

### 3. Configure Frappe CORS for the local frontend

Run once, or whenever the site configuration is recreated:

```bash
conda activate dms-frappe
cd /home/navbc/frappe/dms-frappe-bench
bench --site dms.localhost set-config allow_cors "http://dms.localhost:3000"
```

Verify:

```bash
python3 - <<'PY'
import json
p = "sites/dms.localhost/site_config.json"
c = json.load(open(p))
print("allow_cors =", repr(c.get("allow_cors")))
PY
```

Expected:

```text
allow_cors = 'http://dms.localhost:3000'
```

### 4. Configure the frontend environment

The tracked example is `frontend/.env.example`.

Create the local file:

```bash
cd /home/navbc/projects/dms-service/frontend
cp .env.example .env.local
```

It must contain:

```text
NEXT_PUBLIC_API_URL=http://dms.localhost:8000
DMS_INTERNAL_API_URL=http://127.0.0.1:8000
DMS_FRAPPE_SITE=dms.localhost
NEXT_PUBLIC_APP_NAME=DMS
```

Why both backend URLs are required:

- `NEXT_PUBLIC_API_URL` is used by the browser and therefore uses `dms.localhost`.
- `DMS_INTERNAL_API_URL` is used by Next.js middleware on the server and uses loopback `127.0.0.1`.
- `DMS_FRAPPE_SITE` ensures middleware session checks target the correct Frappe site.

`.env.local` is intentionally ignored by Git and must not be committed.

### 5. Install frontend dependencies

Use the committed lockfile for deterministic installation:

```bash
source ~/.nvm/nvm.sh
nvm use 20.20.2
cd /home/navbc/projects/dms-service/frontend
npm ci
```

### 6. Terminal 1 — visible backend

Open a WSL terminal and keep it open:

```bash
conda activate dms-frappe
cd /home/navbc/frappe/dms-frappe-bench
bench start
```

The terminal should visibly run Frappe web, Redis cache/queue, Socket.IO, scheduler, workers, and the file watcher.

Expected local ports include:

```text
8000   Frappe web
9000   Socket.IO
11000  Redis queue
13000  Redis cache
```

### 7. Terminal 2 — visible frontend

Open a second WSL terminal and keep it open:

```bash
source ~/.nvm/nvm.sh
nvm use 20.20.2
cd /home/navbc/projects/dms-service/frontend
npm run dev -- --hostname 0.0.0.0
```

Expected frontend port:

```text
3000   Next.js
```

### 8. Open the application

Open exactly:

```text
http://dms.localhost:3000/login
```

Do not use `http://localhost:3000/login` for the authenticated demo flow.

### 9. Demo accounts

The demo login accepts these internal accounts. The password field is optional for the demo login flow.

```text
admin@dms.local
honda.manager@dms.local
nexa.manager@dms.local
jaguar.manager@dms.local
```

Expected routing:

```text
admin@dms.local            -> /admin
honda.manager@dms.local    -> /honda
nexa.manager@dms.local     -> /nexa
jaguar.manager@dms.local   -> /jaguar
```

The backend creates a normal Frappe session and sends an HttpOnly `sid` cookie. Next.js middleware validates that session through `dms.api.auth.me` before allowing protected dashboard routes.

## Quick Health Checks

With both visible terminals running:

### Backend ping

```bash
curl -sS \
  -H "Host: dms.localhost" \
  http://127.0.0.1:8000/api/method/ping
```

Expected response contains:

```text
pong
```

### Frontend login page

```bash
curl -sS -o /dev/null -w 'HTTP %{http_code}\n' \
  http://127.0.0.1:3000/login
```

Expected:

```text
HTTP 200
```

### Ports

```bash
ss -ltnp | grep -E ':3000|:8000|:9000|:11000|:13000'
```

### Demo login/session check

```bash
rm -f /tmp/dms_cookiejar.txt

curl -sS \
  --resolve dms.localhost:8000:127.0.0.1 \
  -c /tmp/dms_cookiejar.txt \
  -H 'Origin: http://dms.localhost:3000' \
  'http://dms.localhost:8000/api/method/dms.api.auth.demo_login?email=admin%40dms.local'

curl -sS \
  --resolve dms.localhost:8000:127.0.0.1 \
  -b /tmp/dms_cookiejar.txt \
  'http://dms.localhost:8000/api/method/dms.api.auth.me'
```

Both requests should return successful JSON and the cookie jar should contain `sid`.

## Frontend Validation

Before committing frontend changes:

```bash
source ~/.nvm/nvm.sh
nvm use 20.20.2
cd /home/navbc/projects/dms-service/frontend
npm ci
npm run type-check
npm run build
```

## Backend Database / Migration

Do **not** run `bench migrate` on every startup. Run it only when schema/DocType changes require migration:

```bash
conda activate dms-frappe
cd /home/navbc/frappe/dms-frappe-bench
bench --site dms.localhost migrate
```

The local MariaDB database is the source of truth for the current demo data.

## Authentication and Tenant Scope

The current demo uses Frappe session authentication.

- Group Admin can access all companies.
- Honda Manager is limited to Honda data.
- NEXA Manager is limited to NEXA data.
- Jaguar Manager is limited to Jaguar data.
- Cross-tenant requests must remain blocked.

The demo login endpoint is:

```text
GET /api/method/dms.api.auth.demo_login?email=<approved-account>
```

The authenticated session endpoint is:

```text
GET /api/method/dms.api.auth.me
```

## Vividity AI

The internal AI assistant is named **Vividity**. It operates against server-side DMS data and permissions and can return analytical text, tables, and charts for supported CRM/dealer-management questions.

Primary endpoint:

```text
POST /api/method/dms.api.ai_agent.query
```

Use the authenticated web application for normal demo testing so the server receives the correct Frappe session and tenant context.

## Stopping Local Development

Stop the frontend visibly with `Ctrl+C` in Terminal 2, then stop the backend with `Ctrl+C` in Terminal 1.

Check that the development ports are no longer occupied if required:

```bash
ss -ltnp | grep -E ':3000|:8000|:9000|:11000|:13000' || true
```

## Important Local-Run Notes

- Use `http://dms.localhost:3000`, not `http://localhost:3000`, for the authenticated UI.
- Keep `NEXT_PUBLIC_API_URL=http://dms.localhost:8000`.
- Keep `DMS_INTERNAL_API_URL=http://127.0.0.1:8000`.
- Keep `DMS_FRAPPE_SITE=dms.localhost`.
- Keep Frappe `allow_cors` set to `http://dms.localhost:3000` for this local demo configuration.
- Do not run the hidden systemd frontend at the same time as the visible Next.js dev server.
- Do not commit `.env.local`, Frappe `site_config.json`, database dumps, or API keys.

# DMS — Dealer Management System

Enterprise multi-brand dealer management system for **Honda**, **NEXA**, and **Jaguar** with a unified Group Admin view.

## Current Architecture

```text
frontend/   Next.js 15 dashboard
backend/    Frappe Framework app named dms
deploy/     Frappe-oriented Nginx and Supervisor examples
docs/       Architecture, API, deployment, and security notes
```

The AI dashboard endpoint now lives inside the Frappe app:

```text
POST /api/method/dms.api.ai_agent.query
```

The AI agent is database-backed. It reads from DMS DocTypes such as:

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

## Local URLs

```text
Frontend: http://localhost:3000/login
Backend:  http://dms.localhost:8000
AI API:   http://dms.localhost:8000/api/method/dms.api.ai_agent.query
```

## Frontend Quick Start

```bash
cd frontend
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://dms.localhost:8000
npm run dev
```

## Backend Quick Start

```bash
conda activate dms-frappe
cd ~/frappe/dms-frappe-bench
bench start
```

In a second terminal:

```bash
conda activate dms-frappe
cd ~/frappe/dms-frappe-bench
bench --site dms.localhost migrate
```

## AI API Smoke Test

```bash
curl -X POST \
  -H "Host: dms.localhost" \
  -H "Content-Type: application/json" \
  -H "x-user-role: tenant_user" \
  -H "x-tenant-id: toyota" \
  -d '{"query":"Show me last 3 months sales"}' \
  http://localhost:8000/api/method/dms.api.ai_agent.query
```

## User Roles

| Role | Access |
|------|--------|
| Honda User | Honda-only dashboard data |
| NEXA User | NEXA-only dashboard data |
| Jaguar User | Jaguar-only dashboard data |
| Group Admin | Cross-company dashboard data |

## Notes

- Current frontend mock login sends development headers to the Frappe API.
- `allow_guest=True` remains only for the mock-login phase.
- Remove mock headers and `allow_guest=True` after real Frappe authentication is wired end-to-end.

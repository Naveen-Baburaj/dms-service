# DMS — Dealer Management System

Enterprise multi-brand dealer management system for **Honda**, **NEXA**, and **Jaguar** with a unified Group Admin view.

## Project Structure

```
carcompany/
├── frontend/          # Next.js 15 application (Vercel)
├── backend/           # Frappe Framework app (Ubuntu VPS)
├── deploy/            # Nginx, Supervisor, setup scripts
└── docs/              # Architecture, API, Deployment, Security guides
```

## Quick Start

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local
# Set NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
```

Open [http://localhost:3000/login](http://localhost:3000/login)

### Backend

```bash
# Install Frappe bench, create site, install app
bench init ~/frappe-bench --frappe-branch version-15
cd ~/frappe-bench
bench get-app dms /path/to/backend/dms
bench new-site localhost --admin-password admin
bench --site localhost install-app dms
bench --site localhost migrate
bench start
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui, Recharts, TanStack Query |
| State | Zustand |
| Backend | Frappe Framework 15, Python 3.10+ |
| Database | MariaDB 10.6+ |
| Cache / Queue | Redis 7 |
| Authentication | JWT (HS256), 8h access + 30d refresh tokens |
| Deployment | Vercel (frontend) + Ubuntu VPS / Nginx / Gunicorn (backend) |

## User Roles

| Role | Access |
|------|--------|
| Honda User | Honda leads, customers, sales (read + write) |
| Honda Manager | Honda data (full CRUD + reports) |
| NEXA User | NEXA data only |
| NEXA Manager | NEXA data (full CRUD) |
| Jaguar User | Jaguar data only |
| Jaguar Manager | Jaguar data (full CRUD) |
| Group Admin | All companies — full read/write, analytics |

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Deployment Guide](docs/DEPLOYMENT.md)
- [Security Checklist](docs/SECURITY.md)

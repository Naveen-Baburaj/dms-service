# DMS System Architecture

## Overview

Multi-tenant Dealer Management System serving **Honda**, **NEXA**, and **Jaguar** brands under a single Group Admin umbrella. Built for horizontal scalability to 20+ companies.

```
┌──────────────────────────────────────────────────────────┐
│                    INTERNET                              │
└──────────────────────┬───────────────────────────────────┘
                       │
         ┌─────────────▼──────────────┐
         │      Vercel Edge CDN        │
         │   Next.js 15 Frontend       │
         │   (Mumbai / bom1 region)    │
         └─────────────┬──────────────┘
                       │ HTTPS / JWT
         ┌─────────────▼──────────────┐
         │         Nginx              │
         │  Rate Limiting + TLS       │
         └─────────────┬──────────────┘
                       │
         ┌─────────────▼──────────────┐
         │    Frappe Framework         │
         │    Python REST API          │
         │    Gunicorn (4 workers)     │
         └──────┬──────────┬──────────┘
                │          │
       ┌────────▼──┐  ┌────▼──────┐
       │  MariaDB  │  │   Redis   │
       │  (Primary)│  │  Cache /  │
       │           │  │  Queue    │
       └───────────┘  └───────────┘
```

## Data Isolation Architecture

Every record in the system carries `company_id`. Access control operates at three levels:

```
Level 1: JWT Token Payload
  → company, company_id, role embedded at login

Level 2: Frappe Permission Query Conditions (hooks.py)
  → SQL WHERE company_id = ? automatically appended

Level 3: API-layer check (require_company_access)
  → Explicit validation before any write operation
```

## Company Structure

```
Group Admin
├── Honda (company_id: HONDA-001)
│   ├── Honda Manager
│   └── Honda User
├── NEXA (company_id: NEXA-001)
│   ├── NEXA Manager
│   └── NEXA User
└── Jaguar (company_id: JAGUAR-001)
    ├── Jaguar Manager
    └── Jaguar User
```

## Frontend Architecture

```
app/
├── (auth)/login          # Public route — no auth required
└── (dashboard)/          # Protected by layout.tsx auth guard
    ├── honda/            # Only accessible to Honda users
    ├── nexa/             # Only accessible to NEXA users
    ├── jaguar/           # Only accessible to Jaguar users
    ├── admin/            # Only accessible to Group Admin
    ├── leads/            # Company-scoped data
    ├── customers/        # Company-scoped data
    ├── sales/            # Company-scoped data
    └── reports/          # Company-scoped (Group Admin sees all)
```

## Authentication Flow

```
User → POST /api/login (email + password)
     ↓
Frappe authenticates via frappe.auth.LoginManager
     ↓
Roles fetched → company/role determined
     ↓
JWT issued: { sub, email, company, company_id, role, exp }
Refresh token issued: 30-day validity
     ↓
Tokens stored in localStorage (access) + HttpOnly cookie (refresh)
     ↓
Subsequent requests: Authorization: Bearer <access_token>
     ↓
dms.api.auth.authenticate_jwt hook validates JWT on every request
     ↓
Permission Query Conditions filter DB rows by company_id
```

## Database Schema

### Core Tables

| Table | Key Fields | Purpose |
|-------|-----------|---------|
| `tabDMS Company` | name, company_name, brand | Multi-brand config |
| `tabDMS Lead` | company_id, lead_name, status, source | Lead pipeline |
| `tabDMS Customer` | company_id, customer_name, total_purchases | Customer 360 |
| `tabDMS Vehicle` | company_id, model, variant, stock_status | Inventory |
| `tabDMS Vehicle Sale` | company_id, customer_id, final_price, status | Sales |
| `tabDMS Booking` | company_id, customer_id, booking_amount | Advance bookings |
| `tabDMS Test Drive` | company_id, contact_name, scheduled_date | Test drive scheduling |
| `tabDMS Service Job` | company_id, vehicle_reg_no, total_amount | After-sales service |
| `tabDMS Invoice` | company_id, invoice_type, total_amount | Billing |

### Indexes (Critical for Performance)

```sql
-- Add these indexes for production performance
CREATE INDEX idx_dms_lead_company_status ON `tabDMS Lead` (company_id, status);
CREATE INDEX idx_dms_lead_creation ON `tabDMS Lead` (company_id, creation DESC);
CREATE INDEX idx_dms_customer_company ON `tabDMS Customer` (company_id, status);
CREATE INDEX idx_dms_sale_company_status ON `tabDMS Vehicle Sale` (company_id, status);
CREATE INDEX idx_dms_sale_creation ON `tabDMS Vehicle Sale` (company_id, creation DESC);
CREATE INDEX idx_dms_testdrive_date ON `tabDMS Test Drive` (company_id, scheduled_date);
```

## Scaling to 20+ Companies

The system is designed for expansion:

1. **New company** → Add `DMS Company` record
2. **New roles** → Add to `ROLE_COMPANY_MAP` in `auth.py`
3. **New dashboard** → Add endpoint in `dashboard.py`, add page in Next.js
4. **Frontend routing** → Update `getDashboardRoute()` in `types/auth.ts`

No database schema changes required for new companies.

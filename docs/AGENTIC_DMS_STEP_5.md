# Agentic DMS Step 5 — Frappe Session Authentication Cutover

## Status

Step 5 removes mock browser identity and development tenant headers from the
active DMS AI path. Authentication is now based on Frappe's server-side
session and the roles assigned to the authenticated Frappe user.

## Browser authentication

The browser signs in through:

```text
POST /api/method/dms.api.auth.login
```

Successful login creates the native Frappe `sid` session cookie. The login
response also returns the CSRF token belonging to that session. The frontend:

- sends requests with credentials enabled;
- sends the CSRF token on state-changing requests;
- does not create or persist mock JWTs;
- does not send `x-user-role`, `x-tenant-id`, or `x-client-user-id` as
  authority;
- does not decode an unverified JWT in Next.js middleware.

The Next.js middleware sends the opaque `sid` cookie to the authenticated
`dms.api.auth.me` endpoint before allowing protected navigation. It never
decodes or trusts browser identity claims. The backend remains authoritative
for session, role, company, record, conversation, and snapshot access.

## Backend authority

The authoritative inputs are:

1. `frappe.session.user`;
2. the roles assigned to that user;
3. the DMS role-to-company mapping;
4. the existing database tenant predicates.

Group Admin receives group scope. Honda, NEXA, and Jaguar users receive only
the company mapped from their Frappe role. Unknown or unmapped roles fail
closed.

The active AI query and conversation methods are authenticated Frappe methods
and are wrapped by the Step 4 request guard. Development role/tenant headers
are rejected while production authentication is enabled.

## Conversation ownership

Conversation ownership is derived from the authenticated session user and the
trusted backend scope. Browser-provided client IDs, role headers, tenant
headers, and demo identity fallbacks no longer participate in owner keys.

## Local credentials

The implementation batch provisions four local Frappe users for acceptance
and local use:

- `admin@dms.local` — Group Admin
- `honda.manager@dms.local` — Honda Manager
- `nexa.manager@dms.local` — NEXA Manager
- `jaguar.manager@dms.local` — Jaguar Manager

Passwords are randomly generated during execution. They are written only to a
mode-600 file outside the repository and copied to the Windows Downloads
folder after successful completion. Passwords are never printed to the batch
log or committed to Git.

## Runtime configuration

Successful cutover enables:

```text
dms_production_auth_required = 1
```

CORS is restricted to the local frontend origins required for development.
The frontend should be opened as:

```text
http://dms.localhost:3000
```

Using the same hostname as the Frappe backend allows the browser to send the
Frappe session cookie to both ports.

## Deferred scope

Step 5 does not add write-capable agent tools, cross-resource joins, vector
retrieval, SSO, OAuth, external identity providers, or production deployment.

## Provisioning idempotency

Local acceptance users are reconciled rather than blindly recreated. The
provisioner preserves unrelated Frappe roles, removes conflicting DMS scope
roles, assigns exactly one expected DMS authority role, resets the generated
password, and verifies database, cache Redis, queue Redis, role, and company
preconditions through `dms.auth_setup.preflight_probe`.

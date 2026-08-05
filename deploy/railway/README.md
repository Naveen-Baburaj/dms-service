# Railway deployment assets

Use these files together with `docs/RAILWAY_DEPLOYMENT.md`.

The repository is an isolated monorepo:

- `/frontend` is the Next.js service.
- `/backend` contains the Frappe custom app.
- Frappe production deployment requires a custom Frappe Docker image plus separate web, websocket, worker, scheduler, database and cache services.
- Do not use `bench start` as a Railway production start command.
- Do not expose production business data until development header authentication and guest data endpoints have been replaced by real Frappe session or signed-token authentication.

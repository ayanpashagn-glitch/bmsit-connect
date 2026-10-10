# v0.4 update

Read [DEPLOYMENT.md](DEPLOYMENT.md) before setup. Google sign-in, password recovery,
external image storage, optional uploads, shared Redis throttling and a Compose
deployment are now included. No provider credentials or hosting are provisioned.
The database remains PostgreSQL; no MongoDB rewrite is needed.

# BMSIT Connect v0.3 — team repository handoff

This repository contains the connected React frontend, compiled web UI, FastAPI
backend, PostgreSQL migrations, API schema and tests. Main branch contains the
v0.3 source snapshot, including migrations supporting upgrades from v0.2. This is the web application codebase; the
separate Expo mobile project is not included.

## Database teammate: start here

1. Read DATABASE_TEAM.md and UPGRADE_v0.3.md.
2. Provision a dedicated PostgreSQL database and keep DATABASE_URL server-side.
3. Copy .env.example to .env and configure the database URL and SMTP credentials.
   The SMTP sender supplies registration codes; credentials are not included.
4. Install Python 3.12 dependencies: `python -m pip install -r requirements.txt`.
5. Run `python start.py`. It runs Alembic migrations, bootstraps the initial admin
   interactively if needed, then serves frontend and API at http://localhost:8000.
6. API documentation is available at /docs. See openapi.json and
   schema-postgresql.sql for review. Use migrations instead of re-running SQL
   against an existing database. Back up existing databases before upgrades.
7. Before college deployment, run the included PostgreSQL CI/test workflow on a
   dedicated disposable test database. Tests delete and recreate application tables.

No frontend API wiring remains: the browser calls /v1 on the same host.
The API uses SQLAlchemy models and versioned Alembic migrations; do not rewrite
routes just to set the database URL. Existing unrelated college tables are not
mapped automatically. Existing v0.2 account access settings are preserved.

## Contents

- frontend/: React/TypeScript source.
- web/: prebuilt UI (Node is unnecessary merely to run the app).
- app/: backend routes, schemas, models, authentication, email delivery.
- migrations/: database schema history.
- tests/: API, permission, migration and browser workflow checks.
- VERIFICATION.md: checks performed and deployment checks still required.

## Clone the GitHub repository

```powershell
git clone https://github.com/ayanpashagn-glitch/Bmsit-connect.git
cd Bmsit-connect
```

This repository is private. The owner must grant the database teammate repository
access before they can clone it. No collaborator invitation has been sent.

Never commit .env, SMTP passwords, database credentials, real student records or
local databases. .env.example contains placeholders only.

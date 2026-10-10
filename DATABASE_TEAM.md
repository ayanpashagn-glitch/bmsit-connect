# v0.4 database note

Apply all migrations through `738630c7b772` after backup. New tables cover Google
nonces, password resets and failed object deletion retries; users have an optional
unique Google subject. Cover rows now support external object keys. See
DEPLOYMENT.md for storage migration and restore instructions.

# Handoff to the database / hosting team

The frontend and backend are already connected. React requests `/v1/...` from the
same host that serves the UI. No frontend API URL or route integration is pending.

Please provide:

1. A PostgreSQL database and server-side connection URL using the psycopg driver:
   `postgresql+psycopg://USER:PASSWORD@HOST:PORT/DATABASE`.
2. A database user with migration privileges for the initial setup. Use a dedicated
   database. Apply provider-required TLS settings and encode special URL characters.
3. Set `DATABASE_URL` in `.env` or the deployment secret store. Do not commit it.
4. Start with `python start.py` (or `START_WINDOWS.bat`). The versioned migrations
   create the 21 `bc_` application tables and Alembic version table automatically.
5. Create the first admin via the interactive first-run prompt. For automated
   hosting, run `alembic upgrade head`, then the private server command:
   `python -m app.cli create-admin --email STAFF_EMAIL` before starting the service.
6. Run tests against a separate disposable PostgreSQL database using
   `TEST_DATABASE_URL`. Never point tests at live student data.

Reference files:

- `schema-postgresql.sql`: SQL for reviewing the schema; prefer Alembic execution.
- `migrations/versions/`: frozen, versioned migration operations.
- `app/models.py`: ORM relationships/constraints.
- `openapi.json`: all API paths and input schemas.
- `frontend/src/api.ts`: integrated UI API client; no changes needed for DB switching.
- `README.md`: setup, roles, hosting and operational details.
- `VERIFICATION.md`: passed checks and remaining PostgreSQL verification.

No MySQL/MongoDB adapter or migration from the old demo's D1 JSON is included.
The server does not assume or modify unrelated existing college tables.

For public access, provision a Python/container host, HTTPS, backups and monitoring.
Configure `COOKIE_SECURE=true`, `PUBLIC_ORIGIN=https://YOUR_APP_HOST` and the host's
PORT/HOST environment. The web app and API run together in one process/container.
The previous public ChatGPT demo URL remains a separate demonstration.

Clone this repository from https://github.com/ayanpashagn-glitch/Bmsit-connect.
Read TEAM_HANDOFF.md for the database setup sequence. Hosting is not provisioned.

## v0.3 additions

Configure SMTP_HOST, SMTP_PORT, SMTP_FROM and (when required) SMTP_USERNAME /
SMTP_PASSWORD in the server environment. Port 587 defaults to STARTTLS; port 465
requires SMTP_SSL=true and SMTP_STARTTLS=false. No working email credentials are
bundled. Signup is blocked if delivery fails; admin bootstrap still works.
Set ALLOWED_EMAIL_DOMAINS to the real college email domains to restrict enrollment.
An OTP proves control of an email address, not enrollment or ownership of a USN.

Migration b81c7ad48d12 adds email OTPs, coordinator requests and cover-image storage,
plus cover URLs on student/club records. Existing account access settings remain
unchanged. Backups now include cover-image bytes; monitor database storage.

# BMSIT Connect v0.4 — connected frontend + backend

This is the integrated, self-hostable app. The existing BMSIT Connect design is
connected to the FastAPI backend, with real accounts, permissions and database
persistence. The compiled frontend is included: you do not need Node.js just to
run the delivered app. UI and API are served from the same address.

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for Google sign-in, SMTP, private storage,
Docker Compose with PostgreSQL/Redis/HTTPS, backups and capacity testing.

## What you need to do

1. Install **Python 3.12** if it is not already installed.
2. Extract this package and copy `.env.example` to `.env`.
3. Set `DATABASE_URL` to your PostgreSQL connection string.
4. Configure the SMTP email settings in `.env` for registration OTP delivery.
5. On Windows, double-click **START_WINDOWS.bat**.
6. On the first run, enter an administrator email, name and password when prompted.
7. Open **http://localhost:8000** and sign in.

The launcher installs dependencies on first use, runs the database migrations,
and starts the frontend and backend together. No frontend API URL or API wiring
is required. Keep the terminal open while using the app. Internet is needed for
the first dependency installation and for a remotely hosted database.

Database example (use your actual host, port, username and database):

```dotenv
DATABASE_URL=postgresql+psycopg://USERNAME:URL_ENCODED_PASSWORD@HOST:5432/DATABASE_NAME
```

Use the database provider's required TLS options. URL-encode special password
characters. Keep the `postgresql+psycopg://` prefix. The database team should
provide a PostgreSQL database and a user allowed to create/migrate this app's
tables. Use a dedicated database first. Existing unrelated tables are not imported
or mapped automatically. Never put the database URL in frontend source code.

Local commands if you prefer the terminal:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edit DATABASE_URL in .env now.
.\.venv\Scripts\python.exe start.py
```

Linux/macOS: `python3 -m venv .venv`, `source .venv/bin/activate`,
`pip install -r requirements.txt`, `cp .env.example .env`, edit the URL, then
`python start.py`. Do not overwrite an existing configured `.env`.

For a single-user local trial, `DATABASE_URL=sqlite:///./local.db` also works.
Use PostgreSQL for a shared college pilot; SQLite does not support the row locks
used to protect concurrent event capacity.

## Connected screens and workflows

| Frontend | Real backend behavior |
| --- | --- |
| Sign in / Create account | Email OTP verification, password hashing and session cookie; immediate student access |
| Admin → Students | Enable/disable access; no approval queue for new students |
| Admin → Clubs | Create/edit clubs, assign/revoke coordinator role, hide/restore clubs |
| Clubs | Cover photo, description, member/coordinator list, events, announcements, follow and recruitment |
| Students | Search and view student profiles, skills, public projects and club memberships |
| Profile / Club profile | Upload a cover photo from the device |
| Coordinator requests | Student requests club access; administrator approves or declines |
| Club workspace → Recruitment | Create/edit/close openings, review, shortlist, select/reject, CSV export |
| Club workspace → Interviews | Schedule/reschedule interview, venue, meeting URL and instructions |
| My dashboard → Applications / Interviews | Student application status, withdrawal and joining details |
| Club workspace → Members | Coordinators add existing students; recruitment selection also adds members |
| Events | Coordinator submission, college approval, registration and cancellation |
| Club workspace → Events | Edit events and view actual attendee roster |
| Project showcase | Publish/edit projects, save bookmarks, admin hide/restore |
| Find teammates | Team board, searchable student directory, requests and owner decisions |
| My dashboard → Teams | Join requests, owned teams and team memberships |
| Notifications | Private, persistent inbox with read status; polls every 30 seconds |
| Admin → Activity log | Server-recorded management activity |

There is no fake role switch, demo reset, hardcoded ASTRA application deadline or
sample member count in the connected app. The initial database starts empty.
Only operators can create administrators. Club coordinators have access only to
the clubs assigned to them. Students cannot see private review notes.

The UI is responsive for phone browsers. This package is a web app, not an
Android APK or an iOS App Store binary.

## Upgrade from v0.2

See `UPGRADE_v0.3.md` before replacing your running copy. Keep your existing
database and configuration; startup applies the new migration. Existing account
access settings are retained, including disabled accounts. A legacy v0.2 pending
account can be enabled in Administration → Students. New OTP-verified accounts
never enter that approval queue.

## First college setup

- Sign in using the administrator you created at startup.
- Have the coordinator and student register separate accounts.
- Students verify the six-digit code sent to their email and can sign in immediately.
- Students request coordinator access under Clubs → Explore club. Approve or decline
  in Administration → Coordinator requests. They can keep using the app while waiting.
- Add ASTRA (and other clubs) in Administration. Use **Assign role** to select a
  coordinator directly if needed. Assign `member` to remove that coordinator privilege.
- Coordinator signs in, opens Club workspace, creates a recruitment opening.
- Student applies under Clubs → Explore club → Apply for the role.
- Coordinator shortlists, then schedules the interview. Student checks the
  dashboard or inbox. Selecting the student creates their club membership.

Interview and event date inputs are explicitly in **IST**. The server accepts
aware timestamps and all screens display Asia/Kolkata time. A meeting link is
pasted by the coordinator; there is no automatic Microsoft Teams creation.
Event, interview and team notifications are in-app. Registration verification codes
are delivered by email. SMS and phone push are not included. When a visible event
is published/approved, every active account receives a bell notification, including
non-followers and non-registrants. Repeating an unchanged approval does not duplicate
the alert. Re-approval after edits/restoration sends a fresh alert. Administrator
edits to published events also send an update. The inbox polls every 30 seconds;
there is no separate scheduled day-of-event reminder service.

## Repository structure for the database/development team

- `frontend/src/App.tsx`: connected React screens, forms and navigation.
- `frontend/src/api.ts`: same-origin API requests and role-aware data loading.
- `frontend/components/`, `frontend/src/style.css`: reused campus UI system.
- `web/`: compiled frontend included in this release.
- `app/main.py`: FastAPI routes, browser cookie security and frontend serving.
- `app/models.py`: relational models and constraints.
- `app/security.py`: authentication and server-side account checks.
- `app/config.py`: server environment configuration.
- `migrations/versions/`: five versioned schema migrations.
- `openapi.json`, `schema-postgresql.sql`: API contract and database SQL reference.
- `start.py`, `START_WINDOWS.bat`, `Dockerfile`: startup and hosting.
- `tests/`: backend/security/integration tests.
- `tests/browser-flow.cjs`: browser workflow verification against a local QA server.
- `.github/workflows/test.yml`: disposable PostgreSQL CI checks.

Repository: https://github.com/ayanpashagn-glitch/Bmsit-connect

Start with `TEAM_HANDOFF.md` for the database team. Do not commit `.env`, local databases, `.venv`
or `node_modules`. This package is distinct from the still-running public demo;
the demo URL has not been converted into this Python-hosted application.

## Frontend development (only when changing the UI)

The existing frontend dependencies and pnpm lockfile are retained. Use Node.js
22.13+ and the `pnpm` version in `frontend/package.json`.

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm build
```

The build writes to `../web/`; restart the app after a rebuild. `pnpm dev` runs
a development UI that proxies `/v1` to an already-running backend on port 8000.
There are no database credentials or API base URLs to configure in the UI.
All registered API routes are available at `/docs` after startup.

## Authentication and operational notes

The browser uses an HttpOnly, SameSite=Strict session cookie. Cookie writes require
an allowed Origin and a custom request header; token values are not stored in
browser localStorage. Mobile/API clients can still use bearer-token login at
`/v1/auth/login`. Logout and administrator disable revoke stored sessions.

Password recovery is available from the sign-in screen through configured SMTP.
Google sign-in is available when GOOGLE_CLIENT_ID is configured. An emergency
operator reset is also available:
`python -m app.cli reset-password --email STUDENT_EMAIL`. It revokes sessions.
Registration uses email OTP verification: a six-digit code, 10-minute expiry,
60-second resend cooldown and five guesses per code. Resending invalidates the old
code; successful registration consumes it. Codes are hashed in the database and
are never returned by the production API or logged. SMTP failure leaves signup
blocked with a clear error. Existing accounts sign in with passwords as before.
Google Identity Services and reset emails are included; chat and phone push are not.

Cover photos accept JPEG, PNG and WebP up to 2 MB and 16 megapixels. The server
decodes, strips metadata, crops to 1200×400 and re-encodes them as JPEG. New cover bytes
are stored on persistent local disk or a private S3-compatible bucket and served
only to signed-in users. Legacy database covers remain readable. UPLOADS_ENABLED
can disable uploads entirely. Students can change
only their own cover; coordinators can change only their assigned club covers.
Profiles shown to other students omit email, USN and account/security fields.

The student directory is searched and paginated on the server. Staff data loads
when its workspace opens; notification polling fetches only an unread count.
Some catalogs/staff views still collect pages; measure realistic workloads before
a campus rollout. See DEPLOYMENT.md for the included capacity probe.
Set REDIS_URL for atomic shared authentication throttling across workers.
The blank-URL fallback is for single-process local development only. Review backups, HTTPS and access with college IT.

## Hosting the combined app

A Python/container-capable host is required for public access. The earlier
ChatGPT Sites demo host cannot run this FastAPI process. No external hosting
account has been provisioned by this package.

For HTTPS hosting set `COOKIE_SECURE=true`, `PUBLIC_ORIGIN` to the exact public
origin, `HOST=0.0.0.0`, and the platform's `PORT`. Set `HOST` and `PORT` in the
host process environment. Keep DATABASE_URL as a server secret. Ensure backups
and run the PostgreSQL tests before letting real students join.

Docker (build context: this directory):

```sh
docker build -t bmsit-connect .
# First deployment: migrate and create the first admin interactively.
docker run --rm --env-file .env bmsit-connect alembic upgrade head
docker run --rm -it --env-file .env bmsit-connect python -m app.cli create-admin --email YOUR_EMAIL
# Uses the compiled frontend already included in the image.
docker run --env-file .env -p 8000:8000 bmsit-connect
```

The Docker command's `--env-file` uses literal values: do not wrap the database
URL in quotes there. Do not run multiple migration processes simultaneously.
Use `/health` for process health and `/ready` for database table connectivity.

## Verification

See `VERIFICATION.md` for this release's actual checks and limitations.

```sh
pip install -r requirements-dev.txt
python -m pytest -q
```

Default tests use a disposable temporary SQLite database. For PostgreSQL,
set TEST_DATABASE_URL to a **dedicated disposable test database**, then run pytest.
Tests DROP and recreate this app's tables: never point tests at a college database.
The supplied CI workflow provisions an isolated PostgreSQL service.

References used for the underlying backend design:
https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/
https://docs.sqlalchemy.org/en/20/orm/session_basics.html

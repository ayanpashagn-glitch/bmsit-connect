# Verification — BMSIT Connect v0.4

Verified locally on 27 September 2026 with Python 3.12 and the production React build.

- **50 tests passed, 2 skipped** locally. The skipped tests require PostgreSQL
  concurrent row locks and a real Redis service. Both are enabled in GitHub CI. The first published revision passed all 51
  tests on PostgreSQL/Redis; the follow-up adds a names-only lookup regression test.
- TypeScript check, Vite production build, migration upgrade and Alembic drift check passed.
- Real Google token verifier tested with locally signed RSA tokens and a test
  certificate fetch: invalid signature/audience/issuer/expiry/domain/nonce rejected.
- Account linking requires existing password; student role cannot be injected;
  disabled users blocked; consumed Google nonces and reset tokens cannot be replayed.
- Password reset invalidates sessions; SMTP failure and account enumeration paths tested.
- Local cover persistence, legacy migration, replacement rollback, durable deletion
  retries, disabled uploads and private S3 request contract tested (botocore Stubber).
- Shared limiter fails closed on outage; notification count and bulk-read privacy tested.
- Four-account browser workflow passed again: signup, recruitment, interviews,
  rescheduling, selection, event approval/roster, projects, teams, profiles,
  covers, coordinator requests, bell notifications, mobile layout and logout.
- Google UI signup/returning login and password recovery passed using explicitly
  mocked Google provider + SMTP capture. Production API remained real. Live Google
  consent and delivery were not exercised. No browser runtime errors observed.

## PostgreSQL and deployment checks

GitHub run 36310925738 passed PostgreSQL migrations and schema drift, all 51 tests,
real Redis atomic counter checks, Compose configuration validation and Docker image
build. Its PostgreSQL probe used two workers, 1,000 accounts, 10,000 notifications,
50 concurrent clients and 1,000 authenticated read requests: zero failures,
211.37 requests/second, p50 161.99 ms, p95 641.42 ms. These runner measurements
are not a production capacity guarantee. See the PR checks for later revisions.

## Local capacity probe

SQLite, two workers, 1,000 registered fixture users and 10,000 notification rows:
1,000 authenticated read requests, 50 concurrent clients, zero failures;
259.48 requests/second, p50 136.20 ms, p95 528.32 ms (one local run).
These are environment-specific smoke-test results, not a production capacity promise.
The probe excludes login, uploads, SMTP and full browser workloads. PostgreSQL
capacity results must be read from the CI run or measured on deployment hardware.

## Remaining deployment checks

Real Google/SMTP/S3 credentials, DNS/HTTPS, college enrollment policy, Docker Compose
execution, backup restore drill and realistic peak-load testing on the chosen server
remain required. No external hosting or native mobile binary has been deployed.
Staff/catalog views still collect some paginated data; further paging is needed as
histories grow. See DEPLOYMENT.md for setup, costs, limits and operating responsibilities.

---

The earlier v0.3 verification below is historical, not a substitute for v0.4 checks.

# Verification — BMSIT Connect v0.3

Verified on 25 September 2026, using Python 3.12 and the production React build.

## Passed

- TypeScript type check and Vite production build.
- 27 backend, access-control, integration and migration tests; one PostgreSQL
  concurrency test skipped because no PostgreSQL server was available.
- Six community/upgrade tests rerun after the final event-update adjustment.
- OTP generated randomly, stored hashed, consumed on signup, rejected after expiry
  or five incorrect attempts; resend cooldown; SMTP failure rollback and domain gate.
- Student can sign in immediately after OTP registration. Role injection rejected.
- Coordinator request approval creates scoped coordinator membership. Non-admins
  cannot approve requests, promote members or demote another coordinator.
- Event publication notifies every active account, including non-registrants.
  Repeating the same approval or unchanged administrator edit does not duplicate
  alerts. Changed published event details generate an update. Read-status privacy.
- Student profiles include club memberships while excluding email, USN and flags.
- Cover upload authorization, file validation, JPEG re-encoding and replacement.
- v0.2-to-v0.3 migration retains existing users, clubs and access settings, including
  disabled and legacy pending accounts. Repeated startup migration is harmless.
- Alembic schema drift check; PostgreSQL SQL generation (compilation only).
- Existing interview, recruitment, team, event-capacity, cookie/CSRF and ownership
  tests still pass.

## Browser workflows

`tests/browser-flow.cjs` ran with four separate browser account contexts against
FastAPI and an isolated SQLite database. Production API responses were not mocked.
Only SMTP delivery was replaced by the explicit test-only mail capture in
`tests/browser_server.py`; the browser used the generated OTP.

Passed: admin club creation; OTP signup and immediate login; recruitment application,
shortlisting, private notes, interview/reschedule and selection; event approval,
registration and roster; project persistence; team request and acceptance; student
and club cover uploads; another student's profile and memberships; coordinator
adding a member; requesting and approving coordinator access; event bell alert for
a non-registrant; logout and reload. No browser runtime errors or API server errors
were observed. Mobile 390px had no horizontal overflow. Final desktop/mobile profile
screenshots were visually checked after dialog animations completed.

For reproduction, use a disposable local SQLite path containing `qa`, an absolute
QA_OTP_FILE outside the source tree and a test-only QA_PASSWORD. Run
`python -m tests.browser_server`, then `node tests/browser-flow.cjs` with
QA_ADMIN_EMAIL=admin@example.com, QA_COORDINATOR_EMAIL=coordinator@example.com,
QA_TEAMMATE_EMAIL=teammate@example.com and the same QA_PASSWORD/QA_OTP_FILE.
Playwright must be installed in your QA tooling environment. QA_BROWSER_PATH may
point to a compatible Chromium executable. Never deploy the test server.

## Not verified here

- Real SMTP authentication, sender verification and delivery to actual inboxes.
  These need your provider credentials and an end-to-end check after configuration.
- Your live database, PostgreSQL concurrency under load, or a 1,000-student load test.
  The disposable PostgreSQL CI workflow and concurrency test remain included.
- Windows execution: startup instructions/batch file are provided; execution here
  was Linux. No new external deployment or native Android/iOS binary was produced.

The httpx TestClient deprecation warning did not affect passing tests.

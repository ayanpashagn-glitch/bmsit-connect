# BMSIT Connect v0.4 deployment and operations

This release connects the existing student, coordinator and admin workflows to
PostgreSQL, email OTP/password recovery, optional Google sign-in and private media
storage. It is a responsive web app. Native Android/iOS distribution is separate.
No hosting, SMTP, Google or storage account is provisioned by this repository.

## Affordable pilot

Keep PostgreSQL: this app does not use MongoDB and needs no MongoDB subscription.
The supplied stack can run on a college-managed Linux machine with Docker Compose,
a DNS hostname, HTTPS access and persistent disk. Start with images disabled.
Software being self-hostable does not remove costs for a machine, electricity,
network, email delivery, backups or a person maintaining it. Do not assume a free
cloud tier can support a whole college or will remain available indefinitely.

## Local Windows trial

Copy `.env.example` to `.env` without overwriting existing credentials. Set
DATABASE_URL to a PostgreSQL connection string, or `sqlite:///./local.db` for a
single-user local trial. Configure SMTP for OTP and password recovery. Then:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
```

Create the admin when prompted, with a 12–128 character password. Open
http://localhost:8000. For a shared pilot use PostgreSQL, not SQLite.

## Google sign-in

1. Create/configure a Google Cloud OAuth consent screen and a **Web application**
   OAuth client. Follow your Google Workspace administrator's access policies.
2. Add exact Authorized JavaScript origins: `http://localhost:8000` for local
   testing and `https://YOUR_HOSTNAME` for deployment. Scheme and port matter.
3. Put the web client ID in `GOOGLE_CLIENT_ID`. It is public; no OAuth client
   secret belongs in this integration. The UI uses Google Identity Services'
   JavaScript ID-token callback, not a redirect-based authorization-code flow.
4. Restrict `ALLOWED_EMAIL_DOMAINS` to college-controlled email domains. If using
   Google Workspace, also set `GOOGLE_HOSTED_DOMAIN` to the verified Workspace
   domain; an email suffix alone is not a Workspace-membership claim.
5. Restart the app. Test a new account, a returning account, rejected domains and
   a disabled user. Google sign-in appears only when a client ID is configured.

The backend verifies signature, issuer, audience, expiry, email verification and
one-time browser nonce. Google identity is linked by stable `sub`, not mutable
email. Existing password accounts must confirm their password before linking.
New Google users enter name and USN and become ordinary students immediately;
coordinator/admin permissions are never accepted from the client. An entered USN
is not independently verified against the college's enrollment records. Third-party
Google account email addresses without a Google-hosted identity are rejected.
Google authentication does not require SMTP; OTP and password recovery do.

Reference: https://developers.google.com/identity/gsi/web/guides/verify-google-id-token

## SMTP and password recovery

Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD and SMTP_FROM. Use
STARTTLS on 587 or SSL on 465 according to the provider. Gmail-style providers may
require an app password; a normal account password is not necessarily accepted.
Keep all secrets in the deployment secret store or an uncommitted `.env`.

Set PUBLIC_ORIGIN to the exact HTTPS origin and COOKIE_SECURE=true in production.
Forgot-password responses do not reveal whether the email exists. Reset links
expire in 30 minutes, are single-use, are hashed at rest, and revoke existing
sessions when used. Reset tokens are removed from the browser URL on form load.
The operator CLI still supports emergency resets.

## Self-hosted HTTPS stack

1. Install Docker Engine and Compose on a college-approved Linux host. Point a
   real DNS hostname at it and open only ports 80/443 publicly.
2. Copy `deploy/.env.compose.example` to root `.env`. Set a long random hex
   POSTGRES_PASSWORD and use that **same** password in DATABASE_URL. Set
   CAMPUS_DOMAIN (hostname only), PUBLIC_ORIGIN, email/domain restrictions and
   provider credentials. Compose connects PostgreSQL at host `db`, not localhost.
3. Run `docker compose up -d --build`. A separate migration container runs before
   the app, avoiding concurrent migrations in each worker. Caddy provisions HTTPS
   when DNS and inbound access are correct.
4. Create the first administrator interactively:
   `docker compose exec app python -m app.cli create-admin --email YOUR_EMAIL`.
5. Check `docker compose ps`, `/health`, `/ready` and application logs. Test all
   three roles using separate accounts. Verify password recovery arrives in a real
   inbox before inviting students.

Only the proxy publishes ports. The app trusts proxy headers because its port is
reachable only inside this trusted Compose network. Do not expose port 8000 or
attach untrusted containers to that network while using forwarded-allow-ips `*`.
Keep database/Redis internal. The same Redis URL must be used by all app workers;
configured Redis failures block new authentication instead of bypassing throttling.
Redis is ephemeral rate-limit state, not the account/session database.

Two app workers use at most 20 pooled database connections with defaults
DB_POOL_SIZE=5, DB_MAX_OVERFLOW=5. Leave capacity for migration/maintenance/admin.
Adjust worker count and connection budgets together after measurement. Local media
volumes support multiple workers on this host. For multiple hosts use the same
private S3-compatible bucket, PostgreSQL and Redis, with identical configuration.
The Compose stack is one host, not a high-availability cluster.

## Images and object storage

UPLOADS_ENABLED=false hides upload controls and rejects new uploads server-side.
Existing cover images remain readable. This is the default in the Compose example.

When enabled, STORAGE_BACKEND=local writes to MEDIA_ROOT; mount persistent storage
and back it up. The Compose named volume is persistent across normal restarts.
Never run `docker compose down -v` against real data.

For S3-compatible storage set STORAGE_BACKEND=s3, S3_BUCKET, S3_REGION and optional
S3_ENDPOINT_URL (for a non-AWS provider). Use server-only S3_ACCESS_KEY_ID and
S3_SECRET_ACCESS_KEY or the hosting environment's AWS credential chain. Scope the
identity to GetObject/PutObject/DeleteObject on `BUCKET/covers/*`. Keep the bucket
private. The app serves images through authenticated routes, not public ACLs.
Database rows hold the object key, backend and size; secrets remain server-side.
Do not change a populated bucket or endpoint without transferring its objects.

JPEG/PNG/WebP input is capped at 2 MB and 16 megapixels, stripped/re-encoded to
1200×400 JPEG. One current cover is retained per owner. Replacements queue deletion
of the previous object; the maintenance worker retries failures hourly. Backup
versioning can retain additional versions, so set provider lifecycle/budget rules.
A crash between upload and commit can leave an unreferenced object: periodically
reconcile `covers/` inventory with `bc_cover_images` and `bc_storage_deletions`
before deleting confirmed orphans. No general video/document hosting is included.

## Upgrade and migrate existing covers

Back up the database and media first. Apply `alembic upgrade head` once. Existing
accounts and their access flags are preserved. Legacy database cover bytes remain
readable. Pause writes/uploads and run:

```sh
python -m app.storage_maintenance migrate
python -m app.storage_maintenance cleanup
```

`migrate` moves legacy DB/local covers to the configured backend while retaining
URLs; keep the old backend available until migration and verification finish.
Do not run migration concurrently with uploads or another migration process.
For Compose, stop app/maintenance, run the commands using `docker compose run
--rm maintenance ...`, then start app/maintenance. Failed deletion retries remain
in the database and return nonzero. Storage downgrades require a matching database
and media backup; automatic downgrade is deliberately refused.

## Backups and restore drill

Run `sh deploy/backup.sh /secure/backup/directory` from repository root. It briefly
stops writes and produces a PostgreSQL custom-format dump plus a local-cover
archive, then restarts the app. In S3 mode arrange a separate consistent bucket
backup/versioning policy. Copy backups encrypted to another machine; a backup on
the same disk alone does not protect against disk loss. Schedule daily backups and
retain copies according to the college's retention policy.

Restore into an **isolated** environment first: restore the dump with pg_restore
to an empty PostgreSQL database, extract the cover archive into its media volume
with ownership matching appuser, restore provider/configuration secrets separately,
and start the matching code version. Check account login, club data and image
reads. Avoid sending real emails from the restore environment. Record restore
success and elapsed recovery time. Never run destructive test fixtures on live data.

## Capacity and rollout

The student directory is server-searched and paginated. Notification polling reads
only a count; the inbox loads older records explicitly. Staff workspace data loads
on navigation. Some catalog and staff views still collect paginated records to
support cross-record controls; very large histories need further server-side
filtering. This release does not claim unlimited scalability.

Run `python -m tests.load_test --confirm-disposable --clients 50 --requests 1000`
with DATABASE_URL naming the dedicated PostgreSQL database `bmsit_loadtest`.
It resets that database, seeds 1,000 users and 10,000 notifications, starts two
workers and reports read-API p50/p95, throughput and failures. It does not model
1,000 simultaneous users, uploads, login bursts or every browser action. Test the
actual deployment hardware and peak workflows before expanding beyond a pilot.
The CI workflow runs PostgreSQL concurrency and Redis atomic-limit tests as well.

Start with one club and a small consenting student group. Before college-wide
use, name an accountable maintainer, agree support hours and a handover process,
verify enrollment policy with college IT, complete a backup restore drill, and
monitor uptime, database connections, disk/bucket usage, API failures and response
times. Provider setup and a successful staging pilot remain deployment gates.

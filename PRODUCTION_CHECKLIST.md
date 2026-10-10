# Production checklist (BMSIT Connect)

## Changes in this branch
- `AUTH_IP_LIMIT_PER_MINUTE` (default 300): the per-IP auth ceiling is now configurable. Campus Wi-Fi can share one public IP, so use ~3000 for a college rollout.
- OTP and password-reset emails are sent **after** the DB commit, so a slow SMTP server no longer pins a database connection or row lock (this could exhaust the pool during a signup rush).
- `SMTP_TIMEOUT_SECONDS` (default 10, was a hardcoded 15).
- Event broadcast to all students uses one bulk INSERT instead of thousands of ORM objects.
- Cover images are cacheable for 5 minutes (`private, max-age=300`); other `/v1/` responses stay `no-store`.

## Before launch (not code)
1. Written approval from the dean/college IT; named maintainer; domain such as `connect.<college>`.
2. PostgreSQL via `docker compose up -d --build` using `deploy/.env.compose.example` -> `.env`.
3. Set `PUBLIC_ORIGIN` to the exact `https://` address, `COOKIE_SECURE=true`, `CORS_ORIGINS=[]`, `ALLOWED_EMAIL_DOMAINS` to the college domain.
4. Real email provider (SES/Brevo/Resend) or Google sign-in with `GOOGLE_HOSTED_DOMAIN`. Do not use personal Gmail for 8k students.
5. Daily `deploy/backup.sh`, copied off the server; do one test restore.
6. Load test on the real server including a login burst.
7. Privacy notice / DPDP Act review; pilot with one club before the full college.

## Known follow-ups (not fixed here)
- `frontend/src/api.ts` `workspace()` fetches every list on every navigation; lazy-load per page before 8k users.
- No account deletion/export endpoint yet (data-protection requests).
- No USN format validation or enrollment-list check.
- Notifications are never purged.
- Frontend source has very long lines; run Prettier.

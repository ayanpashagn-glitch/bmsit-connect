# Update your existing app to v0.3

1. Stop the old server with Ctrl+C. Back up your database and existing configuration.
2. Extract the updated archive to a separate folder. Open its `bmsit-connect-fullstack`
   folder (the folder containing `start.py` and `requirements.txt`).
3. Copy your existing `.env` into that folder. If using local SQLite with a relative
   path such as `sqlite:///./local.db`, copy that database file too, while the old
   server is stopped. For PostgreSQL, keep the same connection URL.
4. Add the SMTP settings from the new `.env.example` to your existing `.env`.
   Do not replace the configured database URL with the example placeholder.
5. Open PowerShell in the new `bmsit-connect-fullstack` folder and run:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe start.py
```

Open http://localhost:8000. No virtual-environment activation is required for these
commands. If `py` is unavailable but Python 3.12 is installed, use `python` for the
first command. START_WINDOWS.bat also works from the extracted app folder.

Startup applies the new tables without deleting existing data. Your existing
admin account stays the same. Disabled accounts stay disabled. Existing v0.2
pending accounts keep their previous status; use Administration → Students →
Enable account for those legacy accounts if desired. New students verify their
email and need no administrator approval.

## Email configuration

Ask your email provider or college IT for SMTP connection details. Keep credentials
on the server; do not paste them into chat or frontend source. Example settings:

```dotenv
SMTP_HOST=YOUR_PROVIDER_SMTP_HOST
SMTP_PORT=587
SMTP_USERNAME=YOUR_SMTP_USERNAME
SMTP_PASSWORD=YOUR_SMTP_PASSWORD
SMTP_FROM=YOUR_VERIFIED_SENDER_ADDRESS
SMTP_STARTTLS=true
SMTP_SSL=false
```

For a provider using implicit TLS on port 465, set SMTP_PORT=465, SMTP_SSL=true and
SMTP_STARTTLS=false. Configure ALLOWED_EMAIL_DOMAINS using the actual college email
domains before a college-only launch. Leaving it empty permits any email domain.

## Try the new features

- Register: send an email code, enter it, create the account, then sign in.
- Students: search and open another student's profile; see projects and club roles.
- Edit profile: upload your cover photo. Club workspace → Edit club profile changes
  the club cover and description.
- Clubs → Explore club: view members, coordinators, events and recruitment; request
  coordinator access. Admin reviews in Administration → Coordinator requests.
- Club workspace → Members → Add member: add an existing student without granting
  coordinator or administrator permissions.
- Create an event and approve it as admin. Open another account's notification bell;
  it receives the event even without following the club or registering. In-app
  polling refreshes every 30 seconds; clicking the bell refreshes the workspace.

This release is the connected web app. It does not replace the old public demo URL
or generate native Android/iOS binaries. Your SMTP provider and live database still
need deployment-specific configuration and checks.

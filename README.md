# HashVera Academic Record Network

HashVera is a Flask-based academic-record platform for college demos and project submission. It stores records in a blockchain-style ledger, supports authenticated peer sync, uses role-based workflows, and now follows a campus-style identity model with `Campus ID` and `Campus Email ID`.

## What The App Does

- College-style account activation from a preloaded campus directory
- Role-based access for `Student`, `Faculty`, `Exam Cell`, and `Administrator`
- Blockchain-style record storage with hash chaining and verification
- Certificate verification and certificate-style record preview
- Student record requests and correction requests
- Faculty / Exam Cell review queue for approvals and corrections
- In-app notifications for account, record, request, and system events
- Admin tools for users, peers, audit logs, backups, imports, exports, and email checks
- Authenticated peer-node sync across multiple HashVera instances

## Technology Stack

- Python
- Flask
- SQLite
- HTML, CSS, Jinja
- SHA-256 hashing
- HMAC-based node signing
- PBKDF2 password hashing

## Project Structure

- [app.py](D:\EdTech Prjct\app.py): compatibility launcher so `python app.py` still works
- [run.py](D:\EdTech Prjct\run.py): package app launcher
- [hashvera](D:\EdTech Prjct\hashvera): real application package
- [hashvera\__init__.py](D:\EdTech Prjct\hashvera\__init__.py): app factory, blueprints, error handlers, shared template context
- [hashvera\routes\auth.py](D:\EdTech Prjct\hashvera\routes\auth.py): login, campus-ID signup, password flows
- [hashvera\routes\records.py](D:\EdTech Prjct\hashvera\routes\records.py): dashboard, records, notifications, review queue, profile pages
- [hashvera\routes\admin.py](D:\EdTech Prjct\hashvera\routes\admin.py): admin users, peers, audit, system tools, exports
- [hashvera\routes\api.py](D:\EdTech Prjct\hashvera\routes\api.py): peer/API endpoints
- [hashvera\database.py](D:\EdTech Prjct\hashvera\database.py): schema, runtime backfills, demo seeding, backup helpers
- [templates](D:\EdTech Prjct\templates): Jinja templates
- [static](D:\EdTech Prjct\static): styles, JS, logo, favicon assets
- [data\campus_directory_demo.csv](D:\EdTech Prjct\data\campus_directory_demo.csv): demo campus directory
- [data\edtech_sample_records.csv](D:\EdTech Prjct\data\edtech_sample_records.csv): sample academic records
- [hashvera.db](D:\EdTech Prjct\hashvera.db): active SQLite database
- [tests\test_app.py](D:\EdTech Prjct\tests\test_app.py): test suite
- [docs\DEMO_NOTES.md](D:\EdTech Prjct\docs\DEMO_NOTES.md): demo and presentation notes

## Identity Model

HashVera now uses:

- `Campus Email ID` for login
- `Campus ID` for record ownership and student record access
- `Username` as the display name inside the app

### Create Account Flow

1. User enters `Campus ID`
2. App looks up the preloaded campus directory
3. The stored `Full Name`, `Campus Email ID`, and `Role` appear automatically
4. User sets password
5. That campus identity can activate only once

## Role Model

### Student

- Activate account from campus directory
- Log in with campus email
- Manage own profile and profile photo
- Open only own records by matching `users.campus_id`
- Request record corrections
- Submit new record requests
- Use certificate verification and chain verification

### Faculty

- Create academic records
- Review student requests
- Review correction requests
- View profile directory (non-admin users only)
- Use dashboard staff summary

### Exam Cell

- Create records
- Edit records
- Archive and restore records
- Review student requests
- Review correction requests
- View profile directory (non-admin users only)
- Use dashboard staff summary

### Administrator

- Full user management
- Role assignment
- Disable / enable / remove users
- Peer management with connection testing and sync actions
- Audit logs
- Backups, imports, exports, and email checks
- Full profile visibility

## Campus Demo Data

The demo campus directory uses:

- `20` demo identities
- random `5-digit` campus IDs
- campus emails using `@hashvera.edu.in`

Edit [campus_directory_demo.csv](D:\EdTech Prjct\data\campus_directory_demo.csv) and restart the app if you want to refresh the live demo identities.

## Setup

1. Create and activate your virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Start the app:

```bash
python run.py
```

You can also use:

```bash
python app.py
```

Both launch the same package app now.

4. Open the local Flask URL in your browser.

## Important Environment Values

- `FLASK_SECRET_KEY` or `SECRET_KEY`
- `MAIL_HOST`
- `MAIL_PORT`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`
- `MAIL_USE_TLS`
- `MAIL_FROM`
- `SMS_PROVIDER`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_FROM_NUMBER`
- `ADMIN_EMAIL`
- `ADMIN_PASSWORD`
- `HASHVERA_PEER_SHARED_TOKEN`
- `NODE_NAME`
- `NODE_LOCATION`

## Peer Network Endpoints

Each node exposes:

- `GET /api/health`
- `GET /api/chain`
- `POST /api/chain/sync`

Peer requests are authenticated with:

- `X-HashVera-Token`

## Tests

The active suite lives in [test_app.py](D:\EdTech Prjct\tests\test_app.py).

It covers:

- login and account flows
- CSRF checks
- campus directory activation
- role-based permissions
- profile photo upload/remove
- record requests and review queue
- notifications
- backup/import flows
- peer/admin actions

## Presentation Notes

For college presentation and viva prep, use:

- [DEMO_NOTES.md](D:\EdTech Prjct\docs\DEMO_NOTES.md)

## Project Positioning

HashVera is now strong enough for:

- college final-year project demo
- blockchain + EdTech workflow demonstration
- secure academic record management prototype

It is still best treated as a project/demo system rather than a production campus ERP. For production, you would still extend it with stronger identity proofing, real object storage, stronger distributed consensus, and a hardened deployment setup.

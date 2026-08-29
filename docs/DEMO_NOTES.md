# HashVera Demo Notes

Use this file when you present HashVera in college.

## Demo Story

HashVera is a secure academic-record platform for colleges. It combines:

- campus-style account activation
- blockchain-style academic record storage
- role-based record workflows
- authenticated peer sync across nodes

The idea is to show that records like certificates, marksheets, and compliance documents can be stored in a tamper-evident ledger instead of a normal editable table.

## Login Model

- Login uses `Campus Email ID + Password`
- Record ownership uses `Campus ID`
- New account activation uses the preloaded campus directory

## Demo Roles

### Administrator

- `admin@hashvera.edu.in`
- Use the existing admin password already set in your live database

### Student Demo Accounts

- `10482@hashvera.edu.in` -> `Aswin Raj`
- `15837@hashvera.edu.in` -> `Rifan`
- `20391@hashvera.edu.in` -> `Thoufeeq`

### Faculty Demo Accounts

- `50314@hashvera.edu.in` -> `Arun Das`
- `52896@hashvera.edu.in` -> `Yashwini`

### Exam Cell Demo Accounts

- `72458@hashvera.edu.in` -> `Param`
- `76892@hashvera.edu.in` -> `Bindhya`

If an account is not activated yet:

1. Open `Create Campus Account`
2. Enter the campus ID
3. Let HashVera auto-load the identity
4. Set the password once

## Best Demo Flow

### 1. Student flow

- Log in as a student
- Open `Records`
- Show that the student can open only records linked to their own campus ID
- Submit a new record request
- Submit a correction request
- Open notifications

### 2. Faculty / Exam Cell flow

- Log in as Faculty or Exam Cell
- Show the dashboard summary:
  - pending requests
  - recently approved records
  - recently corrected records
- Open `Review Queue`
- Approve a student request
- Open the generated record

### 3. Administrator flow

- Log in as admin
- Open `Manage Users`
- Show role assignment, disable/enable, password reset, and remove user
- Open `Manage Peers`
- Show:
  - test peer connection
  - sync now
  - last sync result
- Open `System Tools`
- Show backup, import, test email, and export/backup history
- Open `Audit Activity`

### 4. Verification flow

- Open a record
- Show certificate-style preview
- Use `Verify Certificate`
- Use `Verify Chain`

## Key Points To Say In Viva

- Campus Email ID is used for login because that matches a real college identity model.
- Campus ID is used to link student records.
- Students cannot edit official records directly.
- Faculty can create records.
- Exam Cell can create, edit, archive, and restore records.
- Administrator handles user management, peer sync, system tools, and audit.
- The blockchain-style structure helps detect tampering through linked hashes.
- Peer sync makes the demo feel decentralized instead of single-instance only.

## If Someone Asks “Why Blockchain?”

Good short answer:

HashVera uses a blockchain-style ledger mainly for tamper evidence, auditability, and integrity checking. The goal is not cryptocurrency, but secure academic-record verification and trusted history of changes.

## If Someone Asks “Why Campus ID?”

Good short answer:

Campus ID is the academic identity of the student. Even if the display name changes, the record can still stay correctly linked to the right student account through campus ID.

## If Someone Asks “What Makes This Different?”

Good short answer:

Most student-record apps are simple CRUD systems. HashVera adds:

- campus-verified activation
- tamper-evident record chain
- role-based approval workflow
- peer sync
- audit logs
- certificate verification

## Demo Tips

- Keep one student, one faculty, one exam cell, and one admin account ready
- Make sure at least one record already exists for a student campus ID
- Keep the review queue populated with one pending request
- Keep one backup already created in System Tools
- Keep notifications available so the page is not empty during presentation

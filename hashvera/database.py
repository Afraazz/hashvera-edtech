import csv
import sqlite3
import os
import shutil
from datetime import datetime, timezone
from .config import AppConfig


CAMPUS_DIRECTORY_DATA_PATH = os.path.join(AppConfig.BASE_DIR, "data", "campus_directory_demo.csv")


def normalize_csv_row_keys(row):
    normalized = {}
    for key, value in row.items():
        clean_key = str(key or "").strip().lower()
        if clean_key:
            normalized[clean_key] = value
    return normalized

def get_connection():
    conn = sqlite3.connect(AppConfig.DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_runtime_schema(conn)
    return conn

def ensure_column(conn, table_name, column_name, definition):
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    if not cur.fetchone():
        return
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cur.fetchall()]
    if column_name not in columns:
        cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        conn.commit()

def ensure_runtime_schema(conn):
    # This matches the logic in app.py
    ensure_column(conn, "users", "campus_id", "TEXT")
    ensure_column(conn, "users", "email", "TEXT")
    ensure_column(conn, "users", "force_password_change", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "users", "disabled", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "users", "disabled_at", "TEXT")
    ensure_column(conn, "users", "disabled_reason", "TEXT")
    ensure_column(conn, "users", "last_login_at", "TEXT")
    ensure_column(conn, "users", "phone", "TEXT")
    ensure_column(conn, "users", "about_info", "TEXT")
    ensure_column(conn, "users", "profile_photo", "TEXT")
    
    ensure_column(conn, "blocks", "file_name", "TEXT")
    ensure_column(conn, "blocks", "file_path", "TEXT")
    ensure_column(conn, "blocks", "file_size", "INTEGER NOT NULL DEFAULT 0")
    ensure_column(conn, "blocks", "record_type", "TEXT NOT NULL DEFAULT 'Academic Record'")
    ensure_column(conn, "blocks", "record_status", "TEXT NOT NULL DEFAULT 'Active'")
    ensure_column(conn, "blocks", "updated_at", "TEXT")
    ensure_column(conn, "blocks", "last_modified_by", "TEXT")
    ensure_column(conn, "blocks", "signer_node", "TEXT")
    ensure_column(conn, "blocks", "signer_key_id", "TEXT")
    ensure_column(conn, "blocks", "certificate_id", "TEXT")
    ensure_column(conn, "blocks", "block_signature", "TEXT")
    
    ensure_column(conn, "support_tickets", "username", "TEXT")
    
    ensure_column(conn, "nodes", "peer_url", "TEXT")
    ensure_column(conn, "nodes", "node_type", "TEXT NOT NULL DEFAULT 'simulated'")
    ensure_column(conn, "nodes", "api_token", "TEXT")
    ensure_column(conn, "nodes", "signing_key_id", "TEXT")
    ensure_column(conn, "nodes", "signing_secret", "TEXT")
    ensure_column(conn, "nodes", "is_active", "INTEGER NOT NULL DEFAULT 1")
    ensure_column(conn, "nodes", "last_sync_status", "TEXT")
    ensure_column(conn, "nodes", "last_sync_result", "TEXT")
    ensure_column(conn, "nodes", "last_sync_attempt_at", "TEXT")
    
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS campus_directory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campus_id TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            campus_email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            department TEXT,
            is_registered INTEGER NOT NULL DEFAULT 0,
            registered_user_id INTEGER,
            registered_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient_username TEXT NOT NULL,
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            link_url TEXT,
            is_read INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS record_requests(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_type TEXT NOT NULL,
            requester_username TEXT NOT NULL,
            requester_role TEXT NOT NULL,
            campus_id TEXT,
            related_block_id INTEGER,
            requested_payload TEXT,
            request_note TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            reviewer_username TEXT,
            reviewer_note TEXT,
            linked_block_id INTEGER,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS password_resets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            otp_code TEXT NOT NULL,
            expiry TEXT NOT NULL,
            is_verified INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS support_tickets(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            category TEXT NOT NULL,
            message TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Open',
            admin_note TEXT,
            username TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_support_tickets_status ON support_tickets(status, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_recipient ON notifications(recipient_username, is_read, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_record_requests_status ON record_requests(status, created_at DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_campus_directory_registered ON campus_directory(is_registered, role)")
    conn.commit()


def seed_demo_campus_directory(conn):
    cur = conn.cursor()
    if not os.path.exists(CAMPUS_DIRECTORY_DATA_PATH):
        return

    current_rows = {
        row[0]: row
        for row in cur.execute(
            """
            SELECT campus_id, is_registered, registered_user_id, registered_at
            FROM campus_directory
            """
        ).fetchall()
    }

    with open(CAMPUS_DIRECTORY_DATA_PATH, "r", encoding="utf-8-sig", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        incoming_ids = set()
        for row in reader:
            row = normalize_csv_row_keys(row)
            campus_id = str(row.get("campus_id", "")).strip().upper()
            full_name = str(row.get("full_name", "")).strip()
            campus_email = str(row.get("campus_email", "")).strip().lower()
            role = str(row.get("role", "")).strip()
            department = str(row.get("department", "")).strip()
            if not all([campus_id, full_name, campus_email, role]):
                continue
            incoming_ids.add(campus_id)
            existing = current_rows.get(campus_id)
            if existing:
                cur.execute(
                    """
                    UPDATE campus_directory
                    SET full_name = ?, campus_email = ?, role = ?, department = ?
                    WHERE campus_id = ?
                    """,
                    (full_name, campus_email, role, department or None, campus_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO campus_directory(campus_id, full_name, campus_email, role, department)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (campus_id, full_name, campus_email, role, department or None),
                )

    for campus_id, row in current_rows.items():
        if campus_id in incoming_ids:
            continue
        if row[1]:
            continue
        cur.execute("DELETE FROM campus_directory WHERE campus_id = ?", (campus_id,))

    conn.commit()

def backup_database_file(label="manual"):
    os.makedirs(AppConfig.BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_label = "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in label).strip("-") or "manual"
    backup_name = f"hashvera-backup-{safe_label}-{timestamp}.sqlite3"
    backup_path = os.path.join(AppConfig.BACKUP_DIR, backup_name)
    shutil.copy2(AppConfig.DB_PATH, backup_path)
    return backup_path

def list_database_backups():
    os.makedirs(AppConfig.BACKUP_DIR, exist_ok=True)
    backups = []
    from .utils.files import format_file_size
    for file_name in sorted(os.listdir(AppConfig.BACKUP_DIR), reverse=True):
        full_path = os.path.join(AppConfig.BACKUP_DIR, file_name)
        if not os.path.isfile(full_path):
            continue
        backups.append(
            {
                "name": file_name,
                "size": format_file_size(os.path.getsize(full_path)),
                "created_at": datetime.fromtimestamp(os.path.getmtime(full_path), timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            }
        )
    return backups

def validate_database_file(path):
    conn = sqlite3.connect(path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cur.fetchall()}
        required_tables = {"users", "blocks", "nodes", "audit_logs"}
        if not required_tables.issubset(tables):
            missing = ", ".join(sorted(required_tables - tables))
            raise ValueError(f"Backup is missing required tables: {missing}")
    finally:
        conn.close()

def init_db():
    # Ensure directories exist
    os.makedirs(AppConfig.UPLOAD_DIR, exist_ok=True)
    os.makedirs(AppConfig.BACKUP_DIR, exist_ok=True)
    
    conn = sqlite3.connect(AppConfig.DB_PATH)
    cur = conn.cursor()
    
    # Primary tables
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            campus_id TEXT,
            email TEXT,
            password_hash TEXT NOT NULL,
            password_salt TEXT NOT NULL,
            force_password_change INTEGER NOT NULL DEFAULT 0,
            disabled INTEGER NOT NULL DEFAULT 0,
            disabled_at TEXT,
            disabled_reason TEXT,
            last_login_at TEXT,
            phone TEXT,
            about_info TEXT,
            profile_photo TEXT,
            role TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS campus_directory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            campus_id TEXT NOT NULL UNIQUE,
            full_name TEXT NOT NULL,
            campus_email TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL,
            department TEXT,
            is_registered INTEGER NOT NULL DEFAULT 0,
            registered_user_id INTEGER,
            registered_at TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS blocks(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            block_index INTEGER NOT NULL UNIQUE,
            timestamp TEXT NOT NULL,
            payload TEXT NOT NULL,
            previous_hash TEXT NOT NULL,
            block_hash TEXT NOT NULL,
            nonce TEXT NOT NULL,
            owner TEXT NOT NULL,
            file_name TEXT,
            file_path TEXT,
            file_size INTEGER NOT NULL DEFAULT 0,
            record_type TEXT NOT NULL DEFAULT 'Academic Record',
            record_status TEXT NOT NULL DEFAULT 'Active',
            certificate_id TEXT,
            updated_at TEXT,
            last_modified_by TEXT,
            signer_node TEXT,
            signer_key_id TEXT,
            block_signature TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS nodes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            location TEXT NOT NULL,
            status TEXT NOT NULL,
            last_synced_block INTEGER NOT NULL,
            integrity_hash TEXT NOT NULL,
            last_sync_time TEXT NOT NULL,
            peer_url TEXT,
            node_type TEXT NOT NULL DEFAULT 'simulated',
            api_token TEXT,
            signing_key_id TEXT,
            signing_secret TEXT,
            is_active INTEGER NOT NULL DEFAULT 1,
            last_sync_status TEXT,
            last_sync_result TEXT,
            last_sync_attempt_at TEXT
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_name TEXT NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            details TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    
    conn.commit()
    ensure_runtime_schema(conn)
    
    # Extra indexes
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_campus_id ON users(campus_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_blocks_certificate_id ON blocks(certificate_id)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_campus_directory_id ON campus_directory(campus_id)")
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_campus_directory_email ON campus_directory(campus_email)")
    
    conn.commit()
    seed_demo_campus_directory(conn)
    conn.close()

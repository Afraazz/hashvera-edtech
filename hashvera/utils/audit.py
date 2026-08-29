from .common import utc_now


def log_audit_action(conn, user, action, target_type="system", target_id="", details=None):
    if details is None:
        details = str(action).replace("_", " ").title()

    conn.execute(
        """
        INSERT INTO audit_logs(user_name, action, target_type, target_id, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user, action, target_type, str(target_id), details, utc_now()),
    )

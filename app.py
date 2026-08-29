import os

# HashVera Academic Record Network - System Heartbeat
from hashvera import create_app
from hashvera.config import Config, AppConfig
from hashvera.database import (
    init_db as _init_db,
    get_connection as _get_connection,
    backup_database_file,
)
from hashvera.utils.hashing import hash_password, validate_password_strength
from hashvera.utils.blockchain import add_record, fetch_chain_records, check_chain_validity
from hashvera.utils.notifications import create_notification
from hashvera.utils.audit import log_audit_action
from hashvera.utils.email import send_email_message
from hashvera.utils.common import utc_now


# Compatibility entrypoint:
# many local run commands and older tooling still use `python app.py`
# or import helpers from the root module.

INSTANCE_DIR = AppConfig.INSTANCE_DIR
UPLOAD_DIR = AppConfig.UPLOAD_DIR
BACKUP_DIR = AppConfig.BACKUP_DIR
DB_PATH = AppConfig.DB_PATH
SECRET_KEY_PATH = AppConfig.SECRET_KEY_PATH
NODE_SIGNING_SECRET_PATH = AppConfig.NODE_SIGNING_SECRET_PATH


def _sync_compat_paths():
    AppConfig.INSTANCE_DIR = INSTANCE_DIR
    AppConfig.UPLOAD_DIR = UPLOAD_DIR
    AppConfig.BACKUP_DIR = BACKUP_DIR
    AppConfig.DB_PATH = DB_PATH
    AppConfig.SECRET_KEY_PATH = SECRET_KEY_PATH
    AppConfig.NODE_SIGNING_SECRET_PATH = NODE_SIGNING_SECRET_PATH
    Config.INSTANCE_DIR = INSTANCE_DIR
    Config.UPLOAD_DIR = UPLOAD_DIR
    Config.BACKUP_DIR = BACKUP_DIR
    Config.DB_PATH = DB_PATH
    Config.SECRET_KEY_PATH = SECRET_KEY_PATH
    Config.NODE_SIGNING_SECRET_PATH = NODE_SIGNING_SECRET_PATH


def init_db():
    _sync_compat_paths()
    return _init_db()


def get_connection():
    _sync_compat_paths()
    return _get_connection()


_sync_compat_paths()
app = create_app()
application = app


if __name__ == "__main__":
    app.run(
        host=os.environ.get("FLASK_RUN_HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "5000")),
        debug=Config.env_flag("FLASK_DEBUG", True),
        use_reloader=True,
    )

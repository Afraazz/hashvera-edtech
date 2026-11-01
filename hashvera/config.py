import os
import socket
import secrets
import json


class Config:
    APP_TITLE = "HashVera"
    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

    # Environment configuration
    ENV_PATH = os.path.join(BASE_DIR, ".env")

    # Persistent storage directory
    DATA_DIR = os.environ.get("HASHVERA_DATA_DIR", BASE_DIR)

    # Application storage
    INSTANCE_DIR = os.path.join(DATA_DIR, "instance")
    DB_PATH = os.path.join(DATA_DIR, "hashvera.db")
    SAMPLE_DATA_PATH = os.path.join(BASE_DIR, "data", "edtech_sample_records.csv")
    UPLOAD_DIR = os.path.join(DATA_DIR, "uploads")
    BACKUP_DIR = os.path.join(INSTANCE_DIR, "backups")

    SECRET_KEY_PATH = os.path.join(INSTANCE_DIR, "secret_key")
    NODE_SIGNING_SECRET_PATH = os.path.join(INSTANCE_DIR, "node_signing_secret")

    ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    PROFILE_PHOTO_EXTENSIONS = {"png", "jpg", "jpeg"}

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"


    @staticmethod
    def load_local_env():
        if not os.path.exists(Config.ENV_PATH):
            return

        with open(Config.ENV_PATH, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

    @staticmethod
    def env_flag(name, default=False):
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "yes", "on"}

# Load environment variables before initializing other settings
Config.load_local_env()

class AppConfig(Config):
    @staticmethod
    def load_secret_key():
        configured_secret = os.environ.get("SECRET_KEY", "").strip() or os.environ.get("FLASK_SECRET_KEY", "").strip()
        if configured_secret:
            return configured_secret

        if os.path.exists(Config.SECRET_KEY_PATH):
            with open(Config.SECRET_KEY_PATH, "r", encoding="utf-8") as secret_file:
                existing_secret = secret_file.read().strip()
                if existing_secret:
                    return existing_secret

        os.makedirs(Config.INSTANCE_DIR, exist_ok=True)
        generated_secret = secrets.token_hex(32)
        with open(Config.SECRET_KEY_PATH, "w", encoding="utf-8") as secret_file:
            secret_file.write(generated_secret)
        return generated_secret

    @staticmethod
    def load_node_signing_secret():
        configured_secret = os.environ.get("NODE_SIGNING_SECRET", "").strip() or os.environ.get("HASHVERA_NODE_SIGNING_SECRET", "").strip()
        if configured_secret:
            return configured_secret

        if os.path.exists(Config.NODE_SIGNING_SECRET_PATH):
            with open(Config.NODE_SIGNING_SECRET_PATH, "r", encoding="utf-8") as secret_file:
                existing_secret = secret_file.read().strip()
                if existing_secret:
                    return existing_secret

        os.makedirs(Config.INSTANCE_DIR, exist_ok=True)
        generated_secret = secrets.token_hex(32)
        with open(Config.NODE_SIGNING_SECRET_PATH, "w", encoding="utf-8") as secret_file:
            secret_file.write(generated_secret)
        return generated_secret

    SECRET_KEY = load_secret_key()
    LOCAL_SIGNING_SECRET = load_node_signing_secret()
    
    SESSION_COOKIE_SECURE = Config.env_flag("SESSION_COOKIE_SECURE", False)
    PREFERRED_URL_SCHEME = "https" if SESSION_COOKIE_SECURE else "http"
    
    LOCAL_NODE_NAME = os.environ.get("NODE_NAME", socket.gethostname() or "HashVera-Node").strip() or "HashVera-Node"
    LOCAL_NODE_LOCATION = os.environ.get("NODE_LOCATION", "Local Application Instance").strip() or "Local Application Instance"
    LOCAL_SIGNING_KEY_ID = os.environ.get("NODE_SIGNING_KEY_ID", f"{LOCAL_NODE_NAME}-key").strip() or f"{LOCAL_NODE_NAME}-key"
    
    PEER_SHARED_TOKEN = os.environ.get("HASHVERA_PEER_SHARED_TOKEN", "").strip() or os.environ.get("PEER_SHARED_TOKEN", "").strip()
    PEER_REQUEST_TIMEOUT = int(os.environ.get("PEER_REQUEST_TIMEOUT", "5"))
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "").strip().rstrip("/")
    
    MAIL_HOST = os.environ.get("MAIL_HOST", "").strip()
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "").strip()
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "").strip()
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").strip().lower() == "true"
    MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@hashvera.edu.in").strip()
    MAIL_ENABLED = bool(MAIL_HOST and MAIL_FROM)

    SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "").strip().lower()
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
    TWILIO_FROM_NUMBER = os.environ.get("TWILIO_FROM_NUMBER", "").strip()
    SMS_ENABLED = bool(
        SMS_PROVIDER == "twilio"
        and TWILIO_ACCOUNT_SID
        and TWILIO_AUTH_TOKEN
        and TWILIO_FROM_NUMBER
    )

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
    AI_ASSISTANT_MODEL = os.environ.get(
        "HASHVERA_AI_MODEL",
        os.environ.get("OPENAI_MODEL", "gemini-2.0-flash"),
    ).strip() or "gemini-2.0-flash"
    AI_ASSISTANT_TIMEOUT = int(os.environ.get("HASHVERA_AI_TIMEOUT", "12"))

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, session, request, redirect, url_for, flash, render_template
from .config import AppConfig
from .database import get_connection, init_db
from .utils.common import format_local_timestamp, generate_csrf_token, validate_csrf_token
from .utils.notifications import get_notification_summary
from .utils.auth_helpers import require_login, can_create_records, can_edit_records, can_archive_records, can_review_requests
from .utils.records import can_view_record_details

def create_app():
    app = Flask(__name__, 
                template_folder="../templates", 
                static_folder="../static")
    
    app.config.from_object(AppConfig)
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    
    # Configure Logging
    if not app.debug and not app.testing:
        os.makedirs(AppConfig.INSTANCE_DIR, exist_ok=True)
        log_file = os.path.join(AppConfig.INSTANCE_DIR, "hashvera.log")
        file_handler = RotatingFileHandler(log_file, maxBytes=1024 * 1024 * 10, backupCount=10) # 10 MB per file, max 10 files
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('HashVera application startup')

    # Initialize database
    with app.app_context():
        init_db()

    # Register blueprints
    from .routes.auth import auth_bp
    from .routes.records import records_bp
    from .routes.admin import admin_bp
    from .routes.api import api_bp
    from .routes.main import main_bp
    
    app.register_blueprint(auth_bp)
    app.register_blueprint(records_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(main_bp)

    @app.before_request
    def enforce_csrf():
        if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        if request.endpoint and "api" in request.endpoint:
            return None

        token = request.form.get("csrf_token", "").strip()
        if not token and request.is_json:
            payload = request.get_json(silent=True) or {}
            token = str(payload.get("csrf_token", "")).strip()
        if not token:
            token = request.headers.get("X-CSRF-Token", "").strip()

        if validate_csrf_token(token):
            return None

        flash("Your session security token expired. Please try again.", "error")
        return redirect(request.referrer or url_for("auth.login"))

    @app.context_processor
    def inject_globals():
        # Always available helpers
        globals_dict = {
            "app_title": AppConfig.APP_TITLE,
            "format_local_time": format_local_timestamp,
            "csrf_token": generate_csrf_token,
            "can_view_record_details": can_view_record_details,
        }

        try:
            # Session/Role based helpers
            # Define staff roles for frontend visibility
            staff_roles = {"administrator", "faculty", "exam cell"}
            current_role = (session.get("role") or "").strip().lower()
            is_staff = current_role in staff_roles

            globals_dict.update({
                "is_admin": current_role == "administrator",
                "can_create_records": is_staff,
                "can_edit_records": is_staff,
                "can_archive_records": is_staff,
                "can_review_requests": is_staff,
            })

            # Dynamic counts (DB dependent)
            notification_summary = get_notification_summary()
            globals_dict["notification_unread_count"] = notification_summary["unread"]

            review_queue_pending_count = 0
            if can_review_requests() and session.get("user"):
                conn = get_connection()
                try:
                    pending_row = conn.execute(
                        "SELECT COUNT(*) AS total FROM record_requests WHERE status = 'Pending'"
                    ).fetchone()
                    review_queue_pending_count = pending_row["total"] if pending_row else 0
                finally:
                    conn.close()
            globals_dict["review_queue_pending_count"] = review_queue_pending_count

        except Exception as e:
            app.logger.error(f"Error in inject_globals: {e}", exc_info=True)
            # Fallback for missing keys if exception occurred
            globals_dict.setdefault("is_admin", False)
            globals_dict.setdefault("can_create_records", False)
            globals_dict.setdefault("can_edit_records", False)
            globals_dict.setdefault("can_archive_records", False)
            globals_dict.setdefault("can_review_requests", False)
            globals_dict.setdefault("notification_unread_count", 0)
            globals_dict.setdefault("review_queue_pending_count", 0)

        return globals_dict

    @app.errorhandler(403)
    def handle_forbidden(error):
        return render_template("403.html"), 403

    @app.errorhandler(404)
    def handle_not_found(error):
        return render_template("404.html"), 404

    @app.errorhandler(500)
    def handle_internal_error(error):
        app.logger.error(f"Internal server error: {error}", exc_info=True)
        return render_template("500.html"), 500

    return app

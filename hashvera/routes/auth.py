from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from ..database import get_connection
from ..utils.hashing import hash_password, verify_password, validate_password_strength
from ..utils.audit import log_audit_action
from ..utils.auth_helpers import require_login, generate_reset_token, verify_reset_token, create_otp_code, store_otp, verify_otp
from ..utils.email import send_reset_email
from ..utils.sms import send_sms_message
from ..utils.notifications import create_notification
from ..utils.common import utc_now, build_reset_link, normalize_campus_id
import sqlite3

auth_bp = Blueprint("auth", __name__)


SELF_SIGNUP_ROLES = {"Student", "Faculty", "Exam Cell"}


def get_directory_entry(cur, campus_id):
    return cur.execute(
        """
        SELECT id, campus_id, full_name, campus_email, role, department, is_registered, registered_user_id, registered_at
        FROM campus_directory
        WHERE campus_id = ?
        """,
        (campus_id,),
    ).fetchone()


def build_unique_display_name(cur, full_name, campus_id):
    existing = cur.execute("SELECT id FROM users WHERE username = ?", (full_name,)).fetchone()
    if not existing:
        return full_name
    return f"{full_name} [{campus_id}]"

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        campus_email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE lower(email) = ?", (campus_email,))
        user = cur.fetchone()
        
        if user and not user["disabled"] and verify_password(password, user["password_hash"], user["password_salt"]):
            session.clear()
            session["user"] = user["username"]
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["email"] = user["email"]
            session["campus_id"] = user["campus_id"] or ""
            
            cur.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (utc_now(), user["id"]))
            create_notification(conn, user["username"], "security", "New Login Detected", "Your account was successfully signed in.", url_for("records.dashboard"))
            log_audit_action(conn, user["username"], "LOGIN", "user", user["id"], "User signed in successfully.")
            conn.commit()
            conn.close()
            
            return redirect(url_for("records.dashboard"))

        if user and user["disabled"]:
            conn.close()
            flash("This account is currently disabled. Please contact the administrator.", "error")
            return render_template("login.html")
        
        conn.close()
        flash("Invalid campus email or password.", "error")
        
    return render_template("login.html")

@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    username = session.get("user")
    if username:
        conn = get_connection()
        log_audit_action(conn, username, "LOGOUT", "user", session.get("user_id"), "User signed out.")
        conn.commit()
        conn.close()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        campus_id = normalize_campus_id(request.form.get("campus_id", ""))
        password = request.form.get("password", "")
        if not campus_id:
            flash("Campus ID is required to activate your campus account.", "error")
            return render_template("register.html")

        password_error = validate_password_strength(password)
        if password_error:
            flash(password_error, "error")
            return render_template("register.html")

        password_hash, salt = hash_password(password)
        conn = get_connection()
        cur = conn.cursor()
        directory_entry = get_directory_entry(cur, campus_id)

        if not directory_entry:
            conn.close()
            flash("Campus ID not found in campus records.", "error")
            return render_template("register.html")

        if directory_entry["role"] not in SELF_SIGNUP_ROLES:
            conn.close()
            flash("This campus ID cannot be activated from self-service signup.", "error")
            return render_template("register.html")

        if directory_entry["is_registered"]:
            conn.close()
            flash("This campus ID has already been used to create an account.", "error")
            return render_template("register.html")

        existing_user = cur.execute(
            "SELECT id FROM users WHERE campus_id = ? OR lower(email) = ?",
            (campus_id, directory_entry["campus_email"].lower()),
        ).fetchone()
        if existing_user:
            cur.execute(
                """
                UPDATE campus_directory
                SET is_registered = 1,
                    registered_user_id = COALESCE(registered_user_id, ?),
                    registered_at = COALESCE(registered_at, ?)
                WHERE id = ?
                """,
                (existing_user["id"], utc_now(), directory_entry["id"]),
            )
            conn.commit()
            conn.close()
            flash("This campus ID has already been used to create an account.", "error")
            return render_template("register.html")

        username = build_unique_display_name(cur, directory_entry["full_name"], campus_id)
        campus_email = directory_entry["campus_email"].lower()
        role = directory_entry["role"]
        
        try:
            cur.execute(
                """
                INSERT INTO users(username, campus_id, email, password_hash, password_salt, force_password_change, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (username, campus_id, campus_email, password_hash, salt, 0, role, utc_now()),
            )
            user_id = cur.lastrowid
            cur.execute(
                """
                UPDATE campus_directory
                SET is_registered = 1, registered_user_id = ?, registered_at = ?
                WHERE id = ?
                """,
                (user_id, utc_now(), directory_entry["id"]),
            )
            log_audit_action(conn, username, "REGISTER", "user", user_id, f"Campus account activated for {campus_id}.")
            conn.commit()
            conn.close()
            flash("Campus account activated successfully. Please log in with your campus email ID.", "success")
            return redirect(url_for("auth.login"))
        except sqlite3.IntegrityError:
            conn.close()
            flash("This campus identity is already registered.", "error")
            return render_template("register.html")

    return render_template("register.html")


@auth_bp.route("/register/campus-lookup")
def register_campus_lookup():
    campus_id = normalize_campus_id(request.args.get("campus_id", ""))
    if not campus_id:
        return jsonify({"status": "empty"})

    conn = get_connection()
    cur = conn.cursor()
    directory_entry = get_directory_entry(cur, campus_id)
    conn.close()

    has_phone = False
    if directory_entry["is_registered"]:
        conn = get_connection()
        # Check by campus_id or campus_email to be safe
        user = conn.execute("SELECT phone FROM users WHERE campus_id = ? OR lower(email) = ?", 
                            (campus_id, directory_entry["campus_email"].lower())).fetchone()
        conn.close()
        if user and user["phone"]:
            has_phone = True

    return jsonify(
        {
            "status": "ok",
            "campus_id": directory_entry["campus_id"],
            "full_name": directory_entry["full_name"],
            "campus_email": directory_entry["campus_email"],
            "role": directory_entry["role"],
            "department": directory_entry["department"] or "",
            "is_registered": bool(directory_entry["is_registered"]),
            "has_phone": has_phone,
        }
    )


def send_password_recovery_otp(conn, user):
    otp = create_otp_code()
    sent, sms_message = send_sms_message(
        user["phone"],
        f"[HashVera] Your password recovery code is {otp}. It expires in 15 minutes.",
    )
    if sent:
        store_otp(conn, user["email"], otp)
    log_audit_action(
        conn,
        user["username"],
        "PASSWORD_RESET_SMS_REQUEST",
        "user",
        user["id"],
        f"Password recovery OTP generated for {user['phone']}. SMS status: {sms_message}",
    )
    return sent, sms_message


def flash_recovery_otp_status(sent, sms_message):
    if sent:
        flash("A fresh 6-digit verification code has been sent via SMS to your registered mobile number.", "success")
    else:
        flash(f"SMS was not sent: {sms_message}", "error")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        method = request.form.get("method", "link")
        
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, email, phone FROM users WHERE email = ?", (email,))
        user = cur.fetchone()

        if not user:
            conn.close()
            flash("No account found with that identity.", "error")
            return redirect(url_for("auth.forgot_password"))

        session["recovery_email"] = email
        
        if method == "otp":
            phone_verify = request.form.get("phone_verify", "").strip()
            registered_phone = user["phone"]
            
            if not registered_phone:
                conn.close()
                flash("No mobile number is registered with this account. Please use the Direct Link method instead.", "error")
                return redirect(url_for("auth.forgot_password"))
            
            # Simple normalization for comparison (remove spaces/dashes)
            def clean(p): return "".join(filter(str.isdigit, p))
            
            if clean(phone_verify) != clean(registered_phone):
                conn.close()
                flash("The mobile number you entered does not match our records.", "error")
                return redirect(url_for("auth.forgot_password"))
            
            sent, sms_message = send_password_recovery_otp(conn, user)
            conn.commit()
            conn.close()

            flash_recovery_otp_status(sent, sms_message)
            if sent:
                return redirect(url_for("auth.verify_otp_route"))
            return redirect(url_for("auth.forgot_password"))
            
        else:
            # Link method
            token = generate_reset_token(email)
            reset_link = build_reset_link(token)
            
            from ..utils.email import send_email_message
            subject = "HashVera Account Recovery"
            body = f"Hello {user['username']},\n\nPlease click the link below to reset your HashVera password:\n\n{reset_link}\n\nThis link expires in 15 minutes. If you did not request this, please secure your account."
            sent, message = send_email_message(email, subject, body)
            
            log_audit_action(conn, user["username"], "PASSWORD_RESET_LINK_REQUEST", "user", user["id"], f"Reset link generated: {token[:8]}...")
            conn.commit()
            conn.close()
            
            flash("A secure reset link has been sent to your registered campus email address.", "success")
            if not sent:
                flash(f"DEMO MODE: Reset link is {reset_link}", "success")
            return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")

@auth_bp.route("/forgot-password/verify", methods=["GET", "POST"])
def verify_otp_route():
    email = session.get("recovery_email")
    if not email:
        flash("Start the recovery process first.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        otp = request.form.get("otp", "").strip()
        conn = get_connection()
        if verify_otp(conn, email, otp):
            conn.commit()
            conn.close()
            session["otp_verified"] = True
            return redirect(url_for("auth.reset_password_otp"))
        else:
            conn.close()
            flash("Invalid or expired verification code.", "error")

    return render_template("verify_otp.html", email=email)


@auth_bp.route("/forgot-password/resend-code", methods=["POST"])
def resend_otp_code():
    email = session.get("recovery_email")
    if not email:
        flash("Start the recovery process first.", "error")
        return redirect(url_for("auth.forgot_password"))

    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT id, username, email, phone FROM users WHERE email = ?", (email,)).fetchone()

    if not user:
        conn.close()
        flash("No account found for this recovery session.", "error")
        return redirect(url_for("auth.forgot_password"))

    if not user["phone"]:
        conn.close()
        flash("No mobile number is registered with this account. Please restart recovery and use Direct Link.", "error")
        return redirect(url_for("auth.forgot_password"))

    sent, sms_message = send_password_recovery_otp(conn, user)
    conn.commit()
    conn.close()

    flash_recovery_otp_status(sent, sms_message)
    return redirect(url_for("auth.verify_otp_route"))


@auth_bp.route("/forgot-password/reset", methods=["GET", "POST"])
def reset_password_otp():
    email = session.get("recovery_email")
    if not email or not session.get("otp_verified"):
        flash("Unauthorized access to password reset.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        password_error = validate_password_strength(new_password)
        if password_error:
            flash(password_error, "error")
            return render_template("reset_password.html", email=email)

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", email=email)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        
        password_hash, salt = hash_password(new_password)
        cur.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, force_password_change = 0 WHERE email = ?",
            (password_hash, salt, email),
        )
        if user:
            log_audit_action(conn, user["username"], "PASSWORD_RESET", "user", user["id"], "Password reset via OTP verification.")
            create_notification(conn, user["username"], "account", "Password reset successful", "Your password has been updated via recovery flow.", url_for("auth.login"))
        
        conn.commit()
        conn.close()
        session.pop("recovery_email", None)
        session.pop("otp_verified", None)
        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", email=email)

    return render_template("forgot_password.html")

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    email = verify_reset_token(token)
    if not email:
        flash("This reset link is invalid or has expired.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        password_error = validate_password_strength(new_password)
        if password_error:
            flash(password_error, "error")
            return render_template("reset_password.html", token=token, email=email)

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template("reset_password.html", token=token, email=email)

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, username, password_hash, password_salt FROM users WHERE email = ?", (email,))
        user = cur.fetchone()
        
        if user and verify_password(new_password, user["password_hash"], user["password_salt"]):
            conn.close()
            flash("New password must be different from current password.", "error")
            return render_template("reset_password.html", token=token, email=email)

        password_hash, salt = hash_password(new_password)
        cur.execute(
            "UPDATE users SET password_hash = ?, password_salt = ?, force_password_change = 0 WHERE email = ?",
            (password_hash, salt, email),
        )
        if user:
            log_audit_action(conn, user["username"], "PASSWORD_RESET", "user", user["id"], "Password reset from email link.")
            create_notification(conn, user["username"], "account", "Password reset", "Your password was updated.", url_for("auth.login"))
        
        conn.commit()
        conn.close()
        flash("Password reset successful. Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token, email=email)

@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not require_login():
        return redirect(url_for("auth.login"))
    
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = ?", (session["user"],))
        user = cur.fetchone()

        if not user or not verify_password(current_password, user["password_hash"], user["password_salt"]):
            conn.close()
            flash("Current password is incorrect.", "error")
            return render_template("change_password.html")

        password_error = validate_password_strength(new_password)
        if password_error:
            conn.close()
            flash(password_error, "error")
            return render_template("change_password.html")

        if new_password != confirm_password:
            conn.close()
            flash("Passwords do not match.", "error")
            return render_template("change_password.html")

        password_hash, salt = hash_password(new_password)
        cur.execute("UPDATE users SET password_hash = ?, password_salt = ?, force_password_change = 0 WHERE username = ?", (password_hash, salt, session["user"]))
        log_audit_action(conn, session["user"], "CHANGE_PASSWORD", "user", user["id"], "User changed own password.")
        conn.commit()
        conn.close()
        flash("Password changed successfully.", "success")
        return redirect(url_for("records.dashboard"))

    return render_template("change_password.html")

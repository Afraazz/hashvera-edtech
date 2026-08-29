import smtplib
from email.message import EmailMessage
from ..config import AppConfig

def send_email_message(recipient_email, subject, content):
    if not AppConfig.MAIL_ENABLED:
        return False, "Email is not configured in this environment."

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = AppConfig.MAIL_FROM
    message["To"] = recipient_email
    message.set_content(content)

    try:
        with smtplib.SMTP(AppConfig.MAIL_HOST, AppConfig.MAIL_PORT, timeout=15) as smtp:
            if AppConfig.MAIL_USE_TLS:
                smtp.starttls()
            if AppConfig.MAIL_USERNAME:
                smtp.login(AppConfig.MAIL_USERNAME, AppConfig.MAIL_PASSWORD)
            smtp.send_message(message)
    except Exception as exc:
        return False, str(exc)

    return True, "Email sent successfully."

def send_reset_email(recipient_email, reset_link):
    content = (
        "Hello,\n\n"
        "Use the link below to reset your HashVera password:\n"
        f"{reset_link}\n\n"
        "This link expires in 30 minutes.\n"
    )
    return send_email_message(recipient_email, "HashVera Password Reset", content)

def send_admin_reset_email(recipient_email, username, temporary_password):
    content = (
        "Hello,\n\n"
        f"Your HashVera password was reset by the administrator for account: {username}\n"
        f"Temporary password: {temporary_password}\n\n"
        "Please log in with this temporary password and change it immediately.\n"
    )
    return send_email_message(
        recipient_email,
        "HashVera Password Changed by Administrator",
        content,
    )

def get_mail_service_status():
    if not AppConfig.MAIL_HOST:
        return False, "Email service is not configured. MAIL_HOST is missing."
    if AppConfig.MAIL_USERNAME and not AppConfig.MAIL_PASSWORD:
        return False, "Email service is incomplete. MAIL_PASSWORD is missing."
    if not AppConfig.MAIL_FROM:
        return False, "Email service is not configured. MAIL_FROM is missing."
    return True, f"Email service is configured for {AppConfig.MAIL_HOST}:{AppConfig.MAIL_PORT}."

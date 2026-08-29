import base64
import json
from urllib import parse, request
from urllib.error import HTTPError, URLError

from ..config import AppConfig


def get_sms_service_status():
    if not AppConfig.SMS_PROVIDER:
        return False, "SMS provider is not configured. Set SMS_PROVIDER=twilio and Twilio credentials in .env."

    if AppConfig.SMS_PROVIDER != "twilio":
        return False, f"Unsupported SMS provider: {AppConfig.SMS_PROVIDER}."

    missing = []
    if not AppConfig.TWILIO_ACCOUNT_SID:
        missing.append("TWILIO_ACCOUNT_SID")
    if not AppConfig.TWILIO_AUTH_TOKEN:
        missing.append("TWILIO_AUTH_TOKEN")
    if not AppConfig.TWILIO_FROM_NUMBER:
        missing.append("TWILIO_FROM_NUMBER")

    if missing:
        return False, "Missing SMS setting(s): " + ", ".join(missing)

    return True, "Twilio SMS service is configured."


def _format_phone_number(phone_number):
    value = (phone_number or "").strip().replace(" ", "").replace("-", "")
    if not value:
        return ""
    if value.startswith("+"):
        return value
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) == 10:
        return f"+91{digits}"
    return f"+{digits}" if digits else ""


def send_sms_message(phone_number, message):
    ready, status = get_sms_service_status()
    if not ready:
        return False, status

    to_number = _format_phone_number(phone_number)
    if not to_number:
        return False, "Registered mobile number is empty or invalid."

    endpoint = (
        "https://api.twilio.com/2010-04-01/Accounts/"
        f"{AppConfig.TWILIO_ACCOUNT_SID}/Messages.json"
    )
    payload = parse.urlencode(
        {
            "From": AppConfig.TWILIO_FROM_NUMBER,
            "To": to_number,
            "Body": message,
        }
    ).encode("utf-8")
    token = f"{AppConfig.TWILIO_ACCOUNT_SID}:{AppConfig.TWILIO_AUTH_TOKEN}".encode("utf-8")
    headers = {
        "Authorization": "Basic " + base64.b64encode(token).decode("ascii"),
        "Content-Type": "application/x-www-form-urlencoded",
    }

    try:
        sms_request = request.Request(endpoint, data=payload, headers=headers, method="POST")
        with request.urlopen(sms_request, timeout=10) as response:
            body = json.loads(response.read().decode("utf-8"))
            sid = body.get("sid", "unknown")
            return True, f"SMS queued successfully. Provider message id: {sid}"
    except HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(details)
            details = parsed.get("message", details)
        except json.JSONDecodeError:
            pass
        return False, f"Twilio rejected the SMS request: {details}"
    except URLError as exc:
        return False, f"Could not reach the SMS provider: {exc.reason}"
    except TimeoutError:
        return False, "SMS provider request timed out."

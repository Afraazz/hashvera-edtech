import secrets
from datetime import datetime, timedelta, timezone
from flask import request, url_for, current_app, session

def generate_csrf_token():
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_hex(32)
    return session["_csrf_token"]

def validate_csrf_token(token):
    expected = session.get("_csrf_token")
    if not expected or not token:
        return False
    return secrets.compare_digest(str(expected), str(token))

def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

def format_local_timestamp(value):
    if not value:
        return ""

    parsed_dt = None
    for pattern in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S"):
        try:
            parsed_dt = datetime.strptime(str(value), pattern)
            break
        except ValueError:
            continue

    if not parsed_dt:
        return value

    # IST offset is +5:30
    ist_dt = parsed_dt + timedelta(hours=5, minutes=30)
    return ist_dt.strftime("%d %b %Y, %I:%M %p IST")

def get_request_page(param_name="page", default=1):
    try:
        page = int(request.args.get(param_name, default))
    except (TypeError, ValueError):
        page = default
    return max(page, 1)

def paginate_items(items, page, per_page):
    total_items = len(items)
    total_pages = max(1, (total_items + per_page - 1) // per_page) if total_items else 1
    page = min(max(page, 1), total_pages)
    start = (page - 1) * per_page
    end = start + per_page
    return items[start:end], {
        "page": page,
        "per_page": per_page,
        "total_items": total_items,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1,
        "next_page": page + 1,
        "start_item": start + 1 if total_items else 0,
        "end_item": min(end, total_items),
    }

def normalize_campus_id(value):
    if not value:
        return ""
    return str(value).strip().upper()

def build_reset_link(token):
    return url_for("auth.reset_password", token=token, _external=True)

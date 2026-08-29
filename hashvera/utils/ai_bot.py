import json
import re
import urllib.error
import urllib.request

from ..config import AppConfig
from ..database import get_connection
from .blockchain import current_chain_summary


MAX_MESSAGE_LENGTH = 900
MAX_HISTORY_ITEMS = 6


KNOWLEDGE_CARDS = [
    {
        "keywords": {"verify", "verification", "certificate", "id", "hash", "authentic", "portal"},
        "answer": (
            "Use the public verification portal to check a certificate ID or block hash. "
            "HashVera confirms the record exists, checks the ledger chain, and avoids showing unnecessary private profile details."
        ),
        "actions": [{"label": "Open verification", "href": "/verify"}],
    },
    {
        "keywords": {"record", "records", "student", "marksheet", "certificate", "download", "attachment"},
        "answer": (
            "Students can open their own verified records from Records. Staff can manage records from the dashboard based on role permissions. "
            "If a record looks wrong, submit a correction request so the academic team can review it with an audit trail."
        ),
        "actions": [{"label": "View records", "href": "/my-records"}],
    },
    {
        "keywords": {"correction", "wrong", "mistake", "update", "edit", "change", "request"},
        "answer": (
            "For incorrect student data or certificate details, open the record and send a correction request. "
            "Faculty or Exam Cell users can review pending requests from the Review Queue."
        ),
        "actions": [{"label": "Review queue", "href": "/review-queue"}, {"label": "Support", "href": "/support"}],
    },
    {
        "keywords": {"support", "help", "ticket", "contact", "problem", "issue"},
        "answer": (
            "Use Support to create or track a help request. Logged-in users can see their support history, while administrators can manage tickets from Support Inbox."
        ),
        "actions": [{"label": "Open support", "href": "/support"}, {"label": "New ticket", "href": "/support/new"}],
    },
    {
        "keywords": {"blockchain", "ledger", "chain", "integrity", "audit", "node", "peer"},
        "answer": (
            "HashVera stores academic records as signed ledger blocks. Staff can run an integrity scan, inspect the chain explorer, and review public network audit data."
        ),
        "actions": [{"label": "Network audit", "href": "/network/audit"}, {"label": "Chain explorer", "href": "/chain/explorer"}],
    },
    {
        "keywords": {"password", "login", "otp", "account", "reset", "forgot"},
        "answer": (
            "If you cannot sign in, use Forgot Password to request an OTP. If your account is disabled or your role looks wrong, contact institutional support."
        ),
        "actions": [{"label": "Forgot password", "href": "/forgot-password"}, {"label": "Support", "href": "/support/new"}],
    },
    {
        "keywords": {"privacy", "private", "public", "data", "student", "visible"},
        "answer": (
            "Public verification is designed to prove authenticity without exposing unnecessary student profile data. "
            "Detailed record and profile views stay behind role-based access controls."
        ),
        "actions": [{"label": "Privacy", "href": "/privacy"}, {"label": "FAQ", "href": "/faq"}],
    },
]


ROLE_ACTIONS = {
    "Administrator": [
        {"label": "Manage users", "href": "/admin/users"},
        {"label": "Support inbox", "href": "/admin/support-inbox"},
        {"label": "System tools", "href": "/admin/system"},
    ],
    "Faculty": [
        {"label": "Profile directory", "href": "/profiles"},
        {"label": "Review queue", "href": "/review-queue"},
        {"label": "Verify credentials", "href": "/verify"},
    ],
    "Exam Cell": [
        {"label": "Review queue", "href": "/review-queue"},
        {"label": "Bulk minting", "href": "/bulk-mint"},
        {"label": "Archived records", "href": "/archived"},
    ],
    "Student": [
        {"label": "My records", "href": "/my-records"},
        {"label": "Support", "href": "/support"},
        {"label": "Verify credentials", "href": "/verify"},
    ],
}


def _tokens(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _safe_history(history):
    if not isinstance(history, list):
        return []

    clean_items = []
    for item in history[-MAX_HISTORY_ITEMS:]:
        if not isinstance(item, dict):
            continue
        role = item.get("role")
        text = str(item.get("text", "")).strip()
        if role not in {"user", "assistant"} or not text:
            continue
        clean_items.append({"role": role, "text": text[:MAX_MESSAGE_LENGTH]})
    return clean_items


def _dashboard_summary(session_data):
    role = session_data.get("role") or "Visitor"
    username = session_data.get("user") or "visitor"
    context = {
        "username": username,
        "role": role,
        "chain_length": 0,
        "latest_hash": "GENESIS",
        "open_support_tickets": 0,
        "pending_record_requests": 0,
        "unread_notifications": 0,
    }

    conn = get_connection()
    try:
        chain = current_chain_summary(conn)
        context["chain_length"] = chain.get("length", 0)
        context["latest_hash"] = chain.get("latest_hash", "GENESIS")

        if username != "visitor":
            support_row = conn.execute(
                "SELECT COUNT(*) AS total FROM support_tickets WHERE username = ? AND status != 'Closed'",
                (username,),
            ).fetchone()
            context["open_support_tickets"] = support_row["total"] if support_row else 0

            notifications_row = conn.execute(
                "SELECT COUNT(*) AS total FROM notifications WHERE recipient_username = ? AND is_read = 0",
                (username,),
            ).fetchone()
            context["unread_notifications"] = notifications_row["total"] if notifications_row else 0

        if role in {"Administrator", "Faculty", "Exam Cell"}:
            pending_row = conn.execute(
                "SELECT COUNT(*) AS total FROM record_requests WHERE status = 'Pending'"
            ).fetchone()
            context["pending_record_requests"] = pending_row["total"] if pending_row else 0
    finally:
        conn.close()

    return context


def verify_certificate(certificate_id):
    """
    Checks if a certificate exists in the blockchain.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT block_index, timestamp, payload, owner, record_type, record_status, signer_node FROM blocks WHERE certificate_id = ?",
            (certificate_id,),
        ).fetchone()
        if not row:
            return {"found": False, "message": f"No certificate found with ID '{certificate_id}'"}
        
        payload_data = {}
        try:
            payload_data = json.loads(row["payload"])
        except Exception:
            pass

        return {
            "found": True,
            "certificate_id": certificate_id,
            "block_index": row["block_index"],
            "timestamp": row["timestamp"],
            "owner": row["owner"],
            "student_name": payload_data.get("student_name", row["owner"]),
            "course": payload_data.get("course", "Unknown"),
            "document_name": payload_data.get("document_name", "Academic Record"),
            "record_type": row["record_type"],
            "status": row["record_status"],
            "signer_node": row["signer_node"],
        }
    finally:
        conn.close()


def get_my_support_tickets(username):
    """
    Retrieves the support tickets for the current logged-in user.
    """
    if not username or username == "visitor":
        return {"error": "Authentication required. Please log in to check support tickets."}
    
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, category, message, status, admin_note, created_at, updated_at FROM support_tickets WHERE username = ? ORDER BY created_at DESC",
            (username,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_my_records(username, session_data):
    """
    Retrieves the academic records belonging to the current student.
    """
    if not username or username == "visitor":
        return {"error": "Authentication required. Please log in to view academic records."}

    role = session_data.get("role")
    campus_id = session_data.get("campus_id")

    conn = get_connection()
    try:
        if role == "Student":
            if not campus_id:
                rows = conn.execute(
                    "SELECT block_index, timestamp, payload, record_type, record_status, certificate_id FROM blocks WHERE owner = ? ORDER BY block_index DESC",
                    (username,),
                ).fetchall()
                return [dict(row) for row in rows]
            else:
                all_blocks = conn.execute(
                    "SELECT block_index, timestamp, payload, record_type, record_status, certificate_id FROM blocks ORDER BY block_index DESC"
                ).fetchall()
                matching_blocks = []
                for r in all_blocks:
                    try:
                        p = json.loads(r["payload"])
                        if str(p.get("student_id", "")).strip().upper() == str(campus_id).strip().upper():
                            matching_blocks.append(dict(r))
                    except Exception:
                        pass
                return matching_blocks
        else:
            rows = conn.execute(
                "SELECT block_index, timestamp, payload, record_type, record_status, certificate_id FROM blocks ORDER BY block_index DESC LIMIT 10"
            ).fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def check_blockchain_integrity():
    """
    Scans the ledger chain and returns the validation result.
    """
    conn = get_connection()
    try:
        from .blockchain import fetch_chain_records, check_chain_validity
        rows = fetch_chain_records(conn)
        is_valid, issues = check_chain_validity(rows, conn)
        summary = current_chain_summary(conn)
        return {
            "is_valid": is_valid,
            "issues": issues,
            "length": summary.get("length", 0),
            "latest_hash": summary.get("latest_hash", "GENESIS"),
        }
    finally:
        conn.close()


def get_pending_correction_requests(role):
    """
    Retrieves pending correction requests for authorized staff.
    """
    if role not in {"Administrator", "Faculty", "Exam Cell"}:
        return {"error": "Access denied. Only staff users can view pending correction requests."}
    
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, request_type, requester_username, requester_role, campus_id, request_note, status, created_at FROM record_requests WHERE status = 'Pending' ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_notifications(username):
    """
    Retrieves unread notifications for the user.
    """
    if not username or username == "visitor":
        return {"error": "Authentication required. Please log in to view notifications."}
    
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, category, title, message, is_read, created_at FROM notifications WHERE recipient_username = ? AND is_read = 0 ORDER BY created_at DESC",
            (username,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def search_profiles(role, query):
    """
    Search profile directory in campus_directory.
    """
    if not role or role == "Visitor":
        return {"error": "Authentication required. Please log in to search profiles."}

    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT campus_id, full_name, campus_email, role, department FROM campus_directory WHERE full_name LIKE ? OR campus_id LIKE ? OR campus_email LIKE ? LIMIT 5",
            (f"%{query}%", f"%{query}%", f"%{query}%"),
        ).fetchall()
        
        results = []
        for r in rows:
            item = dict(r)
            if role == "Student":
                if item["role"] == "Student":
                    item["campus_email"] = "Hidden for privacy"
            results.append(item)
        return results
    finally:
        conn.close()


def execute_local_tool(name, args, session_data):
    username = session_data.get("user") or "visitor"
    role = session_data.get("role") or "Visitor"
    
    if name == "verify_certificate":
        cert_id = args.get("certificate_id")
        if not cert_id:
            return {"error": "Missing 'certificate_id' parameter."}
        return verify_certificate(cert_id)
        
    elif name == "get_my_support_tickets":
        return get_my_support_tickets(username)
        
    elif name == "get_my_records":
        return get_my_records(username, session_data)
        
    elif name == "check_blockchain_integrity":
        return check_blockchain_integrity()
        
    elif name == "get_pending_correction_requests":
        return get_pending_correction_requests(role)
        
    elif name == "get_notifications":
        return get_notifications(username)
        
    elif name == "search_profiles":
        query = args.get("query")
        if not query:
            return {"error": "Missing 'query' parameter."}
        return search_profiles(role, query)
        
    return {"error": f"Unknown tool: {name}"}


def _local_answer(message, session_data):
    clean_message = message.lower().strip()
    # Remove punctuation for matching
    clean_nopunct = re.sub(r'[^\w\s]', '', clean_message).strip()
    username = session_data.get("user") or "visitor"
    role = session_data.get("role") or "Visitor"
    context = _dashboard_summary(session_data)
    display_name = username.replace("_", " ").title() if username != "visitor" else ""

    # 0. Conversational / casual message detection
    greeting_words = {"hi", "hello", "hey", "hii", "hiii", "helo", "hola", "yo", "sup",
                      "good morning", "good afternoon", "good evening", "namaste", "whats up",
                      "wassup", "howdy", "greetings"}
    how_are_you = {"how are you", "how r u", "how are u", "how do you do", "hows it going",
                   "how is it going", "how you doing", "whats up", "wassup", "kaise ho",
                   "how are you doing", "are you fine", "are you okay", "you good"}
    who_are_you = {"who are you", "what are you", "what is your name", "whats your name",
                   "who r u", "what r u", "introduce yourself", "tell me about yourself"}
    what_can_you = {"what can you do", "what do you do", "help me", "what are your features",
                    "what is this", "how to use", "how does this work", "what is hashvera",
                    "features", "capabilities"}
    thank_words = {"thank you", "thanks", "thank u", "thankyou", "ty", "thx", "thanks a lot",
                   "thank you so much", "appreciated", "great thanks"}
    bye_words = {"bye", "goodbye", "see you", "see ya", "later", "good night", "gn",
                 "take care", "cya", "bye bye"}

    # Greeting
    if clean_nopunct in greeting_words or any(clean_nopunct.startswith(g) for g in greeting_words):
        if display_name:
            ans = f"Hey **{display_name}**! 👋 Welcome back to HashVera.\n\n"
        else:
            ans = "Hey there! 👋 Welcome to HashVera.\n\n"
        ans += "Here's what I can help you with:\n\n"
        ans += "- 🛡️ **Verify a certificate** — just paste the certificate ID\n"
        ans += "- 📄 **View your academic records** — say *\"my records\"*\n"
        ans += "- 🎫 **Check support tickets** — say *\"my tickets\"*\n"
        ans += "- ⛓️ **Blockchain status** — say *\"chain status\"*\n"
        ans += "- 🔔 **Notifications** — say *\"my notifications\"*\n"
        if context["open_support_tickets"]:
            ans += f"\n📌 You currently have **{context['open_support_tickets']}** open support ticket(s)."
        if context["unread_notifications"]:
            ans += f"\n🔔 You have **{context['unread_notifications']}** unread notification(s)."
        actions = ROLE_ACTIONS.get(role, [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}])[:3]
        return {"answer": ans, "actions": actions, "mode": "local"}

    # How are you
    if any(p in clean_nopunct for p in how_are_you):
        name_part = f", **{display_name}**" if display_name else ""
        ans = (
            f"I'm doing great{name_part}! 😊 Thanks for asking.\n\n"
            "I'm HashVera Assist — always here and ready to help you with your academic records, "
            "certificate verification, support tickets, and more.\n\n"
            "How can I help you today?"
        )
        actions = ROLE_ACTIONS.get(role, [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}])[:3]
        return {"answer": ans, "actions": actions, "mode": "local"}

    # Who are you
    if any(p in clean_nopunct for p in who_are_you):
        ans = (
            "I'm **HashVera Assist** 🤖 — your AI-powered assistant for the HashVera academic record verification platform.\n\n"
            "I can help you with:\n"
            "- 🛡️ Verifying certificates on the blockchain\n"
            "- 📄 Viewing your academic records\n"
            "- 🎫 Managing support tickets\n"
            "- ⛓️ Checking ledger integrity\n"
            "- 🔍 Searching the campus directory\n"
            "- 🔔 Checking your notifications\n\n"
            "Just ask me anything! 💬"
        )
        actions = [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}]
        return {"answer": ans, "actions": actions, "mode": "local"}

    # What can you do
    if any(p in clean_nopunct for p in what_can_you):
        name_part = f" **{display_name}**" if display_name else ""
        ans = (
            f"Great question{name_part}! Here's everything I can do for you:\n\n"
            "| Feature | How to ask |\n"
            "|---------|------------|\n"
            "| 🛡️ Verify a certificate | *\"verify STU-1001\"* |\n"
            "| 📄 View your records | *\"show my records\"* |\n"
            "| 🎫 Check support tickets | *\"my tickets\"* |\n"
            "| ⛓️ Blockchain status | *\"chain status\"* |\n"
            "| 🔔 Notifications | *\"my notifications\"* |\n"
            "| 🔍 Search profiles | *\"search profile John\"* |\n"
            "| 📋 Correction requests | *\"pending corrections\"* |\n\n"
            "Just type naturally — I'll understand! 🚀"
        )
        actions = ROLE_ACTIONS.get(role, [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}])[:3]
        return {"answer": ans, "actions": actions, "mode": "local"}

    # Thank you
    if any(p in clean_nopunct for p in thank_words):
        name_part = f" **{display_name}**" if display_name else ""
        ans = f"You're welcome{name_part}! 😊 Happy to help. Let me know if you need anything else! 💬"
        actions = ROLE_ACTIONS.get(role, [{"label": "FAQ", "href": "/faq"}])[:2]
        return {"answer": ans, "actions": actions, "mode": "local"}

    # Goodbye
    if clean_nopunct in bye_words or any(clean_nopunct.startswith(g) for g in bye_words):
        name_part = f", **{display_name}**" if display_name else ""
        ans = f"Goodbye{name_part}! 👋 Have a great day. I'll be right here whenever you need me! ✨"
        actions = []
        return {"answer": ans, "actions": actions, "mode": "local"}
    
    # 1. Certificate Verification Pattern: e.g. "verify certificate STU-1001" or just "STU-1001"
    cert_pattern = re.search(r"\b([a-zA-Z0-9]+-[a-zA-Z0-9]+)\b", message)
    if cert_pattern and any(kw in clean_message for kw in ["verify", "check", "certificate", "valid", "hash", "id"]):
        cert_id = cert_pattern.group(1).upper()
        res = verify_certificate(cert_id)
        if res.get("found"):
            ans = (
                f"### 🛡️ Certificate Verified Successfully!\n\n"
                f"- **Certificate ID:** `{res['certificate_id']}`\n"
                f"- **Student Name:** {res['student_name']}\n"
                f"- **Course:** {res['course']}\n"
                f"- **Document Type:** {res['document_name']} ({res['record_type']})\n"
                f"- **Status:** `{res['status']}`\n"
                f"- **Signing Node:** {res['signer_node']} (Block #{res['block_index']})\n"
                f"- **Timestamp:** {res['timestamp']}\n\n"
                f"The ledger blockchain confirms that this credential exists and has not been tampered with."
            )
            actions = [{"label": "Verify Portal", "href": "/verify"}]
        else:
            ans = f"🔍 **Certificate ID `{cert_id}` was not found** in the HashVera ledger. Please double-check the ID."
            actions = [{"label": "Verify Portal", "href": "/verify"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # 2. Blockchain Integrity Check
    if any(kw in clean_message for kw in ["integrity", "scan blockchain", "chain status", "ledger status"]):
        res = check_blockchain_integrity()
        status_str = "✅ VALID (No issues detected)" if res["is_valid"] else "❌ INVALID/COMPROMISED"
        ans = (
            f"### ⛓️ Ledger Integrity Report\n\n"
            f"- **Validation Status:** {status_str}\n"
            f"- **Chain Length:** {res['length']} blocks\n"
            f"- **Latest Block Hash:** `{res['latest_hash']}`\n\n"
            f"All academic records are signed by authorized node keys. You can view the full chain in the Explorer."
        )
        actions = [{"label": "Chain Explorer", "href": "/chain/explorer"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # 3. Support Tickets
    if any(kw in clean_message for kw in ["support", "ticket", "my tickets"]):
        if username == "visitor":
            ans = "🔒 Please log in to check your support tickets."
            actions = [{"label": "Log In", "href": "/login"}]
        else:
            tickets = get_my_support_tickets(username)
            if isinstance(tickets, dict) and "error" in tickets:
                ans = tickets["error"]
                actions = []
            elif not tickets:
                ans = "You do not have any support tickets open at the moment."
                actions = [{"label": "Open Ticket", "href": "/support/new"}]
            else:
                ans = f"### 🎫 Your Support Tickets ({len(tickets)})\n\n"
                for t in tickets[:3]:
                    status_emoji = "🟢" if t["status"] == "Open" else "🔴"
                    ans += f"- {status_emoji} **[{t['category']}]** {t['message'][:60]}...\n"
                    ans += f"  - *Status:* `{t['status']}` | *Created:* {t['created_at'][:16]}\n"
                    if t["admin_note"]:
                        ans += f"  - *Reply:* _{t['admin_note']}_\n"
                if len(tickets) > 3:
                    ans += f"\n*And {len(tickets) - 3} more tickets...*"
                actions = [{"label": "View Inbox", "href": "/support"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # 4. Academic Records
    if any(kw in clean_message for kw in ["my records", "my marksheets", "my certificates", "download record"]):
        if username == "visitor":
            ans = "🔒 Please log in to view your academic records."
            actions = [{"label": "Log In", "href": "/login"}]
        else:
            records = get_my_records(username, session_data)
            if isinstance(records, dict) and "error" in records:
                ans = records["error"]
                actions = []
            elif not records:
                ans = "No academic records found for your account."
                actions = []
            else:
                ans = f"### 🎓 Your Academic Records ({len(records)})\n\n"
                for r in records[:3]:
                    ans += f"- **{r['record_type']}:** `{r['certificate_id']}` | Status: `{r['record_status']}`\n"
                    try:
                        p = json.loads(r["payload"])
                        ans += f"  - *Document:* {p.get('document_name')}\n"
                    except Exception:
                        pass
                if len(records) > 3:
                    ans += f"\n*And {len(records) - 3} more records...*"
                actions = [{"label": "My Records", "href": "/my-records"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # 5. Pending Correction Requests
    if any(kw in clean_message for kw in ["pending correction", "correction requests", "review queue"]):
        if role not in {"Administrator", "Faculty", "Exam Cell"}:
            ans = "🔒 Only staff members can access the correction queue."
            actions = []
        else:
            requests = get_pending_correction_requests(role)
            if isinstance(requests, dict) and "error" in requests:
                ans = requests["error"]
                actions = []
            elif not requests:
                ans = "There are no pending correction requests in the queue."
                actions = [{"label": "Review Queue", "href": "/review-queue"}]
            else:
                ans = f"### 📋 Pending Correction Requests ({len(requests)})\n\n"
                for r in requests[:3]:
                    ans += f"- **Request #{r['id']}** by `{r['requester_username']}` ({r['requester_role']})\n"
                    ans += f"  - *Note:* \"{r['request_note']}\"\n"
                if len(requests) > 3:
                    ans += f"\n*And {len(requests) - 3} more requests...*"
                actions = [{"label": "Review Queue", "href": "/review-queue"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # 6. Notifications
    if any(kw in clean_message for kw in ["notifications", "alerts", "my alerts"]):
        if username == "visitor":
            ans = "🔒 Please log in to view your notifications."
            actions = [{"label": "Log In", "href": "/login"}]
        else:
            notifs = get_notifications(username)
            if isinstance(notifs, dict) and "error" in notifs:
                ans = notifs["error"]
                actions = []
            elif not notifs:
                ans = "You have no unread notifications."
                actions = []
            else:
                ans = f"### 🔔 Unread Notifications ({len(notifs)})\n\n"
                for n in notifs[:3]:
                    ans += f"- **{n['title']}** ({n['category']})\n"
                    ans += f"  - {n['message']}\n"
                actions = [{"label": "Notifications Hub", "href": "/notifications"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # 7. Search profiles
    search_match = re.search(r"(?:search profile|find student|lookup|search name|search for)\s+([a-zA-Z0-9_ ]+)", clean_message)
    if search_match:
        q = search_match.group(1).strip()
        if username == "visitor":
            ans = "🔒 Please log in to search the campus directory."
            actions = [{"label": "Log In", "href": "/login"}]
        else:
            profiles = search_profiles(role, q)
            if isinstance(profiles, dict) and "error" in profiles:
                ans = profiles["error"]
                actions = []
            elif not profiles:
                ans = f"No profile matching '{q}' was found in the directory."
                actions = []
            else:
                ans = f"### 🔍 Profile Search Results for '{q}':\n\n"
                for p in profiles:
                    ans += f"- **{p['full_name']}** ({p['role']})\n"
                    ans += f"  - *ID:* `{p['campus_id']}` | *Dept:* {p['department'] or 'General'}\n"
                    if p['campus_email'] != "Hidden for privacy":
                        ans += f"  - *Email:* {p['campus_email']}\n"
                actions = [{"label": "Profiles Directory", "href": "/profiles"}]
        return {"answer": ans, "actions": actions, "mode": "local_agent"}

    # Original keyword cards logic
    message_tokens = _tokens(message)
    best_card = None
    best_score = 0
    for card in KNOWLEDGE_CARDS:
        score = len(message_tokens & card["keywords"])
        if score > best_score:
            best_card = card
            best_score = score

    if best_card:
        answer = best_card["answer"]
        actions = list(best_card["actions"])
    else:
        if display_name:
            answer = f"I'm not quite sure what you mean, **{display_name}**. 🤔\n\n"
        else:
            answer = "I'm not quite sure what you mean. 🤔\n\n"
        answer += "Try asking me something like:\n"
        answer += "- *\"Verify certificate STU-1001\"*\n"
        answer += "- *\"Show my records\"*\n"
        answer += "- *\"Check my support tickets\"*\n"
        answer += "- *\"What is the blockchain status?\"*\n"
        actions = [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}]

    role_actions = ROLE_ACTIONS.get(role, [])
    action_keys = {item["href"] for item in actions}
    for action in role_actions:
        if action["href"] not in action_keys:
            actions.append(action)
        if len(actions) >= 4:
            break

    return {"answer": answer, "actions": actions[:4], "mode": "local"}


def _openai_messages(message, history, session_data):
    context = _dashboard_summary(session_data)
    system_prompt = (
        "You are HashVera Assist, a concise assistant for an academic record verification web app. "
        "Help users navigate verification, records, correction requests, support, ledger integrity, and account recovery. "
        "Do not invent private record data or reveal sensitive details. If a task needs staff action, point to the right workflow. "
        f"Current user: {context['username']} ({context['role']}). "
        f"Ledger blocks: {context['chain_length']}. Pending record requests: {context['pending_record_requests']}. "
        f"Open support tickets for the user: {context['open_support_tickets']}."
    )

    input_items = [{"role": "system", "content": system_prompt}]
    for item in _safe_history(history):
        input_items.append({"role": item["role"], "content": item["text"]})
    input_items.append({"role": "user", "content": message})
    return input_items


def _extract_response_text(payload):
    if payload.get("output_text"):
        return str(payload["output_text"]).strip()

    chunks = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text") or content.get("output_text")
            if text:
                chunks.append(str(text))
    return "\n".join(chunks).strip()


def _openai_answer(message, history, session_data):
    if not AppConfig.OPENAI_API_KEY:
        return None

    body = {
        "model": AppConfig.AI_ASSISTANT_MODEL,
        "input": _openai_messages(message, history, session_data),
        "max_output_tokens": 350,
    }
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {AppConfig.OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=AppConfig.AI_ASSISTANT_TIMEOUT) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return None

    answer = _extract_response_text(payload)
    if not answer:
        return None

    role = session_data.get("role") or "Visitor"
    return {
        "answer": answer,
        "actions": ROLE_ACTIONS.get(role, [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}])[:3],
        "mode": "openai",
    }


def _gemini_answer(message, history, session_data):
    if not AppConfig.GEMINI_API_KEY:
        return None

    tools_payload = [
        {
            "functionDeclarations": [
                {
                    "name": "verify_certificate",
                    "description": "Verify an academic certificate's authenticity, status, owner and signer node using its unique Certificate ID.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "certificate_id": {
                                "type": "STRING",
                                "description": "The unique certificate ID to verify, e.g. STU-1001, CP-1001, REQ-9001"
                            }
                        },
                        "required": ["certificate_id"]
                    }
                },
                {
                    "name": "get_my_support_tickets",
                    "description": "Retrieve the support tickets submitted by the current logged-in user including their status and replies.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "get_my_records",
                    "description": "Retrieve the academic records and marksheets owned by the current logged-in user.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "check_blockchain_integrity",
                    "description": "Perform an integrity scan of the ledger blockchain and return status, length, and validation result.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "get_pending_correction_requests",
                    "description": "Retrieve pending record/certificate correction requests. Only available for staff users (Faculty, Exam Cell, Administrator).",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "get_notifications",
                    "description": "Retrieve unread notifications and alerts for the current logged-in user.",
                    "parameters": {"type": "OBJECT", "properties": {}}
                },
                {
                    "name": "search_profiles",
                    "description": "Search campus directory profiles by name, email, or department.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "query": {
                                "type": "STRING",
                                "description": "Name, email, department, or student ID query to search"
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
    ]

    context = _dashboard_summary(session_data)
    username = context["username"]
    role = context["role"]

    system_instruction = (
        "You are HashVera Assist, a highly capable and intelligent AI assistant for HashVera, "
        "an academic record verification web app. You help users navigate verification, records, "
        "correction requests, support tickets, ledger integrity, notifications, and profile directory searches.\n"
        "You have access to live database and blockchain tools. ALWAYS use these tools when a user asks for "
        "specific information (e.g. verifying a certificate, checking their tickets, notifications, or records, "
        "or looking up someone in the directory).\n"
        f"Context: Current user is '{username}' with role '{role}'.\n"
        f"Ledger blocks: {context['chain_length']}. Pending record requests: {context['pending_record_requests']}.\n"
        "Guidelines:\n"
        "1. DO NOT invent private record data. Always fetch it using tools.\n"
        "2. If a tool returns an error (e.g. authentication or permission denied), convey it clearly.\n"
        "3. Provide answers in clean Markdown. Use bolding, lists, and formatting to make it extremely premium.\n"
        "4. Be concise but helpful.\n"
        "5. IMPORTANT: You are also a general-purpose AI. If the user asks a general knowledge question, asks for advice, or wants to chat about unrelated topics (like coding, math, history, etc), answer them naturally just like ChatGPT or Gemini would."
    )

    contents = []
    
    safe_hist = _safe_history(history)
    for h in safe_hist:
        gemini_role = "user" if h["role"] == "user" else "model"
        contents.append({
            "role": gemini_role,
            "parts": [{"text": h["text"]}]
        })

    contents.append({
        "role": "user",
        "parts": [{"text": message}]
    })

    model_name = AppConfig.AI_ASSISTANT_MODEL
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={AppConfig.GEMINI_API_KEY}"

    for _ in range(3):
        body = {
            "contents": contents,
            "systemInstruction": {
                "parts": [{"text": system_instruction}]
            },
            "tools": tools_payload,
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 800
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=AppConfig.AI_ASSISTANT_TIMEOUT) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = ""
            try:
                error_body = e.read().decode("utf-8")
            except Exception:
                pass
            try:
                error_json = json.loads(error_body)
                err_msg = error_json.get("error", {}).get("message", "API request failed.")
            except Exception:
                err_msg = error_body or str(e)
            
            # If it's a rate limit / quota issue, fallback to free unauthenticated LLM
            if e.code == 429 or "quota" in error_body.lower() or "rate" in error_body.lower():
                try:
                    from urllib.parse import quote as urlquote
                    # Add context for the free model
                    prompt = f"You are HashVera Assist. The user says: {message}"
                    safe_url = "https://text.pollinations.ai/" + urlquote(prompt)
                    free_req = urllib.request.Request(safe_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(free_req, timeout=10) as free_res:
                        free_ans = free_res.read().decode("utf-8")
                        return {
                            "answer": free_ans,
                            "actions": [],
                            "mode": "free_fallback"
                        }
                except Exception:
                    pass

                return {
                    "answer": f"⚠️ **Your Gemini API Key is out of quota!**\n\nGoogle blocked the key (`Limit: 0`). I also tried a backup AI service but it failed. Please update your API key in `.env`.\n\n*Error: {err_msg}*",
                    "actions": [],
                    "mode": "gemini"
                }

            return {
                "answer": f"⚠️ **AI assistant is temporarily unavailable.** Please try again in a moment.\n\n*Details: {err_msg}*",
                "actions": [],
                "mode": "gemini"
            }
        except Exception:
            return None  # fall back to local answer

        candidates = payload.get("candidates", [])
        if not candidates:
            return None

        candidate = candidates[0]
        content_obj = candidate.get("content", {})
        parts = content_obj.get("parts", [])
        
        function_calls = [p.get("functionCall") for p in parts if p.get("functionCall")]
        
        if not function_calls:
            text_response = "\n".join([p["text"] for p in parts if p.get("text")])
            return {
                "answer": text_response,
                "actions": ROLE_ACTIONS.get(role, [{"label": "FAQ", "href": "/faq"}, {"label": "Support", "href": "/support"}])[:3],
                "mode": "gemini"
            }

        contents.append(content_obj)

        response_parts = []
        for fc in function_calls:
            name = fc["name"]
            args = fc.get("args", {})
            tool_output = execute_local_tool(name, args, session_data)
            
            response_parts.append({
                "functionResponse": {
                    "name": name,
                    "response": {"output": tool_output}
                }
            })

        contents.append({
            "role": "function",
            "parts": response_parts
        })

    return None


def build_assistant_response(message, session_data, history=None):
    clean_message = str(message or "").strip()
    if not clean_message:
        return {"error": "Please enter a message."}
    if len(clean_message) > MAX_MESSAGE_LENGTH:
        return {"error": f"Please keep messages under {MAX_MESSAGE_LENGTH} characters."}

    # Try Gemini first (if API key is configured and working)
    if AppConfig.GEMINI_API_KEY:
        gemini_ans = _gemini_answer(clean_message, history or [], session_data)
        if gemini_ans:
            return gemini_ans

    # Try OpenAI (if API key is configured)
    if AppConfig.OPENAI_API_KEY:
        ai_answer = _openai_answer(clean_message, history or [], session_data)
        if ai_answer:
            return ai_answer

    # Smart local bot — works offline, no API limits
    return _local_answer(clean_message, session_data)

from flask import Blueprint, request, jsonify, session
from ..utils.auth_helpers import require_peer_token
from ..utils.blockchain import current_chain_summary, fetch_chain_records, serialize_block_record, validate_chain_payload, should_adopt_chain, replace_chain, sync_nodes
from ..database import get_connection
from ..utils.audit import log_audit_action
from ..utils.ai_bot import build_assistant_response

api_bp = Blueprint("api", __name__, url_prefix="/api")

@api_bp.route("/assistant", methods=["POST"])
def api_assistant():
    payload = request.get_json(silent=True) or {}
    result = build_assistant_response(
        payload.get("message", ""),
        session,
        payload.get("history", []),
    )
    if "error" in result:
        return jsonify({"status": "error", "message": result["error"]}), 400
    return jsonify({"status": "ok", **result})

@api_bp.route("/health")
def api_health():
    authorized, error_response = require_peer_token()
    if not authorized:
        message, status = error_response
        return jsonify({"status": "error", "message": message}), status
    return jsonify(current_chain_summary())

@api_bp.route("/chain")
def api_chain():
    authorized, error_response = require_peer_token()
    if not authorized:
        message, status = error_response
        return jsonify({"status": "error", "message": message}), status

    conn = get_connection()
    blocks = [serialize_block_record(row) for row in fetch_chain_records(conn)]
    summary = current_chain_summary(conn)
    conn.close()
    return jsonify(
        {
            "status": "ok",
            "node_name": summary["node_name"],
            "length": summary["length"],
            "latest_hash": summary["latest_hash"],
            "blocks": blocks,
        }
    )

@api_bp.route("/chain/sync", methods=["POST"])
def api_chain_sync():
    authorized, error_response = require_peer_token()
    if not authorized:
        message, status = error_response
        return jsonify({"status": "error", "message": message}), status

    payload = request.get_json(silent=True) or {}
    incoming_blocks = payload.get("blocks", [])
    source_node = str(payload.get("source_node", "peer")).strip() or "peer"
    
    valid, issues, normalized_rows = validate_chain_payload(incoming_blocks)
    if not valid:
        return jsonify({"status": "rejected", "issues": issues}), 400

    conn = get_connection()
    local_rows = fetch_chain_records(conn)
    if not should_adopt_chain(local_rows, normalized_rows):
        summary = current_chain_summary(conn)
        conn.close()
        return jsonify(
            {
                "status": "ignored",
                "message": "Incoming chain is not newer than the local valid chain.",
                "length": summary["length"],
                "latest_hash": summary["latest_hash"],
            }
        )

    replace_chain(conn, normalized_rows)
    latest_hash = normalized_rows[-1]["block_hash"] if normalized_rows else "GENESIS"
    latest_index = normalized_rows[-1]["block_index"] if normalized_rows else 0
    sync_nodes(conn, latest_hash, latest_index)
    
    log_audit_action(
        conn,
        source_node,
        "PEER_SYNC",
        "network",
        source_node,
        f"Accepted replicated chain from peer node {source_node}.",
    )
    conn.commit()
    conn.close()
    return jsonify({"status": "accepted", "length": len(normalized_rows), "latest_hash": latest_hash})

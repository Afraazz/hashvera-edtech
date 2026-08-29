from .hashing import build_block_hash, sign_block_data, serialize_payload
from ..config import AppConfig
from .common import utc_now
from .audit import log_audit_action
from .records import build_record_payload
import json
import secrets
import sqlite3

def current_chain_summary(conn=None):
    close_conn = False
    if conn is None:
        from ..database import get_connection
        conn = get_connection()
        close_conn = True
    
    cur = conn.cursor()
    cur.execute("SELECT block_index, block_hash FROM blocks ORDER BY block_index DESC LIMIT 1")
    row = cur.fetchone()
    
    if close_conn:
        conn.close()
        
    if row:
        return {
            "node_name": AppConfig.LOCAL_NODE_NAME,
            "length": row["block_index"],
            "latest_hash": row["block_hash"]
        }
    return {
        "node_name": AppConfig.LOCAL_NODE_NAME,
        "length": 0,
        "latest_hash": "GENESIS"
    }

def fetch_chain_records(conn):
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_index ASC")
    return cur.fetchall()

def serialize_block_record(row):
    return {
        "block_index": row["block_index"],
        "timestamp": row["timestamp"],
        "payload": row["payload"],
        "previous_hash": row["previous_hash"],
        "block_hash": row["block_hash"],
        "nonce": row["nonce"],
        "owner": row["owner"],
        "file_name": row["file_name"],
        "file_path": row["file_path"],
        "file_size": row["file_size"],
        "record_type": row["record_type"],
        "record_status": row["record_status"],
        "updated_at": row["updated_at"],
        "last_modified_by": row["last_modified_by"],
        "signer_node": row["signer_node"],
        "signer_key_id": row["signer_key_id"],
        "block_signature": row["block_signature"],
    }

def validate_chain_payload(incoming_blocks):
    if not isinstance(incoming_blocks, list):
        return False, ["Payload is not a list of blocks."], []
        
    normalized = []
    issues = []
    for block in incoming_blocks:
        normalized.append(block)
        
    return True, issues, normalized

def should_adopt_chain(local_rows, incoming_rows):
    if not incoming_rows:
        return False
    if not local_rows:
        return True
    
    local_len = len(local_rows)
    incoming_len = len(incoming_rows)
    
    if incoming_len > local_len:
        return True
    return False

def replace_chain(conn, normalized_rows):
    cur = conn.cursor()
    cur.execute("DELETE FROM blocks")
    for block in normalized_rows:
        cur.execute(
            """
            INSERT INTO blocks(
                block_index, timestamp, payload, previous_hash, block_hash, nonce, owner,
                file_name, file_path, file_size, record_type, record_status, 
                updated_at, last_modified_by, signer_node, signer_key_id, block_signature
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                block["block_index"], block["timestamp"], block["payload"], block["previous_hash"],
                block["block_hash"], block["nonce"], block["owner"], block["file_name"],
                block["file_path"], block["file_size"], block["record_type"], block["record_status"],
                block["updated_at"], block["last_modified_by"], block["signer_node"],
                block["signer_key_id"], block["block_signature"]
            )
        )

def sync_nodes(conn, latest_hash, latest_index):
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE nodes 
        SET last_synced_block = ?, integrity_hash = ?, last_sync_time = ? 
        WHERE node_type = 'local'
        """,
        (latest_index, latest_hash, utc_now())
    )

def add_record(owner, form_data, file_meta, conn=None, manual_index=None):
    payload = serialize_payload(build_record_payload(form_data, file_meta))

    close_conn = False
    if conn is None:
        from ..database import get_connection
        conn = get_connection()
        close_conn = True
        
    cur = conn.cursor()
    if manual_index is not None:
        next_index = manual_index
    else:
        cur.execute("SELECT block_index, block_hash FROM blocks ORDER BY block_index DESC LIMIT 1")
        previous_block = cur.fetchone()
        next_index = previous_block["block_index"] + 1 if previous_block else 1
    previous_hash = previous_block["block_hash"] if previous_block else "GENESIS"
    timestamp = utc_now()
    nonce = secrets.token_hex(8)
    block_hash = build_block_hash(next_index, timestamp, payload, previous_hash, owner, nonce)
    block_signature = sign_block_data(
        next_index, timestamp, payload, previous_hash, owner, nonce, block_hash,
        AppConfig.LOCAL_NODE_NAME, AppConfig.LOCAL_SIGNING_KEY_ID, AppConfig.LOCAL_SIGNING_SECRET
    )

    cur.execute(
        """
        INSERT INTO blocks(
            block_index, timestamp, payload, previous_hash, block_hash, nonce, owner,
            file_name, file_path, file_size, record_type, record_status, certificate_id, updated_at, last_modified_by,
            signer_node, signer_key_id, block_signature
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            next_index, timestamp, payload, previous_hash, block_hash, nonce, owner,
            file_meta["file_name"] if file_meta else None,
            file_meta["file_path"] if file_meta else None,
            file_meta["file_size"] if file_meta else 0,
            form_data["record_type"], form_data["record_status"],
            form_data.get("certificate_id"),
            timestamp, owner, AppConfig.LOCAL_NODE_NAME, AppConfig.LOCAL_SIGNING_KEY_ID, block_signature,
        ),
    )
    block_id = cur.lastrowid
    sync_nodes(conn, block_hash, next_index)
    log_audit_action(conn, owner, "ADD_RECORD", "block", block_id, f"Added {form_data['document_name']} for {form_data['student_id']}")
    
    if close_conn:
        conn.commit()
        conn.close()
    return block_id

def add_record_to_batch(owner, form_data, file_meta, conn, index, previous_hash):
    """Specific for batch operations where index and prev_hash are managed externally"""
    payload = serialize_payload(build_record_payload(form_data, file_meta))
    timestamp = utc_now()
    nonce = secrets.token_hex(8)
    
    block_hash = build_block_hash(index, timestamp, payload, previous_hash, owner, nonce)
    block_signature = sign_block_data(
        index, timestamp, payload, previous_hash, owner, nonce, block_hash,
        AppConfig.LOCAL_NODE_NAME, AppConfig.LOCAL_SIGNING_KEY_ID, AppConfig.LOCAL_SIGNING_SECRET
    )

    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO blocks(
            block_index, timestamp, payload, previous_hash, block_hash, nonce, owner,
            file_name, file_path, file_size, record_type, record_status, certificate_id, updated_at, last_modified_by,
            signer_node, signer_key_id, block_signature
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            index, timestamp, payload, previous_hash, block_hash, nonce, owner,
            file_meta["file_name"] if file_meta else None,
            file_meta["file_path"] if file_meta else None,
            file_meta["file_size"] if file_meta else 0,
            form_data["record_type"], form_data["record_status"],
            form_data.get("certificate_id"),
            timestamp, owner, AppConfig.LOCAL_NODE_NAME, AppConfig.LOCAL_SIGNING_KEY_ID, block_signature,
        ),
    )
    block_id = cur.lastrowid
    sync_nodes(conn, block_hash, index)
    log_audit_action(conn, owner, "ADD_RECORD", "block", block_id, f"Added {form_data['document_name']} for {form_data['student_id']}")
    
    return block_id, block_hash

def check_chain_validity(rows, conn):
    from .hashing import build_block_hash
    issues = []
    if not rows:
        return True, issues
        
    for i, block in enumerate(rows):
        if i == 0:
            if block["previous_hash"] != "GENESIS":
                issues.append({
                    "block_index": block["block_index"],
                    "issue_type": "GENESIS_MISMATCH",
                    "expected": "GENESIS",
                    "actual": block["previous_hash"],
                    "description": "First block does not have GENESIS as previous hash."
                })
        else:
            prev_block = rows[i-1]
            if block["previous_hash"] != prev_block["block_hash"]:
                issues.append({
                    "block_index": block["block_index"],
                    "issue_type": "CHAIN_BROKEN",
                    "expected": prev_block["block_hash"],
                    "actual": block["previous_hash"],
                    "description": "Previous hash does not match hash of preceding block."
                })
        
        recalc_hash = build_block_hash(
            block["block_index"], block["timestamp"], block["payload"],
            block["previous_hash"], block["owner"], block["nonce"]
        )
        if recalc_hash != block["block_hash"]:
            issues.append({
                "block_index": block["block_index"],
                "issue_type": "HASH_MISMATCH",
                "expected": recalc_hash,
                "actual": block["block_hash"],
                "description": "Block payload or metadata has been tampered with."
            })
            
    return len(issues) == 0, issues

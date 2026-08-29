import hashlib
import hmac
import secrets
import json

def hash_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        120000,
    ).hex()
    return digest, salt

def verify_password(password, stored_hash, stored_salt):
    computed_hash, _ = hash_password(password, stored_salt)
    return hmac.compare_digest(computed_hash, stored_hash)

def serialize_payload(payload):
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))

def build_block_hash(block_index, timestamp, payload_text, previous_hash, owner, nonce):
    block_material = f"{block_index}|{timestamp}|{payload_text}|{previous_hash}|{owner}|{nonce}"
    return hash_text(block_material)

def build_block_signature_material(
    block_index,
    timestamp,
    payload_text,
    previous_hash,
    owner,
    nonce,
    block_hash,
    signer_node,
    signer_key_id,
):
    return (
        f"{block_index}|{timestamp}|{payload_text}|{previous_hash}|{owner}|{nonce}|"
        f"{block_hash}|{signer_node}|{signer_key_id}"
    )

def sign_block_data(
    block_index,
    timestamp,
    payload_text,
    previous_hash,
    owner,
    nonce,
    block_hash,
    signer_node,
    signer_key_id,
    signing_secret,
):
    material = build_block_signature_material(
        block_index,
        timestamp,
        payload_text,
        previous_hash,
        owner,
        nonce,
        block_hash,
        signer_node,
        signer_key_id,
    )
    return hmac.new(
        signing_secret.encode("utf-8"),
        material.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

def validate_password_strength(password):
    if len(password) < 8:
        return "Password must be at least 8 characters long."
    if not any(char.isupper() for char in password):
        return "Password must include at least one uppercase letter."
    if not any(char.islower() for char in password):
        return "Password must include at least one lowercase letter."
    if not any(char.isdigit() for char in password):
        return "Password must include at least one number."
    if not any(not char.isalnum() for char in password):
        return "Password must include at least one special character."
    return None

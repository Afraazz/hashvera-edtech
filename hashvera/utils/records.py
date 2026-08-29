import json
from flask import session, url_for
from .files import format_file_size
from .common import normalize_campus_id

def build_record_payload(form_data, file_meta):
    return {
        "student_id": form_data["student_id"],
        "student_name": form_data["student_name"],
        "course": form_data["course"],
        "document_name": form_data["document_name"],
        "certificate_id": form_data["certificate_id"],
        "storage_node": form_data["storage_node"],
        "record_notes": form_data["record_notes"],
        "record_type": form_data["record_type"],
        "record_status": form_data["record_status"],
        "marks_obtained": form_data["marks_obtained"],
        "max_marks": form_data["max_marks"],
        "file_name": file_meta["file_name"] if file_meta else None,
        "file_path": file_meta["file_path"] if file_meta else None,
        "file_size": file_meta["file_size"] if file_meta else 0,
    }

def parse_payload(block_row):
    payload = json.loads(block_row["payload"])
    payload["submitted_by"] = block_row["owner"]
    payload["timestamp"] = block_row["timestamp"]
    payload["block_hash"] = block_row["block_hash"]
    payload["previous_hash"] = block_row["previous_hash"]
    payload["block_index"] = block_row["block_index"]
    payload["record_type"] = payload.get("record_type") or block_row["record_type"] or "Academic Record"
    payload["record_status"] = payload.get("record_status") or block_row["record_status"] or "Active"
    payload["certificate_id"] = payload.get("certificate_id", "")
    payload["marks_obtained"] = payload.get("marks_obtained", "")
    payload["max_marks"] = payload.get("max_marks", "")
    payload["file_name"] = payload.get("file_name") or block_row["file_name"]
    payload["file_path"] = payload.get("file_path") or block_row["file_path"]
    payload["file_size"] = payload.get("file_size") or block_row["file_size"] or 0
    payload["file_size_label"] = format_file_size(payload["file_size"])
    payload["updated_at"] = block_row["updated_at"]
    payload["last_modified_by"] = block_row["last_modified_by"]
    payload["signer_node"] = block_row["signer_node"]
    payload["signer_key_id"] = block_row["signer_key_id"]
    payload["block_signature"] = block_row["block_signature"]
    payload["id"] = block_row["id"]
    return payload

def current_student_campus_id():
    return (session.get("campus_id") or session.get("user") or "").strip()

def student_record_matches_user(block, campus_id):
    campus_id = normalize_campus_id(campus_id).lower()
    if not campus_id:
        return False
    return campus_id == str(block.get("student_id") or "").strip().lower()

def can_view_record_details(block):
    role = session.get("role")
    if role in {"Administrator", "Faculty", "Exam Cell"}:
        return True
    if role == "Student":
        return student_record_matches_user(block, current_student_campus_id())
    return False

def get_form_record_data(source):
    return {
        "student_id": source.get("student_id", "").strip(),
        "student_name": source.get("student_name", "").strip(),
        "course": source.get("course", "").strip(),
        "document_name": source.get("document_name", "").strip(),
        "certificate_id": source.get("certificate_id", "").strip().upper(),
        "storage_node": source.get("storage_node", "").strip(),
        "record_notes": source.get("record_notes", "").strip(),
        "record_type": source.get("record_type", "Certificate").strip() or "Certificate",
        "record_status": source.get("record_status", "Active").strip() or "Active",
        "marks_obtained": source.get("marks_obtained", "").strip(),
        "max_marks": source.get("max_marks", "").strip(),
    }

def normalize_record_data(data):
    if data.get("marks_obtained") and data.get("max_marks"):
        try:
            m = float(data["marks_obtained"])
            mx = float(data["max_marks"])
            if m < 0 or mx < 0 or m > mx:
                raise ValueError("Marks obtained must be between 0 and maximum marks.")
        except ValueError as exc:
            if "between" in str(exc):
                raise
            raise ValueError("Marks must be numeric values.")
    data["student_id"] = normalize_campus_id(data["student_id"])
    return data

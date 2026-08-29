import os
import secrets
from werkzeug.utils import secure_filename
from ..config import AppConfig

def format_file_size(size_bytes):
    if not size_bytes:
        return "No file"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in AppConfig.ALLOWED_EXTENSIONS

def allowed_profile_photo(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in AppConfig.PROFILE_PHOTO_EXTENSIONS

def save_uploaded_file(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_file(file_storage.filename):
        raise ValueError("Only PDF, PNG, JPG, and JPEG files are allowed for academic record attachments.")

    os.makedirs(AppConfig.UPLOAD_DIR, exist_ok=True)
    original_name = secure_filename(file_storage.filename)
    stored_name = f"{secrets.token_hex(8)}_{original_name}"
    stored_path = os.path.join(AppConfig.UPLOAD_DIR, stored_name)
    file_storage.save(stored_path)

    return {
        "file_name": original_name,
        "file_path": stored_name,
        "file_size": os.path.getsize(stored_path),
    }

def save_profile_photo(file_storage, existing_path=None):
    if not file_storage or not file_storage.filename:
        return existing_path

    if not allowed_profile_photo(file_storage.filename):
        raise ValueError("Only PNG, JPG, and JPEG images are allowed for profile photos.")

    profile_dir = os.path.join(AppConfig.UPLOAD_DIR, "profiles")
    os.makedirs(profile_dir, exist_ok=True)
    
    original_name = secure_filename(file_storage.filename)
    stored_name = f"{secrets.token_hex(8)}_{original_name}"
    relative_path = os.path.join("profiles", stored_name).replace("\\", "/")
    stored_path = os.path.join(AppConfig.UPLOAD_DIR, relative_path.replace("/", os.sep))
    file_storage.save(stored_path)

    if existing_path:
        old_path = os.path.join(AppConfig.UPLOAD_DIR, existing_path.replace("/", os.sep))
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError:
                pass

    return relative_path

def delete_profile_photo(stored_path):
    if not stored_path:
        return None

    full_path = os.path.join(AppConfig.UPLOAD_DIR, stored_path.replace("/", os.sep))
    if os.path.exists(full_path):
        try:
            os.remove(full_path)
        except OSError:
            pass

    return None

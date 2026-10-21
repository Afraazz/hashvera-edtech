import io
import os
import shutil
import tempfile
import unittest

import app as hashvera_app


class HashVeraAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="hashvera-tests-")
        self.instance_dir = os.path.join(self.temp_dir, "instance")
        self.upload_dir = os.path.join(self.temp_dir, "uploads")
        self.backup_dir = os.path.join(self.instance_dir, "backups")
        self.db_path = os.path.join(self.temp_dir, "hashvera-test.sqlite3")

        hashvera_app.INSTANCE_DIR = self.instance_dir
        hashvera_app.UPLOAD_DIR = self.upload_dir
        hashvera_app.BACKUP_DIR = self.backup_dir
        hashvera_app.DB_PATH = self.db_path
        hashvera_app.SECRET_KEY_PATH = os.path.join(self.instance_dir, "secret_key")
        hashvera_app.NODE_SIGNING_SECRET_PATH = os.path.join(self.instance_dir, "node_signing_secret")
        hashvera_app.app.config["TESTING"] = True
        hashvera_app.app.config["SECRET_KEY"] = "test-secret-key"
        hashvera_app.AppConfig.OPENAI_API_KEY = ""
        hashvera_app.AppConfig.GEMINI_API_KEY = ""

        hashvera_app.init_db()
        self.client = hashvera_app.app.test_client()
        self._create_user("tester", "tester@example.com", "ValidPass1!", "Administrator")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_user(self, username, email, password, role, campus_id=None):
        password_hash, salt = hashvera_app.hash_password(password)
        if campus_id is None and role == "Student":
            campus_id = username
        conn = hashvera_app.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR REPLACE INTO users(username, campus_id, email, password_hash, password_salt, force_password_change, role, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?, ?)
            """,
            (username, campus_id, email, password_hash, salt, role, hashvera_app.utc_now()),
        )
        conn.commit()
        conn.close()

    def _set_csrf(self, token="test-csrf-token"):
        with self.client.session_transaction() as sess:
            sess["_csrf_token"] = token
        return token

    def _login(self, username="tester", password="ValidPass1!"):
        token = self._set_csrf()
        conn = hashvera_app.get_connection()
        user = conn.execute("SELECT email FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()
        email = user["email"] if user else username
        return self.client.post(
            "/login",
            data={"email": email, "password": password, "csrf_token": token},
            follow_redirects=False,
        )

    def test_login_successful_redirects_to_dashboard(self):
        response = self._login()

        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_post_without_csrf_is_rejected(self):
        response = self.client.post(
            "/register",
            data={
                "username": "no-token",
                "email": "notoken@example.com",
                "password": "ValidPass1!",
                "role": "Student",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)

    def test_chain_validation_is_true_for_seeded_data(self):
        conn = hashvera_app.get_connection()
        rows = hashvera_app.fetch_chain_records(conn)
        valid, issues = hashvera_app.check_chain_validity(rows, conn)
        conn.close()

        self.assertTrue(valid)
        self.assertEqual(issues, [])

    def test_database_backup_file_is_created(self):
        backup_path = hashvera_app.backup_database_file("unit-test")

        self.assertTrue(os.path.exists(backup_path))
        self.assertTrue(backup_path.endswith(".sqlite3"))

    def test_password_strength_requires_special_character(self):
        message = hashvera_app.validate_password_strength("ValidPass1")
        self.assertEqual(message, "Password must include at least one special character.")

    def test_disabled_user_cannot_log_in(self):
        self._create_user("disabled-user", "disabled@example.com", "ValidPass1!", "Student")
        conn = hashvera_app.get_connection()
        conn.execute(
            "UPDATE users SET disabled = 1, disabled_at = ? WHERE username = ?",
            (hashvera_app.utc_now(), "disabled-user"),
        )
        conn.commit()
        conn.close()

        token = self._set_csrf()
        response = self.client.post(
            "/login",
            data={"email": "disabled@example.com", "password": "ValidPass1!", "csrf_token": token},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"This account is currently disabled", response.data)

    def test_admin_can_disable_and_enable_user(self):
        self._create_user("switch-user", "switch@example.com", "ValidPass1!", "Student")
        self._login()

        conn = hashvera_app.get_connection()
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", ("switch-user",)).fetchone()["id"]
        conn.close()

        token = self._set_csrf("disable-token")
        response = self.client.post(
            f"/admin/users/{user_id}/disable",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        conn = hashvera_app.get_connection()
        user_row = conn.execute("SELECT disabled, disabled_reason FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        self.assertEqual(user_row["disabled"], 1)
        self.assertFalse(user_row["disabled_reason"])

        token = self._set_csrf("enable-token")
        response = self.client.post(f"/admin/users/{user_id}/enable", data={"csrf_token": token}, follow_redirects=False)
        self.assertEqual(response.status_code, 302)

        conn = hashvera_app.get_connection()
        user_row = conn.execute("SELECT disabled, disabled_reason FROM users WHERE id = ?", (user_id,)).fetchone()
        conn.close()
        self.assertEqual(user_row["disabled"], 0)
        self.assertFalse(user_row["disabled_reason"])

    def test_successful_login_updates_last_login(self):
        self._login()

        conn = hashvera_app.get_connection()
        last_login_at = conn.execute("SELECT last_login_at FROM users WHERE username = ?", ("tester",)).fetchone()["last_login_at"]
        conn.close()

        self.assertTrue(last_login_at)

    def test_admin_role_assignment_updates_user(self):
        self._create_user("role-user", "role@example.com", "ValidPass1!", "Student")
        self._login()

        conn = hashvera_app.get_connection()
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", ("role-user",)).fetchone()["id"]
        conn.close()

        token = self._set_csrf("role-token")
        response = self.client.post(
            f"/admin/users/{user_id}/update-role",
            data={"csrf_token": token, "role": "Exam Cell"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)

        conn = hashvera_app.get_connection()
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()["role"]
        conn.close()
        self.assertEqual(role, "Exam Cell")


    def test_admin_cannot_assign_student_role_without_campus_id(self):
        self._create_user("faculty-no-campus", "facnocampus@example.com", "ValidPass1!", "Faculty", campus_id=None)
        self._login()

        conn = hashvera_app.get_connection()
        user_id = conn.execute("SELECT id FROM users WHERE username = ?", ("faculty-no-campus",)).fetchone()["id"]
        conn.close()

        token = self._set_csrf("role-campus-token")
        response = self.client.post(
            f"/admin/users/{user_id}/update-role",
            data={"csrf_token": token, "role": "Student"},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Set a campus ID before assigning the Student role.", response.data)

        conn = hashvera_app.get_connection()
        role = conn.execute("SELECT role FROM users WHERE id = ?", (user_id,)).fetchone()["role"]
        conn.close()
        self.assertEqual(role, "Faculty")
    def test_profile_directory_permissions_are_limited_for_faculty(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        self._create_user("faculty-one", "faculty@example.com", "ValidPass1!", "Faculty")
        self._login("faculty-one", "ValidPass1!")

        response = self.client.get("/profiles")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"23BCA101", response.data)
        self.assertIn(b"Hidden for privacy", response.data)
        self.assertNotIn(b"student@example.com", response.data)
        self.assertNotIn(b"Administrator", response.data)

    def test_faculty_cannot_open_administrator_profile(self):
        self._create_user("faculty-one", "faculty@example.com", "ValidPass1!", "Faculty")
        self._login("faculty-one", "ValidPass1!")

        conn = hashvera_app.get_connection()
        admin_id = conn.execute("SELECT id FROM users WHERE role = ?", ("Administrator",)).fetchone()["id"]
        conn.close()

        response = self.client.get(f"/profiles/{admin_id}", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Administrator profiles are hidden in this view.", response.data)

    def test_student_cannot_access_profile_directory(self):
        self._create_user("student-only", "studentonly@example.com", "ValidPass1!", "Student")
        self._login("student-only", "ValidPass1!")

        response = self.client.get("/profiles", follow_redirects=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_profile_photo_upload_and_remove(self):
        self._login()

        upload_token = self._set_csrf("photo-upload-token")
        response = self.client.post(
            "/profile/settings",
            data={
                "csrf_token": upload_token,
                "profile_action": "save",
                "username": "tester",
                "email": "tester@example.com",
                "phone": "",
                "about_info": "",
                "profile_photo": (io.BytesIO(b"\x89PNG\r\n\x1a\nfakepng"), "avatar.png"),
            },
            content_type="multipart/form-data",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)

        conn = hashvera_app.get_connection()
        photo_path = conn.execute("SELECT profile_photo FROM users WHERE username = ?", ("tester",)).fetchone()["profile_photo"]
        conn.close()
        self.assertTrue(photo_path)
        self.assertTrue(os.path.exists(os.path.join(hashvera_app.UPLOAD_DIR, photo_path.replace("/", os.sep))))

        remove_token = self._set_csrf("photo-remove-token")
        response = self.client.post(
            "/profile/settings",
            data={
                "csrf_token": remove_token,
                "profile_action": "remove_photo",
                "username": "tester",
                "email": "tester@example.com",
                "phone": "",
                "about_info": "",
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)

        conn = hashvera_app.get_connection()
        photo_path = conn.execute("SELECT profile_photo FROM users WHERE username = ?", ("tester",)).fetchone()["profile_photo"]
        conn.close()
        self.assertFalse(photo_path)

    def test_admin_delete_backup_removes_file(self):
        self._login()
        backup_path = hashvera_app.backup_database_file("delete-me")
        hashvera_app.backup_database_file("keep-me")
        backup_name = os.path.basename(backup_path)

        token = self._set_csrf("backup-delete-token")
        response = self.client.post(
            f"/admin/system/backups/{backup_name}/delete",
            data={"csrf_token": token},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(os.path.exists(backup_path))

    def test_admin_import_backup_replaces_database(self):
        self._login()
        backup_path = hashvera_app.backup_database_file("import-source")
        self._create_user("extra-user", "extra@example.com", "ValidPass1!", "Student")

        token = self._set_csrf("backup-import-token")
        with open(backup_path, "rb") as backup_file:
            response = self.client.post(
                "/admin/system/import",
                data={
                    "csrf_token": token,
                    "database_file": (io.BytesIO(backup_file.read()), os.path.basename(backup_path)),
                },
                content_type="multipart/form-data",
                follow_redirects=False,
            )

        self.assertEqual(response.status_code, 302)
        conn = hashvera_app.get_connection()
        extra_user = conn.execute("SELECT id FROM users WHERE username = ?", ("extra-user",)).fetchone()
        conn.close()
        self.assertIsNone(extra_user)

    def test_admin_test_email_route_reports_success(self):
        from hashvera.routes import admin as admin_routes

        self._login()
        original_send_email = admin_routes.send_email_message
        admin_routes.send_email_message = lambda recipient, subject, content: (True, "Email sent successfully.")
        try:
            token = self._set_csrf("test-email-token")
            response = self.client.post(
                "/admin/system/test-email",
                data={"csrf_token": token, "recipient_email": "mail@example.com"},
                follow_redirects=True,
            )
        finally:
            admin_routes.send_email_message = original_send_email

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Email sent successfully.", response.data)

    def test_dashboard_contains_search_and_filter_sections(self):
        self._login()

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'id="dashboard-quick-search"', response.data)
        self.assertIn(b"Filters and Charts", response.data)
        self.assertIn(b"Open Filters", response.data)

    def test_profile_settings_shows_account_status_and_last_login(self):
        self._login()

        response = self.client.get("/profile/settings")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Account Status", response.data)
        self.assertIn(b"Last Login", response.data)
        self.assertIn(b"Profile Completeness", response.data)

    def test_student_my_records_page_shows_matching_records_only(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        hashvera_app.add_record(
            "tester",
            {
                "student_id": "23BCA101",
                "student_name": "Student One",
                "course": "BCA",
                "document_name": "Semester Marksheet",
                "certificate_id": "STU-1001",
                "storage_node": "Node-A",
                "record_notes": "Marks verified.",
                "record_type": "Marksheet",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        hashvera_app.add_record(
            "tester",
            {
                "student_id": "other-student",
                "student_name": "Other Student",
                "course": "BCA",
                "document_name": "Other Record",
                "certificate_id": "OTH-2001",
                "storage_node": "Node-A",
                "record_notes": "Other record.",
                "record_type": "Certificate",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        hashvera_app.add_record(
            "tester",
            {
                "student_id": "different-campus-id",
                "student_name": "Student One",
                "course": "BCA",
                "document_name": "Name Match Only",
                "certificate_id": "NAME-3001",
                "storage_node": "Node-A",
                "record_notes": "Should stay hidden because campus ID does not match.",
                "record_type": "Certificate",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        self._login("student-one", "ValidPass1!")

        response = self.client.get("/my-records")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Records", response.data)
        self.assertIn(b"campus ID", response.data)
        self.assertIn(b"Semester Marksheet", response.data)
        self.assertNotIn(b"Other Record", response.data)
        self.assertNotIn(b"Name Match Only", response.data)

    def test_student_can_open_own_record_from_dashboard_link(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        hashvera_app.add_record(
            "tester",
            {
                "student_id": "23BCA101",
                "student_name": "Student One",
                "course": "BCA",
                "document_name": "Semester Marksheet",
                "certificate_id": "STU-1001",
                "storage_node": "Node-A",
                "record_notes": "Marks verified.",
                "record_type": "Marksheet",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        self._login("student-one", "ValidPass1!")

        conn = hashvera_app.get_connection()
        block_id = conn.execute("SELECT id FROM blocks WHERE payload LIKE ? ORDER BY id DESC LIMIT 1", ('%23BCA101%',)).fetchone()["id"]
        conn.close()

        response = self.client.get(f"/records/{block_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Record Preview", response.data)
        self.assertIn(b"Campus ID", response.data)
        self.assertIn(b"23BCA101", response.data)

    def test_student_cannot_open_other_campus_record(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        hashvera_app.add_record(
            "tester",
            {
                "student_id": "other-campus-id",
                "student_name": "Other Student",
                "course": "BCA",
                "document_name": "Locked Record",
                "certificate_id": "OTH-1001",
                "storage_node": "Node-A",
                "record_notes": "Should stay blocked.",
                "record_type": "Certificate",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        self._login("student-one", "ValidPass1!")

        conn = hashvera_app.get_connection()
        block_id = conn.execute("SELECT id FROM blocks WHERE payload LIKE ? ORDER BY id DESC LIMIT 1", ('%other-campus-id%',)).fetchone()["id"]
        conn.close()

        response = self.client.get(f"/records/{block_id}", follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"You do not have permission to view this record.", response.data)
        self.assertNotIn(b"Record Details", response.data)

    def test_student_can_request_record_correction(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        hashvera_app.add_record(
            "tester",
            {
                "student_id": "23BCA101",
                "student_name": "Student One",
                "course": "BCA",
                "document_name": "Semester Marksheet",
                "certificate_id": "STU-1001",
                "storage_node": "Node-A",
                "record_notes": "Marks verified.",
                "record_type": "Marksheet",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        self._login("student-one", "ValidPass1!")

        conn = hashvera_app.get_connection()
        block_id = conn.execute("SELECT id FROM blocks WHERE payload LIKE ? ORDER BY id DESC LIMIT 1", ('%23BCA101%',)).fetchone()["id"]
        conn.close()

        token = self._set_csrf("correction-token")
        response = self.client.post(
            f"/records/{block_id}/correction",
            data={"csrf_token": token, "correction_note": "The certificate ID should be updated."},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Correction request sent to academic team.", response.data)
        conn = hashvera_app.get_connection()
        audit_entry = conn.execute(
            "SELECT details FROM audit_logs WHERE action = 'REQUEST_RECORD_CORRECTION' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn.close()
        self.assertIsNotNone(audit_entry)
        self.assertIn("certificate ID should be updated", audit_entry["details"])

    def test_admin_system_history_lists_recent_actions(self):
        self._login()
        conn = hashvera_app.get_connection()
        hashvera_app.log_audit_action(conn, "tester", "EXPORT_CSV", "ledger", "demo", "Exported blockchain CSV.")
        conn.commit()
        conn.close()

        response = self.client.get("/admin/system")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Export and Backup History", response.data)
        self.assertIn(b"Exported blockchain CSV.", response.data)



    def test_student_can_submit_new_record_request(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        self._login("student-one", "ValidPass1!")

        token = self._set_csrf("new-record-request-token")
        response = self.client.post(
            "/submit-request",
            data={
                "csrf_token": token,
                "course": "BCA",
                "document_name": "Internship Letter",
                "record_type": "Certificate",
                "certificate_id": "REQ-9001",
                "request_note": "Please add my internship completion letter.",
            },
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Record request submitted", response.data)
        conn = hashvera_app.get_connection()
        request_row = conn.execute(
            "SELECT request_type, campus_id, status FROM record_requests WHERE requester_username = ? ORDER BY id DESC LIMIT 1",
            ("student-one",),
        ).fetchone()
        conn.close()
        self.assertIsNotNone(request_row)
        self.assertEqual(request_row["request_type"], "NEW_RECORD")
        self.assertEqual(request_row["campus_id"], "23BCA101")
        self.assertEqual(request_row["status"], "Pending")

    def test_exam_cell_can_review_and_approve_new_record_request(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        self._create_user("examcell", "examcell@example.com", "ValidPass1!", "Exam Cell")

        conn = hashvera_app.get_connection()
        conn.execute(
            """
            INSERT INTO record_requests(
                request_type, requester_username, requester_role, campus_id, related_block_id,
                requested_payload, request_note, status, reviewer_username, reviewer_note,
                linked_block_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "NEW_RECORD",
                "student-one",
                "Student",
                "23BCA101",
                None,
                '{"student_id":"23BCA101","student_name":"Student One","course":"BCA","document_name":"Internship Letter","certificate_id":"REQ-9001","storage_node":"Node-A","record_notes":"Requested by student.","record_type":"Certificate","record_status":"Active","marks_obtained":"","max_marks":""}',
                "Please add my internship completion letter.",
                "Pending",
                None,
                None,
                None,
                hashvera_app.utc_now(),
                hashvera_app.utc_now(),
            ),
        )
        request_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
        conn.commit()
        conn.close()

        self._login("examcell", "ValidPass1!")
        token = self._set_csrf("review-approve-token")
        response = self.client.post(
            f"/review-queue/{request_id}/action",
            data={"csrf_token": token, "decision": "approve", "reviewer_note": "Approved and created."},
            follow_redirects=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Request action processed.", response.data)
        conn = hashvera_app.get_connection()
        reviewed_request = conn.execute(
            "SELECT status, linked_block_id FROM record_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
        linked_block = conn.execute(
            "SELECT id FROM blocks WHERE payload LIKE ? ORDER BY id DESC LIMIT 1",
            ('%REQ-9001%',),
        ).fetchone()
        conn.close()
        self.assertEqual(reviewed_request["status"], "Approved")
        self.assertIsNotNone(reviewed_request["linked_block_id"])
        self.assertIsNotNone(linked_block)

    def test_notifications_page_shows_record_update_notification(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        conn = hashvera_app.get_connection()
        hashvera_app.create_notification(
            conn,
            "student-one",
            "record",
            "Record updated",
            "Your semester record was updated.",
            "/records/1",
        )
        conn.commit()
        conn.close()
        self._login("student-one", "ValidPass1!")

        response = self.client.get("/notifications")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Record updated", response.data)
        self.assertIn(b"Your semester record was updated.", response.data)

    def test_certificate_preview_is_available_for_authorized_student(self):
        self._create_user("student-one", "student@example.com", "ValidPass1!", "Student", campus_id="23BCA101")
        block_id = hashvera_app.add_record(
            "tester",
            {
                "student_id": "23BCA101",
                "student_name": "Student One",
                "course": "BCA",
                "document_name": "Certificate Preview Record",
                "certificate_id": "CP-1001",
                "storage_node": "Node-A",
                "record_notes": "Preview ready.",
                "record_type": "Certificate",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        self._login("student-one", "ValidPass1!")

        response = self.client.get(f"/certificate/preview/{block_id}")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Certificate Preview", response.data)
        self.assertIn(b"CP-1001", response.data)

    def test_dashboard_contains_extended_analytics_cards(self):
        self._login()

        response = self.client.get("/dashboard")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Records by Course", response.data)
        self.assertIn(b"Active vs Archived Trends", response.data)
        self.assertIn(b"User Activity Trends", response.data)

    def test_ai_assistant_endpoint_answers_hashvera_questions(self):
        self._login()

        response = self.client.post(
            "/api/assistant",
            json={"message": "How do I verify a certificate?"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("verification", payload["answer"].lower())
        self.assertTrue(payload["actions"])

    def test_ai_assistant_rejects_empty_message(self):
        response = self.client.post("/api/assistant", json={"message": "   "})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "error")

    def test_ai_assistant_local_verification(self):
        # Create a sample block record so verify_certificate finds it
        from hashvera.utils.blockchain import add_record
        add_record(
            "tester",
            {
                "student_id": "23BCA101",
                "student_name": "Student One",
                "course": "BCA",
                "document_name": "Semester Marksheet",
                "certificate_id": "STU-1001",
                "storage_node": "Node-A",
                "record_notes": "Marks verified.",
                "record_type": "Marksheet",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            },
            None,
        )
        
        self._login()
        response = self.client.post(
            "/api/assistant",
            json={"message": "verify certificate STU-1001"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("verified successfully", payload["answer"].lower())
        self.assertIn("stu-1001", payload["answer"].lower())
        self.assertIn("student one", payload["answer"].lower())

    def test_ai_assistant_local_integrity_check(self):
        self._login()
        response = self.client.post(
            "/api/assistant",
            json={"message": "scan blockchain integrity"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("integrity report", payload["answer"].lower())
        self.assertIn("validation status", payload["answer"].lower())

    def test_ai_assistant_local_support_tickets_visitor(self):
        # Not logged in
        response = self.client.post(
            "/api/assistant",
            json={"message": "check my tickets"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("log in to check", payload["answer"].lower())

    def test_ai_assistant_local_support_tickets_user(self):
        self._login()
        # Create a support ticket in db
        conn = hashvera_app.get_connection()
        conn.execute(
            "INSERT INTO support_tickets (name, email, category, message, status, username, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Tester", "tester@example.com", "System", "Need assistance with verification portal", "Open", "tester", hashvera_app.utc_now(), hashvera_app.utc_now())
        )
        conn.commit()
        conn.close()

        response = self.client.post(
            "/api/assistant",
            json={"message": "show my support tickets"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["status"], "ok")
        self.assertIn("your support tickets", payload["answer"].lower())
        self.assertIn("need assistance", payload["answer"].lower())

if __name__ == "__main__":
    unittest.main()

















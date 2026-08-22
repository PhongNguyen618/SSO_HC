import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = (ROOT / "backend" / "main.py").read_text(encoding="utf-8")
SYNC = (ROOT / "backend" / "sync_engine.py").read_text(encoding="utf-8")
AUTH = (ROOT / "backend" / "auth.py").read_text(encoding="utf-8")
DB = (ROOT / "backend" / "database.py").read_text(encoding="utf-8")
ENV_EXAMPLE = (ROOT / ".env.example").read_text(encoding="utf-8")
TEMPLATE_ADMIN = (ROOT / "templates" / "admin.html").read_text(encoding="utf-8")


class SecurityRegressionTests(unittest.TestCase):
    def test_no_raw_athlete_id_oauth_state(self):
        self.assertNotIn("&state={athlete_id}", MAIN)
        self.assertNotIn("&state={new_athlete.id}", MAIN)
        self.assertIn("verify_oauth_state(request, db, state, \"athlete_strava\")", MAIN)

    def test_unlink_uses_real_model_fields(self):
        self.assertNotIn("athlete.strava_id = None", MAIN)
        self.assertNotIn("athlete.strava_token_expires_at = None", MAIN)
        self.assertIn("athlete.strava_athlete_id = None", MAIN)
        self.assertIn("athlete.strava_expires_at = None", MAIN)

    def test_passwords_are_salted_and_legacy_is_only_for_verify(self):
        self.assertIn("pbkdf2_sha256", AUTH)
        self.assertIn("pbkdf2_sha256", DB)
        self.assertNotIn('os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")', DB)

    def test_backup_uses_sqlite_backup_api(self):
        self.assertIn("src.backup(dst)", DB)
        self.assertNotIn("shutil.copyfile(db_path, backup_path)", SYNC)

    def test_no_project_specific_sync_cutoff(self):
        self.assertNotIn("2026-06-16", SYNC)
        self.assertNotIn("2026-06-16", MAIN)

    def test_suspicious_activity_excluded_from_scoring(self):
        self.assertIn("_valid_activity_clause()", MAIN)
        self.assertIn("valid_activities = [a for a in all_activities if not bool(a.is_suspicious)]", MAIN)

    def test_sync_serialized(self):
        self.assertIn("_sync_lock.acquire(blocking=False)", SYNC)

    def test_private_backups_are_not_under_static(self):
        self.assertIn('get_private_backup_dir()', MAIN)
        self.assertIn('get_private_audit_log_path()', MAIN)
        self.assertNotIn('"static", "uploads", "backups"', SYNC)
        self.assertNotIn('backup_file = "static/uploads/deleted_activities_backup.jsonl"', MAIN)
        self.assertNotIn('temp_dir = "static/uploads/temp"', MAIN)
        self.assertIn('get_private_storage_dir("restore_temp")', MAIN)
        self.assertIn('SQLite format 3', MAIN)

    def test_new_profile_does_not_claim_activity_before_oauth(self):
        self.assertNotIn('link_unlinked_activities(db, new_athlete)', MAIN)
        self.assertIn('link_unlinked_activities(db, athlete)', MAIN)
        self.assertNotIn('return _set_athlete_session_cookie(response, request, db, new_athlete.id)', MAIN)


    def test_admin_logout_cannot_be_revoked_anonymously(self):
        self.assertIn('def admin_logout(request: Request', MAIN)
        logout = MAIN.split('@app.post("/admin/logout")', 1)[1].split('@app.post("/admin/config")', 1)[0]
        self.assertIn('get_admin_session(request, db)', logout)

    def test_admin_login_and_webhook_are_throttled(self):
        self.assertIn('_rate_limit(request, "admin_login", limit=10, window_seconds=600)', MAIN)
        self.assertIn('_rate_limit(request, "strava_webhook", limit=60, window_seconds=60)', MAIN)
        self.assertNotIn('STRAVA_WEBHOOK_VERIFY_TOKEN", "SSO_HC_VERIFY_TOKEN"', MAIN)

    def test_suspicious_activity_can_be_admin_approved(self):
        self.assertIn('/admin/activity/approve/{activity_id}', MAIN)
        self.assertIn('activity.is_suspicious = False', MAIN)
        self.assertIn('function approveActivity(', TEMPLATE_ADMIN)

    def test_no_insecure_defaults_or_hardcoded_restore_cutoff_in_ui(self):
        self.assertNotIn('DEFAULT_ADMIN_PASSWORD=admin', ENV_EXAMPLE)
        self.assertNotIn('16/06/2026', TEMPLATE_ADMIN)

    def test_sync_postprocessing_uses_same_serialization_guard(self):
        self.assertIn('def run_serialized_maintenance', SYNC)
        self.assertIn('_deduplicate_if_sync_idle()', MAIN)


if __name__ == "__main__":
    unittest.main()

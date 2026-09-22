import unittest
from unittest.mock import MagicMock
import sqlite3
from fastapi import Request

from backend.database import SessionLocal, Athlete, Activity, init_db
from backend.main import get_effective_strava_config, _strava_identity_matches

class TestStravaLinkingFixes(unittest.TestCase):
    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_effective_strava_config_local(self):
        request = MagicMock(spec=Request)
        request.headers = {"host": "localhost:8008"}
        request.url = MagicMock(scheme="http")

        client_id, client_secret, app_url = get_effective_strava_config(request, self.db)
        self.assertEqual(client_id, "164041")
        self.assertIn("localhost:8008", app_url)

    def test_effective_strava_config_prod(self):
        request = MagicMock(spec=Request)
        request.headers = {"host": "ssohc.ppt-sso.com"}
        request.url = MagicMock(scheme="https")

        client_id, client_secret, app_url = get_effective_strava_config(request, self.db)
        self.assertEqual(client_id, "162169")
        self.assertEqual(app_url, "https://ssohc.ppt-sso.com")

    def test_strava_identity_matches_verified_vs_unverified(self):
        # 1. VĐV đã xác minh OAuth thật: không cho phép đổi sang Strava ID khác
        verified_ath = Athlete(
            id=9991,
            full_name="Nguyễn Văn A",
            strava_name="Van A",
            strava_athlete_id="111111",
            strava_refresh_token="valid_token_xyz"
        )
        self.assertTrue(_strava_identity_matches(verified_ath, {"id": 111111}))
        self.assertFalse(_strava_identity_matches(verified_ath, {"id": 222222, "firstname": "Van", "lastname": "A"}))

        # 2. VĐV chưa từng có refresh_token (ID chỉ do Scraper gán đoán trước đó):
        # Nếu ID khác nhưng tên khớp hợp lý -> CHO PHÉP xác minh
        unverified_ath = Athlete(
            id=9992,
            full_name="Trần Minh Mẩn",
            strava_name="Man T.",
            strava_athlete_id="999999", # ID gán nhầm
            strava_refresh_token=None
        )
        strava_data_real = {"id": 333333, "firstname": "Minh Man", "lastname": "Tran"}
        self.assertTrue(_strava_identity_matches(unverified_ath, strava_data_real))

    def test_strava_name_non_unique_index(self):
        conn = sqlite3.connect("SSO_HC.db")
        cur = conn.cursor()
        cur.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name='ix_athletes_strava_name'")
        row = cur.fetchone()
        conn.close()
        self.assertIsNotNone(row)
        self.assertNotIn("UNIQUE", row[0].upper())

    def test_zero_orphan_activities(self):
        orphan_count = self.db.query(Activity).filter(Activity.athlete_id == None).count()
        self.assertEqual(orphan_count, 0)

if __name__ == "__main__":
    unittest.main()

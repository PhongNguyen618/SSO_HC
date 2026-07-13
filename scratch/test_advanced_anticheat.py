import sys
import os
import unittest
from datetime import datetime

# Import thư viện cần thiết
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database import engine, SessionLocal, init_db, CompetitionEvent, Activity, Athlete
from backend.calculations import check_suspicious_activity

class TestAdvancedAntiCheat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Chạy khởi tạo database để tự động di trú/ALTER TABLE
        print("\n=== SETUP TEST DATA FOR ADVANCED ANTI-CHEAT ===")
        init_db()
        cls.db = SessionLocal()
        
        # Tạo một giải đấu test
        cls.event = CompetitionEvent(
            title="Giải Chống Gian Lận Thử Nghiệm",
            strava_club_id="test_club_anticheat",
            start_date="2026-01-01",
            end_date="2026-12-31",
            is_active=True,
            flag_manual_activities=True,  # Bật kiểm tra manual
            heartrate_check=True,         # Bật kiểm tra nhịp tim
            max_rest_ratio=0.5            # Giới hạn nghỉ tối đa 50%
        )
        cls.db.add(cls.event)
        cls.db.commit()
        cls.db.refresh(cls.event)

    @classmethod
    def tearDownClass(cls):
        # Dọn dẹp dữ liệu test
        cls.db.query(Activity).filter(Activity.event_id == cls.event.id).delete()
        cls.db.query(CompetitionEvent).filter(CompetitionEvent.id == cls.event.id).delete()
        cls.db.commit()
        cls.db.close()

    def test_database_columns_exist(self):
        """Verify that the database columns exist after migration"""
        from sqlalchemy import inspect
        inspector = inspect(engine)
        
        comp_cols = [c['name'] for c in inspector.get_columns('competition_events')]
        self.assertIn('flag_manual_activities', comp_cols)
        self.assertIn('heartrate_check', comp_cols)
        self.assertIn('max_rest_ratio', comp_cols)
        
        act_cols = [c['name'] for c in inspector.get_columns('activities')]
        self.assertIn('is_manual', act_cols)
        self.assertIn('has_heartrate', act_cols)
        self.assertIn('average_heartrate', act_cols)
        self.assertIn('max_heartrate', act_cols)
        print("=> Database columns verified!")

    def test_manual_activity_flagging(self):
        """Verify that manual activities are correctly flagged when enabled"""
        # Case 1: Manual activity, check enabled
        is_suspicious, reason = check_suspicious_activity(
            sport_type="Run",
            distance_km=5.0,
            pace_min_km=6.0,
            elevation_gain_m=10.0,
            configs={},
            is_manual=True,
            event_obj=self.event
        )
        self.assertTrue(is_suspicious)
        self.assertIn("nhập tay thủ công", reason)
        
        # Case 2: Manual activity, check disabled
        disabled_event = CompetitionEvent(flag_manual_activities=False)
        is_suspicious, reason = check_suspicious_activity(
            sport_type="Run",
            distance_km=5.0,
            pace_min_km=6.0,
            elevation_gain_m=10.0,
            configs={},
            is_manual=True,
            event_obj=disabled_event
        )
        self.assertFalse(is_suspicious)
        print("=> Manual activities verification OK!")

    def test_rest_ratio_flagging(self):
        """Verify that activities with high rest ratio are flagged"""
        # Case 1: Rest ratio is 1.0 (moving=10, elapsed=20) which is > max_rest_ratio (0.5)
        is_suspicious, reason = check_suspicious_activity(
            sport_type="Run",
            distance_km=5.0,
            pace_min_km=6.0,
            elevation_gain_m=10.0,
            configs={},
            moving_time_min=10.0,
            elapsed_time_min=20.0,
            event_obj=self.event
        )
        self.assertTrue(is_suspicious)
        self.assertIn("ngắt quãng nghỉ quá lâu", reason)
        
        # Case 2: Rest ratio is 0.2 (moving=10, elapsed=12) which is <= max_rest_ratio (0.5)
        is_suspicious, reason = check_suspicious_activity(
            sport_type="Run",
            distance_km=5.0,
            pace_min_km=6.0,
            elevation_gain_m=10.0,
            configs={},
            moving_time_min=10.0,
            elapsed_time_min=12.0,
            event_obj=self.event
        )
        self.assertFalse(is_suspicious)
        print("=> Rest ratio verification OK!")

    def test_heartrate_flagging(self):
        """Verify that fast running with low heart rate is flagged"""
        # Case 1: Fast pace (3.5 min/km), has heartrate, average heartrate is 80 (low)
        is_suspicious, reason = check_suspicious_activity(
            sport_type="Run",
            distance_km=5.0,
            pace_min_km=3.5,
            elevation_gain_m=10.0,
            configs={},
            has_heartrate=True,
            average_heartrate=80.0,
            event_obj=self.event
        )
        self.assertTrue(is_suspicious)
        self.assertIn("Nhịp tim quá thấp", reason)
        
        # Case 2: Fast pace (3.5 min/km), normal heartrate (145)
        is_suspicious, reason = check_suspicious_activity(
            sport_type="Run",
            distance_km=5.0,
            pace_min_km=3.5,
            elevation_gain_m=10.0,
            configs={},
            has_heartrate=True,
            average_heartrate=145.0,
            event_obj=self.event
        )
        self.assertFalse(is_suspicious)
        print("=> Heartrate check verification OK!")

if __name__ == '__main__':
    unittest.main()

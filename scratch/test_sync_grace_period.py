import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime

# Đảm bảo import được các module trong thư mục backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Thiết lập utf-8 cho stdout trên Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database import Base, Athlete, CompetitionEvent, Activity, EventMultiplier, Config
from backend.sync_engine import _sync_single_event

class TestSyncGracePeriod(unittest.TestCase):
    def setUp(self):
        # Sử dụng database SQLite in-memory để tránh lỗi khóa file trên Windows
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=self.engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionLocal()
        
        # Thiết lập cấu hình mặc định
        self.configs = {
            "sync_grace_period_hours": "12",
            "rule_run_pace_min": "3.0",
            "rule_run_pace_max": "10.0",
            "rule_run_elev_ratio": "5.0",
        }
        for k, v in self.configs.items():
            self.db.add(Config(key=k, value=v))
            
        # Thêm vận động viên test
        self.athlete = Athlete(
            id=1,
            full_name="Nguyen Van A",
            department="PHONG KY THUAT",
            gender="Nam",
            weight=70.0,
            strava_name="Nguyen Van A"
        )
        self.db.add(self.athlete)
        
        # Thêm giải đấu test (Chủ nhật 2026-06-21 đến Thứ hai 2026-06-22)
        self.event = CompetitionEvent(
            id=1,
            title="Giai Chay Test",
            strava_club_id="12345",
            start_date="2026-06-15",
            end_date="2026-06-30",
            is_active=True
        )
        self.db.add(self.event)
        
        # Thêm quy tắc multiplier x2 cho Chủ Nhật (weekday = 6)
        self.db.add(EventMultiplier(
            event_id=1,
            day_of_week=6,  # 6 = Sunday
            multiplier=2.0,
            description="Chủ Nhật x2"
        ))
        
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    @patch('backend.sync_engine.requests.get')
    def test_sync_monday_morning_with_afternoon_run_lùi_về_chủ_nhật(self, mock_get):
        # 1. Giả lập API Strava trả về hoạt động "Afternoon Run" (chạy chiều Chủ Nhật nhưng sync sáng Thứ Hai)
        mock_get.return_value.json.return_value = [
            {
                "athlete": {"firstname": "Nguyen Van", "lastname": "A"},
                "name": "Afternoon Run",
                "type": "Run",
                "sport_type": "Run",
                "distance": 10000.0,  # 10 km
                "moving_time": 3000,   # 50 phut
                "elapsed_time": 3000,
                "total_elevation_gain": 10.0
            }
        ]
        
        # Giả lập thời gian hiện tại là Thứ Hai lúc 08:00 sáng GMT+7 (01:00 UTC)
        simulated_utcnow = datetime(2026, 6, 22, 1, 0, 0)
        
        class MockDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return simulated_utcnow

        with patch('backend.sync_engine.datetime', MockDatetime):
            result = _sync_single_event(self.db, self.configs, "mock_token", self.event)
            self.assertEqual(result["status"], "success")
            
            act = self.db.query(Activity).first()
            self.assertIsNotNone(act)
            
            # Kiểm tra xem hoạt động "Afternoon Run" có bị lùi về ngày Chủ Nhật 2026-06-21 hay không
            print(f"Test 1 (Afternoon Run, 08:00): Ngay = {act.activity_date}, Gio = {act.activity_time}, Multiplier = {act.multiplier}")
            self.assertEqual(act.activity_date, "2026-06-21")
            self.assertEqual(act.activity_time, "23:59")
            self.assertEqual(act.multiplier, 2.0)
            self.assertEqual(act.distance_km, 20.0)  # 10km * 2 = 20km

    @patch('backend.sync_engine.requests.get')
    def test_sync_monday_morning_with_morning_run_giữ_nguyên_thứ_hai(self, mock_get):
        # 2. Giả lập API Strava trả về hoạt động "Morning Run" (người chạy sáng sớm Thứ Hai thật và sync ngay)
        mock_get.return_value.json.return_value = [
            {
                "athlete": {"firstname": "Nguyen Van", "lastname": "A"},
                "name": "Morning Run",
                "type": "Run",
                "sport_type": "Run",
                "distance": 10000.0,  # 10 km
                "moving_time": 3000,
                "elapsed_time": 3000,
                "total_elevation_gain": 10.0
            }
        ]
        
        # Giả lập thời gian hiện tại là Thứ Hai lúc 08:00 sáng GMT+7 (01:00 UTC)
        simulated_utcnow = datetime(2026, 6, 22, 1, 0, 0)
        
        class MockDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return simulated_utcnow

        with patch('backend.sync_engine.datetime', MockDatetime):
            result = _sync_single_event(self.db, self.configs, "mock_token", self.event)
            self.assertEqual(result["status"], "success")
            
            act = self.db.query(Activity).first()
            self.assertIsNotNone(act)
            
            # Kiểm tra xem hoạt động "Morning Run" có được giữ ở ngày Thứ Hai 2026-06-22 hay không
            print(f"Test 2 (Morning Run, 08:00): Ngay = {act.activity_date}, Gio = {act.activity_time}, Multiplier = {act.multiplier}")
            self.assertEqual(act.activity_date, "2026-06-22")
            self.assertEqual(act.multiplier, 1.0)
            self.assertEqual(act.distance_km, 10.0)

    @patch('backend.sync_engine.requests.get')
    def test_sync_monday_morning_with_custom_name_giữ_nguyên_thứ_hai(self, mock_get):
        # 3. Giả lập API Strava trả về hoạt động có tên tự đặt "Chạy nhẹ nhàng" (không chứa từ khóa chiều/tối/trưa)
        mock_get.return_value.json.return_value = [
            {
                "athlete": {"firstname": "Nguyen Van", "lastname": "A"},
                "name": "Chạy nhẹ nhàng",
                "type": "Run",
                "sport_type": "Run",
                "distance": 5000.0,  # 5 km
                "moving_time": 1500,
                "elapsed_time": 1500,
                "total_elevation_gain": 5.0
            }
        ]
        
        # Giả lập thời gian hiện tại là Thứ Hai lúc 08:00 sáng GMT+7 (01:00 UTC)
        simulated_utcnow = datetime(2026, 6, 22, 1, 0, 0)
        
        class MockDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return simulated_utcnow

        with patch('backend.sync_engine.datetime', MockDatetime):
            result = _sync_single_event(self.db, self.configs, "mock_token", self.event)
            self.assertEqual(result["status"], "success")
            
            act = self.db.query(Activity).first()
            self.assertIsNotNone(act)
            
            # Kiểm tra xem tên tự đặt không chứa từ khóa buổi chiều/tối có giữ nguyên ngày Thứ Hai không
            print(f"Test 3 (Chạy nhẹ nhàng, 08:00): Ngay = {act.activity_date}, Gio = {act.activity_time}, Multiplier = {act.multiplier}")
            self.assertEqual(act.activity_date, "2026-06-22")
            self.assertEqual(act.multiplier, 1.0)

    @patch('backend.sync_engine.requests.get')
    def test_sync_monday_morning_with_vietnamese_keyword_lùi_về_chủ_nhật(self, mock_get):
        # 4. Giả lập API Strava trả về hoạt động có tên tiếng Việt "Chạy buổi chiều" (chạy chiều Chủ Nhật nhưng sync sáng Thứ Hai)
        mock_get.return_value.json.return_value = [
            {
                "athlete": {"firstname": "Nguyen Van", "lastname": "A"},
                "name": "Chạy buổi chiều cùng team",
                "type": "Run",
                "sport_type": "Run",
                "distance": 10000.0,  # 10 km
                "moving_time": 3000,
                "elapsed_time": 3000,
                "total_elevation_gain": 10.0
            }
        ]
        
        # Giả lập thời gian hiện tại là Thứ Hai lúc 08:00 sáng GMT+7 (01:00 UTC)
        simulated_utcnow = datetime(2026, 6, 22, 1, 0, 0)
        
        class MockDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return simulated_utcnow

        with patch('backend.sync_engine.datetime', MockDatetime):
            result = _sync_single_event(self.db, self.configs, "mock_token", self.event)
            self.assertEqual(result["status"], "success")
            
            act = self.db.query(Activity).first()
            self.assertIsNotNone(act)
            
            # Kiểm tra xem hoạt động chứa từ khóa tiếng Việt "chiều" có bị lùi về ngày Chủ Nhật hay không
            print(f"Test 4 (Chạy buổi chiều, 08:00): Ngay = {act.activity_date}, Gio = {act.activity_time}, Multiplier = {act.multiplier}")
            self.assertEqual(act.activity_date, "2026-06-21")
            self.assertEqual(act.multiplier, 2.0)

    @patch('backend.sync_engine.requests.get')
    def test_sync_monday_afternoon_with_afternoon_run_giữ_nguyên_thứ_hai(self, mock_get):
        # 5. Giả lập API Strava trả về hoạt động "Afternoon Run" nhưng đồng bộ muộn lúc 14:00 chiều Thứ Hai
        mock_get.return_value.json.return_value = [
            {
                "athlete": {"firstname": "Nguyen Van", "lastname": "A"},
                "name": "Afternoon Run",
                "type": "Run",
                "sport_type": "Run",
                "distance": 10000.0,  # 10 km
                "moving_time": 3000,
                "elapsed_time": 3000,
                "total_elevation_gain": 10.0
            }
        ]
        
        # Giả lập thời gian hiện tại là Thứ Hai lúc 14:00 chiều GMT+7 (07:00 UTC) - Sau 12:00 trưa
        simulated_utcnow = datetime(2026, 6, 22, 7, 0, 0)
        
        class MockDatetime(datetime):
            @classmethod
            def utcnow(cls):
                return simulated_utcnow

        with patch('backend.sync_engine.datetime', MockDatetime):
            result = _sync_single_event(self.db, self.configs, "mock_token", self.event)
            self.assertEqual(result["status"], "success")
            
            act = self.db.query(Activity).first()
            self.assertIsNotNone(act)
            
            # Sau 12h trưa, hoạt động phải giữ nguyên ngày Thứ Hai 2026-06-22
            print(f"Test 5 (Afternoon Run, 14:00): Ngay = {act.activity_date}, Gio = {act.activity_time}, Multiplier = {act.multiplier}")
            self.assertEqual(act.activity_date, "2026-06-22")
            self.assertEqual(act.multiplier, 1.0)

if __name__ == "__main__":
    unittest.main()

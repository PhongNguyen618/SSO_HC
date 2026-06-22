import os
import sys
import unittest
from datetime import datetime
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

# Đảm bảo import được các module từ thư mục backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Thiết lập utf-8 cho stdout trên Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

from backend.database import Base, Athlete, CompetitionEvent, Activity, CompetitionRegistration, Config

class TestRunWalkRanking(unittest.TestCase):
    def setUp(self):
        # Tạo engine SQLite in-memory test
        self.engine = create_engine("sqlite://")
        Base.metadata.create_all(bind=self.engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = SessionLocal()
        
        # Thêm giải đấu test (id=2)
        self.event = CompetitionEvent(
            id=2,
            title="Giai Chay Run Walk",
            strava_club_id="12345",
            start_date="2026-06-01",
            end_date="2026-06-30",
            is_active=True,
            ranking_metric="distance"
        )
        self.db.add(self.event)
        
        # Thêm VĐV
        self.athletes = [
            Athlete(id=1, full_name="VĐV A (Run 10km, Walk 5km)", gender="Nam", weight=60.0, is_active=True),
            Athlete(id=2, full_name="VĐV B (Run 12km)", gender="Nam", weight=60.0, is_active=True),
            Athlete(id=3, full_name="VĐV C (Walk 8km)", gender="Nam", weight=60.0, is_active=True),
            Athlete(id=4, full_name="VĐV D (Ride 30km)", gender="Nam", weight=60.0, is_active=True)
        ]
        for ath in self.athletes:
            self.db.add(ath)
            self.db.add(CompetitionRegistration(athlete_id=ath.id, event_id=2))
            
        # Thêm các hoạt động
        self.activities = [
            # VĐV A: Run 10km, Walk 5km. Tổng Run + Walk = 15km
            Activity(id="act1", athlete_id=1, event_id=2, name="Chay 10k", sport_type="Run", distance_km=10.0, moving_time_min=60.0, kcal_burned=600.0, activity_date="2026-06-10", is_suspicious=False),
            Activity(id="act2", athlete_id=1, event_id=2, name="Di bo 5k", sport_type="Walk", distance_km=5.0, moving_time_min=45.0, kcal_burned=200.0, activity_date="2026-06-11", is_suspicious=False),
            
            # VĐV B: Run 12km. Tổng Run + Walk = 12km
            Activity(id="act3", athlete_id=2, event_id=2, name="Chay 12k", sport_type="Run", distance_km=12.0, moving_time_min=70.0, kcal_burned=720.0, activity_date="2026-06-12", is_suspicious=False),
            
            # VĐV C: Walk 8km. Tổng Run + Walk = 8km
            Activity(id="act4", athlete_id=3, event_id=2, name="Di bo 8k", sport_type="Walk", distance_km=8.0, moving_time_min=80.0, kcal_burned=320.0, activity_date="2026-06-13", is_suspicious=False),
            
            # VĐV D: Ride 30km. (Không thuộc Run/Walk)
            Activity(id="act5", athlete_id=4, event_id=2, name="Dap xe 30k", sport_type="Ride", distance_km=30.0, moving_time_min=60.0, kcal_burned=450.0, activity_date="2026-06-14", is_suspicious=False),
        ]
        for act in self.activities:
            self.db.add(act)
            
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_run_walk_ranking_calculation(self):
        # Giả lập các biến môi trường của hàm index trong main.py
        event_id = 2
        is_distance = True
        gender = "Nam"
        base_filters = []
        db = self.db
        
        # Bắt chước hàm get_sport_ranking(gender) trong backend/main.py
        stats_query = db.query(
            Athlete.id,
            Athlete.full_name,
            Activity.sport_type,
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.distance_km).label("total_dist"),
            func.sum(Activity.moving_time_min).label("total_time")
        ).join(Activity, Athlete.id == Activity.athlete_id)
        
        if event_id:
            stats_query = stats_query.join(
                CompetitionRegistration,
                (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
            )
            
        if is_distance:
            stats = stats_query.filter(Athlete.is_active == True, Athlete.gender == gender, *base_filters)\
             .group_by(Athlete.id, Activity.sport_type)\
             .order_by(Activity.sport_type, func.sum(Activity.distance_km).desc()).all()
        else:
            stats = stats_query.filter(Athlete.is_active == True, Athlete.gender == gender, *base_filters)\
             .group_by(Athlete.id, Activity.sport_type)\
             .order_by(func.sum(Activity.kcal_burned).desc()).all()
         
        grouped = {}
        for item in stats:
            sport = item.sport_type
            if sport not in grouped:
                grouped[sport] = []
            grouped[sport].append({
                "id": item.id,
                "full_name": item.full_name,
                "total_kcal": int(item.total_kcal or 0),
                "total_dist": round(item.total_dist or 0, 1),
                "total_time": round((item.total_time or 0) / 60.0, 1)
            })
            
        # Thêm thứ hạng vào danh sách
        for sport in grouped:
            for rank, ath in enumerate(grouped[sport], 1):
                ath["rank"] = rank

        # --- ĐOẠN CODE BỔ SUNG CẦN KIỂM TRA ---
        run_walk_query = db.query(
            Athlete.id,
            Athlete.full_name,
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.distance_km).label("total_dist"),
            func.sum(Activity.moving_time_min).label("total_time")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .filter(Activity.sport_type.in_(["Run", "Walk"]))

        if event_id:
            run_walk_query = run_walk_query.join(
                CompetitionRegistration,
                (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
            )

        if is_distance:
            run_walk_stats = run_walk_query.filter(Athlete.is_active == True, Athlete.gender == gender, *base_filters)\
             .group_by(Athlete.id)\
             .order_by(func.sum(Activity.distance_km).desc()).all()
        else:
            run_walk_stats = run_walk_query.filter(Athlete.is_active == True, Athlete.gender == gender, *base_filters)\
             .group_by(Athlete.id)\
             .order_by(func.sum(Activity.kcal_burned).desc()).all()

        run_walk_list = []
        for item in run_walk_stats:
            run_walk_list.append({
                "id": item.id,
                "full_name": item.full_name,
                "total_kcal": int(item.total_kcal or 0),
                "total_dist": round(item.total_dist or 0, 1),
                "total_time": round((item.total_time or 0) / 60.0, 1)
            })

        for rank, ath in enumerate(run_walk_list, 1):
            ath["rank"] = rank

        if run_walk_list:
            grouped["Chạy & Đi bộ"] = run_walk_list
        # --------------------------------------

        # Kiểm tra sự tồn tại của BXH "Chạy & Đi bộ"
        self.assertIn("Chạy & Đi bộ", grouped)
        run_walk_list = grouped["Chạy & Đi bộ"]
        
        print("\nKet qua Bang xep hang gop 'Chay & Di bo':")
        for ath in run_walk_list:
            print(f"Hang: {ath['rank']} | Ten: {ath['full_name']} | Tong KM: {ath['total_dist']} km")
            
        # Kiểm tra số lượng người tham gia (VĐV A, B, C tham gia; VĐV D đạp xe bị loại)
        self.assertEqual(len(run_walk_list), 3)
        
        # Kiểm tra thứ tự và thành tích:
        # Hạng 1: VĐV A (15.0 km)
        self.assertEqual(run_walk_list[0]["rank"], 1)
        self.assertEqual(run_walk_list[0]["full_name"], "VĐV A (Run 10km, Walk 5km)")
        self.assertEqual(run_walk_list[0]["total_dist"], 15.0)
        
        # Hạng 2: VĐV B (12.0 km)
        self.assertEqual(run_walk_list[1]["rank"], 2)
        self.assertEqual(run_walk_list[1]["full_name"], "VĐV B (Run 12km)")
        self.assertEqual(run_walk_list[1]["total_dist"], 12.0)
        
        # Hạng 3: VĐV C (8.0 km)
        self.assertEqual(run_walk_list[2]["rank"], 3)
        self.assertEqual(run_walk_list[2]["full_name"], "VĐV C (Walk 8km)")
        self.assertEqual(run_walk_list[2]["total_dist"], 8.0)

if __name__ == "__main__":
    unittest.main()

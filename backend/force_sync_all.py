import sqlite3
import os
import sys
import time

# Thiết lập đường dẫn thư mục dự án
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Athlete, CompetitionEvent
from backend.sync_engine import sync_single_athlete_all_events

def force_sync_all_linked_athletes():
    """
    Script quét qua toàn bộ VĐV đã liên kết Strava, thực hiện gọi API cá nhân của họ
    để đồng bộ lại dữ liệu chuẩn và tự động re-assign các hoạt động bị gán nhầm trong quá khứ.
    """
    db = SessionLocal()
    try:
        # Lấy danh sách VĐV đã liên kết Strava
        athletes = db.query(Athlete).filter(Athlete.strava_refresh_token != None).all()
        print(f"=== PHÁT KHỞI ĐỒNG BỘ TOÀN BỘ VĐV ĐÃ LIÊN KẾT ({len(athletes)} VĐV) ===")
        
        success_count = 0
        for i, athlete in enumerate(athletes):
            print(f"\n[{i+1}/{len(athletes)}] Đồng bộ cho VĐV: {athlete.full_name} (ID={athlete.id})...")
            try:
                # Gọi hàm đồng bộ an toàn mới của chúng ta
                sync_single_athlete_all_events(db, athlete)
                success_count += 1
                # Nghỉ ngắn giữa các request để tránh bị Strava rate limit (100 requests / 15 mins)
                time.sleep(1.0)
            except Exception as athlete_err:
                print(f"Lỗi khi đồng bộ cho {athlete.full_name}: {athlete_err}")
                db.rollback()
                
        print(f"\n=== HOÀN THÀNH ĐỒNG BỘ TOÀN BỘ VĐV ===")
        print(f"Đã xử lý thành công {success_count}/{len(athletes)} VĐV.")
        
    except Exception as e:
        print(f"Lỗi hệ thống: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    force_sync_all_linked_athletes()

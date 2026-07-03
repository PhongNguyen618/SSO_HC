import sys
import json
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Activity

def cleanup_old_numeric_ids():
    db = SessionLocal()
    to_delete = []
    
    try:
        # Lấy tất cả hoạt động
        all_acts = db.query(Activity).all()
        for act in all_acts:
            # Nếu ID là số thuần túy (không chứa dấu gạch dưới '_' và không phải chuỗi hash 64 ký tự)
            if act.id.isdigit() and len(act.id) < 25:
                to_delete.append(act.id)
                
        if to_delete:
            backup_file = "static/uploads/deleted_activities_backup.jsonl"
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            
            # Ghi log backup trước khi xóa
            with open(backup_file, "a", encoding="utf-8") as f:
                for act_id in to_delete:
                    act = db.query(Activity).filter(Activity.id == act_id).first()
                    if act:
                        act_dict = {
                            "id": act.id,
                            "athlete_id": act.athlete_id,
                            "event_id": act.event_id,
                            "athlete_name_raw": act.athlete_name_raw,
                            "name": act.name,
                            "type": act.type,
                            "sport_type": act.sport_type,
                            "distance_km": act.distance_km,
                            "moving_time_min": act.moving_time_min,
                            "elapsed_time_min": act.elapsed_time_min,
                            "pace_min_km": act.pace_min_km,
                            "elevation_gain_m": act.elevation_gain_m,
                            "activity_date": act.activity_date,
                            "activity_time": act.activity_time,
                            "kcal_burned": act.kcal_burned,
                            "mets_value": act.mets_value,
                            "is_suspicious": act.is_suspicious,
                            "suspicion_reason": act.suspicion_reason,
                            "distance_km_raw": act.distance_km_raw,
                            "kcal_burned_raw": act.kcal_burned_raw,
                            "multiplier": act.multiplier,
                            "backup_time": "2026-07-03T13:45:00Z",
                            "reason": "Don dep ID so thuan tuy cua code loi cu de nap lai composite ID"
                        }
                        f.write(json.dumps(act_dict, ensure_ascii=False) + "\n")
            
            # Xóa các hoạt động ID số cũ khỏi DB
            db.query(Activity).filter(Activity.id.in_(to_delete)).delete(synchronize_session=False)
            db.commit()
            print(f"Đã dọn dẹp thành công {len(to_delete)} hoạt động dùng ID số cũ.")
        else:
            print("Không có hoạt động nào dùng ID số cũ cần dọn dẹp.")
            
    except Exception as e:
        db.rollback()
        print(f"Lỗi khi dọn dẹp ID số cũ: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_old_numeric_ids()

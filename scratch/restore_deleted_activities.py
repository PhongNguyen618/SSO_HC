import sys
import json
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Activity

def restore_activities(backup_file="static/uploads/deleted_activities_backup.jsonl"):
    if not os.path.exists(backup_file):
        print(f"File backup {backup_file} không tồn tại.")
        return
        
    db = SessionLocal()
    restored_count = 0
    skipped_count = 0
    
    try:
        with open(backup_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                try:
                    act_data = json.loads(line.strip())
                    
                    # Bỏ qua thời gian backup khi khôi phục vào bảng Activity
                    act_id = act_data.get("id")
                    
                    # Kiểm tra xem hoạt động đã tồn tại lại trong DB chưa
                    exists = db.query(Activity).filter(Activity.id == act_id).first()
                    if exists:
                        skipped_count += 1
                        continue
                        
                    # Tạo đối tượng Activity mới
                    new_act = Activity(
                        id=act_data.get("id"),
                        athlete_id=act_data.get("athlete_id"),
                        event_id=act_data.get("event_id"),
                        athlete_name_raw=act_data.get("athlete_name_raw"),
                        name=act_data.get("name"),
                        type=act_data.get("type"),
                        sport_type=act_data.get("sport_type"),
                        distance_km=act_data.get("distance_km"),
                        moving_time_min=act_data.get("moving_time_min"),
                        elapsed_time_min=act_data.get("elapsed_time_min"),
                        pace_min_km=act_data.get("pace_min_km"),
                        elevation_gain_m=act_data.get("elevation_gain_m"),
                        activity_date=act_data.get("activity_date"),
                        activity_time=act_data.get("activity_time"),
                        kcal_burned=act_data.get("kcal_burned"),
                        mets_value=act_data.get("mets_value"),
                        is_suspicious=act_data.get("is_suspicious", False),
                        suspicion_reason=act_data.get("suspicion_reason"),
                        distance_km_raw=act_data.get("distance_km_raw"),
                        kcal_burned_raw=act_data.get("kcal_burned_raw"),
                        multiplier=act_data.get("multiplier", 1.0)
                    )
                    db.add(new_act)
                    restored_count += 1
                except Exception as line_err:
                    print(f"Lỗi khi giải mã dòng dữ liệu: {line_err}")
                    
        if restored_count > 0:
            db.commit()
            print(f"Đã khôi phục thành công {restored_count} hoạt động vào Database. (Bỏ qua {skipped_count} hoạt động đã tồn tại)")
        else:
            print(f"Không có hoạt động nào cần khôi phục. (Bỏ qua {skipped_count} hoạt động đã tồn tại)")
            
    except Exception as e:
        db.rollback()
        print(f"Lỗi hệ thống trong quá trình khôi phục: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    restore_activities()

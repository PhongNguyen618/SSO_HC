import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath("c:/Users/PC/Desktop/SSO_HC"))
from backend.database import SessionLocal, Activity, Athlete

def cleanup_historical_duplicates():
    print("--- HISTORICAL DUPLICATES CLEANUP START ---")
    db = SessionLocal()
    try:
        activities = db.query(Activity).all()
        
        from collections import defaultdict
        
        # Nhóm các hoạt động theo VĐV
        by_athlete = defaultdict(list)
        for act in activities:
            ath_key = act.athlete_id if act.athlete_id is not None else act.athlete_name_raw
            by_athlete[ath_key].append(act)
            
        to_delete = []
        
        for ath_key, act_list in by_athlete.items():
            if len(act_list) < 2:
                continue
                
            # Duyệt qua từng cặp hoạt động để so khớp trùng lặp
            merged_indices = set()
            
            for i in range(len(act_list)):
                if i in merged_indices:
                    continue
                    
                act1 = act_list[i]
                
                for j in range(i + 1, len(act_list)):
                    if j in merged_indices:
                        continue
                        
                    act2 = act_list[j]
                    
                    # 1. Phải cùng giải đấu (event_id)
                    if act1.event_id != act2.event_id:
                        continue
                        
                    # 2. Phải cùng loại hình thể thao (sport_type)
                    if act1.sport_type != act2.sport_type:
                        continue
                        
                    # 3. Chênh lệch cự ly (distance_km_raw)
                    dist1 = act1.distance_km_raw if act1.distance_km_raw is not None else act1.distance_km
                    dist2 = act2.distance_km_raw if act2.distance_km_raw is not None else act2.distance_km
                    dist_diff = abs((dist1 or 0.0) - (dist2 or 0.0))
                    
                    # 4. Chênh lệch thời gian di chuyển (moving_time_min)
                    time_diff = abs((act1.moving_time_min or 0.0) - (act2.moving_time_min or 0.0))
                    
                    # 5. Chênh lệch độ cao tăng thêm (elevation_gain_m)
                    elev_diff = abs((act1.elevation_gain_m or 0.0) - (act2.elevation_gain_m or 0.0))
                    
                    # Ngưỡng so sánh trùng lặp: cự ly <= 0.05 km, thời gian <= 1.0 phút, độ cao <= 10.0 m
                    if dist_diff <= 0.05 and time_diff <= 1.0 and elev_diff <= 10.0:
                        # So sánh tên hoạt động (nếu tự đặt tên khác nhau thì không xóa)
                        name1_clean = (act1.name or "").strip().lower()
                        name2_clean = (act2.name or "").strip().lower()
                        
                        generic_keywords = [
                            "activity", "hoạt động strava", "hoạt động", "workout", "run", "walk", "ride",
                            "morning run", "afternoon run", "evening run", "night run",
                            "morning walk", "afternoon walk", "evening walk", "night walk",
                            "morning ride", "afternoon ride", "evening ride", "night ride",
                            "lunch run", "lunch walk", "lunch ride"
                        ]
                        is_generic1 = any(k in name1_clean for k in generic_keywords) or name1_clean == ""
                        is_generic2 = any(k in name2_clean for k in generic_keywords) or name2_clean == ""
                        
                        name_match = True
                        if name1_clean != name2_clean and not is_generic1 and not is_generic2:
                            name_match = False
                            
                        if name_match:
                            # PHÁT HIỆN TRÙNG LẶP LỊCH SỬ!
                            # Quyết định giữ lại bản ghi có hệ số nhân (multiplier) cao hơn
                            mult1 = act1.multiplier or 1.0
                            mult2 = act2.multiplier or 1.0
                            
                            if mult1 >= mult2:
                                # Giữ lại act1, xóa act2
                                to_delete.append(act2.id)
                                merged_indices.add(j)
                                try:
                                    print(f"Duplicate found for Athlete {repr(ath_key)}: Keep ID={act1.id[:8]} (Date={act1.activity_date}, Mult={mult1}x) - Delete ID={act2.id[:8]} (Date={act2.activity_date}, Mult={mult2}x)")
                                except:
                                    print(f"Duplicate found for Athlete ID {act1.athlete_id}: Keep ID={act1.id[:8]} - Delete ID={act2.id[:8]}")
                            else:
                                # Giữ lại act2, xóa act1
                                to_delete.append(act1.id)
                                merged_indices.add(i)
                                try:
                                    print(f"Duplicate found for Athlete {repr(ath_key)}: Keep ID={act2.id[:8]} (Date={act2.activity_date}, Mult={mult2}x) - Delete ID={act1.id[:8]} (Date={act1.activity_date}, Mult={mult1}x)")
                                except:
                                    print(f"Duplicate found for Athlete ID {act2.athlete_id}: Keep ID={act2.id[:8]} - Delete ID={act1.id[:8]}")
                                break # Thoát vòng lặp trong của act1 vì act1 đã bị xóa
                                
        deleted_count = 0
        if to_delete:
            deleted_count = db.query(Activity).filter(Activity.id.in_(to_delete)).delete(synchronize_session=False)
            db.commit()
            print(f"\n--- SUCCESS: Deleted {deleted_count} historical duplicate records ---")
        else:
            print("\n--- No historical duplicate records found ---")
            
    except Exception as e:
        db.rollback()
        print(f"Error during historical duplicates cleanup: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_historical_duplicates()

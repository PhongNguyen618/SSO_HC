import time
import requests
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import UploadFile
from backend.database import SessionLocal, Config, Athlete, Activity, CompetitionEvent
from backend.calculations import get_mets_value, calculate_kcal, check_suspicious_activity, get_multiplier_for_date

def get_config_dict(db: Session) -> dict:
    configs = db.query(Config).all()
    return {c.key: c.value for c in configs}

def update_config(db: Session, key: str, value: str):
    config = db.query(Config).filter(Config.key == key).first()
    if config:
        config.value = str(value)
    else:
        db.add(Config(key=key, value=str(value)))
    db.commit()

def refresh_strava_token(db: Session, configs: dict) -> str:
    """
    Làm mới access token của Strava bằng refresh token nếu đã hết hạn.
    """
    client_id = configs.get("strava_client_id")
    client_secret = configs.get("strava_client_secret")
    refresh_token = configs.get("strava_refresh_token")
    expires_at = int(configs.get("strava_expires_at", 0))

    if not refresh_token:
        print("Sync Engine: No refresh token. Please authorize via Admin Panel.")
        return None

    # Nếu token vẫn còn hạn hơn 60 giây, trả về luôn
    if expires_at > int(time.time()) + 60:
        return configs.get("strava_access_token")

    print("Sync Engine: Access token expired. Refreshing...")
    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        
        # Lưu token mới vào DB
        update_config(db, "strava_access_token", token_data["access_token"])
        update_config(db, "strava_refresh_token", token_data["refresh_token"])
        update_config(db, "strava_expires_at", str(token_data["expires_at"]))
        
        print("Sync Engine: Token refreshed successfully.")
        return token_data["access_token"]
    except Exception as e:
        print(f"Sync Engine: Error refreshing token: {e}")
        return None

def _sync_single_event(db, configs, access_token, event) -> dict:
    """
    Đồng bộ hoạt động từ Strava Club của một giải đấu cụ thể.
    """
    result = {"status": "idle", "new_activities": 0, "error": None}
    club_id = event.strava_club_id
    event_id = event.id
    
    if not club_id:
        result["status"] = "error"
        result["error"] = f"Giải đấu '{event.title}' thiếu Club ID."
        return result

    # Gọi API Strava Club Activities
    print(f"Sync Engine: Starting sync for Event '{event.title}' (Club {club_id})...")
    url = f"https://www.strava.com/api/v3/clubs/{club_id}/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    all_activities = []
    page = 1
    per_page = 200
    
    while True:
        response = requests.get(url, headers=headers, params={"page": page, "per_page": per_page}, timeout=10)
        response.raise_for_status()
        chunk = response.json()
        if not chunk:
            break
        all_activities.extend(chunk)
        if len(chunk) < per_page:
            break
        page += 1

    print(f"Sync Engine: Downloaded {len(all_activities)} activities from Strava for event '{event.title}'.")
    
    new_count = 0
    gmt7_now = datetime.utcnow() + timedelta(hours=7)
    today_str = gmt7_now.strftime("%Y-%m-%d")
    seen_ids = set()

    # Cache danh sách vận động viên để đối khớp tốc độ cao (hỗ trợ nhiều tên cách nhau bằng dấu phẩy)
    athletes = db.query(Athlete).all()
    athlete_map = {}
    for a in athletes:
        if a.strava_name:
            for part in a.strava_name.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    athlete_map[cleaned] = a

    for act in all_activities:
        athlete_data = act.get("athlete", {})
        firstname = athlete_data.get("firstname", "")
        lastname = athlete_data.get("lastname", "")
        athlete_name_raw = f"{firstname} {lastname}".strip()
        
        name = act.get("name", "Hoạt động Strava")
        act_type = act.get("type", "Run")
        sport_type = act.get("sport_type", "Run")
        
        distance_m = float(act.get("distance", 0.0))
        moving_time_s = float(act.get("moving_time", 0.0))
        elapsed_time_s = float(act.get("elapsed_time", 0.0))
        elevation_gain_m = float(act.get("total_elevation_gain", 0.0))
        
        distance_km = round(distance_m / 1000.0, 2)
        moving_time_min = round(moving_time_s / 60.0, 1)
        elapsed_time_min = round(elapsed_time_s / 60.0, 1)
        
        pace_min_km = 0.0
        if distance_km > 0:
            pace_min_km = round(moving_time_min / distance_km, 2)

        # Phân giải VĐV sớm để phục vụ kiểm tra trùng lặp
        athlete = athlete_map.get(athlete_name_raw.lower())
        athlete_id = athlete.id if athlete else None

        # --- Kiểm tra trùng lặp sớm (Early Dedup) cho Club API ---
        # API Strava Club Activities KHÔNG trả về start_date_local (ngày giờ thực tế).
        # Nếu hoạt động đã được sync ở lần trước (với ngày đúng), phải phát hiện
        # và bỏ qua TRƯỚC KHI thuật toán grace period gán nhầm ngày.
        start_date_local = act.get("start_date_local") or act.get("start_date")
        if not start_date_local:
            from sqlalchemy import func as sa_func
            early_limit = (gmt7_now - timedelta(days=7)).strftime("%Y-%m-%d")
            if athlete_id:
                early_matches = db.query(Activity).filter(
                    Activity.athlete_id == athlete_id,
                    Activity.event_id == event_id,
                    Activity.sport_type == sport_type,
                    Activity.activity_date >= early_limit
                ).all()
            else:
                early_matches = db.query(Activity).filter(
                    sa_func.lower(Activity.athlete_name_raw) == athlete_name_raw.lower(),
                    Activity.event_id == event_id,
                    Activity.sport_type == sport_type,
                    Activity.activity_date >= early_limit
                ).all()

            is_already_synced = False
            for ext in early_matches:
                dist_ext = ext.distance_km_raw if ext.distance_km_raw is not None else ext.distance_km
                if abs((dist_ext or 0.0) - distance_km) <= 0.05 \
                   and abs((ext.moving_time_min or 0.0) - moving_time_min) <= 1.0 \
                   and abs((ext.elevation_gain_m or 0.0) - elevation_gain_m) <= 10.0:
                    is_already_synced = True
                    print(f"Sync Engine: Early dedup - skip '{name}' of {athlete_name_raw} "
                          f"(already synced on {ext.activity_date})")
                    break

            if is_already_synced:
                continue
        act_time_str = None
        if start_date_local:
            act_date_str = start_date_local[:10]  # Định dạng YYYY-MM-DD
            if len(start_date_local) >= 16:
                act_time_str = start_date_local[11:16]  # Định dạng HH:MM
        else:
            act_date_str = today_str
            # Tự động áp giờ chạy mặc định là giờ local hiện tại (GMT+7)
            act_time_str = gmt7_now.strftime("%H:%M")

            # Cấu hình giờ ân hạn đồng bộ, mặc định là 12 giờ trưa
            grace_hours = 12
            grace_config = configs.get("sync_grace_period_hours")
            if grace_config:
                try:
                    grace_hours = int(grace_config)
                except ValueError:
                    pass

            # Chỉ lùi ngày nếu quét trước giờ ân hạn (ví dụ trước 12:00 trưa)
            if gmt7_now.hour < grace_hours:
                # Nếu quét vào rạng sáng (trước 5:00 sáng), chắc chắn bất kỳ hoạt động nào (kể cả Morning Run)
                # cũng đều là hoạt động của ngày hôm trước vì sáng hôm nay chưa thể diễn ra.
                # Ngược lại, nếu từ 5:00 sáng đến 12:00 trưa, chỉ lùi các hoạt động có từ khóa trưa/chiều/tối.
                is_early_morning = gmt7_now.hour < 5
                
                name_lower = (name or "").lower()
                time_keywords = ["afternoon", "evening", "night", "lunch", "sunset", "dusk", "chiều", "tối", "trưa"]
                has_time_keyword = any(kw in name_lower for kw in time_keywords)

                if is_early_morning or has_time_keyword:
                    yesterday = gmt7_now - timedelta(days=1)
                    yesterday_str = yesterday.strftime("%Y-%m-%d")

                    # Tra cứu hệ số nhân của ngày quét và ngày hôm trước
                    mult_today = get_multiplier_for_date(act_date_str, event_id, db)
                    mult_yesterday = get_multiplier_for_date(yesterday_str, event_id, db)

                    # Nếu ngày hôm trước có hệ số nhân lớn hơn ngày hiện tại, lùi ngày hoạt động
                    if mult_yesterday > mult_today:
                        act_date_str = yesterday_str
                        act_time_str = "23:59"  # Đánh dấu chạy muộn ngày hôm trước
                        reason = "quet vao rang sang" if is_early_morning else "ten co tu khoa buoi chieu/toi"
                        print(f"Sync Engine: Tu dong lui ngay hoat dong cua {athlete_name_raw} ('{name}') tu {gmt7_now.strftime('%Y-%m-%d')} ve {yesterday_str} "
                              f"do {reason}, ngay hom truoc co he so nhan cao hon ({mult_yesterday} > {mult_today}) va quet truoc {grace_hours}h.")

        # Tạo mã định danh duy nhất bao gồm event_id và ngày hoạt động thực tế để chống trùng lặp
        unique_str = f"{athlete_name_raw}_{act_date_str}_{name}_{act_type}_{distance_km}_{moving_time_min}_{elapsed_time_min}_{elevation_gain_m}_{event_id}"
        act_id = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()
        
        # Lọc trùng lặp in-memory trong cùng một lượt tải từ Strava
        if act_id in seen_ids:
            continue
            
        # Kiểm tra xem hoạt động đã có trong DB chưa
        exists = db.query(Activity).filter(Activity.id == act_id).first()
        if exists:
            seen_ids.add(act_id)
            continue
            
        seen_ids.add(act_id)
            
        # Chặn trùng lặp nâng cao (Pre-sync Deduplication) trước khi chèn
        # Tìm trong DB xem có hoạt động nào trùng khớp cự ly và thời gian gần đây không
        # Hỗ trợ cả VĐV đã liên kết (athlete_id) và chưa liên kết (athlete_name_raw)
        existing_similar = []
        limit_date = (gmt7_now - timedelta(days=4)).strftime("%Y-%m-%d")
        if athlete_id:
            existing_similar = db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.event_id == event_id,
                Activity.sport_type == sport_type,
                Activity.activity_date >= limit_date
            ).all()
        else:
            from sqlalchemy import func as sa_func
            existing_similar = db.query(Activity).filter(
                sa_func.lower(Activity.athlete_name_raw) == athlete_name_raw.lower(),
                Activity.event_id == event_id,
                Activity.sport_type == sport_type,
                Activity.activity_date >= limit_date
            ).all()

        if existing_similar:
            is_dup_pre = False
            for ext in existing_similar:
                dist_ext = ext.distance_km_raw if ext.distance_km_raw is not None else ext.distance_km
                dist_diff = abs((dist_ext or 0.0) - distance_km)
                time_diff = abs((ext.moving_time_min or 0.0) - moving_time_min)
                elev_diff = abs((ext.elevation_gain_m or 0.0) - elevation_gain_m)
                
                # Check overlap thời gian (bổ sung cho trường hợp ghi song song nhiều thiết bị)
                time_overlap_dup = False
                if ext.activity_date == act_date_str and ext.activity_time and act_time_str:
                    try:
                        parts1 = ext.activity_time.split(":")
                        parts2 = act_time_str.split(":")
                        h1, m1 = int(parts1[0]), int(parts1[1])
                        h2, m2 = int(parts2[0]), int(parts2[1])
                        start1 = h1 * 60 + m1
                        start2 = h2 * 60 + m2
                        
                        dur1 = ext.elapsed_time_min if ext.elapsed_time_min is not None else ext.moving_time_min
                        dur2 = elapsed_time_min if elapsed_time_min is not None else moving_time_min
                        
                        dur1 = dur1 or 0.0
                        dur2 = dur2 or 0.0
                        
                        end1 = start1 + dur1
                        end2 = start2 + dur2
                        
                        overlap_mins = max(0.0, min(end1, end2) - max(start1, start2))
                        min_dur = min(dur1, dur2)
                        
                        if min_dur > 0:
                            overlap_ratio = overlap_mins / min_dur
                            if overlap_ratio > 0.5 and abs(start1 - start2) <= 15:
                                time_overlap_dup = True
                    except Exception:
                        pass

                # So sánh tên hoạt động
                name1_clean = (ext.name or "").strip().lower()
                name2_clean = (name or "").strip().lower()
                
                generic_keywords = [
                    "activity", "hoạt động strava", "hoạt động", "workout", "run", "walk", "ride",
                    "morning run", "afternoon run", "evening run", "night run",
                    "morning walk", "afternoon walk", "evening walk", "night walk",
                    "morning ride", "afternoon ride", "evening ride", "night ride",
                    "lunch run", "lunch walk", "lunch ride"
                ]
                is_generic1 = name1_clean in generic_keywords or name1_clean == ""
                is_generic2 = name2_clean in generic_keywords or name2_clean == ""
                
                name_match = True
                is_similar_tight = dist_diff <= 0.05 and time_diff <= 1.0 and elev_diff <= 10.0
                if name1_clean != name2_clean and (not is_generic1 or not is_generic2) and not time_overlap_dup and not is_similar_tight:
                    name_match = False
                    
                # Thiết lập dung sai cho cự ly và thời gian
                max_dist_diff = 0.05
                max_time_diff = 1.0
                max_elev_diff = 10.0
                
                # Nếu trùng overlap thời gian (do cùng giờ sync), nới lỏng thành tỉ lệ tương đối 8% cự ly và 5% thời gian
                if time_overlap_dup:
                    min_dist = min(dist_ext or 0.0, distance_km)
                    min_time = min(ext.moving_time_min or 0.0, moving_time_min)
                    max_dist_diff = max(0.05, 0.08 * min_dist)
                    max_time_diff = max(1.0, 0.05 * min_time)
                    max_elev_diff = max(10.0, 15.0)
                    
                if name_match and dist_diff <= max_dist_diff and time_diff <= max_time_diff and elev_diff <= max_elev_diff:
                    is_dup_pre = True
                    break
                    
            if is_dup_pre:
                # Hoạt động đã được đồng bộ trước đó (có thể với ngày quét khác), bỏ qua không lưu trùng
                continue
        
        # Tính toán METs & KCAL
        mets_value = 0.0
        kcal_burned = 0.0
        
        if athlete:
            speed_kmh = 0.0
            if moving_time_min > 0:
                speed_kmh = distance_km / (moving_time_min / 60.0)
            
            actual_time_min = elapsed_time_min if moving_time_min < 1.0 else moving_time_min
            
            mets_value = get_mets_value(sport_type, speed_kmh, db, distance_km, elevation_gain_m, event_id=event_id)
            mult = get_multiplier_for_date(act_date_str, event_id, db)
            kcal_burned = calculate_kcal(mets_value, athlete.weight, actual_time_min, elevation_gain_m, sport_type, multiplier=mult)

        # Kiểm tra gian lận
        is_suspicious, suspicion_reason = check_suspicious_activity(
            sport_type=sport_type,
            distance_km=distance_km,
            pace_min_km=pace_min_km,
            elevation_gain_m=elevation_gain_m,
            configs=configs
        )

        # Tính multiplier cho ngày hoạt động thực tế
        activity_multiplier = get_multiplier_for_date(act_date_str, event_id, db) if athlete else 1.0
        kcal_burned_raw = round(kcal_burned / activity_multiplier) if activity_multiplier > 0 else kcal_burned
        
        new_activity = Activity(
            id=act_id,
            athlete_id=athlete_id,
            event_id=event_id,
            athlete_name_raw=athlete_name_raw,
            name=name,
            type=act_type,
            sport_type=sport_type,
            distance_km=round(distance_km * activity_multiplier, 2),
            distance_km_raw=distance_km,
            moving_time_min=moving_time_min,
            elapsed_time_min=elapsed_time_min,
            pace_min_km=pace_min_km,
            elevation_gain_m=elevation_gain_m,
            activity_date=act_date_str,
            activity_time=act_time_str,
            kcal_burned=kcal_burned,
            kcal_burned_raw=kcal_burned_raw,
            mets_value=mets_value,
            multiplier=activity_multiplier,
            is_suspicious=is_suspicious,
            suspicion_reason=suspicion_reason
        )
        
        db.add(new_activity)
        new_count += 1
        
    try:
        db.commit()
        print(f"Sync Engine: Saved {new_count} new activities for event '{event.title}'.")
        result["status"] = "success"
        result["new_activities"] = new_count
    except Exception as e:
        db.rollback()
        print(f"Sync Engine: Error committing activities for event '{event.title}': {e}")
        result["status"] = "error"
        result["error"] = f"Lỗi lưu cơ sở dữ liệu: {str(e)}"
        
    return result


def sync_club_activities(event_id: int = None) -> dict:
    """
    Đồng bộ hoạt động từ Strava Club và lưu vào SQLite Database.
    Nếu truyền event_id: chỉ đồng bộ cho giải đấu đó.
    Nếu không truyền: lặp qua tất cả giải đấu đang hoạt động.
    """
    db = SessionLocal()
    result = {"status": "idle", "new_activities": 0, "error": None, "details": []}
    try:
        # 1. Tự động đóng các giải đấu đã hết hạn trước tiên
        today_str = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
        if not event_id:
            expired_events = db.query(CompetitionEvent).filter(
                CompetitionEvent.is_active == True,
                CompetitionEvent.end_date != None,
                CompetitionEvent.end_date != '',
                CompetitionEvent.end_date < today_str
            ).all()
            if expired_events:
                for ex_ev in expired_events:
                    ex_ev.is_active = False
                    print(f"Sync Engine: Event '{ex_ev.title}' (ID {ex_ev.id}) has ended on {ex_ev.end_date}. Auto marked as INACTIVE.")
                db.commit()

        # 2. Xác định danh sách giải đấu cần đồng bộ
        if event_id:
            events = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).all()
        else:
            events = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).all()

        configs = get_config_dict(db)

        if not events:
            # Fallback: đồng bộ theo club_id toàn cục (tương thích ngược) nếu có cấu hình
            club_id = configs.get("strava_club_id")
            if not club_id:
                result["status"] = "success"
                result["new_activities"] = 0
                return result
                
            # Lấy Access Token cho fallback
            access_token = refresh_strava_token(db, configs)
            if not access_token:
                result["status"] = "error"
                result["error"] = "Không thể lấy Access Token cho cấu hình toàn cục."
                return result
                
            from types import SimpleNamespace
            fake_event = SimpleNamespace(id=None, title="Global (Legacy)", strava_club_id=club_id)
            sub_result = _sync_single_event(db, configs, access_token, fake_event)
            result["status"] = sub_result["status"]
            result["new_activities"] = sub_result["new_activities"]
            result["error"] = sub_result.get("error")
            return result
        
        # 3. Lấy Access Token hợp lệ (chỉ khi thực sự có giải đấu cần đồng bộ)
        access_token = refresh_strava_token(db, configs)
        if not access_token:
            result["status"] = "error"
            result["error"] = "Không thể lấy Access Token. Vui lòng cấu hình OAuth."
            return result
        
        total_new = 0
        all_success = True
        for ev in events:
            try:
                sub_result = _sync_single_event(db, configs, access_token, ev)
                total_new += sub_result.get("new_activities", 0)
                result["details"].append({"event": ev.title, "status": sub_result["status"], "new": sub_result.get("new_activities", 0)})
                if sub_result["status"] == "error":
                    all_success = False
            except Exception as e:
                db.rollback()
                result["details"].append({"event": ev.title, "status": "error", "error": str(e)})
                all_success = False
        
        result["status"] = "success" if all_success else "partial"
        result["new_activities"] = total_new
        if not all_success:
            errs = [detail.get("error") for detail in result.get("details", []) if detail.get("error")]
            result["error"] = "Loi giai chay: " + "; ".join(errs) if errs else "Một số giải đấu đồng bộ thất bại. Vui lòng kiểm tra chi tiết."
        
    except Exception as e:
        db.rollback()
        print(f"Sync Engine: Sync error: {e}")
        result["status"] = "error"
        result["error"] = str(e)
    finally:
        try:
            if "status" in result and result["status"] != "idle":
                gmt7_now = datetime.utcnow() + timedelta(hours=7)
                now_str = gmt7_now.strftime("%Y-%m-%d %H:%M:%S")
                update_config(db, "last_sync_time", now_str)
                update_config(db, "last_sync_status", result["status"])
                update_config(db, "last_sync_new_count", str(result.get("new_activities", 0)))
                update_config(db, "last_sync_error", result.get("error") or "")
                db.commit()
        except Exception as log_ex:
            print(f"Sync Engine: Error saving finally sync log: {log_ex}")
        db.close()
        
    return result

def link_unlinked_activities(db: Session, athlete: Athlete):
    """
    Khi một VĐV đăng ký mới hoặc đổi tên, tự động liên kết các hoạt động chưa được liên kết
    nhưng có tên trùng khớp với một trong các tên hiển thị Strava của VĐV đó (ngăn cách bởi dấu phẩy, không phân biệt hoa thường).
    """
    from sqlalchemy import func
    if not athlete.strava_name:
        return
        
    names = [n.strip().lower() for n in athlete.strava_name.split(",") if n.strip()]
    if not names:
        return
        
    unlinked = db.query(Activity).filter(
        Activity.athlete_id == None,
        func.lower(Activity.athlete_name_raw).in_(names)
    ).all()
    
    if not unlinked:
        return
        
    for act in unlinked:
        act.athlete_id = athlete.id
        
        # Tính lại KCAL và METs dựa trên cân nặng của VĐV vừa đăng ký
        dist_raw = act.distance_km_raw if act.distance_km_raw is not None else act.distance_km
        speed_kmh = 0.0
        if act.moving_time_min > 0:
            speed_kmh = dist_raw / (act.moving_time_min / 60.0)
            
        actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
        mets_val = get_mets_value(act.sport_type, speed_kmh, db, dist_raw, act.elevation_gain_m, event_id=act.event_id)
        mult = get_multiplier_for_date(act.activity_date, act.event_id, db)
        
        act.mets_value = mets_val
        kcal_raw = calculate_kcal(mets_val, athlete.weight, actual_time_min, act.elevation_gain_m, act.sport_type)
        act.kcal_burned_raw = kcal_raw
        act.kcal_burned = round(kcal_raw * mult)
        act.multiplier = mult
        act.distance_km_raw = dist_raw
        act.distance_km = round(dist_raw * mult, 2)
        
    db.commit()
    print(f"Sync Engine: Linked {len(unlinked)} old activities for athlete {athlete.full_name}.")

async def import_excel_files(files: list[UploadFile], db: Session, event_id: int = None) -> dict:
    """
    Nhận danh sách các file Excel tải lên từ trình duyệt,
    đọc trực tiếp và nạp dữ liệu hoạt động vào SQLite.
    Nếu event_id được truyền, gắn hoạt động vào giải đấu tương ứng.
    """
    import pandas as pd
    import io
    import re
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    # Cache danh sách vận động viên để tối ưu hóa truy vấn tốc độ cao (hỗ trợ nhiều tên cách nhau bằng dấu phẩy)
    athletes = db.query(Athlete).all()
    athlete_map = {}
    for a in athletes:
        if a.strava_name:
            for part in a.strava_name.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    athlete_map[cleaned] = a
    seen_ids = set()
    
    # Nếu không truyền event_id, lấy giải đấu đang hoạt động đầu tiên
    if event_id is None:
        active_event = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).first()
        if active_event:
            event_id = active_event.id
    
    for file in files:
        if not file.filename.endswith(".xlsx"):
            continue
            
        try:
            # Đọc file in-memory
            file_bytes = await file.read()
            xl = pd.ExcelFile(io.BytesIO(file_bytes))
            
            sheet_name = "SSO_HC"
            if sheet_name not in xl.sheet_names:
                sheet_name = xl.sheet_names[0]
                
            df = pd.read_excel(io.BytesIO(file_bytes), sheet_name=sheet_name)
            
            # Chuẩn hóa tên cột
            col_map = {c.strip(): c for c in df.columns}
            
            for _, row in df.iterrows():
                name_raw = str(row.get(col_map.get("Tên Vận động viên"), "")).strip()
                act_name = str(row.get(col_map.get("Tên Hoạt động"), "Activity")).strip()
                act_type = str(row.get(col_map.get("Loại Hoạt động"), "Walk")).strip()
                sport_type = str(row.get(col_map.get("Loại Thể thao"), "Walk")).strip()
                
                dist_val = row.get(col_map.get("Khoảng cách (km)"))
                dist_km = float(dist_val) if pd.notna(dist_val) else 0.0
                
                mov_val = row.get(col_map.get("Thời gian Di chuyển (phút)"))
                mov_time = float(mov_val) if pd.notna(mov_val) else 0.0
                
                ela_val = row.get(col_map.get("Thời gian Tổng cộng (phút)"))
                ela_time = float(ela_val) if pd.notna(ela_val) else mov_time
                
                pace_val = row.get(col_map.get("Pace (min/km)"))
                pace = float(pace_val) if pd.notna(pace_val) else 0.0
                
                elev_val = row.get(col_map.get("Elevation Gain (m)"))
                elev = float(elev_val) if pd.notna(elev_val) else 0.0
                
                date_val = row.get(col_map.get("Ngày"))
                
                # Chuẩn hóa ngày và giờ
                activity_date = None
                activity_time = None
                if pd.notna(date_val):
                    if isinstance(date_val, datetime):
                        activity_date = date_val.strftime("%Y-%m-%d")
                        if date_val.hour > 0 or date_val.minute > 0:
                            activity_time = date_val.strftime("%H:%M")
                    elif hasattr(date_val, 'strftime'):
                        activity_date = date_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(date_val).strip()
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y %H:%M", "%Y-%m-%d %H:%M", "%d-%m-%Y %H:%M"):
                            try:
                                parsed_dt = datetime.strptime(date_str, fmt)
                                activity_date = parsed_dt.strftime("%Y-%m-%d")
                                if parsed_dt.hour > 0 or parsed_dt.minute > 0:
                                    activity_time = parsed_dt.strftime("%H:%M")
                                break
                            except ValueError:
                                continue
                if not activity_date:
                    file_date_part = file.filename.replace(".xlsx", "").strip()
                    try:
                        match = re.search(r'\d{2}-\d{2}-\d{4}', file_date_part)
                        if match:
                            activity_date = datetime.strptime(match.group(), "%d-%m-%Y").strftime("%Y-%m-%d")
                        else:
                            activity_date = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
                    except Exception:
                        activity_date = (datetime.utcnow() + timedelta(hours=7)).strftime("%Y-%m-%d")
                
                # Nghi vấn gian lận
                susp_val = row.get(col_map.get("Nghi_ngo_Gian_lan"))
                is_suspicious = False
                suspicion_reason = None
                if pd.notna(susp_val) and str(susp_val).strip() != "" and str(susp_val).strip().lower() != "nan":
                    is_suspicious = True
                    suspicion_reason = str(susp_val).strip()
                    
                if not name_raw or (dist_km == 0.0 and mov_time == 0.0):
                    continue
                    
                # Đồng bộ công thức tạo hash ID bao gồm event_id để chống trùng lặp giữa các giải
                dist_km_round = round(dist_km, 2)
                mov_time_round = round(mov_time, 1)
                ela_time_round = round(ela_time, 1)
                elev_round = float(elev)
                
                composite_key = f"{name_raw}_{activity_date}_{act_name}_{act_type}_{dist_km_round}_{mov_time_round}_{ela_time_round}_{elev_round}_{event_id}"
                activity_id = hashlib.sha256(composite_key.encode('utf-8')).hexdigest()
                
                if activity_id in seen_ids:
                    skipped_count += 1
                    continue
                    
                exists = db.query(Activity).filter(Activity.id == activity_id).first()
                if exists:
                    seen_ids.add(activity_id)
                    skipped_count += 1
                    continue
                    
                seen_ids.add(activity_id)
                    
                ath = athlete_map.get(name_raw.lower())
                athlete_id = ath.id if ath else None
                weight = ath.weight if ath else 60.0
                
                speed_kmh = (dist_km / (mov_time / 60.0)) if mov_time > 0 else 0.0
                actual_time_min = ela_time if mov_time < 1.0 else mov_time
                
                mets_val = get_mets_value(sport_type, speed_kmh, db, dist_km, elev, event_id=event_id)
                kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, elev, sport_type)
                mult = get_multiplier_for_date(activity_date, event_id, db)
                kcal_val = round(kcal_raw * mult)
                
                new_act = Activity(
                    id=activity_id,
                    athlete_id=athlete_id,
                    event_id=event_id,
                    athlete_name_raw=name_raw,
                    name=act_name,
                    type=act_type,
                    sport_type=sport_type,
                    distance_km=round(dist_km * mult, 2),
                    distance_km_raw=dist_km,
                    moving_time_min=mov_time,
                    elapsed_time_min=ela_time,
                    pace_min_km=pace,
                    elevation_gain_m=elev,
                    activity_date=activity_date,
                    activity_time=activity_time,
                    kcal_burned=kcal_val,
                    kcal_burned_raw=kcal_raw,
                    mets_value=mets_val,
                    multiplier=mult,
                    is_suspicious=is_suspicious,
                    suspicion_reason=suspicion_reason
                )
                db.add(new_act)
                imported_count += 1
                
            db.commit()
        except Exception as e:
            db.rollback()
            err_msg = f"Lỗi đọc file {file.filename}: {e}"
            print(err_msg)
            errors.append(err_msg)
            
    return {
        "status": "success",
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "errors": errors
    }

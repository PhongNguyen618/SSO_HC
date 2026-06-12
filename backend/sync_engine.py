import time
import requests
import hashlib
from datetime import datetime
from sqlalchemy.orm import Session
from fastapi import UploadFile
from backend.database import SessionLocal, Config, Athlete, Activity
from backend.calculations import get_mets_value, calculate_kcal, check_suspicious_activity

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
        })
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

def sync_club_activities() -> dict:
    """
    Đồng bộ hoạt động từ Strava Club và lưu vào SQLite Database.
    """
    db = SessionLocal()
    result = {"status": "idle", "new_activities": 0, "error": None}
    try:
        configs = get_config_dict(db)
        
        # 1. Kiểm tra cấu hình cần thiết
        club_id = configs.get("strava_club_id")
        if not club_id:
            result["status"] = "error"
            result["error"] = "Thiếu Club ID trong cấu hình."
            return result

        # 2. Lấy Access Token hợp lệ
        access_token = refresh_strava_token(db, configs)
        if not access_token:
            result["status"] = "error"
            result["error"] = "Không thể lấy Access Token. Vui lòng cấu hình OAuth."
            return result

        # 3. Gọi API Strava Club Activities
        print(f"Sync Engine: Starting sync for Club {club_id}...")
        url = f"https://www.strava.com/api/v3/clubs/{club_id}/activities"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        all_activities = []
        page = 1
        per_page = 200
        
        while True:
            response = requests.get(url, headers=headers, params={"page": page, "per_page": per_page})
            response.raise_for_status()
            chunk = response.json()
            if not chunk:
                break
            all_activities.extend(chunk)
            if len(chunk) < per_page:
                break
            page += 1

        print(f"Sync Engine: Downloaded {len(all_activities)} activities from Strava.")
        
        new_count = 0
        today_str = datetime.now().strftime("%Y-%m-%d")

        # 4. Lưu hoạt động vào Database
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

            # Tạo mã định danh duy nhất (SHA256 của các thuộc tính chính) để chống trùng lặp
            unique_str = f"{athlete_name_raw}_{name}_{act_type}_{distance_km}_{moving_time_min}_{elapsed_time_min}_{elevation_gain_m}"
            act_id = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()
            
            # Kiểm tra xem hoạt động đã có trong DB chưa
            exists = db.query(Activity).filter(Activity.id == act_id).first()
            if exists:
                continue
                
            # Khớp vận động viên đã đăng ký
            athlete = db.query(Athlete).filter(Athlete.strava_name == athlete_name_raw).first()
            athlete_id = athlete.id if athlete else None
            
            # Tính toán METs & KCAL
            mets_value = 0.0
            kcal_burned = 0.0
            
            if athlete:
                speed_kmh = 0.0
                if moving_time_min > 0:
                    speed_kmh = distance_km / (moving_time_min / 60.0)
                
                # Sửa đổi thời gian di chuyển theo logic cũ (sử dụng elapsed_time nếu moving_time quá nhỏ)
                # tg = lambda t1, t2: t2 if t1 < 1 else t1
                actual_time_min = elapsed_time_min if moving_time_min < 1.0 else moving_time_min
                
                mets_value = get_mets_value(sport_type, speed_kmh, db, distance_km, elevation_gain_m)
                kcal_burned = calculate_kcal(mets_value, athlete.weight, actual_time_min, elevation_gain_m, sport_type)

            # Kiểm tra gian lận
            is_suspicious, suspicion_reason = check_suspicious_activity(
                sport_type=sport_type,
                distance_km=distance_km,
                pace_min_km=pace_min_km,
                elevation_gain_m=elevation_gain_m,
                configs=configs
            )

            new_activity = Activity(
                id=act_id,
                athlete_id=athlete_id,
                athlete_name_raw=athlete_name_raw,
                name=name,
                type=act_type,
                sport_type=sport_type,
                distance_km=distance_km,
                moving_time_min=moving_time_min,
                elapsed_time_min=elapsed_time_min,
                pace_min_km=pace_min_km,
                elevation_gain_m=elevation_gain_m,
                activity_date=today_str, # Không có timestamp trong API, gán ngày đồng bộ
                kcal_burned=kcal_burned,
                mets_value=mets_value,
                is_suspicious=is_suspicious,
                suspicion_reason=suspicion_reason
            )
            
            db.add(new_activity)
            new_count += 1
            
        db.commit()
        print(f"Sync Engine: Saved {new_count} new activities to database.")
        result["status"] = "success"
        result["new_activities"] = new_count
        
    except Exception as e:
        db.rollback()
        print(f"Sync Engine: Sync error: {e}")
        result["status"] = "error"
        result["error"] = str(e)
    finally:
        db.close()
        
    return result

def link_unlinked_activities(db: Session, athlete: Athlete):
    """
    Khi một VĐV đăng ký mới, tự động liên kết các hoạt động chưa được liên kết
    nhưng có tên trùng khớp với `strava_name` của VĐV đó.
    """
    unlinked = db.query(Activity).filter(
        Activity.athlete_id == None,
        Activity.athlete_name_raw == athlete.strava_name
    ).all()
    
    if not unlinked:
        return
        
    for act in unlinked:
        act.athlete_id = athlete.id
        
        # Tính lại KCAL và METs dựa trên cân nặng của VĐV vừa đăng ký
        speed_kmh = 0.0
        if act.moving_time_min > 0:
            speed_kmh = act.distance_km / (act.moving_time_min / 60.0)
            
        actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
        mets_val = get_mets_value(act.sport_type, speed_kmh, db, act.distance_km, act.elevation_gain_m)
        
        act.mets_value = mets_val
        act.kcal_burned = calculate_kcal(mets_val, athlete.weight, actual_time_min, act.elevation_gain_m, act.sport_type)
        
    db.commit()
    print(f"Sync Engine: Linked {len(unlinked)} old activities for athlete {athlete.full_name}.")

async def import_excel_files(files: list[UploadFile], db: Session) -> dict:
    """
    Nhận danh sách các file Excel tải lên từ trình duyệt,
    đọc trực tiếp và nạp dữ liệu hoạt động vào SQLite.
    """
    import pandas as pd
    import io
    import re
    
    imported_count = 0
    skipped_count = 0
    errors = []
    
    # Cache danh sách vận động viên để tối ưu hóa truy vấn tốc độ cao
    athletes = db.query(Athlete).all()
    athlete_map = {a.strava_name.strip().lower(): a for a in athletes}
    seen_ids = set()
    
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
                
                # Chuẩn hóa ngày
                activity_date = None
                if pd.notna(date_val):
                    if isinstance(date_val, datetime):
                        activity_date = date_val.strftime("%Y-%m-%d")
                    elif hasattr(date_val, 'strftime'):
                        activity_date = date_val.strftime("%Y-%m-%d")
                    else:
                        date_str = str(date_val).strip()
                        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                            try:
                                activity_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
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
                            activity_date = datetime.now().strftime("%Y-%m-%d")
                    except Exception:
                        activity_date = datetime.now().strftime("%Y-%m-%d")
                
                # Nghi vấn gian lận
                susp_val = row.get(col_map.get("Nghi_ngo_Gian_lan"))
                is_suspicious = False
                suspicion_reason = None
                if pd.notna(susp_val) and str(susp_val).strip() != "" and str(susp_val).strip().lower() != "nan":
                    is_suspicious = True
                    suspicion_reason = str(susp_val).strip()
                    
                if not name_raw or (dist_km == 0.0 and mov_time == 0.0):
                    continue
                    
                composite_key = f"{name_raw}_{act_name}_{activity_date}_{dist_km}_{mov_time}"
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
                
                mets_val = get_mets_value(sport_type, speed_kmh, db, dist_km, elev)
                kcal_val = calculate_kcal(mets_val, weight, actual_time_min, elev, sport_type)
                
                new_act = Activity(
                    id=activity_id,
                    athlete_id=athlete_id,
                    athlete_name_raw=name_raw,
                    name=act_name,
                    type=act_type,
                    sport_type=sport_type,
                    distance_km=dist_km,
                    moving_time_min=mov_time,
                    elapsed_time_min=ela_time,
                    pace_min_km=pace,
                    elevation_gain_m=elev,
                    activity_date=activity_date,
                    kcal_burned=kcal_val,
                    mets_value=mets_val,
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

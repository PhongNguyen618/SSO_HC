import time
import requests
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from fastapi import UploadFile
from backend.database import SessionLocal, Config, Athlete, Activity, CompetitionEvent, CompetitionRegistration
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

def backup_db_file(reason: str = "auto"):
    """
    Tạo bản sao lưu CSDL vật lý trước các thao tác chỉnh sửa dữ liệu quan trọng.
    Chỉ giữ lại tối đa 5 bản sao lưu gần nhất để tránh đầy ổ cứng VPS.
    """
    import os
    import shutil
    from datetime import datetime
    
    db_path = "SSO_HC.db"
    if not os.path.exists(db_path):
        return
        
    backup_dir = os.path.join("static", "uploads", "backups")
    os.makedirs(backup_dir, exist_ok=True)
    
    time_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"SSO_HC_link_backup_{time_str}_{reason}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copyfile(db_path, backup_path)
        print(f"Backup Engine: Created instant DB backup at {backup_path} for reason: {reason}")
        
        # Xoay vòng bản sao lưu (Rotate): Giữ lại tối đa 5 bản backup loại link_backup
        backups = [
            os.path.join(backup_dir, f) 
            for f in os.listdir(backup_dir) 
            if f.startswith("SSO_HC_link_backup_") and f.endswith(".db")
        ]
        backups.sort(key=os.path.getmtime)
        
        while len(backups) > 5:
            oldest = backups.pop(0)
            try:
                os.remove(oldest)
                print(f"Backup Engine: Removed oldest link backup to save space: {oldest}")
            except Exception as e:
                print(f"Backup Engine: Error removing old backup {oldest}: {e}")
    except Exception as e:
        print(f"Backup Engine: Error creating DB backup: {e}")

def parse_time_str_to_seconds(time_str: str) -> float:
    import re
    time_str = time_str.strip().lower()
    if not time_str:
        return 0.0
        
    # Hỗ trợ tiếng Việt
    time_str = time_str.replace("giờ", "h").replace("gio", "h")
    time_str = time_str.replace("phút", "m").replace("phut", "m").replace("p", "m")
    time_str = time_str.replace("giây", "s").replace("giay", "s").replace("g", "s")
    
    if ":" in time_str:
        parts = time_str.split(":")
        try:
            if len(parts) == 2:
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        except ValueError:
            pass
    total_seconds = 0.0
    h_match = re.search(r'(\d+)\s*h', time_str)
    if h_match:
        total_seconds += int(h_match.group(1)) * 3600
    m_match = re.search(r'(\d+)\s*m', time_str)
    if m_match:
        total_seconds += int(m_match.group(1)) * 60
    s_match = re.search(r'(\d+)\s*s', time_str)
    if s_match:
        total_seconds += int(s_match.group(1))
    if total_seconds == 0.0:
        try:
            total_seconds = float(time_str)
        except ValueError:
            pass
    return total_seconds

def clean_html_tags(raw_html):
    import re
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', str(raw_html)).strip()

def parse_stat_distance(raw_val):
    import re
    text = clean_html_tags(raw_val).lower().replace(",", ".")
    is_km = "km" in text or "kilomet" in text
    
    num_part = ""
    for char in text:
        if char.isdigit() or char in ['.', ',']:
            num_part += char
            
    if not num_part:
        return 0.0
        
    if not is_km:
        if len(num_part) >= 5 and num_part[-4] in ['.', ',']:
            num_part = num_part[:-4] + num_part[-3:]
            
    if ',' in num_part and '.' in num_part:
        num_part = num_part.replace(',', '')
    elif ',' in num_part:
        num_part = num_part.replace(',', '.')
        
    try:
        num = float(num_part)
        if is_km:
            return num * 1000.0
        return num
    except ValueError:
        return 0.0

def convert_utc_to_gmt7(utc_str: str) -> str:
    if not utc_str:
        return None
    import datetime
    clean_str = utc_str.replace("Z", "")
    try:
        dt = datetime.datetime.fromisoformat(clean_str)
        dt_gmt7 = dt + datetime.timedelta(hours=7)
        return dt_gmt7.isoformat()
    except Exception:
        return utc_str

def scrape_club_activities_web(club_id: str, cookie: str = "") -> list:
    """
    Cào hoạt động từ trang web Strava Club sử dụng session cookie.
    Hỗ trợ cả giao diện Next.js (khi chưa đăng nhập) và React Microfrontend (khi đã đăng nhập).
    """
    import requests
    import re
    import html
    import json
    import random
    import time
    
    # 1. Thêm thời gian trễ ngẫu nhiên trước khi cào (Random Delay từ 3 đến 8 giây)
    delay = random.uniform(3.0, 8.0)
    print(f"Sync Engine (Scraper): Sleeping for {delay:.2f}s to avoid rate limiting/IP ban...")
    time.sleep(delay)
    
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ]
    
    # Khi đã đăng nhập (có cookie), truy cập trực tiếp trang recent_activity để lấy feed chính xác
    if cookie:
        url = f"https://www.strava.com/clubs/{club_id}/recent_activity"
    else:
        url = f"https://www.strava.com/clubs/{club_id}"
        
    headers = {
        "User-Agent": user_agents[0],
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "vi-VN,vi;q=0.9,fr-FR;q=0.8,fr;q=0.7,en-US;q=0.6,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "Referer": "https://www.strava.com/dashboard",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0"
    }
    
    if cookie:
        if "=" not in cookie:
            headers["Cookie"] = f"_strava4_session={cookie.strip()}"
        else:
            headers["Cookie"] = cookie.strip()
            
    print(f"Sync Engine (Scraper): Fetching web page for club {club_id}...")
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    
    html_content = response.text
    activities = []
    
    # THẾ HỆ 1: Thử parse qua React Microfrontend props (Khi đã đăng nhập - Logged In)
    react_feed_matches = re.findall(r"data-react-class='Microfrontend'\s+data-react-props='([^']+)'", html_content)
    pre_fetched = []
    for m in react_feed_matches:
        try:
            decoded = html.unescape(m)
            data = json.loads(decoded)
            if data.get("scope") == "strava_feed":
                pre_fetched = data.get("appContext", {}).get("preFetchedEntries", [])
                print(f"Sync Engine (Scraper): Found {len(pre_fetched)} entries in React Microfrontend props.")
                break
        except Exception:
            pass
            
    if pre_fetched:
        # Bóc tách từ Microfrontend
        for entry in pre_fetched:
            if entry.get("entity") != "Activity":
                continue
            try:
                activity_info = entry.get("activity", {})
                athlete_info = activity_info.get("athlete", {})
                
                athlete_id_val = athlete_info.get("athleteId")
                fullname = athlete_info.get("athleteName") or ""
                
                firstname = athlete_info.get("firstName") or ""
                lastname = ""
                if not firstname:
                    parts = fullname.strip().split()
                    if len(parts) > 1:
                        firstname = parts[0]
                        lastname = " ".join(parts[1:])
                    elif parts:
                        firstname = parts[0]
                else:
                    parts = fullname.strip().split()
                    if len(parts) > len(firstname.split()):
                        lastname = fullname.replace(firstname, "").strip()
                
                act_name = activity_info.get("activityName") or "Hoạt động Strava"
                act_type = activity_info.get("type") or "Run"
                sport_type = act_type
                
                distance_m = 0.0
                moving_time_s = 0.0
                elevation_gain_m = 0.0
                
                stats = activity_info.get("stats", [])
                stats_dict = {s.get("key"): s.get("value") for s in stats}
                
                dist_key = None
                time_key = None
                elev_key = None
                
                for k, v in stats_dict.items():
                    if k.endswith("_subtitle"):
                        base_key = k.replace("_subtitle", "")
                        val_text = clean_html_tags(str(v)).lower()
                        if "quãng đường" in val_text or "distance" in val_text:
                            dist_key = base_key
                        elif "thời gian" in val_text or "time" in val_text or "moving" in val_text:
                            time_key = base_key
                        elif "độ cao" in val_text or "elevation" in val_text:
                            elev_key = base_key

                if dist_key and dist_key in stats_dict:
                    distance_m = parse_stat_distance(stats_dict[dist_key])
                if time_key and time_key in stats_dict:
                    moving_time_s = parse_time_str_to_seconds(clean_html_tags(stats_dict[time_key]))
                else:
                    moving_time_s = float(activity_info.get("elapsedTime", 0))
                    
                if elev_key and elev_key in stats_dict:
                    elevation_gain_m = parse_stat_distance(stats_dict[elev_key])
                    
                start_date_local = convert_utc_to_gmt7(activity_info.get("startDate"))
                
                if distance_m == 0.0 and moving_time_s == 0.0:
                    continue
                    
                activities.append({
                    "athlete": {
                        "id": athlete_id_val,
                        "firstname": firstname,
                        "lastname": lastname
                    },
                    "name": act_name,
                    "distance": distance_m,
                    "moving_time": moving_time_s,
                    "elapsed_time": float(activity_info.get("elapsedTime", moving_time_s)),
                    "total_elevation_gain": elevation_gain_m,
                    "type": act_type,
                    "sport_type": sport_type,
                    "start_date_local": start_date_local
                })
            except Exception as entry_err:
                print(f"Sync Engine (Scraper): Error parsing React entry: {entry_err}")
                
    else:
        # THẾ HỆ 2: Thử parse qua Next.js JSON (__NEXT_DATA__) (Khi chưa đăng nhập - Logged Out)
        next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">({.*?})</script>', html_content)
        if next_data_match:
            try:
                data = json.loads(next_data_match.group(1))
                props = data.get("props", {})
                page_props = props.get("pageProps", {})
                pre_fetched = page_props.get("preFetchedEntries") or []
                
                if not pre_fetched:
                    def find_entries(obj):
                        if isinstance(obj, list):
                            if obj and isinstance(obj[0], dict) and ("athlete" in obj[0] or "activity" in obj[0] or "activityName" in obj[0]):
                                return obj
                            for item in obj:
                                res = find_entries(item)
                                if res:
                                    return res
                        elif isinstance(obj, dict):
                            for k, v in obj.items():
                                res = find_entries(v)
                                if res:
                                    return res
                        return None
                    pre_fetched = find_entries(page_props) or []
                    
                print(f"Sync Engine (Scraper): Found {len(pre_fetched)} entries in Next.js props.")
                
                for entry in pre_fetched:
                    athlete_info = entry.get("athlete", {})
                    athlete_id_val = athlete_info.get("id") or athlete_info.get("athleteId")
                    firstname = athlete_info.get("firstName") or athlete_info.get("firstname") or ""
                    lastname = athlete_info.get("lastName") or athlete_info.get("lastname") or ""
                    if not firstname and not lastname:
                        fullname = athlete_info.get("name") or entry.get("athleteName") or ""
                        parts = fullname.strip().split()
                        if len(parts) > 1:
                            firstname = parts[0]
                            lastname = " ".join(parts[1:])
                        elif parts:
                            firstname = parts[0]
                            lastname = ""
                    
                    activity_info = entry.get("activity") or entry
                    act_name = activity_info.get("name") or entry.get("activityName") or "Hoạt động Strava"
                    act_type = activity_info.get("type") or activity_info.get("sportType") or entry.get("type") or "Run"
                    sport_type = activity_info.get("sportType") or activity_info.get("sport_type") or act_type
                    
                    # Parse distance
                    dist_val = activity_info.get("distance")
                    distance_m = 0.0
                    if dist_val is not None:
                        try:
                            if isinstance(dist_val, (int, float)):
                                if dist_val > 100:
                                    distance_m = float(dist_val)
                                else:
                                    distance_m = float(dist_val) * 1000.0
                            else:
                                dist_str = str(dist_val).strip().lower()
                                num_match = re.search(r'([\d\.,]+)', dist_str)
                                if num_match:
                                    num_val = float(num_match.group(1).replace(",", "."))
                                    if "km" in dist_str:
                                        distance_m = num_val * 1000.0
                                    else:
                                        distance_m = num_val
                        except Exception:
                            pass
                    
                    # Parse moving time
                    mov_val = activity_info.get("movingTime") or activity_info.get("moving_time")
                    moving_time_s = 0.0
                    if mov_val is not None:
                        try:
                            if isinstance(mov_val, (int, float)):
                                moving_time_s = float(mov_val)
                            else:
                                moving_time_s = parse_time_str_to_seconds(str(mov_val))
                        except Exception:
                            pass
                    
                    # Parse elapsed time
                    ela_val = activity_info.get("elapsedTime") or activity_info.get("elapsed_time")
                    elapsed_time_s = moving_time_s
                    if ela_val is not None:
                        try:
                            if isinstance(ela_val, (int, float)):
                                elapsed_time_s = float(ela_val)
                            else:
                                elapsed_time_s = parse_time_str_to_seconds(str(ela_val))
                        except Exception:
                            pass
                    
                    # Parse elevation
                    elev_val = activity_info.get("elevationGain") or activity_info.get("totalElevationGain") or activity_info.get("total_elevation_gain")
                    elevation_gain_m = 0.0
                    if elev_val is not None:
                        try:
                            if isinstance(elev_val, (int, float)):
                                elevation_gain_m = float(elev_val)
                            else:
                                elev_str = str(elev_val).strip().lower()
                                num_match = re.search(r'([\d\.,]+)', elev_str)
                                if num_match:
                                    elevation_gain_m = float(num_match.group(1).replace(",", "."))
                        except Exception:
                            pass
                            
                    start_date_local = activity_info.get("startDateLocal") or activity_info.get("start_date_local") or activity_info.get("startDate") or activity_info.get("start_date")
                    
                    if distance_m == 0.0 and moving_time_s == 0.0:
                        continue
                    
                    activities.append({
                        "athlete": {
                            "id": athlete_id_val,
                            "firstname": firstname,
                            "lastname": lastname
                        },
                        "name": act_name,
                        "distance": distance_m,
                        "moving_time": moving_time_s,
                        "elapsed_time": elapsed_time_s,
                        "total_elevation_gain": elevation_gain_m,
                        "type": act_type,
                        "sport_type": sport_type,
                        "start_date_local": start_date_local
                    })
            except Exception as json_err:
                print(f"Sync Engine (Scraper): Error parsing Next.js JSON: {json_err}")
            
    return activities

def refresh_user_strava_token(db, athlete, configs) -> str:
    """
    Tự động làm mới và trả về Access Token cá nhân của vận động viên.
    """
    import time
    import requests
    
    client_id = configs.get("strava_client_id")
    client_secret = configs.get("strava_client_secret")
    refresh_token = athlete.strava_refresh_token
    
    if not refresh_token:
        return None
        
    expires_at = 0
    try:
        expires_at = int(athlete.strava_expires_at or 0)
    except ValueError:
        pass
        
    if expires_at > int(time.time()) + 60:
        return athlete.strava_access_token
        
    print(f"Sync Engine: User token expired for {athlete.full_name}. Refreshing...")
    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        
        athlete.strava_access_token = token_data["access_token"]
        athlete.strava_refresh_token = token_data["refresh_token"]
        athlete.strava_expires_at = str(token_data["expires_at"])
        db.commit()
        
        print(f"Sync Engine: User token refreshed successfully for {athlete.full_name}.")
        return token_data["access_token"]
    except Exception as e:
        print(f"Sync Engine: Error refreshing user token for {athlete.full_name}: {e}")
        # Tự động hủy liên kết nếu refresh token bị vô hiệu hóa (400, 401 hoặc 403)
        if any(err_code in str(e) for err_code in ["400", "401", "403"]):
            print(f"Sync Engine: Refresh token invalid for {athlete.full_name}. Unlinking automatically...")
            try:
                athlete.strava_access_token = None
                athlete.strava_refresh_token = None
                athlete.strava_expires_at = None
                db.commit()
            except Exception as db_err:
                print(f"Sync Engine: Error clearing credentials: {db_err}")
        return None

def sync_athlete_activities_api(db, athlete, access_token, start_date_str: str = None) -> list:
    """
    Gọi API Strava cá nhân lấy các hoạt động mới nhất của VĐV.
    """
    import requests
    
    print(f"Sync Engine (User API): Fetching activities for {athlete.full_name} via personal API...")
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # Tìm ngày bắt đầu để lấy lịch sử hoạt động phù hợp
    after_timestamp = int(time.time()) - 30 * 24 * 60 * 60 # Mặc định 30 ngày trước
    target_start_date = start_date_str
    
    if not target_start_date:
        try:
            active_event = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.start_date).first()
            if active_event:
                target_start_date = active_event.start_date
        except Exception as te:
            print(f"Sync Engine (User API): Error finding earliest active event: {te}")
            
    if target_start_date:
        try:
            # Ví dụ: start_date = "2026-06-16"
            # Cần lấy đúng 00:00:00 ngày start_date theo giờ Việt Nam (GMT+7)
            from datetime import timezone
            dt = datetime.strptime(target_start_date, "%Y-%m-%d")
            tz_vn = timezone(timedelta(hours=7))
            dt_vn = dt.replace(tzinfo=tz_vn)
            after_timestamp = int(dt_vn.timestamp())
            
            # Giới hạn cứng không lấy dữ liệu trước ngày 16/06/2026 cho cả 2 giải
            min_timestamp = 1781542800  # Epoch tương ứng 2026-06-16 00:00:00 GMT+7
            if after_timestamp < min_timestamp:
                after_timestamp = min_timestamp
        except Exception as te:
            print(f"Sync Engine (User API): Error calculating after_timestamp: {te}")

    raw_acts = []
    page = 1
    max_pages = 10
    while page <= max_pages:
        params = {
            "after": after_timestamp,
            "page": page,
            "per_page": 200
        }
        try:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            
            # Kiểm tra quyền hạn từ header trả về của Strava (X-OAuth-Scopes)
            scopes_header = response.headers.get("X-OAuth-Scopes", "")
            if scopes_header:
                granted_scopes = [s.strip().lower() for s in scopes_header.split(",")]
                if "activity:read" not in granted_scopes and "activity:read_all" not in granted_scopes:
                    print(f"Sync Engine: Athlete {athlete.full_name} lacks activity read permission (scopes: {scopes_header}). Unlinking automatically...")
                    try:
                        athlete.strava_access_token = None
                        athlete.strava_refresh_token = None
                        athlete.strava_expires_at = None
                        db.commit()
                    except Exception as db_err:
                        print(f"Sync Engine: Error clearing credentials on scope error: {db_err}")
                    return None
            
            page_acts = response.json()
            if not page_acts:
                break
            raw_acts.extend(page_acts)
            if len(page_acts) < 200:
                break
            page += 1
        except Exception as e:
            print(f"Sync Engine (User API): Error fetching page {page} for {athlete.full_name}: {e}")
            # Tự động hủy liên kết nếu gặp lỗi xác thực 401 hoặc 403 từ Strava
            if any(err_code in str(e) for err_code in ["401", "403"]):
                print(f"Sync Engine: Auth error for {athlete.full_name} during activities fetch. Unlinking automatically...")
                try:
                    athlete.strava_access_token = None
                    athlete.strava_refresh_token = None
                    athlete.strava_expires_at = None
                    db.commit()
                except Exception as db_err:
                    print(f"Sync Engine: Error clearing credentials: {db_err}")
            break
            
    try:
        formatted_acts = []
        for ra in raw_acts:
            dist_m = float(ra.get("distance", 0.0))
            mov_s = float(ra.get("moving_time", 0.0))
            if dist_m == 0.0 and mov_s == 0.0:
                continue
                
            formatted_acts.append({
                "athlete": {
                    "id": athlete.strava_athlete_id,
                    "firstname": athlete.strava_name.split(",")[0].strip() if athlete.strava_name else athlete.full_name,
                    "lastname": ""
                },
                "id": str(ra.get("id")) if ra.get("id") else None,
                "name": ra.get("name", "Hoạt động Strava"),
                "distance": dist_m,
                "moving_time": mov_s,
                "elapsed_time": float(ra.get("elapsed_time", 0.0)),
                "total_elevation_gain": float(ra.get("total_elevation_gain", 0.0)),
                "type": ra.get("type", "Run"),
                "sport_type": ra.get("sport_type") or ra.get("type") or "Run",
                "start_date_local": ra.get("start_date_local")
            })
            
        print(f"Sync Engine (User API): Found {len(formatted_acts)} valid activities for {athlete.full_name}.")
        return formatted_acts
    except Exception as e:
        print(f"Sync Engine (User API): Error fetching activities for {athlete.full_name}: {e}")
        return []

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

    # 1. Đồng bộ các VĐV đã ủy quyền cá nhân qua API cá nhân của họ
    user_api_activities = []
    
    # Lấy danh sách các VĐV đăng ký tham gia giải đấu này
    registered_athletes = db.query(Athlete).join(
        CompetitionRegistration,
        Athlete.id == CompetitionRegistration.athlete_id
    ).filter(
        CompetitionRegistration.event_id == event_id,
        Athlete.is_active == True
    ).all()
    
    authorized_athletes = [a for a in registered_athletes if a.strava_refresh_token]
    if authorized_athletes:
        print(f"Sync Engine: Found {len(authorized_athletes)} authorized athletes. Syncing via personal APIs...")
        for ath in authorized_athletes:
            # Nghỉ 1.5 giây giữa mỗi VĐV để tránh spam request làm khóa API/IP
            time.sleep(1.5)
            u_token = refresh_user_strava_token(db, ath, configs)
            if u_token:
                start_date = event.start_date if event.start_date else "2026-06-16"
                if start_date < "2026-06-16":
                    start_date = "2026-06-16"
                ath_acts = sync_athlete_activities_api(db, ath, u_token, start_date)
                if ath_acts is not None:
                    # Gán cờ để nhận biết đây là hoạt động API cá nhân
                    for a_act in ath_acts:
                        a_act["is_personal_api"] = True
                    user_api_activities.extend(ath_acts)
                    
                    # Tìm và dọn dẹp các hoạt động cào web cũ (ID dài đúng 64 ký tự) của VĐV này
                    # CHỈ xóa nếu API trả về ít nhất 1 hoạt động (tránh mất dữ liệu khi API lỗi)
                    if len(ath_acts) > 0:
                        try:
                            from sqlalchemy import func as sa_func
                            import json
                            import os
                            
                            club_acts = db.query(Activity).filter(
                                Activity.athlete_id == ath.id,
                                Activity.event_id == event_id,
                                Activity.activity_date >= start_date,
                                sa_func.length(Activity.id) == 64
                            ).all()
                            
                            if club_acts:
                                backup_file = "static/uploads/deleted_activities_backup.jsonl"
                                os.makedirs("static/uploads", exist_ok=True)
                                with open(backup_file, "a", encoding="utf-8") as f:
                                    for act in club_acts:
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
                                            "backup_time": datetime.utcnow().isoformat(),
                                            "reason": f"Nang cap len API ca nhan cho {ath.full_name}"
                                        }
                                        f.write(json.dumps(act_dict, ensure_ascii=False) + "\n")
                                        
                                # Xóa khỏi DB để chuẩn bị ghi đè dữ liệu API mới
                                db.query(Activity).filter(
                                    Activity.athlete_id == ath.id,
                                    Activity.event_id == event_id,
                                    Activity.activity_date >= start_date,
                                    sa_func.length(Activity.id) == 64
                                ).delete(synchronize_session=False)
                                db.commit()
                                print(f"Sync Engine: Backed up and cleared {len(club_acts)} old Club-sourced activities for authorized athlete {ath.full_name} since {start_date}.")
                        except Exception as clean_err:
                            print(f"Sync Engine: Error clearing old Club activities for {ath.full_name}: {clean_err}")
                    else:
                        print(f"Sync Engine: API returned 0 activities for {ath.full_name}. Keeping existing Club data to prevent data loss.")
            else:
                print(f"Sync Engine: Cannot refresh token for {ath.full_name}, skipping personal API sync.")
                
    # 2. Đồng bộ các hoạt động chung qua Club (API Club hoặc Scraper)
    club_activities = []
    sync_method = configs.get("sync_method", "api")
    strava_cookie = configs.get("strava_cookie", "")
    
    use_scraper = (sync_method == "scraper") or (not access_token and strava_cookie)
    
    if use_scraper:
        print(f"Sync Engine: Using Scraper to sync Event '{event.title}' (Club {club_id})...")
        try:
            club_activities = scrape_club_activities_web(club_id, strava_cookie)
        except Exception as e:
            if user_api_activities:
                print(f"Sync Engine: Scraper failed ({e}) but personal API sync succeeded. Continuing with personal activities...")
            else:
                result["status"] = "error"
                result["error"] = f"Loi cao du lieu web: {str(e)}"
                return result
    else:
        # Gọi API Strava Club Activities
        print(f"Sync Engine: Starting API sync for Event '{event.title}' (Club {club_id})...")
        url = f"https://www.strava.com/api/v3/clubs/{club_id}/activities"
        headers = {"Authorization": f"Bearer {access_token}"}
        page = 1
        per_page = 200
        try:
            while True:
                response = requests.get(url, headers=headers, params={"page": page, "per_page": per_page}, timeout=10)
                if response.status_code == 403 and strava_cookie:
                    print(f"Sync Engine: API returned 403 Forbidden. Automatically falling back to Scraper Engine...")
                    club_activities = scrape_club_activities_web(club_id, strava_cookie)
                    break
                response.raise_for_status()
                chunk = response.json()
                if not chunk:
                    break
                club_activities.extend(chunk)
                if len(chunk) < per_page:
                    break
                page += 1
        except Exception as api_err:
            is_403 = False
            if hasattr(api_err, "response") and api_err.response is not None:
                is_403 = (api_err.response.status_code == 403)
            elif "403" in str(api_err):
                is_403 = True
                
            if is_403 and strava_cookie:
                print(f"Sync Engine: API failed with 403. Fallback to Scraper Engine: {api_err}")
                try:
                    club_activities = scrape_club_activities_web(club_id, strava_cookie)
                except Exception as scrap_ex:
                    if user_api_activities:
                        print(f"Sync Engine: Fallback scraper failed ({scrap_ex}) but personal API sync succeeded. Continuing...")
                    else:
                        result["status"] = "error"
                        result["error"] = f"API bi chan (403) va cao du phong that bai: {str(scrap_ex)}"
                        return result
            else:
                if user_api_activities:
                    print(f"Sync Engine: API failed ({api_err}) but personal API sync succeeded. Continuing...")
                else:
                    result["status"] = "error"
                    result["error"] = f"Loi goi API Strava: {str(api_err)}"
                    return result

    # Gộp tất cả hoạt động từ 2 luồng
    all_activities = user_api_activities + club_activities
    print(f"Sync Engine: Total downloaded activities to process: {len(all_activities)} (Personal API: {len(user_api_activities)}, Club/Scraper: {len(club_activities)}) for event '{event.title}'.")
    
    new_count = 0
    gmt7_now = datetime.utcnow() + timedelta(hours=7)
    today_str = gmt7_now.strftime("%Y-%m-%d")
    seen_ids = set()

    # Cache danh sách vận động viên để đối khớp tốc độ cao (hỗ trợ nhiều tên cách nhau bằng dấu phẩy)
    athletes = db.query(Athlete).all()
    athlete_map = {}
    id_map = {}
    for a in athletes:
        if a.strava_athlete_id:
            id_map[str(a.strava_athlete_id).strip()] = a
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
        athlete = None
        strava_athlete_id_raw = str(athlete_data.get("id") or "").strip()
        if strava_athlete_id_raw and strava_athlete_id_raw != "None" and strava_athlete_id_raw != "":
            athlete = id_map.get(strava_athlete_id_raw)
            
        if not athlete:
            athlete = athlete_map.get(athlete_name_raw.lower())
            if athlete and strava_athlete_id_raw and strava_athlete_id_raw != "None" and strava_athlete_id_raw != "":
                # Cập nhật ID VĐV vào DB
                athlete.strava_athlete_id = strava_athlete_id_raw
                db.commit()
                # Cập nhật id_map trong bộ nhớ để các hoạt động tiếp theo của VĐV này được map nhanh
                id_map[strava_athlete_id_raw] = athlete
                print(f"Sync Engine: Automatically updated strava_athlete_id = {strava_athlete_id_raw} for athlete {athlete.full_name}")
                
        athlete_id = athlete.id if athlete else None

        # Nếu hoạt động này đến từ Club/Scraper (không có cờ is_personal_api)
        # nhưng VĐV đã ủy quyền API cá nhân, ta bỏ qua không xử lý hoạt động Club này.
        is_from_club = not act.get("is_personal_api")
        if is_from_club and athlete and athlete.strava_refresh_token:
            continue
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

        # Rất quan trọng: Chỉ lưu các hoạt động diễn ra trong khoảng thời gian diễn ra giải đấu (từ start_date đến end_date)
        if event.start_date and act_date_str < event.start_date:
            print(f"Sync Engine: Skip '{name}' of {athlete_name_raw} - activity date {act_date_str} is before event start date {event.start_date}")
            continue
        if event.end_date and act_date_str > event.end_date:
            print(f"Sync Engine: Skip '{name}' of {athlete_name_raw} - activity date {act_date_str} is after event end date {event.end_date}")
            continue

        # Sử dụng ID số chuẩn kết hợp event_id từ Personal API nếu có, ngược lại tạo mã băm cho Club Scraper
        original_id = act.get("id")
        if original_id:
            act_id = f"{original_id}_{event_id}"
        else:
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
        sync_method = configs.get("sync_method", "api")
        strava_cookie = configs.get("strava_cookie", "")
        
        access_token = None
        if sync_method == "api":
            access_token = refresh_strava_token(db, configs)
            if not access_token and not strava_cookie:
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

def sync_single_athlete_all_events(db: Session, athlete):
    """
    Đồng bộ ngay lập tức toàn bộ hoạt động của 1 VĐV vừa mới ủy quyền.
    An toàn: Chỉ dọn dẹp hoạt động cào web cũ SAU KHI đã xác nhận có dữ liệu API mới thay thế.
    """
    from backend.database import CompetitionEvent, CompetitionRegistration, Activity
    from sqlalchemy import func as sa_func
    import json
    import os
    
    # 1. Tìm tất cả các giải đấu mà VĐV này đã đăng ký
    registered_events = db.query(CompetitionEvent).join(
        CompetitionRegistration,
        CompetitionEvent.id == CompetitionRegistration.event_id
    ).filter(
        CompetitionRegistration.athlete_id == athlete.id
    ).all()
    
    if not registered_events:
        print(f"Sync Single Athlete: {athlete.full_name} is not registered in any events.")
        return
        
    configs = get_config_dict(db)
    
    # Backup CSDL truoc khi thuc hien de phong sai sot
    backup_db_file(reason=f"oauth_link_{athlete.id}")
    
    # 2. Làm mới access token của VĐV
    u_token = refresh_user_strava_token(db, athlete, configs)
    if not u_token:
        print(f"Sync Single Athlete: Cannot refresh token for {athlete.full_name}")
        return
        
    for event in registered_events:
        event_id = event.id
        start_date = event.start_date if event.start_date else "2026-06-16"
        if start_date < "2026-06-16":
            start_date = "2026-06-16"
        
        # Gọi API lấy các hoạt động kể cả ngày bắt đầu giải (bị cap mốc tối thiểu 16/06/2026)
        ath_acts = sync_athlete_activities_api(db, athlete, u_token, start_date)
        if ath_acts is None:
            print(f"Sync Single Athlete: API returned None for {athlete.full_name} in event '{event.title}'. Keeping existing data.")
            continue
            
        print(f"Sync Single Athlete: Found {len(ath_acts)} activities for {athlete.full_name} in event '{event.title}'.")
        
        # === BƯỚC 1: NẠP DỮ LIỆU MỚI TRƯỚC (không xóa dữ liệu cũ) ===
        new_count = 0
        
        for act in ath_acts:
            # Lấy thông số
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
                
            start_date_local = act.get("start_date_local")
            act_time_str = None
            if start_date_local:
                act_date_str = start_date_local[:10]
                if len(start_date_local) >= 16:
                    act_time_str = start_date_local[11:16]
            else:
                act_date_str = start_date
                
            # Rất quan trọng: Chỉ lưu các hoạt động diễn ra trong khoảng thời gian diễn ra giải đấu (từ start_date đến end_date)
            if event.start_date and act_date_str < event.start_date:
                continue
            if event.end_date and act_date_str > event.end_date:
                continue
                
            original_id = act.get("id")
            act_id = f"{original_id}_{event_id}" if original_id else f"{athlete.full_name}_{act_date_str}"
            
            # Kiểm tra xem hoạt động đã có chưa
            exists = db.query(Activity).filter(Activity.id == act_id).first()
            if exists:
                continue
                
            # Tính toán METs & KCAL
            speed_kmh = (distance_km / (moving_time_min / 60.0)) if moving_time_min > 0 else 0.0
            actual_time_min = elapsed_time_min if moving_time_min < 1.0 else moving_time_min
            
            mets_value = get_mets_value(sport_type, speed_kmh, db, distance_km, elevation_gain_m, event_id=event_id)
            mult = get_multiplier_for_date(act_date_str, event_id, db)
            kcal_burned = calculate_kcal(mets_value, athlete.weight, actual_time_min, elevation_gain_m, sport_type, multiplier=mult)
            
            is_suspicious, suspicion_reason = check_suspicious_activity(
                sport_type=sport_type,
                distance_km=distance_km,
                pace_min_km=pace_min_km,
                elevation_gain_m=elevation_gain_m,
                configs=configs
            )
            
            activity_multiplier = get_multiplier_for_date(act_date_str, event_id, db)
            kcal_burned_raw = round(kcal_burned / activity_multiplier) if activity_multiplier > 0 else kcal_burned
            
            new_activity = Activity(
                id=act_id,
                athlete_id=athlete.id,
                event_id=event_id,
                athlete_name_raw=athlete.full_name,
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
            print(f"Sync Single Athlete: Saved {new_count} new activities for {athlete.full_name} in event '{event.title}'.")
        except Exception as e:
            db.rollback()
            print(f"Sync Single Athlete: Error saving new activities: {e}")
            continue  # Lỗi lưu → bỏ qua, KHÔNG xóa dữ liệu cũ
        
        # === BƯỚC 2: CHỈ DỌN DẸP SAU KHI ĐÃ CÓ DỮ LIỆU THAY THẾ ===
        # Chỉ xóa hoạt động cào Club cũ nếu API trả về ít nhất 1 hoạt động mới HOẶC đã có dữ liệu API trước đó
        if len(ath_acts) > 0:
            try:
                club_acts = db.query(Activity).filter(
                    Activity.athlete_id == athlete.id,
                    Activity.event_id == event_id,
                    Activity.activity_date >= start_date,
                    sa_func.length(Activity.id) == 64
                ).all()
                
                if club_acts:
                    backup_file = "static/uploads/deleted_activities_backup.jsonl"
                    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
                    with open(backup_file, "a", encoding="utf-8") as f:
                        for act in club_acts:
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
                                "backup_time": datetime.utcnow().isoformat(),
                                "reason": f"Nang cap tuc thi khi vua uy quyen cho {athlete.full_name}"
                            }
                            f.write(json.dumps(act_dict, ensure_ascii=False) + "\n")
                    
                    db.query(Activity).filter(
                        Activity.athlete_id == athlete.id,
                        Activity.event_id == event_id,
                        Activity.activity_date >= start_date,
                        sa_func.length(Activity.id) == 64
                    ).delete(synchronize_session=False)
                    db.commit()
                    print(f"Sync Single Athlete: Cleared {len(club_acts)} old Club acts for {athlete.full_name}.")
            except Exception as clean_err:
                print(f"Sync Single Athlete: Error clearing old Club acts: {clean_err}")
        else:
            print(f"Sync Single Athlete: API returned 0 activities for {athlete.full_name} in event '{event.title}'. Keeping existing Club data to prevent data loss.")


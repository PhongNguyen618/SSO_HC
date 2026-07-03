import os
import hashlib
import time
import json
import requests
from typing import Optional
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, Request, Form, HTTPException, status, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

# Tải các biến môi trường từ file .env
load_dotenv()

# Domain công khai của ứng dụng, dùng để build redirect_uri cho Strava OAuth
# Ví dụ: https://yourdomain.com hoặc http://localhost:8000 khi dev local
APP_URL = os.getenv("APP_URL", "").rstrip("/")

from backend.database import SessionLocal, init_db, get_db, Config, Athlete, Activity, MetsRule, RewardRule, hash_password, CompetitionEvent, CompetitionRegistration, EventMultiplier, SupportTicket
from backend.calculations import get_award_info, get_multiplier_for_date
from backend.sync_engine import sync_club_activities, get_config_dict, update_config, link_unlinked_activities, import_excel_files
from backend.auth import get_admin_session, COOKIE_NAME, verify_password

app = FastAPI(title="Strava SSO HC Web App")

def extract_strava_club_id(input_str: str) -> str:
    """Tự động trích xuất ID nhóm Strava từ đường link URL hoặc chuỗi nhập vào."""
    if not input_str:
        return ""
    input_str = input_str.strip()
    import re
    # Hỗ trợ link định dạng: https://www.strava.com/clubs/1534169 hoặc strava.com/clubs/1534169/...
    match = re.search(r'clubs/(\d+)', input_str)
    if match:
        return match.group(1)
    # Hỗ trợ link định dạng query param: club_id=1534169
    match2 = re.search(r'club.*?=(\d+)', input_str)
    if match2:
        return match2.group(1)
    # Nếu chỉ có chữ số thì trả về luôn
    if input_str.isdigit():
        return input_str
    return input_str

def clean_name(name: str) -> str:
    """Chuẩn hóa họ tên: viết thường, bỏ khoảng trắng và bỏ dấu tiếng Việt để so sánh trùng."""
    if not name:
        return ""
    import unicodedata
    name = name.strip().lower()
    name = "".join(name.split())
    # Loại bỏ dấu tiếng Việt
    name = unicodedata.normalize('NFKD', name)
    name = "".join([c for c in name if not unicodedata.combining(c)])
    # Thay thế chữ đ/Đ
    name = name.replace("đ", "d")
    return name

def duc_lo_frame_neu_duc(frame_image, scale=0.72, offset_x=0.0, offset_y=0.0):
    """
    Tự động đục lỗ tròn ở vị trí tùy chỉnh (offset X, Y theo phần trăm) nếu ảnh khung viền là ảnh đặc.
    Nếu ảnh đã được đục lỗ sẵn (điểm ở tâm đã trong suốt), giữ nguyên để tránh làm hỏng thiết kế.
    """
    try:
        from PIL import Image, ImageDraw
        img = frame_image.convert("RGBA")
        width, height = img.size
        
        # Tính toán tọa độ tâm dựa trên offset (offset_x, offset_y ở dạng số thực từ -0.5 đến 0.5)
        center_x = int(width * (0.5 + offset_x))
        center_y = int(height * (0.5 + offset_y))
        
        # Kiểm tra pixel ở tâm đục lỗ mới (đảm bảo nằm trong giới hạn ảnh)
        check_x = max(0, min(width - 1, center_x))
        check_y = max(0, min(height - 1, center_y))
        center_pixel = img.getpixel((check_x, check_y))
        
        # Nếu alpha = 0, tức là tâm đã trong suốt (đã được đục lỗ sẵn), trả về ảnh gốc
        if center_pixel[3] == 0:
            return frame_image
            
        # Ngược lại, tiến hành đục lỗ hình tròn
        empty = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        mask = Image.new("L", (width, height), 0)
        draw = ImageDraw.Draw(mask)
        
        r = int((min(width, height) * scale) / 2)
        draw.ellipse((center_x - r, center_y - r, center_x + r, center_y + r), fill=255)
        
        img.paste(empty, (0, 0), mask=mask)
        return img
    except Exception as e:
        print(f"Error in duc_lo_frame_neu_duc: {e}")
        return frame_image

def tao_frame_mau_neu_thieu(path_frame, size=1000):
    """
    Tu dong tao mot khung hinh dac mau dep mat (frame.png) neu chua co san.
    """
    from PIL import Image, ImageDraw
    if os.path.exists(path_frame):
        return
    
    print("Khong tim thay file frame.png, dang tu dong tao mot khung vien mau dac ky niem...")
    # Tao anh dac mau toi trung voi giao dien Studio
    frame = Image.new("RGB", (size, size), (24, 20, 42))
    draw = ImageDraw.Draw(frame)
    
    # Vien day hon de trung khop voi ty le lo duc mac dinh 65% (moi ben 17.5% vien)
    vien_day = int(size * 0.175)
    draw.ellipse((vien_day, vien_day, size - vien_day, size - vien_day), outline=(65, 105, 225), width=vien_day)
    draw.ellipse((vien_day + 15, vien_day + 15, size - vien_day - 15, size - vien_day - 15), 
                 outline=(255, 215, 0, 200), width=4)
    
    draw.arc((10, 10, size // 4, size // 4), start=180, end=270, fill=(255, 215, 0, 255), width=8)
    draw.arc((size - size // 4, size - size // 4, size - 10, size - 10), start=0, end=90, fill=(255, 215, 0, 255), width=8)
    
    draw.polygon([
        (size // 4, size - vien_day),
        (3 * size // 4, size - vien_day),
        (size - vien_day, size - size // 4),
        (vien_day, size - size // 4)
    ], fill=(220, 20, 60, 240)) # Crimson
    
    frame.save(path_frame, "PNG")
    print(f"Da tao thanh cong khung vien mau tai: {path_frame}")

# Đảm bảo các thư mục templates và static tồn tại
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/branding", StaticFiles(directory="branding"), name="branding")
APP_VERSION = "v1.4.0"
# Lấy thời gian deploy tự động từ ngày sửa đổi file main.py
try:
    main_path = os.path.abspath(__file__)
    mtime = os.path.getmtime(main_path)
    deploy_dt = datetime.fromtimestamp(mtime)
    DEPLOY_TIME = deploy_dt.strftime("%d/%m/%Y %H:%M:%S")
except Exception:
    DEPLOY_TIME = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

templates = Jinja2Templates(directory="templates")
templates.env.globals["APP_VERSION"] = APP_VERSION
templates.env.globals["DEPLOY_TIME"] = DEPLOY_TIME

scheduler = BackgroundScheduler()

def deduplicate_activities_logic(db: Session, mode: str = "all", dry_run: bool = False) -> dict:
    """Core logic dọn dẹp dữ liệu trùng lặp trong DB, hỗ trợ sai số (dung sai) nhỏ và lệch ngày."""
    try:
        activities = db.query(Activity).all()
        
        from collections import defaultdict
        from datetime import datetime
        import hashlib
        
        # Nhóm các hoạt động theo VĐV
        by_athlete = defaultdict(list)
        for act in activities:
            ath_key = act.athlete_id if act.athlete_id is not None else act.athlete_name_raw
            by_athlete[ath_key].append(act)
            
        to_delete = []
        updated_count = 0
        deleted_details = []
        
        for ath_key, act_list in by_athlete.items():
            if len(act_list) < 2:
                continue
                
            # Sắp xếp các hoạt động để giữ lại bản ghi có thông tin tốt nhất
            def sort_key(x):
                has_athlete = 1 if x.athlete_id is not None else 0
                is_generic_name = 1 if x.name in ["Activity", "Hoạt động Strava"] else 0
                date_val = x.activity_date or "9999-12-31"
                return (-has_athlete, is_generic_name, date_val, x.id)
                
            act_list.sort(key=sort_key)
            
            # Đánh dấu các phần tử đã bị gộp để không so sánh trùng lặp nữa
            merged_indices = set()
            
            for i in range(len(act_list)):
                if i in merged_indices:
                    continue
                    
                act1 = act_list[i]
                act1_idx = i
                
                # So sánh chéo với các hoạt động phía sau
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
                        
                    # 3. Chênh lệch ngày không quá 4 ngày (để xử lý lệch múi giờ sâu hoặc đồng bộ trễ lịch sử)
                    date_diff_days = 999
                    if act1.activity_date and act2.activity_date:
                        try:
                            d1 = datetime.strptime(act1.activity_date, "%Y-%m-%d")
                            d2 = datetime.strptime(act2.activity_date, "%Y-%m-%d")
                            date_diff_days = abs((d1 - d2).days)
                        except Exception:
                            pass
                            
                    if date_diff_days > 4:
                        continue
                        
                    # Check overlap thời gian (bổ sung cho trường hợp ghi song song nhiều thiết bị)
                    time_overlap_dup = False
                    h_diff_val = 0
                    if act1.activity_date == act2.activity_date and act1.activity_time and act2.activity_time:
                        try:
                            parts1 = act1.activity_time.split(":")
                            parts2 = act2.activity_time.split(":")
                            h1, m1 = int(parts1[0]), int(parts1[1])
                            h2, m2 = int(parts2[0]), int(parts2[1])
                            start1 = h1 * 60 + m1
                            start2 = h2 * 60 + m2
                            
                            dur1 = act1.elapsed_time_min if act1.elapsed_time_min is not None else act1.moving_time_min
                            dur2 = act2.elapsed_time_min if act2.elapsed_time_min is not None else act2.moving_time_min
                            
                            dur1 = dur1 or 0.0
                            dur2 = dur2 or 0.0
                            
                            end1 = start1 + dur1
                            end2 = start2 + dur2
                            
                            overlap_mins = max(0.0, min(end1, end2) - max(start1, start2))
                            min_dur = min(dur1, dur2)
                            
                            diff_mins = abs(start1 - start2)
                            if min_dur > 0:
                                overlap_ratio = overlap_mins / min_dur
                                if overlap_ratio > 0.5 and diff_mins <= 15:
                                    time_overlap_dup = True
                                    
                            # Nếu chưa trùng overlap, kiểm tra trùng lệch múi giờ chẵn tiếng (h_diff từ 1 đến 14 tiếng)
                            if not time_overlap_dup:
                                h_diff = round(diff_mins / 60.0)
                                if 1 <= h_diff <= 14 and abs(diff_mins - h_diff * 60) <= 15:
                                    time_overlap_dup = True
                                    h_diff_val = h_diff
                        except Exception:
                            pass

                    # 5. Kiểm tra độ lệch cự ly (distance_km_raw)
                    dist1 = act1.distance_km_raw if act1.distance_km_raw is not None else act1.distance_km
                    dist2 = act2.distance_km_raw if act2.distance_km_raw is not None else act2.distance_km
                    dist_diff = abs((dist1 or 0.0) - (dist2 or 0.0))
                    
                    # 6. Kiểm tra độ lệch thời gian di chuyển (moving_time_min)
                    time_diff = abs((act1.moving_time_min or 0.0) - (act2.moving_time_min or 0.0))
                    
                    # 7. Kiểm tra độ lệch độ cao tăng thêm (elevation_gain_m)
                    elev_diff = abs((act1.elevation_gain_m or 0.0) - (act2.elevation_gain_m or 0.0))

                    # 4. Quy tắc về tên hoạt động: để tránh xóa nhầm hai hoạt động thực tế khác nhau tự đặt tên riêng
                    name1_clean = (act1.name or "").strip().lower()
                    name2_clean = (act2.name or "").strip().lower()
                    
                    generic_keywords = [
                        "activity", "hoạt động strava", "hoạt động", "workout", "run", "walk", "ride",
                        "morning run", "afternoon run", "evening run", "night run",
                        "morning walk", "afternoon walk", "evening walk", "night walk",
                        "morning ride", "afternoon ride", "evening ride", "night ride",
                        "lunch run", "lunch walk", "lunch ride"
                    ]
                    is_generic1 = name1_clean in generic_keywords or name1_clean == ""
                    is_generic2 = name2_clean in generic_keywords or name2_clean == ""
                    
                    # Nếu không phải trùng overlap thời gian và không quá giống nhau tuyệt đối (chặt chẽ) thì mới kiểm tra tên hoạt động nghiêm ngặt
                    is_similar_tight = dist_diff <= 0.05 and time_diff <= 1.0 and elev_diff <= 10.0
                    if name1_clean != name2_clean and (not is_generic1 or not is_generic2) and not time_overlap_dup and not is_similar_tight:
                        continue
                        
                    # Ngưỡng gộp an toàn:
                    # - Mặc định cự ly lệch <= 0.05 km, thời gian lệch <= 1.0 phút, độ cao lệch <= 10.0 m
                    # - Nếu lệch > 2 ngày: thắt chặt cự ly <= 0.02 km, thời gian <= 0.5 phút để tránh xóa nhầm hoạt động thật
                    max_dist_diff = 0.05
                    max_time_diff = 1.0
                    max_elev_diff = 10.0
                    if date_diff_days > 2:
                        max_dist_diff = 0.02
                        max_time_diff = 0.5
                        max_elev_diff = 5.0
                        
                    # Nếu phát hiện trùng lặp thời gian (overlap), ta nới lỏng dung sai thành tỷ lệ tương đối:
                    # - Cự ly lệch không quá 8% cự ly hoạt động (tối thiểu 0.05 km)
                    # - Thời gian lệch không quá 5% thời lượng hoạt động (tối thiểu 1.0 phút)
                    # - Độ cao lệch không quá 15m
                    if time_overlap_dup:
                        min_dist = min(dist1 or 0.0, dist2 or 0.0)
                        min_time = min(act1.moving_time_min or 0.0, act2.moving_time_min or 0.0)
                        max_dist_diff = max(0.05, 0.08 * min_dist)
                        max_time_diff = max(1.0, 0.05 * min_time)
                        max_elev_diff = max(10.0, 15.0)
                        
                    is_similar_static = dist_diff <= max_dist_diff and time_diff <= max_time_diff and elev_diff <= max_elev_diff
                    
                    # Xác định xem hoạt động này có nên được gộp ở chế độ hiện tại không
                    should_merge = False
                    reason = ""
                    if is_similar_tight:
                        if mode in ["all", "standard"]:
                            should_merge = True
                            reason = "Trùng thông số tuyệt đối (cự ly <= 50m, thời gian <= 1m)"
                    elif time_overlap_dup and is_similar_static:
                        if mode in ["all", "two_devices"]:
                            should_merge = True
                            if h_diff_val > 0:
                                reason = f"Trùng 2 thiết bị lệch múi giờ (lệch ~{h_diff_val}h, cự ly lệch <= 8%)"
                            else:
                                reason = "Trùng lặp 2 thiết bị (chồng chéo thời gian > 50%, lệch cự ly <= 8%)"

                    # Chế độ dọn trùng Chủ nhật: cùng thông số chặt, KHÁC ngày, 1 bản là CN
                    if not should_merge and mode in ["all", "sunday_dup"] and is_similar_tight and date_diff_days >= 1:
                        day1 = d1.weekday() if 'd1' in dir() else -1
                        day2 = d2.weekday() if 'd2' in dir() else -1
                        # Chỉ xét khi 1 trong 2 bản là CN (weekday=6) và bản kia không phải CN
                        if (day1 == 6) != (day2 == 6):
                            should_merge = True
                            sun_date = act1.activity_date if day1 == 6 else act2.activity_date
                            real_date = act2.activity_date if day1 == 6 else act1.activity_date
                            reason = f"Trùng lặp CN (grace period gán nhầm {real_date} → {sun_date})"
                            
                    if should_merge:
                        # Quyết định giữ lại bản ghi tối ưu hơn
                        mult1 = act1.multiplier or 1.0
                        mult2 = act2.multiplier or 1.0
                        
                        act_to_delete = None
                        act_to_keep = None
                        
                        if mult1 > mult2:
                            act_to_delete = act2
                            act_to_keep = act1
                            to_delete.append(act2.id)
                            merged_indices.add(j)
                        elif mult2 > mult1:
                            act_to_delete = act1
                            act_to_keep = act2
                            to_delete.append(act1.id)
                            merged_indices.add(act1_idx)
                            act1 = act2
                            act1_idx = j
                        else: # mult1 == mult2 (Bằng hệ số nhân, giữ lại bản ghi có cự ly dài hơn)
                            dist_1_val = act1.distance_km_raw if act1.distance_km_raw is not None else act1.distance_km
                            dist_2_val = act2.distance_km_raw if act2.distance_km_raw is not None else act2.distance_km
                            if (dist_1_val or 0.0) >= (dist_2_val or 0.0):
                                act_to_delete = act2
                                act_to_keep = act1
                                to_delete.append(act2.id)
                                merged_indices.add(j)
                            else:
                                act_to_delete = act1
                                act_to_keep = act2
                                to_delete.append(act1.id)
                                merged_indices.add(act1_idx)
                                act1 = act2
                                act1_idx = j
                                
                        if act_to_delete and act_to_keep:
                            ath_name = db.query(Athlete.full_name).filter(Athlete.id == act1.athlete_id).scalar() or act1.athlete_name_raw or "VĐV ẩn danh"
                            deleted_details.append({
                                "athlete_name": ath_name,
                                "deleted": {
                                    "id": act_to_delete.id,
                                    "name": act_to_delete.name or "Hoạt động Strava",
                                    "distance": act_to_delete.distance_km,
                                    "time": act_to_delete.moving_time_min,
                                    "date": act_to_delete.activity_date
                                },
                                "kept": {
                                    "id": act_to_keep.id,
                                    "name": act_to_keep.name or "Hoạt động Strava",
                                    "distance": act_to_keep.distance_km,
                                    "time": act_to_keep.moving_time_min,
                                    "date": act_to_keep.activity_date
                                },
                                "reason": reason
                            })
                            
                # Giữ nguyên ID nguyên bản của hoạt động chính (act1) để tránh việc Strava đồng bộ lại
                pass

                        
        deleted_count = 0
        if to_delete:
            if not dry_run:
                # BACKUP LOGIC: Lưu trữ bản sao của các hoạt động sắp bị xóa tự động vào file jsonl
                try:
                    import json
                    import os
                    backup_activities = db.query(Activity).filter(Activity.id.in_(to_delete)).all()
                    backup_file = "static/uploads/deleted_activities_backup.jsonl"
                    os.makedirs("static/uploads", exist_ok=True)
                    
                    with open(backup_file, "a", encoding="utf-8") as f:
                        for act in backup_activities:
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
                                "backup_time": datetime.utcnow().isoformat()
                            }
                            f.write(json.dumps(act_dict, ensure_ascii=False) + "\n")
                except Exception as backup_err:
                    print(f"Deduplicate Backup Error: {backup_err}")
                
                deleted_count = db.query(Activity).filter(Activity.id.in_(to_delete)).delete(synchronize_session=False)
                db.commit()
            else:
                deleted_count = len(to_delete)
        else:
            if not dry_run:
                db.commit()
            
        mode_vi = "tất cả"
        if mode == "standard":
            mode_vi = "cơ bản"
        elif mode == "two_devices":
            mode_vi = "2 thiết bị"
        elif mode == "sunday_dup":
            mode_vi = "trùng CN"
            
        action_word = "Phát hiện" if dry_run else "Đã dọn dẹp thành công"
        return {
            "deleted_count": deleted_count,
            "updated_count": updated_count,
            "deleted_details": deleted_details,
            "message": f"{action_word} {deleted_count} hoạt động trùng lặp ở chế độ {mode_vi}."
        }
    except Exception as e:
        db.rollback()
        raise e

def run_background_sync():
    print("Background Sync: Starting periodic sync...")
    res = sync_club_activities()
    print(f"Background Sync: Completed. Status: {res.get('status')}, New activities: {res.get('new_activities')}")
    
    # Tự động dọn dẹp hoạt động trùng lặp sau mỗi lần đồng bộ
    db = SessionLocal()
    try:
        print("Background Sync: Auto deduplicating activities...")
        dedup_res = deduplicate_activities_logic(db)
        print(f"Background Sync: Auto deduplicated. Deleted: {dedup_res['deleted_count']}, Updated: {dedup_res['updated_count']}")
    except Exception as e:
        print(f"Background Sync: Error during auto deduplication: {e}")
    finally:
        db.close()

def run_auto_db_backup():
    """Tự động sao lưu file SQLite DB định kỳ hàng ngày, giữ tối đa 5 bản gần nhất."""
    print("Auto Backup: Starting database backup...")
    db_url = os.getenv("DATABASE_URL", "sqlite:///SSO_HC.db")
    db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "SSO_HC.db"
    if not os.path.exists(db_path):
        print(f"Auto Backup: Main DB file not found at {db_path}. Skip.")
        return
        
    backup_dir = "static/uploads/backups"
    os.makedirs(backup_dir, exist_ok=True)
    
    import shutil
    time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"SSO_HC_auto_{APP_VERSION}_{time_str}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        shutil.copyfile(db_path, backup_path)
        print(f"Auto Backup: Successfully created backup at {backup_path}")
        
        # Xoay vòng (rotate): Chỉ giữ lại 5 bản backup tự động gần nhất
        backups = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("SSO_HC_auto_") and f.endswith(".db")]
        backups.sort(key=os.path.getmtime) # xếp từ cũ đến mới
        
        while len(backups) > 5:
            oldest = backups.pop(0)
            try:
                os.remove(oldest)
                print(f"Auto Backup: Removed old backup file to free disk space: {oldest}")
            except Exception as rm_ex:
                print(f"Auto Backup: Failed to remove oldest backup: {rm_ex}")
    except Exception as e:
        print(f"Auto Backup: Error during database backup: {e}")

def start_scheduler():
    db = SessionLocal()
    try:
        interval_val = db.query(Config).filter(Config.key == "sync_interval_hours").first()
        interval = int(interval_val.value) if interval_val and interval_val.value else 1
    except Exception:
        interval = 1
    finally:
        db.close()
        
    # Xóa job cũ nếu tồn tại
    if scheduler.get_job("strava_sync_job"):
        scheduler.remove_job("strava_sync_job")
        
    scheduler.add_job(
        run_background_sync,
        "interval",
        hours=interval,
        id="strava_sync_job",
        replace_existing=True
    )
    
    # Đăng ký job tự động backup DB mỗi 24 giờ
    if scheduler.get_job("db_auto_backup_job"):
        scheduler.remove_job("db_auto_backup_job")
    scheduler.add_job(
        run_auto_db_backup,
        "interval",
        hours=24,
        id="db_auto_backup_job",
        replace_existing=True
    )
    
    if not scheduler.running:
        scheduler.start()
    print(f"Scheduler: Started periodic background sync every {interval} hours.")

@app.on_event("startup")
def startup_event():
    # Đảm bảo thư mục upload và avatar tồn tại
    os.makedirs("static/uploads", exist_ok=True)
    os.makedirs("static/uploads/avatars", exist_ok=True)
    # Khởi tạo frame mặc định nếu thiếu
    tao_frame_mau_neu_thieu("static/uploads/frame.png")
    # Khởi tạo database và di chuyển dữ liệu cũ từ Excel nếu có
    init_db()
    # Khởi chạy Scheduler đồng bộ ngầm
    start_scheduler()
    # Đồng bộ lần đầu khi chạy ứng dụng (chạy bất đồng bộ để tránh block startup)
    import threading
    threading.Thread(target=run_background_sync, daemon=True).start()
    threading.Thread(target=run_auto_db_backup, daemon=True).start()

@app.on_event("shutdown")
def shutdown_event():
    if scheduler.running:
        scheduler.shutdown()

# --- CUSTOM JINJA FILTERS ---
def format_currency(value):
    try:
        return f"{int(value):,} VND".replace(",", ".")
    except (ValueError, TypeError):
        return "0 VND"

templates.env.filters["currency"] = format_currency

# --- GLOBAL JINJA CONTEXT ---
def get_global_configs():
    db = SessionLocal()
    try:
        from backend.sync_engine import get_config_dict
        configs = get_config_dict(db)
        
        # Chỉ hiện Welcome Banner cho các giải đấu mới đang hoạt động (không hiện cho giải trường kỳ SSO's HC ID=1)
        active_event = db.query(CompetitionEvent).filter(
            CompetitionEvent.is_active == True,
            CompetitionEvent.id != 1
        ).order_by(CompetitionEvent.id.desc()).first()
        if active_event:
            if active_event.title:
                configs["rules_title"] = active_event.title
            if active_event.rules_description or active_event.description:
                configs["rules_description"] = active_event.rules_description or active_event.description
            if active_event.rules_banner_text:
                configs["rules_banner_text"] = active_event.rules_banner_text
            if active_event.rules_general_text:
                configs["rules_general_text"] = active_event.rules_general_text
            if active_event.banner_image:
                configs["rules_banner_image"] = active_event.banner_image
            configs["active_event_id"] = active_event.id
            
        # Tạo mã hash duy nhất cho nội dung quy chế/banner để tự động kích hoạt lại popup ở client-side khi có thay đổi
        import hashlib
        r_ver = configs.get("rules_version", "1.0")
        r_txt = configs.get("rules_banner_text", "")
        r_img = configs.get("rules_banner_image", "")
        raw_str = f"{r_ver}_{r_txt}_{r_img}"
        configs["rules_hash"] = hashlib.md5(raw_str.encode("utf-8")).hexdigest()[:8]
                
        return configs
    except Exception:
        return {}
    finally:
        db.close()

templates.env.globals["get_configs"] = get_global_configs

def get_department_members(db: Session, start_date: str = None, end_date: str = None, event_id: int = None) -> dict:
    """Calculate department member counts dynamically based on active registered athletes who have activities in the timeframe, or configured event department sizes."""
    dept_members = {}
    
    # 1. Nếu có event_id và giải đấu đó cấu hình sĩ số phòng ban riêng (JSON)
    if event_id:
        event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).first()
        if event and event.department_members:
            try:
                import json
                configured = json.loads(event.department_members)
                if isinstance(configured, dict):
                    # Trích xuất sĩ số từ JSON
                    dept_members = {k: int(v) for k, v in configured.items() if v}
            except Exception as e:
                print(f"Error parsing event department_members JSON: {e}")
                
    # 2. Nếu không có cấu hình riêng hoặc cấu hình bị lỗi, lấy cấu hình chung từ Config
    if not dept_members:
        try:
            import json
            dept_members_conf = db.query(Config).filter(Config.key == "department_members").first()
            if dept_members_conf and dept_members_conf.value:
                configured = json.loads(dept_members_conf.value)
                if isinstance(configured, dict):
                    dept_members = {k: int(v) for k, v in configured.items() if v}
        except Exception as e:
            print(f"Error parsing global department_members Config: {e}")
            
    # 3. Tính toán bổ sung động cho các phòng ban dựa trên số VĐV thực tế nếu không có cấu hình cố định
    try:
        # Lấy danh sách phòng ban thực tế từ database
        all_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().all()
        for row in all_depts:
            dept_name = row[0]
            if dept_name and dept_name not in dept_members:
                # Nếu chưa được cấu hình, đếm số VĐV thực tế đang hoạt động
                if event_id:
                    active_count = db.query(Athlete).join(
                        CompetitionRegistration,
                        Athlete.id == CompetitionRegistration.athlete_id
                    ).filter(
                        Athlete.department == dept_name,
                        Athlete.is_active == True,
                        CompetitionRegistration.event_id == event_id
                    ).count()
                else:
                    active_count = db.query(Athlete).filter(Athlete.department == dept_name, Athlete.is_active == True).count()
                dept_members[dept_name] = active_count or 1
    except Exception as e:
        print(f"Error resolving dynamic department members fallback: {e}")
        
    return dept_members

# --- FRONTEND ROUTES ---
@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    event_id: Optional[str] = None,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Trang chủ hiển thị Bảng xếp hạng (BXH), Tìm kiếm và Thống kê tổng quan theo khung thời gian.
    Hỗ trợ lọc theo giải đấu (event_id).
    """
    configs = get_config_dict(db)
    
    # Bổ sung thông tin active event và rules_hash vào configs để welcome modal hoạt động chính xác
    active_event = db.query(CompetitionEvent).filter(
        CompetitionEvent.is_active == True,
        CompetitionEvent.id != 1
    ).order_by(CompetitionEvent.id.desc()).first()
    if active_event:
        configs["active_event_id"] = active_event.id
        if active_event.title:
            configs["rules_title"] = active_event.title
        if active_event.rules_description or active_event.description:
            configs["rules_description"] = active_event.rules_description or active_event.description
        if active_event.rules_banner_text:
            configs["rules_banner_text"] = active_event.rules_banner_text
        if active_event.rules_general_text:
            configs["rules_general_text"] = active_event.rules_general_text
        if active_event.banner_image:
            configs["rules_banner_image"] = active_event.banner_image
        if active_event.rules_group_qr:
            configs["rules_group_qr"] = active_event.rules_group_qr
            
    import hashlib
    r_ver = configs.get("rules_version", "1.0")
    r_txt = configs.get("rules_banner_text", "")
    r_img = configs.get("rules_banner_image", "")
    configs["rules_hash"] = hashlib.md5(f"{r_ver}_{r_txt}_{r_img}".encode("utf-8")).hexdigest()[:8]
    
    # Lấy danh sách giải đấu đang hoạt động
    active_competitions = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.id).all()
    
    # Parse event_id safely to avoid 422 errors for empty queries like event_id=
    parsed_event_id = None
    if event_id is not None and str(event_id).strip():
        try:
            parsed_event_id = int(str(event_id).strip())
        except ValueError:
            pass

    # Xác định giải đấu được chọn
    selected_event = None
    if parsed_event_id:
        selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == parsed_event_id).first()
    if not selected_event and active_competitions:
        # Ưu tiên chọn giải đấu mới hoạt động (ID != 1) sắp xếp theo ID giảm dần, nếu không có thì fallback giải ID=1
        new_active = [c for c in active_competitions if c.id != 1]
        if new_active:
            selected_event = sorted(new_active, key=lambda x: x.id, reverse=True)[0]
        else:
            selected_event = active_competitions[0]
        event_id = selected_event.id
    else:
        event_id = selected_event.id if selected_event else None
    
    # Lấy cấu hình hiển thị cột của BXH Cá nhân
    col_configs = {
        "show_col_gender": configs.get("show_col_gender", "true").lower() == "true",
        "show_col_dept": configs.get("show_col_dept", "true").lower() == "true",
        "show_col_dist": configs.get("show_col_dist", "true").lower() == "true",
        "show_col_time": configs.get("show_col_time", "true").lower() == "true",
        "show_col_award": configs.get("show_col_award", "true").lower() == "true",
    }
    
    # 0. Xử lý khung thời gian mặc định
    # Nếu có giải đấu được chọn, sử dụng khoảng thời gian của giải đấu đó
    if not start_date or not end_date:
        if selected_event and selected_event.start_date and selected_event.end_date:
            if not start_date:
                start_date = selected_event.start_date
            if not end_date:
                end_date = selected_event.end_date
        else:
            # Fallback: 7 ngày từ ngày có hoạt động mới nhất
            base_query = db.query(func.max(Activity.activity_date))
            if event_id:
                base_query = base_query.filter(Activity.event_id == event_id)
            max_date_str = base_query.scalar()
            if max_date_str:
                try:
                    end_dt = datetime.strptime(max_date_str, "%Y-%m-%d")
                except ValueError:
                    end_dt = datetime.now()
            else:
                end_dt = datetime.now()
            
            start_dt = end_dt - timedelta(days=6)
            
            if not start_date:
                start_date = start_dt.strftime("%Y-%m-%d")
            if not end_date:
                end_date = end_dt.strftime("%Y-%m-%d")

    # Xây dựng bộ lọc cơ bản cho giải đấu + khoảng thời gian
    base_filters = [Activity.activity_date >= start_date, Activity.activity_date <= end_date]
    if event_id:
        base_filters.append(Activity.event_id == event_id)
        if selected_event:
            allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]
            if "All" not in allowed_sports:
                base_filters.append(Activity.sport_type.in_(allowed_sports))

    # 1. Thống kê tổng quan (Kpi Cards)
    total_kcal = db.query(func.sum(Activity.kcal_burned))\
        .filter(*base_filters)\
        .scalar() or 0
    total_dist = db.query(func.sum(Activity.distance_km))\
        .filter(*base_filters)\
        .scalar() or 0
    if event_id:
        total_athletes = db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == event_id).count()
    else:
        total_athletes = db.query(Athlete).filter(Athlete.is_active == True).count()
    
    # 2. Xếp hạng cá nhân (BXH Tổng) theo KCAL (Chỉ các VĐV đã đăng ký giải đấu này)
    query_stats = db.query(
        Athlete.id,
        Athlete.full_name,
        Athlete.gender,
        Athlete.department,
        Athlete.avatar_url,
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)
    
    if event_id:
        query_stats = query_stats.join(
            CompetitionRegistration,
            (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
        )
        
    athlete_stats_query = query_stats.filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.id)
     
    is_distance = selected_event and getattr(selected_event, "ranking_metric", "kcal") == "distance"
    if is_distance:
        athlete_stats = athlete_stats_query.order_by(func.sum(Activity.distance_km).desc()).all()
    else:
        athlete_stats = athlete_stats_query.order_by(func.sum(Activity.kcal_burned).desc()).all()
     
    # Tính giải thưởng tương ứng cho từng VĐV trên BXH
    ranked_athletes = []
    for rank, item in enumerate(athlete_stats, 1):
        metric_value = item.total_dist if is_distance else item.total_kcal
        award_info = get_award_info(item.gender, metric_value or 0, db, event_id=event_id)
        ranked_athletes.append({
            "rank": rank,
            "id": item.id,
            "full_name": item.full_name,
            "gender": item.gender,
            "department": item.department,
            "avatar_url": item.avatar_url,
            "total_dist": round(item.total_dist or 0, 1),
            "total_time": round((item.total_time or 0) / 60.0, 1), # Đổi sang giờ
            "total_kcal": int(item.total_kcal or 0),
            "award": award_info["reward_amount"],
            "has_award": award_info["has_award"]
        })

    # 3. Xếp hạng theo Phòng ban
    dept_members = get_department_members(db, start_date, end_date, event_id=event_id)
    
    dept_query = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal"),
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time")
    ).join(Activity, Athlete.id == Activity.athlete_id)
    
    if event_id:
        dept_query = dept_query.join(
            CompetitionRegistration,
            (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
        )
        
    dept_query = dept_query.filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.department)
    dept_stats_raw = dept_query.all()
     
    dept_stats = []
    for item in dept_stats_raw:
        dept_name = item.department
        members = dept_members.get(dept_name, 1)
        total_k = item.total_kcal or 0
        total_d = item.total_dist or 0
        total_t = item.total_time or 0
        avg_k = total_k / members
        avg_d = total_d / members
        avg_t = (total_t / 60.0) / members
        
        dept_stats.append({
            "department": dept_name,
            "total_kcal": int(total_k),
            "total_distance": round(total_d, 1),
            "total_time": round(total_t / 60.0, 1),
            "members": members,
            "avg_kcal": round(avg_k, 0),
            "avg_distance": round(avg_d, 2),
            "avg_time": round(avg_t, 2)
        })
        
    if is_distance:
        dept_stats = sorted(dept_stats, key=lambda x: x["avg_distance"], reverse=True)
    else:
        dept_stats = sorted(dept_stats, key=lambda x: x["avg_kcal"], reverse=True)
        
    for idx, d in enumerate(dept_stats, 1):
        d["rank"] = idx

    # 4. Xếp hạng theo Môn Thể Thao (Nam / Nữ riêng)
    def get_sport_ranking(gender: str):
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
             .order_by(Activity.sport_type, func.sum(Activity.kcal_burned).desc()).all()
         
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

        # --- BỔ SUNG: Xếp hạng gộp Chạy & Đi bộ (Walk + Run) ---
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
        # --- KẾT THÚC BỔ SUNG ---
        
        return grouped

    sport_rank_male = get_sport_ranking("Nam")
    sport_rank_female = get_sport_ranking("Nữ")

    # Danh sách VĐV dùng cho tính năng tìm kiếm (search dropdown)
    all_athletes = db.query(Athlete).filter(Athlete.is_active == True).all()

    from backend.database import ArchivedEvent
    db_events = db.query(ArchivedEvent).order_by(ArchivedEvent.id.desc()).all()
    archived_events = [
        {
            "id": ev.id,
            "title": ev.title,
            "banner_image": ev.banner_image,
            "video_url": ev.video_url,
            "summary_text": ev.summary_text,
            "gallery_images": ev.gallery_images
        }
        for ev in db_events
    ]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "configs": configs,
            "total_kcal": int(total_kcal),
            "total_dist": round(total_dist, 1),
            "total_athletes": total_athletes,
            "ranked_athletes": ranked_athletes,
            "dept_stats": dept_stats,
            "sport_rank_male": sport_rank_male,
            "sport_rank_female": sport_rank_female,
            "all_athletes": all_athletes,
            "club_id": configs.get("strava_club_id"),
            "start_date": start_date,
            "end_date": end_date,
            "archived_events": archived_events,
            "col_configs": col_configs,
            "active_competitions": active_competitions,
            "selected_event": selected_event,
            "selected_event_id": event_id,
            "selected_metric": "distance" if is_distance else "kcal"
        }
    )

@app.get("/rules", response_class=HTMLResponse)
def rules_page(
    request: Request,
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Trang quy chế giải đấu."""
    configs = get_config_dict(db)
    
    # Lấy danh sách giải đấu đang hoạt động
    active_competitions = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.id).all()
    
    # Parse event_id safely to avoid 422 errors for empty queries like event_id=
    parsed_event_id = None
    if event_id is not None and str(event_id).strip():
        try:
            parsed_event_id = int(str(event_id).strip())
        except ValueError:
            pass

    # Xác định giải đấu được chọn
    selected_event = None
    if parsed_event_id:
        selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == parsed_event_id).first()
    if not selected_event and active_competitions:
        # Ưu tiên chọn giải đấu mới hoạt động (ID != 1) sắp xếp theo ID giảm dần, nếu không có thì fallback giải ID=1
        new_active = [c for c in active_competitions if c.id != 1]
        if new_active:
            selected_event = sorted(new_active, key=lambda x: x.id, reverse=True)[0]
        else:
            selected_event = active_competitions[0]
        
    if selected_event:
        if selected_event.title:
            configs["rules_title"] = selected_event.title
        if selected_event.rules_description or selected_event.description:
            configs["rules_description"] = selected_event.rules_description or selected_event.description
        if selected_event.rules_banner_text:
            configs["rules_banner_text"] = selected_event.rules_banner_text
        if selected_event.rules_general_text:
            configs["rules_general_text"] = selected_event.rules_general_text
        if selected_event.banner_image:
            configs["rules_banner_image"] = selected_event.banner_image
        if selected_event.rules_group_qr:
            configs["rules_group_qr"] = selected_event.rules_group_qr
            
    selected_event_id = selected_event.id if selected_event else None
    
    # Tạo mã hash quy chế sau khi đã ghi đè từ giải đấu
    import hashlib
    r_ver = configs.get("rules_version", "1.0")
    r_txt = configs.get("rules_banner_text", "")
    r_img = configs.get("rules_banner_image", "")
    configs["rules_hash"] = hashlib.md5(f"{r_ver}_{r_txt}_{r_img}".encode("utf-8")).hexdigest()[:8]
    
    allowed_sports = None
    if selected_event:
        allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]

    mets = []
    if selected_event_id:
        mets = db.query(MetsRule).filter(MetsRule.event_id == selected_event_id).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
    if not mets:
        mets = db.query(MetsRule).filter(MetsRule.event_id == None).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
        
    if allowed_sports and "All" not in allowed_sports:
        mets = [m for m in mets if m.sport_type in allowed_sports]
        
    rewards = []
    if selected_event_id:
        rewards = db.query(RewardRule).filter(RewardRule.event_id == selected_event_id).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
        # Chỉ fallback về mốc mặc định nếu giải đấu là milestone và chưa cấu hình mốc nào
        if not rewards and selected_event and (selected_event.reward_type or "milestone") == "milestone":
            rewards = db.query(RewardRule).filter(RewardRule.event_id == None).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
    else:
        rewards = db.query(RewardRule).filter(RewardRule.event_id == None).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
    return templates.TemplateResponse(
        request=request,
        name="rules.html",
        context={
            "configs": configs,
            "mets": mets,
            "rewards": rewards,
            "active_competitions": active_competitions,
            "selected_event": selected_event,
            "selected_event_id": selected_event.id if selected_event else None
        }
    )

@app.get("/avatar", response_class=HTMLResponse)
def get_avatar_page(
    request: Request,
    event_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Trang giao dien ghep frame avatar cho VDVs."""
    configs = get_config_dict(db)
    
    # Xác định đường dẫn khung viền avatar toàn cục
    global_frame = configs.get("global_avatar_frame")
    avatar_frame_url = "/static/uploads/frame.png"
    
    if global_frame:
        clean_path = global_frame.lstrip("/")
        if os.path.exists(clean_path):
            avatar_frame_url = global_frame
            
    # Thêm timestamp để tránh cache ảnh cũ của trình duyệt
    avatar_frame_url = f"{avatar_frame_url}?t={int(time.time())}"
    
    # Lấy đường dẫn khung viền raw chưa đục lỗ
    global_frame_raw = configs.get("global_avatar_frame_raw")
    avatar_frame_raw_url = "/static/uploads/frame_raw.png"
    
    if global_frame_raw:
        clean_path_raw = global_frame_raw.lstrip("/")
        if os.path.exists(clean_path_raw):
            avatar_frame_raw_url = global_frame_raw
    else:
        # Fallback dùng global_frame đã đục lỗ nếu không có file raw
        avatar_frame_raw_url = global_frame if global_frame else "/static/uploads/frame.png"
        
    avatar_frame_raw_url = f"{avatar_frame_raw_url}?t={int(time.time())}"
            
    # Lấy toàn bộ VĐV đang hoạt động (avatar là duy nhất cho mỗi người, không phụ thuộc giải đấu)
    all_athletes = db.query(Athlete).filter(
        Athlete.is_active == True
    ).order_by(Athlete.full_name).all()
    
    return templates.TemplateResponse(
        request=request,
        name="avatar.html",
        context={
            "request": request,
            "configs": configs,
            "all_athletes": all_athletes,
            "avatar_frame_url": avatar_frame_url,
            "avatar_frame_raw_url": avatar_frame_raw_url
        }
    )

@app.post("/api/avatar/sync-profile")
async def sync_profile_avatar(
    request: Request,
    db: Session = Depends(get_db)
):
    """API luu tru avatar da ghep va dong bo vao CSDL cho VDV."""
    try:
        data = await request.json()
        athlete_id = data.get("athlete_id")
        image_data = data.get("image_data")
        
        if not athlete_id or not image_data:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Thieu du lieu athlete_id hoac image_data"})
            
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Khong tim thay van dong vien"})
        
        # Xu ly chuoi Base64 gui tu Canvas
        if "," in image_data:
            header, base64_str = image_data.split(",", 1)
        else:
            base64_str = image_data
            
        import base64
        image_bytes = base64.b64decode(base64_str)
        
        import time
        # Luu file anh thuc te kem timestamp de tranh cache trinh duyet
        os.makedirs("static/uploads/avatars", exist_ok=True)
        
        # Xoa file anh cu neu co de don dep bo nho
        if athlete.avatar_url:
            old_path = athlete.avatar_url.lstrip("/")
            if os.path.exists(old_path) and "default" not in old_path:
                try:
                    os.remove(old_path)
                except Exception:
                    pass
        
        timestamp = int(time.time())
        file_name = f"athlete_{athlete_id}_{timestamp}.png"
        file_path = os.path.join("static/uploads/avatars", file_name)
        with open(file_path, "wb") as f:
            f.write(image_bytes)
            
        # Cap nhat duong dan avatar vao DB
        avatar_url = f"/static/uploads/avatars/{file_name}"
        athlete.avatar_url = avatar_url
        db.commit()
        
        return {"status": "success", "message": "Cap nhat anh dai dien thanh cong", "avatar_url": avatar_url}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Loi he thong: {str(e)}"})

@app.post("/api/avatar/upload-direct")
async def upload_direct_avatar(
    athlete_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """API cho phep VDV tai anh dai dien tho len truc tiep tu thiet bi (khong qua trang ghep frame)."""
    try:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        if not athlete:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Khong tim thay van dong vien"})
            
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Dinh dang anh khong hop le (ho tro PNG, JPG, WEBP)"})
            
        content = await file.read()
        
        os.makedirs("static/uploads/avatars", exist_ok=True)
        
        # Xoa file anh cu neu co
        if athlete.avatar_url:
            old_path = athlete.avatar_url.lstrip("/")
            if os.path.exists(old_path) and "default" not in old_path:
                try:
                    os.remove(old_path)
                except Exception:
                    pass
                    
        timestamp = int(time.time())
        file_name = f"athlete_direct_{athlete_id}_{timestamp}{ext}"
        file_path = os.path.join("static/uploads/avatars", file_name)
        with open(file_path, "wb") as f:
            f.write(content)
            
        avatar_url = f"/static/uploads/avatars/{file_name}"
        athlete.avatar_url = avatar_url
        db.commit()
        
        return {"status": "success", "message": "Cap nhat anh dai dien truc tiep thanh cong", "avatar_url": avatar_url}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Loi he thong: {str(e)}"})

@app.post("/api/avatar/remove-bg")
async def api_remove_background(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """API nhan file anh chan dung, tu dong xoa nen bang rembg va tra ve file PNG trong suot."""
    try:
        content = await file.read()
        
        # Su dung rembg de xoa nen
        from rembg import remove
        import io
        from fastapi.responses import StreamingResponse
        
        # Thuc hien xoa nen
        output_bytes = remove(content)
        
        # Tra ve file PNG trong suot cho client
        return StreamingResponse(io.BytesIO(output_bytes), media_type="image/png")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Loi xoa nen: {str(e)}"})

@app.post("/admin/upload-frame")
def upload_custom_frame(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """API cho phep admin tai len khung vien ky niem moi va tu dong duc lo."""
    # Kiem tra quyen Admin
    admin_user = get_admin_session(request, db)
    if not admin_user:
        return RedirectResponse(url="/admin/login", status_code=status.HTTP_303_SEE_OTHER)
        
    try:
        contents = file.file.read()
        from io import BytesIO
        from PIL import Image
        
        img = Image.open(BytesIO(contents))
        
        # Duc lo tron o giua voi scale = 0.72
        processed_img = duc_lo_frame_neu_duc(img, scale=0.72)
        
        os.makedirs("static/uploads", exist_ok=True)
        path_frame = "static/uploads/frame.png"
        processed_img.save(path_frame, "PNG")
        
        return RedirectResponse(url="/admin?msg=frame_updated", status_code=status.HTTP_303_SEE_OTHER)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return HTMLResponse(content=f"<h3>Loi khi xu ly file anh: {str(e)}</h3>", status_code=500)

@app.get("/register", response_class=HTMLResponse)
def register_page(
    request: Request,
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Trang đăng ký tham gia cho vận động viên."""
    db_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().order_by(Athlete.department).all()
    departments = [r[0] for r in db_depts] if db_depts else [
        "BAN GIÁM ĐỐC", "PHÒNG HÀNH CHÍNH NHÂN SỰ", "PHÒNG KỸ THUẬT", 
        "PHÒNG KINH DOANH", "PHÒNG TÀI CHÍNH KẾ TOÁN", "PHÒNG KHAI THÁC", "PHÒNG VẬN HÀNH"
    ]
    active_competitions = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.id).all()
    
    # Parse event_id safely to avoid 422 errors for empty queries like event_id=
    parsed_event_id = None
    if event_id is not None and str(event_id).strip():
        try:
            parsed_event_id = int(str(event_id).strip())
        except ValueError:
            pass

    selected_event_id = parsed_event_id
    if not selected_event_id and active_competitions:
        new_active = [c for c in active_competitions if c.id != 1]
        if new_active:
            selected_event_id = sorted(new_active, key=lambda x: x.id, reverse=True)[0].id
        else:
            selected_event_id = active_competitions[0].id
        
    # Lấy danh sách tên Strava từ các hoạt động chưa liên kết với bất kỳ VĐV nào để làm gợi ý đăng ký
    unlinked_names = db.query(Activity.athlete_name_raw)\
        .filter(Activity.athlete_id == None)\
        .group_by(Activity.athlete_name_raw).all()
    # Loại bỏ các tên thô đã trùng với bất kỳ tên Strava nào (kể cả tên phụ) của các VĐV đã đăng ký
    registered_names = set()
    athletes = db.query(Athlete).all()
    for a in athletes:
        if a.strava_name:
            for part in a.strava_name.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    registered_names.add(cleaned)
    unlinked_athletes = [name[0] for name in unlinked_names if name[0] and name[0].strip().lower() not in registered_names]

    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "configs": get_config_dict(db),
            "departments": departments,
            "active_competitions": active_competitions,
            "selected_event_id": selected_event_id,
            "unlinked_athletes": unlinked_athletes,
            "success": None,
            "error": None,
            "already_exists": False
        }
    )

@app.post("/register", response_class=HTMLResponse)
def register_athlete(
    request: Request,
    full_name: str = Form(...),
    gender: str = Form(...),
    department: str = Form(...),
    weight: float = Form(...),
    strava_name: str = Form(...),
    event_id: int = Form(...),
    is_update: str = Form("false"),
    db: Session = Depends(get_db)
):
    db_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().order_by(Athlete.department).all()
    departments = [r[0] for r in db_depts] if db_depts else [
        "BAN GIÁM ĐỐC", "PHÒNG HÀNH CHÍNH NHÂN SỰ", "PHÒNG KỸ THUẬT", 
        "PHÒNG KINH DOANH", "PHÒNG TÀI CHÍNH KẾ TOÁN", "PHÒNG KHAI THÁC", "PHÒNG VẬN HÀNH"
    ]
    active_competitions = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.id).all()
    configs = get_config_dict(db)
    full_name = full_name.strip()
    strava_name = strava_name.strip()
    
    # Kiểm tra ràng buộc giải đấu nội bộ (SSO's HC) chỉ dành cho người thuộc khối SSO
    chosen_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).first()
    is_sso_hc = chosen_event and ("SSO'S HC" in chosen_event.title.upper() or "SSO’S HC" in chosen_event.title.upper())
    if is_sso_hc:
        dept_upper = department.strip().upper()
        is_internal = any(dept_upper.startswith(prefix) for prefix in ["SSO", "NSMO", "NSO", "CSO"])
        if not is_internal:
            unlinked_names = db.query(Activity.athlete_name_raw)\
                .filter(Activity.athlete_id == None)\
                .group_by(Activity.athlete_name_raw).all()
            registered_names = set()
            for a in db.query(Athlete).all():
                if a.strava_name:
                    for part in a.strava_name.split(","):
                        cleaned = part.strip().lower()
                        if cleaned:
                            registered_names.add(cleaned)
            unlinked_athletes = [name[0] for name in unlinked_names if name[0] and name[0].strip().lower() not in registered_names]
            
            return templates.TemplateResponse(
                request=request,
                name="register.html",
                context={
                    "configs": configs,
                    "departments": departments,
                    "active_competitions": active_competitions,
                    "selected_event_id": event_id,
                    "unlinked_athletes": unlinked_athletes,
                    "success": None,
                    "error": "Giải đấu SSO's HC là giải đấu nội bộ, chỉ dành riêng cho nhân viên thuộc khối SSO. Vui lòng chọn đúng giải đấu của bạn.",
                    "already_exists": False,
                    "needs_strava_auth": False,
                    "auth_url": "",
                    "form_data": {
                        "full_name": full_name,
                        "gender": gender,
                        "weight": weight,
                        "department": department,
                        "strava_name": strava_name,
                        "event_id": event_id
                    }
                }
            )
    
    # Lấy danh sách tên Strava chưa liên kết để hiển thị gợi ý khi xảy ra lỗi/cập nhật
    unlinked_names = db.query(Activity.athlete_name_raw)\
        .filter(Activity.athlete_id == None)\
        .group_by(Activity.athlete_name_raw).all()
    # Loại bỏ các tên thô đã trùng với bất kỳ tên Strava nào (kể cả tên phụ) của các VĐV đã đăng ký
    registered_names = set()
    athletes = db.query(Athlete).all()
    for a in athletes:
        if a.strava_name:
            for part in a.strava_name.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    registered_names.add(cleaned)
    unlinked_athletes = [name[0] for name in unlinked_names if name[0] and name[0].strip().lower() not in registered_names]

    # Kiểm tra xem tên Strava hoặc Họ tên đã được đăng ký chưa
    new_names = [n.strip().lower() for n in strava_name.split(",") if n.strip()]
    exists = None
    
    # 1. Kiểm tra trùng lặp theo Họ và tên đã chuẩn hóa
    new_clean_fullname = clean_name(full_name)
    for a in athletes:
        if clean_name(a.full_name) == new_clean_fullname:
            exists = a
            break
            
    # 2. Nếu chưa trùng họ tên, kiểm tra trùng lặp theo Strava Name
    if not exists:
        for a in athletes:
            if a.strava_name:
                existing_names = [n.strip().lower() for n in a.strava_name.split(",") if n.strip()]
                if set(new_names) & set(existing_names):
                    exists = a
                    break
                    
    if exists:
        if is_update == "true":
            try:
                # Cho phép cập nhật cả Họ và tên mới và Strava Name mới nếu họ chỉnh sửa lỗi viết nhầm
                exists.full_name = full_name.strip()
                exists.department = department
                exists.weight = weight
                if strava_name and strava_name.strip():
                    exists.strava_name = strava_name.strip()
                db.commit()
                
                # Cập nhật và tính toán lại lượng calo (KCAL) của các hoạt động cũ dựa theo cân nặng mới
                acts = db.query(Activity).filter(Activity.athlete_id == exists.id).all()
                for act in acts:
                    dist_raw = act.distance_km_raw if act.distance_km_raw is not None else act.distance_km
                    speed_kmh = 0.0
                    if act.moving_time_min > 0:
                        speed_kmh = dist_raw / (act.moving_time_min / 60.0)
                    actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
                    
                    from backend.calculations import get_mets_value, calculate_kcal
                    mets_val = get_mets_value(act.sport_type, speed_kmh, db, dist_raw, act.elevation_gain_m, event_id=act.event_id)
                    act.mets_value = mets_val
                    mult = get_multiplier_for_date(act.activity_date, act.event_id, db)
                    kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m, act.sport_type)
                    act.kcal_burned_raw = kcal_raw
                    act.kcal_burned = round(kcal_raw * mult)
                    act.multiplier = mult
                    act.distance_km_raw = dist_raw
                    act.distance_km = round(dist_raw * mult, 2)
                db.commit()
                
                # ĐĂNG KÝ GIẢI ĐẤU NẾU CHƯA CÓ
                reg_exists = db.query(CompetitionRegistration).filter(
                    CompetitionRegistration.athlete_id == exists.id,
                    CompetitionRegistration.event_id == event_id
                ).first()
                if not reg_exists:
                    new_reg = CompetitionRegistration(athlete_id=exists.id, event_id=event_id)
                    db.add(new_reg)
                    db.commit()
                    print(f"Main.py: Registered existing Athlete {exists.full_name} for event {event_id} during update.")
                
                # Liên kết các hoạt động cũ (chưa được liên kết trước đó) cho VĐV này
                link_unlinked_activities(db, exists)
                
                configs = get_config_dict(db)
                needs_auth = not exists.strava_refresh_token
                auth_url = ""
                if needs_auth:
                    client_id = configs.get("strava_client_id")
                    app_url = APP_URL
                    if not app_url:
                        host = request.headers.get("host", "localhost:8080")
                        scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
                        app_url = f"{scheme}://{host}"
                    redirect_uri = f"{app_url}/exchange_user_token"
                    auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=activity:read_all,profile:read_all&state={exists.id}"
                    return RedirectResponse(auth_url, status_code=303)

                return templates.TemplateResponse(
                    request=request,
                    name="register.html",
                    context={
                        "configs": configs,
                        "departments": departments,
                        "active_competitions": active_competitions,
                        "selected_event_id": event_id,
                        "unlinked_athletes": unlinked_athletes,
                        "success": f"Đã cập nhật thông tin và đăng ký giải chạy thành công cho VĐV {exists.full_name}!",
                        "error": None,
                        "already_exists": False,
                        "needs_strava_auth": False,
                        "auth_url": "",
                        "athlete_id": exists.id,
                        "athlete_name": exists.full_name
                    }
                )
            except Exception as e:
                db.rollback()
                return templates.TemplateResponse(
                    request=request,
                    name="register.html",
                    context={
                        "configs": get_config_dict(db),
                        "departments": departments,
                        "active_competitions": active_competitions,
                        "selected_event_id": event_id,
                        "unlinked_athletes": unlinked_athletes,
                        "success": None,
                        "error": f"Lỗi hệ thống khi cập nhật: {str(e)}",
                        "already_exists": False
                    }
                )
        else:
            # Báo cho người dùng biết thông tin cũ và hỏi xem họ có muốn cập nhật không
            return templates.TemplateResponse(
                request=request,
                name="register.html",
                context={
                    "configs": get_config_dict(db),
                    "departments": departments,
                    "active_competitions": active_competitions,
                    "selected_event_id": event_id,
                    "unlinked_athletes": unlinked_athletes,
                    "success": None,
                    "error": f"Tên hiển thị Strava '{strava_name}' đã được đăng ký trong hệ thống.",
                    "already_exists": True,
                    "existing_athlete": exists,
                    "form_data": {
                        "full_name": full_name,
                        "gender": gender,
                        "department": department,
                        "weight": weight,
                        "strava_name": strava_name,
                        "event_id": event_id
                    }
                }
            )

    try:
        new_athlete = Athlete(
            full_name=full_name,
            gender=gender,
            department=department,
            weight=weight,
            strava_name=strava_name,
            is_active=True
        )
        db.add(new_athlete)
        db.commit()
        db.refresh(new_athlete)
        
        # ĐĂNG KÝ GIẢI ĐẤU CHO VĐV MỚI
        new_reg = CompetitionRegistration(athlete_id=new_athlete.id, event_id=event_id)
        db.add(new_reg)
        db.commit()
        print(f"Main.py: Registered new Athlete {new_athlete.full_name} for event {event_id}.")
        
        # Liên kết các hoạt động cũ (chưa được liên kết trước đó) sang VĐV mới này
        link_unlinked_activities(db, new_athlete)
        
        configs = get_config_dict(db)
        client_id = configs.get("strava_client_id")
        app_url = APP_URL
        if not app_url:
            host = request.headers.get("host", "localhost:8080")
            scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
            app_url = f"{scheme}://{host}"
        redirect_uri = f"{app_url}/exchange_user_token"
        auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=activity:read_all,profile:read_all&state={new_athlete.id}"

        # Tự động chuyển hướng thẳng sang Strava OAuth để liên kết tài khoản
        return RedirectResponse(auth_url, status_code=303)
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "configs": get_config_dict(db),
                "departments": departments,
                "active_competitions": active_competitions,
                "selected_event_id": event_id,
                "unlinked_athletes": unlinked_athletes,
                "success": None,
                "error": f"Lỗi hệ thống: {str(e)}",
                "already_exists": False
            }
        )

@app.get("/profile/{athlete_id}", response_class=HTMLResponse)
def profile_page(
    request: Request,
    athlete_id: int,
    event_id: Optional[str] = None,
    page: int = 1,
    db: Session = Depends(get_db)
):
    """Trang thống kê chi tiết cá nhân vận động viên."""
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id, Athlete.is_active == True).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Không tìm thấy Vận động viên.")

    # Lấy danh sách các giải đấu VĐV đã đăng ký
    registered_events = db.query(CompetitionEvent).join(
        CompetitionRegistration,
        CompetitionEvent.id == CompetitionRegistration.event_id
    ).filter(CompetitionRegistration.athlete_id == athlete.id).all()
    
    # Sắp xếp danh sách giải đấu theo ID giảm dần để hiển thị tab mới nhất trước
    registered_events = sorted(registered_events, key=lambda x: x.id, reverse=True)
    
    # Parse event_id safely to avoid 422 errors for empty queries like event_id=
    parsed_event_id = None
    if event_id is not None and str(event_id).strip():
        try:
            parsed_event_id = int(str(event_id).strip())
        except ValueError:
            pass

    # Xác định giải đấu được chọn xem chi tiết
    selected_event = None
    if parsed_event_id:
        is_reg = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.athlete_id == athlete.id,
            CompetitionRegistration.event_id == parsed_event_id
        ).first()
        if is_reg:
            selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == parsed_event_id).first()
            
    if not selected_event and registered_events:
        # Ưu tiên chọn:
        # 1. Các giải đang hoạt động (is_active == True) và ID != 1 (mới), sắp xếp theo ID giảm dần
        # 2. Giải đang hoạt động ID = 1
        # 3. Các giải đã đóng, sắp xếp theo ID giảm dần
        active_new = [e for e in registered_events if e.is_active and e.id != 1]
        active_default = [e for e in registered_events if e.is_active and e.id == 1]
        closed_events = [e for e in registered_events if not e.is_active]
        
        if active_new:
            selected_event = sorted(active_new, key=lambda x: x.id, reverse=True)[0]
        elif active_default:
            selected_event = active_default[0]
        elif closed_events:
            selected_event = sorted(closed_events, key=lambda x: x.id, reverse=True)[0]
        else:
            selected_event = registered_events[0]
            
    if not selected_event:
        # Fallback nếu chưa đăng ký giải nào, lấy giải đang hoạt động mới nhất giống trang chủ
        active_competitions = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).all()
        if active_competitions:
            new_active = [c for c in active_competitions if c.id != 1]
            if new_active:
                selected_event = sorted(new_active, key=lambda x: x.id, reverse=True)[0]
            else:
                selected_event = active_competitions[0]
                
    selected_event_id = selected_event.id if selected_event else None

    # Lấy các giải đấu đang mở mà VĐV chưa đăng ký
    registered_ids = [re.id for re in registered_events]
    unregistered_events = db.query(CompetitionEvent).filter(
        CompetitionEvent.is_active == True,
        ~CompetitionEvent.id.in_(registered_ids) if registered_ids else True
    ).order_by(CompetitionEvent.id).all()

    # 1. Lấy danh sách hoạt động thuộc giải đấu được chọn
    activities_query = db.query(Activity).filter(Activity.athlete_id == athlete.id)
    if selected_event_id:
        activities_query = activities_query.filter(Activity.event_id == selected_event_id)
        if selected_event:
            allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]
            if "All" not in allowed_sports:
                activities_query = activities_query.filter(Activity.sport_type.in_(allowed_sports))
        
    all_activities = activities_query.order_by(Activity.activity_date.desc()).all()
    valid_activities = all_activities
    
    # Phân trang nhật ký hoạt động hiển thị (15 hoạt động trên trang)
    per_page = 15
    total_activities_count = len(all_activities)
    total_pages = (total_activities_count + per_page - 1) // per_page
    
    page = max(1, page)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    paginated_activities = all_activities[start_idx:end_idx]
    
    # 2. Tính toán các KPI
    total_kcal = sum(a.kcal_burned for a in valid_activities)
    total_dist = sum(a.distance_km for a in valid_activities)
    total_time = sum(a.moving_time_min for a in valid_activities)
    
    # Tính số ngày hoạt động liên tục tối đa (streak)
    dates = sorted(list(set(a.activity_date for a in valid_activities)))
    max_streak = 0
    current_streak = 0
    if dates:
        max_streak = 1
        current_streak = 1
        for i in range(1, len(dates)):
            d1 = datetime.strptime(dates[i-1], "%Y-%m-%d")
            d2 = datetime.strptime(dates[i], "%Y-%m-%d")
            if d2 - d1 == timedelta(days=1):
                current_streak += 1
            else:
                current_streak = 1
            max_streak = max(max_streak, current_streak)

    # 3. Trực quan hóa tiến độ giải thưởng
    is_distance = selected_event and getattr(selected_event, "ranking_metric", "kcal") == "distance"
    metric_value = total_dist if is_distance else total_kcal
    metric_unit = "KM" if is_distance else "KCAL"
    
    award_info = get_award_info(athlete.gender, metric_value, db, event_id=selected_event_id)
    
    progress_percent = 100
    if award_info["next_threshold"] > 0:
        progress_percent = min(int((metric_value / award_info["next_threshold"]) * 100), 100)

    # 4. Tạo dữ liệu cho biểu đồ
    # Biểu đồ xu hướng (KCAL hoặc KM) theo ngày
    daily_stats = {}
    for a in reversed(valid_activities):
        val = a.distance_km if is_distance else a.kcal_burned
        daily_stats[a.activity_date] = daily_stats.get(a.activity_date, 0) + val
    
    # Biểu đồ tròn tỷ lệ môn thể thao (quãng đường)
    sport_stats = {}
    for a in valid_activities:
        sport_stats[a.sport_type] = sport_stats.get(a.sport_type, 0) + round(a.distance_km, 1)

    chart_dates = list(daily_stats.keys())
    chart_kcal = list(daily_stats.values())
    chart_sports = list(sport_stats.keys())
    chart_sport_dists = list(sport_stats.values())

    # 5. Tính toán các huy hiệu đạt được
    from backend.calculations import get_athlete_badges
    badges = get_athlete_badges(
        athlete=athlete,
        valid_activities=valid_activities,
        max_streak=max_streak,
        total_kcal=total_kcal,
        total_time_hours=total_time / 60.0,
        db=db,
        event_id=selected_event_id
    )

    # Kiểm tra quyền Admin
    is_admin = get_admin_session(request, db) is not None

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "athlete": athlete,
            "activities": paginated_activities,
            "current_page": page,
            "total_pages": total_pages,
            "total_activities_count": total_activities_count,
            "total_kcal": total_kcal,
            "total_dist": round(total_dist, 1),
            "total_time": round(total_time / 60.0, 1), # Sang giờ
            "max_streak": max_streak,
            "award_info": award_info,
            "progress_percent": progress_percent,
            "chart_dates": chart_dates,
            "chart_kcal": chart_kcal,
            "chart_sports": chart_sports,
            "chart_sport_dists": chart_sport_dists,
            "badges": badges,
            "is_admin": is_admin,
            "registered_events": registered_events,
            "unregistered_events": unregistered_events,
            "selected_event": selected_event,
            "selected_event_id": selected_event_id,
            "metric_value": metric_value,
            "metric_unit": metric_unit
        }
    )

@app.post("/profile/{athlete_id}/register-event")
def register_event_for_athlete(
    athlete_id: int,
    request: Request,
    event_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Đăng ký tham gia một giải đấu cho vận động viên."""
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id, Athlete.is_active == True).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Không tìm thấy Vận động viên.")
        
    event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id, CompetitionEvent.is_active == True).first()
    if not event:
        raise HTTPException(status_code=404, detail="Giải đấu không khả dụng hoặc đã kết thúc.")
        
    # Kiểm tra xem đã đăng ký chưa
    exists = db.query(CompetitionRegistration).filter(
        CompetitionRegistration.athlete_id == athlete.id,
        CompetitionRegistration.event_id == event_id
    ).first()
    
    if not exists:
        try:
            reg = CompetitionRegistration(athlete_id=athlete.id, event_id=event_id)
            db.add(reg)
            db.commit()
            print(f"Main.py: Registered Athlete {athlete.full_name} for event '{event.title}'.")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=f"Lỗi khi lưu đăng ký: {str(e)}")
            
    return RedirectResponse(url=f"/profile/{athlete_id}?event_id={event_id}", status_code=status.HTTP_303_SEE_OTHER)

@app.get("/event/{event_id}", response_class=HTMLResponse)
def event_detail_page(request: Request, event_id: int, db: Session = Depends(get_db)):
    """Trang chi tiết sự kiện lịch sử (giải chạy cũ)."""
    from backend.database import ArchivedEvent
    event = db.query(ArchivedEvent).filter(ArchivedEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Không tìm thấy sự kiện.")
        
    configs = get_config_dict(db)
    
    # Phân tách album ảnh gallery
    images = []
    if event.gallery_images and event.gallery_images.strip():
        images = [img.strip() for img in event.gallery_images.split(",") if img.strip()]
        
    # Chuẩn hóa link video Youtube sang embed url
    embed_url = None
    if event.video_url:
        video_url = event.video_url.strip()
        if "youtube.com/watch?v=" in video_url:
            try:
                video_id = video_url.split("v=")[1].split("&")[0]
                embed_url = f"https://www.youtube.com/embed/{video_id}"
            except Exception:
                embed_url = video_url
        elif "youtu.be/" in video_url:
            try:
                video_id = video_url.split("youtu.be/")[1].split("?")[0]
                embed_url = f"https://www.youtube.com/embed/{video_id}"
            except Exception:
                embed_url = video_url
        else:
            embed_url = video_url

    return templates.TemplateResponse(
        request=request,
        name="event_detail.html",
        context={
            "configs": configs,
            "event": event,
            "images": images,
            "embed_url": embed_url
        }
    )

# --- ADMIN PANEL ROUTES ---

@app.get("/admin", response_class=HTMLResponse)
def admin_dashboard(
    request: Request,
    error: str = None,
    success: str = None,
    event_id: str = None,
    db: Session = Depends(get_db)
):
    """Trang quản trị (Admin Dashboard)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={
                "logged_in": False,
                "error": error,
                "success": success
            }
        )
        
    configs = get_config_dict(db)
    
    selected_event_id = None
    if event_id is not None:
        if event_id.strip():
            try:
                selected_event_id = int(event_id)
            except ValueError:
                pass
    else:
        # Tự động chọn giải đấu đang hoạt động làm mặc định giống trang chủ
        active_competitions = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.id).all()
        if active_competitions:
            new_active = [c for c in active_competitions if c.id != 1]
            if new_active:
                selected_event_id = sorted(new_active, key=lambda x: x.id, reverse=True)[0].id
            else:
                selected_event_id = active_competitions[0].id

    if selected_event_id:
        athletes = db.query(Athlete).join(
            CompetitionRegistration,
            Athlete.id == CompetitionRegistration.athlete_id
        ).filter(CompetitionRegistration.event_id == selected_event_id).order_by(Athlete.id).all()
    else:
        athletes = db.query(Athlete).order_by(Athlete.id).all()

    # Thống kê ngày giờ đăng ký giải chạy của các VĐV
    reg_map = {}
    if selected_event_id:
        reg_map = {r.athlete_id: r.registered_at for r in db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == selected_event_id).all()}
    else:
        # Nếu xem tất cả giải đấu, lấy ngày đăng ký gần nhất của từng VĐV
        all_regs = db.query(CompetitionRegistration).order_by(CompetitionRegistration.registered_at.desc()).all()
        for r in all_regs:
            if r.athlete_id not in reg_map:
                reg_map[r.athlete_id] = r.registered_at

    for a in athletes:
        reg_time = reg_map.get(a.id)
        if reg_time:
            # Quy đổi sang GMT+7 và định dạng chuỗi
            local_time = reg_time + timedelta(hours=7)
            a.registered_at_str = local_time.strftime("%d/%m/%Y %H:%M")
        else:
            a.registered_at_str = "N/A"

    # Lấy METs Rules
    mets = []
    if selected_event_id:
        mets = db.query(MetsRule).filter(MetsRule.event_id == selected_event_id).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
    if not mets:
        mets = db.query(MetsRule).filter(MetsRule.event_id == None).order_by(MetsRule.sport_type, MetsRule.min_speed).all()

    # Lấy Reward Rules
    rewards = []
    if selected_event_id:
        rewards = db.query(RewardRule).filter(RewardRule.event_id == selected_event_id).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
    if not rewards:
        rewards = db.query(RewardRule).filter(RewardRule.event_id == None).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()

    # Lấy Badge Rules
    from backend.database import BadgeRule
    badges = []
    if selected_event_id:
        badges = db.query(BadgeRule).filter(BadgeRule.event_id == selected_event_id).order_by(BadgeRule.id).all()
    if not badges:
        badges = db.query(BadgeRule).filter(BadgeRule.event_id == None).order_by(BadgeRule.id).all()

    # Lấy danh sách thành viên Strava có hoạt động nhưng chưa đăng ký Web App
    unlinked_names = db.query(Activity.athlete_name_raw)\
        .filter(Activity.athlete_id == None)\
        .group_by(Activity.athlete_name_raw).all()
    # Loại bỏ các tên thô đã trùng với bất kỳ tên Strava nào (kể cả tên phụ) của các VĐV đã đăng ký
    registered_names = set()
    all_registered_athletes = db.query(Athlete).all()
    for a in all_registered_athletes:
        if a.strava_name:
            for part in a.strava_name.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    registered_names.add(cleaned)
    unlinked_athletes = [name[0] for name in unlinked_names if name[0] and name[0].strip().lower() not in registered_names]

    # Tạo đường link authorize với Strava
    client_id = configs.get("strava_client_id")
    # Ưu tiên APP_URL từ .env (domain công khai, cần khớp với Strava App settings)
    # Fallback về request.base_url khi dev local (không có APP_URL)
    if APP_URL:
        redirect_uri = f"{APP_URL}/exchange_token"
    else:
        redirect_uri = str(request.base_url).rstrip("/") + "/exchange_token"
    auth_url = (
        f"https://www.strava.com/oauth/authorize?client_id={client_id}"
        f"&response_type=code&redirect_uri={redirect_uri}"
        f"&approval_prompt=force&scope=read,activity:read_all"
    )

    from backend.database import ArchivedEvent
    archived_events = db.query(ArchivedEvent).order_by(ArchivedEvent.id.desc()).all()

    # Lấy danh sách giải đấu để hiển thị trong tab quản lý
    all_competitions = db.query(CompetitionEvent).order_by(CompetitionEvent.id.desc()).all()

    # --- LOGIC THỐNG KÊ PHÂN TÍCH CHO ADMIN ---
    # --- LOGIC THỐNG KÊ PHÂN TÍCH CHO ADMIN ---
    # 1. Chỉ số KPIs tổng hợp
    selected_event = None
    allowed_sports = None
    if selected_event_id:
        selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == selected_event_id).first()
        if selected_event:
            allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]

    if selected_event_id:
        total_active_athletes = db.query(Athlete).join(
            CompetitionRegistration,
            Athlete.id == CompetitionRegistration.athlete_id
        ).filter(CompetitionRegistration.event_id == selected_event_id, Athlete.is_active == True).count()
        
        act_query = db.query(Activity).filter(Activity.event_id == selected_event_id)
        kcal_query = db.query(func.sum(Activity.kcal_burned)).filter(Activity.event_id == selected_event_id)
        dist_query = db.query(func.sum(Activity.distance_km)).filter(Activity.event_id == selected_event_id)
        time_query = db.query(func.sum(Activity.moving_time_min)).filter(Activity.event_id == selected_event_id)
        
        if allowed_sports and "All" not in allowed_sports:
            act_query = act_query.filter(Activity.sport_type.in_(allowed_sports))
            kcal_query = kcal_query.filter(Activity.sport_type.in_(allowed_sports))
            dist_query = dist_query.filter(Activity.sport_type.in_(allowed_sports))
            time_query = time_query.filter(Activity.sport_type.in_(allowed_sports))
            
        total_valid_activities = act_query.count()
        total_kcal_burned = kcal_query.scalar() or 0.0
        total_distance = dist_query.scalar() or 0.0
        total_moving_time_min = time_query.scalar() or 0.0
    else:
        total_active_athletes = db.query(Athlete).filter(Athlete.is_active == True).count()
        total_valid_activities = db.query(Activity).count()
        total_kcal_burned = db.query(func.sum(Activity.kcal_burned)).scalar() or 0.0
        total_distance = db.query(func.sum(Activity.distance_km)).scalar() or 0.0
        total_moving_time_min = db.query(func.sum(Activity.moving_time_min)).scalar() or 0.0
        
    total_hours = total_moving_time_min / 60.0

    # Tính tổng chi phí giải thưởng (Tổng số tiền thưởng cần chi)
    total_reward = 0.0
    from backend.calculations import get_award_info
    
    # Lấy danh sách VĐV tương ứng
    if selected_event_id:
        athletes_for_reward = db.query(Athlete).join(
            CompetitionRegistration,
            Athlete.id == CompetitionRegistration.athlete_id
        ).filter(CompetitionRegistration.event_id == selected_event_id, Athlete.is_active == True).all()
    else:
        athletes_for_reward = db.query(Athlete).filter(Athlete.is_active == True).all()

    # Tính giải thưởng cho từng VĐV
    for ath in athletes_for_reward:
        act_ath_query = db.query(Activity).filter(Activity.athlete_id == ath.id)
        if selected_event_id:
            act_ath_query = act_ath_query.filter(Activity.event_id == selected_event_id)
            if allowed_sports and "All" not in allowed_sports:
                act_ath_query = act_ath_query.filter(Activity.sport_type.in_(allowed_sports))
        
        ath_activities = act_ath_query.all()
        
        # Tính metric_value (Kcal hoặc Km) của VĐV
        ath_kcal = sum(a.kcal_burned for a in ath_activities) or 0.0
        ath_dist = sum(a.distance_km for a in ath_activities) or 0.0
        
        is_distance = selected_event and getattr(selected_event, "ranking_metric", "kcal") == "distance"
        metric_value = ath_dist if is_distance else ath_kcal
        
        award_info = get_award_info(ath.gender, metric_value, db, event_id=selected_event_id)
        total_reward += award_info.get("reward_amount", 0.0)

    # 2. Thống kê Calo/Km theo tuần (12 tuần gần nhất) và tháng (6 tháng gần nhất)
    import datetime
    max_date_str_db = db.query(func.max(Activity.activity_date)).scalar()
    if max_date_str_db:
        try:
            max_date = datetime.datetime.strptime(max_date_str_db, "%Y-%m-%d").date()
        except Exception:
            max_date = datetime.date.today()
    else:
        max_date = datetime.date.today()
    max_date_str = max_date.strftime("%Y-%m-%d")

    metric = "kcal"
    if selected_event and getattr(selected_event, "ranking_metric", "kcal") == "distance":
        metric = "distance"

    # A. Tính theo tuần (12 tuần gần nhất)
    weekly_data = {}  # Monday_date_str -> total_val
    max_date_monday = max_date - datetime.timedelta(days=max_date.weekday())
    for i in range(12):
        w_monday = max_date_monday - datetime.timedelta(weeks=i)
        weekly_data[w_monday.strftime("%Y-%m-%d")] = 0.0

    start_week_date = max_date_monday - datetime.timedelta(weeks=11)
    start_week_date_str = start_week_date.strftime("%Y-%m-%d")
    
    week_query = db.query(Activity.activity_date, Activity.kcal_burned, Activity.distance_km)\
        .filter(Activity.activity_date >= start_week_date_str)\
        .filter(Activity.activity_date <= max_date_str)
    if selected_event_id:
        week_query = week_query.filter(Activity.event_id == selected_event_id)
        if allowed_sports and "All" not in allowed_sports:
            week_query = week_query.filter(Activity.sport_type.in_(allowed_sports))
    week_activities = week_query.all()

    for act_date_str, kcal, dist in week_activities:
        try:
            val = dist if metric == "distance" else kcal
            act_date = datetime.datetime.strptime(act_date_str, "%Y-%m-%d").date()
            act_monday = act_date - datetime.timedelta(days=act_date.weekday())
            act_monday_str = act_monday.strftime("%Y-%m-%d")
            if act_monday_str in weekly_data:
                weekly_data[act_monday_str] += val
        except Exception:
            continue

    sorted_weeks = sorted(weekly_data.keys())
    weekly_labels = []
    for w in sorted_weeks:
        d = datetime.datetime.strptime(w, "%Y-%m-%d").date()
        weekly_labels.append(d.strftime("Tuần %d/%m"))
    weekly_kcal = [round(weekly_data[w], 1) for w in sorted_weeks]

    # B. Tính theo tháng (6 tháng gần nhất)
    monthly_data = {}  # YYYY-MM -> total_val
    curr_year = max_date.year
    curr_month = max_date.month
    for i in range(6):
        m = curr_month - i
        y = curr_year
        while m <= 0:
            m += 12
            y -= 1
        monthly_data[f"{y:04d}-{m:02d}"] = 0.0

    sorted_months_keys = sorted(monthly_data.keys())
    start_month_str = sorted_months_keys[0]
    start_month_date_str = f"{start_month_str}-01"

    month_query = db.query(Activity.activity_date, Activity.kcal_burned, Activity.distance_km)\
        .filter(Activity.activity_date >= start_month_date_str)\
        .filter(Activity.activity_date <= max_date_str)
    if selected_event_id:
        month_query = month_query.filter(Activity.event_id == selected_event_id)
        if allowed_sports and "All" not in allowed_sports:
            month_query = month_query.filter(Activity.sport_type.in_(allowed_sports))
    month_activities = month_query.all()

    for act_date_str, kcal, dist in month_activities:
        try:
            val = dist if metric == "distance" else kcal
            ym = act_date_str[:7]
            if ym in monthly_data:
                monthly_data[ym] += val
        except Exception:
            continue

    monthly_labels = []
    for ym in sorted_months_keys:
        y, m = ym.split("-")
        monthly_labels.append(f"Tháng {m}/{y}")
    monthly_kcal = [round(monthly_data[ym], 1) for ym in sorted_months_keys]

    # 3. Cơ cấu hoạt động theo bộ môn (Sport Type Distribution)
    sport_query = db.query(
        Activity.sport_type,
        func.count(Activity.id).label("count"),
        func.sum(Activity.kcal_burned).label("kcal"),
        func.sum(Activity.distance_km).label("dist")
    )
    if selected_event_id:
        sport_query = sport_query.filter(Activity.event_id == selected_event_id)
        if allowed_sports and "All" not in allowed_sports:
            sport_query = sport_query.filter(Activity.sport_type.in_(allowed_sports))
    sport_stats = sport_query.group_by(Activity.sport_type).all()

    sport_labels = []
    sport_kcal = []
    sport_count = []
    sport_dist = []
    for stat in sport_stats:
        sport_labels.append(stat.sport_type)
        sport_kcal.append(round(stat.kcal or 0, 1))
        sport_count.append(stat.count or 0)
        sport_dist.append(round(stat.dist or 0, 1))

    stats_data = {
        "metric": metric,
        "kpis": {
            "total_athletes": total_active_athletes,
            "total_activities": total_valid_activities,
            "total_kcal": round(total_kcal_burned, 1),
            "total_dist": round(total_distance, 1),
            "total_hours": round(total_hours, 1),
            "total_reward": total_reward
        },
        "weekly": {
            "labels": weekly_labels,
            "kcal": weekly_kcal
        },
        "monthly": {
            "labels": monthly_labels,
            "kcal": monthly_kcal
        },
        "sports": {
            "labels": sport_labels,
            "kcal": sport_kcal,
            "counts": sport_count,
            "dists": sport_dist
        }
    }

    # Lấy danh sách phòng ban động để phục vụ autocomplete
    db_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().order_by(Athlete.department).all()
    departments = [r[0] for r in db_depts] if db_depts else [
        "BAN GIÁM ĐỐC", "PHÒNG HÀNH CHÍNH NHÂN SỰ", "PHÒNG KỸ THUẬT", 
        "PHÒNG KINH DOANH", "PHÒNG TÀI CHÍNH KẾ TOÁN", "PHÒNG KHAI THÁC", "PHÒNG VẬN HÀNH"
    ]

    # Phát hiện các trường hợp trùng tên hiển thị Strava
    from collections import defaultdict
    strava_name_to_athletes = defaultdict(list)
    active_athletes = db.query(Athlete).filter(Athlete.is_active == True).all()
    for ath in active_athletes:
        if ath.strava_name:
            for part in ath.strava_name.split(","):
                cleaned = part.strip().lower()
                if cleaned:
                    if ath not in strava_name_to_athletes[cleaned]:
                        strava_name_to_athletes[cleaned].append(ath)
                        
    dup_strava_alerts = []
    for name, aths in strava_name_to_athletes.items():
        if len(aths) > 1:
            dup_strava_alerts.append({
                "strava_name": name,
                "athletes": [{"id": a.id, "full_name": a.full_name, "department": a.department or "Chưa phân phòng", "strava_name_raw": a.strava_name} for a in aths]
            })

    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "logged_in": True,
            "error": error,
            "success": success,
            "configs": configs,
            "athletes": athletes,
            "mets": mets,
            "rewards": rewards,
            "auth_url": auth_url,
            "unlinked_athletes": unlinked_athletes,
            "badges": badges,
            "archived_events": archived_events,
            "stats_data": stats_data,
            "departments": departments,
            "all_competitions": all_competitions,
            "selected_event_id": selected_event_id,
            "time_stamp": int(time.time()),
            "dup_strava_alerts": dup_strava_alerts
        }
    )

@app.post("/admin/login")
def admin_login(username: str = Form(...), password: str = Form(...), db: Session = Depends(get_db)):
    """Xử lý đăng nhập Admin."""
    admin_user = db.query(Config).filter(Config.key == "admin_username").first()
    admin_pass = db.query(Config).filter(Config.key == "admin_password_hash").first()

    if not admin_user or not admin_pass:
        return RedirectResponse("/admin?error=He thong chua duoc khoi tao", status_code=303)

    if username == admin_user.value and verify_password(password, admin_pass.value):
        # Thiết lập session token động
        import uuid
        import time
        session_token = uuid.uuid4().hex
        expiry_time = int(time.time()) + (86400 * 7) # Hết hạn sau 7 ngày

        update_config(db, "admin_session_id", session_token)
        update_config(db, "admin_session_expiry", str(expiry_time))

        response = RedirectResponse("/admin", status_code=303)
        response.set_cookie(key=COOKIE_NAME, value=session_token, max_age=86400 * 7, httponly=True)
        return response
    else:
        return RedirectResponse("/admin?error=Sai ten dang nhap hoac mat khau", status_code=303)

@app.post("/admin/logout")
def admin_logout(db: Session = Depends(get_db)):
    """Xử lý đăng xuất Admin."""
    update_config(db, "admin_session_id", "")
    update_config(db, "admin_session_expiry", "0")
    response = RedirectResponse("/admin", status_code=303)
    response.delete_cookie(key=COOKIE_NAME)
    return response

@app.post("/admin/config")
async def update_configs(
    request: Request,
    strava_client_id: str = Form(...),
    strava_client_secret: str = Form(...),
    strava_club_id: str = Form(...),
    sync_interval_hours: int = Form(...),
    sync_method: str = Form("api"),
    strava_cookie: str = Form(""),
    user_auth_banner_show: str = Form("false"),
    user_auth_banner_text: str = Form(""),
    user_auth_popup_show: str = Form("true"),
    user_auth_popup_title: str = Form(""),
    user_auth_popup_desc: str = Form(""),
    user_auth_popup_cooldown: str = Form("12"),
    rules_title: str = Form(...),
    rules_version: str = Form(...),
    rules_description: str = Form(...),
    rules_banner_text: str = Form(...),
    rules_general_text: str = Form(...),
    banner_file: UploadFile = File(None),
    group_qr_file: UploadFile = File(None),
    zalo_group_qr_file: UploadFile = File(None),
    rules_banner_mode: str = Form("version"),
    rules_banner_reset_days: str = Form("1"),
    apply_to_event_id: str = Form("active"),
    # Quy tắc chống gian lận
    rule_run_pace_min: str = Form(...),
    rule_run_pace_max: str = Form(...),
    rule_run_elev_ratio: str = Form(...),
    rule_ride_pace_min: str = Form(...),
    rule_ride_pace_max: str = Form(...),
    rule_ride_elev_ratio: str = Form(...),
    rule_walk_pace_min: str = Form(...),
    rule_walk_pace_max: str = Form(...),
    rule_walk_elev_ratio: str = Form(...),
    db: Session = Depends(get_db)
):
    # Xác thực quyền admin
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)

    try:
        # Xác định giải đấu để đồng bộ cấu hình quy chế & banner
        target_event = None
        if apply_to_event_id and apply_to_event_id.strip() != "active":
            try:
                target_event_id = int(apply_to_event_id.strip())
                target_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == target_event_id).first()
            except ValueError:
                pass
                
        if not target_event:
            # Fallback tìm giải đấu đang hoạt động mới (ID != 1) để đồng bộ cấu hình quy chế & banner
            target_event = db.query(CompetitionEvent).filter(
                CompetitionEvent.is_active == True,
                CompetitionEvent.id != 1
            ).order_by(CompetitionEvent.id.desc()).first()

        club_id_extracted = extract_strava_club_id(strava_club_id)
        
        # Tự động phát hiện đổi Client ID để reset token cũ của Admin (buộc Admin kết nối lại với App mới)
        old_client_id_conf = db.query(Config).filter(Config.key == "strava_client_id").first()
        old_client_id = old_client_id_conf.value if old_client_id_conf else ""
        if old_client_id and old_client_id.strip() != strava_client_id.strip():
            print(f"API Change Detected: Client ID changed from {old_client_id} to {strava_client_id}. Resetting Admin tokens...")
            update_config(db, "strava_access_token", "")
            update_config(db, "strava_refresh_token", "")
            update_config(db, "strava_expires_at", "0")
            db.commit()

        update_config(db, "strava_client_id", strava_client_id)
        update_config(db, "strava_client_secret", strava_client_secret)
        update_config(db, "strava_club_id", club_id_extracted)
        update_config(db, "sync_method", sync_method)
        update_config(db, "strava_cookie", strava_cookie.strip())
        update_config(db, "user_auth_banner_show", user_auth_banner_show)
        update_config(db, "user_auth_banner_text", user_auth_banner_text.strip())
        update_config(db, "user_auth_popup_show", user_auth_popup_show)
        update_config(db, "user_auth_popup_title", user_auth_popup_title.strip())
        update_config(db, "user_auth_popup_desc", user_auth_popup_desc.strip())
        update_config(db, "user_auth_popup_cooldown", user_auth_popup_cooldown)
        
        
        
        # Nếu thay đổi tần suất đồng bộ, cần cập nhật lại Scheduler
        old_interval = db.query(Config).filter(Config.key == "sync_interval_hours").first()
        old_val = int(old_interval.value) if old_interval else 1
        
        update_config(db, "sync_interval_hours", str(sync_interval_hours))
        
        # Cập nhật thông tin quy chế và banner
        update_config(db, "rules_title", rules_title.strip())
        update_config(db, "rules_version", rules_version.strip())
        update_config(db, "rules_description", rules_description.strip())
        update_config(db, "rules_banner_text", rules_banner_text.strip())
        update_config(db, "rules_general_text", rules_general_text.strip())
        update_config(db, "rules_banner_mode", rules_banner_mode.strip())
        update_config(db, "rules_banner_reset_days", rules_banner_reset_days.strip())
        
        if target_event:
            target_event.title = rules_title.strip()
            target_event.rules_description = rules_description.strip()
            target_event.rules_banner_text = rules_banner_text.strip()
            target_event.rules_general_text = rules_general_text.strip()
        
        # Xử lý upload ảnh banner tùy chỉnh
        if banner_file and banner_file.filename:
            ext = os.path.splitext(banner_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                filename = f"banner_{int(time.time())}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                
                # Lưu file ảnh mới
                with open(file_path, "wb") as f:
                    content = await banner_file.read()
                    f.write(content)
                
                # Xóa file cũ của target_event (nếu có) hoặc config chung để giải phóng dung lượng
                if target_event and target_event.banner_image:
                    old_path = target_event.banner_image.lstrip("/")
                    if os.path.exists(old_path) and "static/uploads/" in old_path:
                        try:
                            os.remove(old_path)
                        except Exception as ex:
                            print(f"Error removing old event banner file: {ex}")
                else:
                    old_banner = db.query(Config).filter(Config.key == "rules_banner_image").first()
                    if old_banner and old_banner.value:
                        old_path = old_banner.value.lstrip("/")
                        if os.path.exists(old_path) and "static/uploads/" in old_path:
                            try:
                                os.remove(old_path)
                            except Exception as ex:
                                print(f"Error removing old banner file: {ex}")
                
                # Lưu đường dẫn vào database
                update_config(db, "rules_banner_image", f"/static/uploads/{filename}")
                if target_event:
                    target_event.banner_image = f"/static/uploads/{filename}"
        
        # Xử lý upload ảnh QR group tùy chỉnh
        if group_qr_file and group_qr_file.filename:
            ext = os.path.splitext(group_qr_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                filename = f"group_qr_{int(time.time())}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                
                # Lưu file ảnh mới
                with open(file_path, "wb") as f:
                    content = await group_qr_file.read()
                    f.write(content)
                
                # Xóa file cũ của target_event (nếu có) hoặc config chung để giải phóng dung lượng
                if target_event and target_event.rules_group_qr:
                    old_path = target_event.rules_group_qr.lstrip("/")
                    if os.path.exists(old_path) and "static/uploads/" in old_path:
                        try:
                            os.remove(old_path)
                        except Exception as ex:
                            print(f"Error removing old event QR file: {ex}")
                else:
                    old_qr = db.query(Config).filter(Config.key == "rules_group_qr").first()
                    if old_qr and old_qr.value:
                        old_path = old_qr.value.lstrip("/")
                        if os.path.exists(old_path) and "static/uploads/" in old_path:
                            try:
                                os.remove(old_path)
                            except Exception as ex:
                                print(f"Error removing old QR file: {ex}")
                
                # Lưu đường dẫn vào database
                update_config(db, "rules_group_qr", f"/static/uploads/{filename}")
                if target_event:
                    target_event.rules_group_qr = f"/static/uploads/{filename}"
                    
        # Xử lý upload ảnh QR Group Zalo tùy chỉnh
        if zalo_group_qr_file and zalo_group_qr_file.filename:
            ext = os.path.splitext(zalo_group_qr_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                filename = f"zalo_group_qr_{int(time.time())}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                
                with open(file_path, "wb") as f:
                    content = await zalo_group_qr_file.read()
                    f.write(content)
                
                # Xóa file Zalo QR cũ
                old_zalo_qr = db.query(Config).filter(Config.key == "zalo_group_qr").first()
                if old_zalo_qr and old_zalo_qr.value:
                    old_path = old_zalo_qr.value.lstrip("/")
                    if os.path.exists(old_path) and "static/uploads/" in old_path:
                        try:
                            os.remove(old_path)
                        except Exception as ex:
                            print(f"Error removing old Zalo QR file: {ex}")
                            
                update_config(db, "zalo_group_qr", f"/static/uploads/{filename}")
        
        # Cập nhật quy tắc gian lận
        update_config(db, "rule_run_pace_min", rule_run_pace_min)
        update_config(db, "rule_run_pace_max", rule_run_pace_max)
        update_config(db, "rule_run_elev_ratio", rule_run_elev_ratio)
        update_config(db, "rule_ride_pace_min", rule_ride_pace_min)
        update_config(db, "rule_ride_pace_max", rule_ride_pace_max)
        update_config(db, "rule_ride_elev_ratio", rule_ride_elev_ratio)
        update_config(db, "rule_walk_pace_min", rule_walk_pace_min)
        update_config(db, "rule_walk_pace_max", rule_walk_pace_max)
        update_config(db, "rule_walk_elev_ratio", rule_walk_elev_ratio)

        # Cập nhật cấu hình hiển thị cột của BXH Cá nhân
        form_data = await request.form()
        show_col_gender = "true" if form_data.get("show_col_gender") == "on" else "false"
        show_col_dept = "true" if form_data.get("show_col_dept") == "on" else "false"
        show_col_dist = "true" if form_data.get("show_col_dist") == "on" else "false"
        show_col_time = "true" if form_data.get("show_col_time") == "on" else "false"
        show_col_award = "true" if form_data.get("show_col_award") == "on" else "false"
        
        update_config(db, "show_col_gender", show_col_gender)
        update_config(db, "show_col_dept", show_col_dept)
        update_config(db, "show_col_dist", show_col_dist)
        update_config(db, "show_col_time", show_col_time)
        update_config(db, "show_col_award", show_col_award)

        if old_val != sync_interval_hours:
            start_scheduler()

        return RedirectResponse("/admin?success=Cap nhat cau hinh thanh cong#tab-config", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error=Loi khi luu cau hinh: {str(e)}#tab-config", status_code=303)

@app.post("/admin/config/avatar-frame")
async def update_avatar_frame(
    request: Request,
    global_avatar_frame: UploadFile = File(...),
    frame_remove_bg: str = Form("false"),
    db: Session = Depends(get_db)
):
    """API upload khung viền avatar chung hệ thống (nằm trên Form độc lập)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    if not global_avatar_frame or not global_avatar_frame.filename:
        return RedirectResponse("/admin?error=Vui long chon file khung vien#tab-config", status_code=303)
        
    try:
        ext = os.path.splitext(global_avatar_frame.filename)[1].lower()
        if ext not in [".png", ".jpg", ".jpeg", ".webp"]:
            return RedirectResponse("/admin?error=Dinh dang anh khong hop le (ho tro PNG, JPG, WEBP)#tab-config", status_code=303)
            
        # Đọc nội dung file ảnh tải lên
        content = await global_avatar_frame.read()
        
        # Nếu được yêu cầu tự động tách nền bằng AI (rìa ngoài)
        if frame_remove_bg in ["on", "true"]:
            try:
                from rembg import remove
                content = remove(content)
                ext = ".png"
            except Exception as rembg_ex:
                print(f"Error removing bg for frame: {rembg_ex}")
                
        # 1. Lưu file ảnh gốc chưa đục lỗ lòng trong (Raw) trước để dùng cho đục lỗ động ở client
        timestamp = int(time.time())
        filename_raw = f"frame_raw_{timestamp}{ext}"
        upload_dir = "static/uploads"
        os.makedirs(upload_dir, exist_ok=True)
        file_path_raw = os.path.join(upload_dir, filename_raw)
        
        with open(file_path_raw, "wb") as f:
            f.write(content)
            
        # Xóa file raw cũ nếu có
        old_frame_raw = db.query(Config).filter(Config.key == "global_avatar_frame_raw").first()
        if old_frame_raw and old_frame_raw.value:
            old_path_raw = old_frame_raw.value.lstrip("/")
            if os.path.exists(old_path_raw) and "static/uploads/" in old_path_raw:
                try:
                    if old_path_raw != "static/uploads/frame_raw.png":
                        os.remove(old_path_raw)
                except Exception as ex:
                    print(f"Error removing old global raw frame file: {ex}")
                    
        new_frame_raw_url = f"/static/uploads/{filename_raw}"
        update_config(db, "global_avatar_frame_raw", new_frame_raw_url)
        
        # Đồng thời copy đè vào static/uploads/frame_raw.png làm mặc định
        try:
            import shutil
            shutil.copyfile(file_path_raw, "static/uploads/frame_raw.png")
        except Exception as ex:
            print(f"Error copying to default frame_raw.png: {ex}")

        # 2. Đục lỗ lòng trong tĩnh mặc định (scale=0.65) làm fallback tương thích ngược
        content_punched = content
        try:
            from io import BytesIO
            from PIL import Image
            img = Image.open(BytesIO(content))
            processed_img = duc_lo_frame_neu_duc(
                img, 
                scale=0.65, 
                offset_x=0.0, 
                offset_y=0.0
            )
            out_buf = BytesIO()
            processed_img.save(out_buf, format="PNG")
            content_punched = out_buf.getvalue()
            ext = ".png" # Định dạng PNG hỗ trợ kênh trong suốt
        except Exception as img_ex:
            print(f"Error checking/punching hole for fallback frame: {img_ex}")
            
        filename_punched = f"frame_{timestamp}{ext}"
        file_path_punched = os.path.join(upload_dir, filename_punched)
        
        with open(file_path_punched, "wb") as f:
            f.write(content_punched)
            
        # Xóa file đục lỗ cũ nếu có
        old_frame = db.query(Config).filter(Config.key == "global_avatar_frame").first()
        if old_frame and old_frame.value:
            old_path = old_frame.value.lstrip("/")
            if os.path.exists(old_path) and "static/uploads/" in old_path:
                try:
                    if old_path != "static/uploads/frame.png":
                        os.remove(old_path)
                except Exception as ex:
                    print(f"Error removing old global frame file: {ex}")
                    
        new_frame_url = f"/static/uploads/{filename_punched}"
        update_config(db, "global_avatar_frame", new_frame_url)
        
        # Đồng thời copy đè vào static/uploads/frame.png
        try:
            shutil.copyfile(file_path_punched, "static/uploads/frame.png")
        except Exception as ex:
            print(f"Error copying to default frame.png: {ex}")
            
        db.commit()
        return RedirectResponse("/admin?success=Cap nhat khung vien avatar thanh cong#tab-config", status_code=303)
    except Exception as e:
        db.rollback()
        print(f"Error updating avatar frame: {e}")
        return RedirectResponse(f"/admin?error=Loi khi luu khung vien: {str(e)}#tab-config", status_code=303)

@app.get("/admin/api/competition-rules/{event_id}")
def api_get_competition_rules(event_id: str, request: Request, db: Session = Depends(get_db)):
    """API lấy thông tin cấu hình quy chế & banner của một giải đấu cụ thể (hoặc mặc định)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    configs = get_config_dict(db)
    
    # Nếu là giải đấu mặc định (đang hoạt động) hoặc "active"
    if event_id == "active":
        # Ưu tiên lấy QR code từ giải đấu đang hoạt động
        active_event = db.query(CompetitionEvent).filter(
            CompetitionEvent.is_active == True,
            CompetitionEvent.id != 1
        ).order_by(CompetitionEvent.id.desc()).first()
        
        group_qr = configs.get("rules_group_qr", "")
        if active_event and active_event.rules_group_qr:
            group_qr = active_event.rules_group_qr
            
        return JSONResponse(content={
            "title": configs.get("rules_title", ""),
            "rules_description": configs.get("rules_description", ""),
            "rules_banner_text": configs.get("rules_banner_text", ""),
            "rules_general_text": configs.get("rules_general_text", ""),
            "banner_image": configs.get("rules_banner_image", ""),
            "rules_version": configs.get("rules_version", ""),
            "rules_banner_mode": configs.get("rules_banner_mode", "version"),
            "rules_banner_reset_days": configs.get("rules_banner_reset_days", "1"),
            "rules_group_qr": group_qr,
            "strava_club_id": (active_event.strava_club_id if active_event else "") or configs.get("strava_club_id", "")
        })
        
    try:
        eid = int(event_id)
        comp = db.query(CompetitionEvent).filter(CompetitionEvent.id == eid).first()
        if not comp:
            return JSONResponse(status_code=404, content={"error": "Không tìm thấy giải đấu"})
            
        return JSONResponse(content={
            "title": comp.title or "",
            "rules_description": comp.rules_description or "",
            "rules_banner_text": comp.rules_banner_text or "",
            "rules_general_text": comp.rules_general_text or "",
            "banner_image": comp.banner_image or "",
            "rules_version": configs.get("rules_version", ""),
            "rules_banner_mode": configs.get("rules_banner_mode", "version"),
            "rules_banner_reset_days": configs.get("rules_banner_reset_days", "1"),
            "rules_group_qr": comp.rules_group_qr or configs.get("rules_group_qr", ""),
            "strava_club_id": comp.strava_club_id or configs.get("strava_club_id", "")
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/admin/security")
def update_admin_security(
    request: Request,
    new_username: str = Form(...),
    new_password: str = Form(...),
    db: Session = Depends(get_db)
):
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    new_username = new_username.strip()
    if not new_username or not new_password.strip():
        return RedirectResponse("/admin?error=Tên đăng nhập hoặc mật khẩu không hợp lệ", status_code=303)
        
    try:
        update_config(db, "admin_username", new_username)
        update_config(db, "admin_password_hash", hash_password(new_password))
        
        # Buộc đăng xuất để đăng nhập lại bằng thông tin mới
        response = RedirectResponse("/admin?success=Cập nhật tài khoản Admin thành công. Vui lòng đăng nhập lại.", status_code=303)
        response.delete_cookie(key=COOKIE_NAME)
        return response
    except Exception as e:
        return RedirectResponse(f"/admin?error=Lỗi cập nhật tài khoản: {str(e)}", status_code=303)

@app.get("/connect-existing", response_class=HTMLResponse)
def connect_existing_page(request: Request, error: Optional[str] = None, db: Session = Depends(get_db)):
    """Trang liên kết Strava cho VĐV đã đăng ký từ trước."""
    configs = get_config_dict(db)
    # Lấy danh sách VĐV chưa liên kết (chưa có refresh_token)
    athletes = db.query(Athlete).filter(
        (Athlete.strava_refresh_token == None) | (Athlete.strava_refresh_token == '')
    ).order_by(Athlete.full_name).all()
    
    return templates.TemplateResponse(
        request=request,
        name="connect_existing.html",
        context={
            "configs": configs,
            "athletes": athletes,
            "error": error
        }
    )

@app.post("/connect-existing")
def connect_existing_athlete(
    request: Request,
    athlete_id: int = Form(...),
    db: Session = Depends(get_db)
):
    """Xử lý yêu cầu liên kết Strava, chuyển hướng VĐV sang trang OAuth."""
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/connect-existing?error=Không tìm thấy VĐV", status_code=303)
        
    configs = get_config_dict(db)
    client_id = configs.get("strava_client_id")
    if not client_id:
        return RedirectResponse("/connect-existing?error=Hệ thống chưa cấu hình Strava Client ID", status_code=303)
        
    app_url = APP_URL
    if not app_url:
        host = request.headers.get("host", "localhost:8080")
        scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
        app_url = f"{scheme}://{host}"
        
    redirect_uri = f"{app_url}/exchange_user_token"
    auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=activity:read_all,profile:read_all&state={athlete_id}"
    
    return RedirectResponse(auth_url, status_code=303)

@app.get("/exchange_user_token")
def exchange_user_token(
    request: Request,
    code: str = None,
    state: str = None,
    error: str = None,
    db: Session = Depends(get_db)
):
    """Endpoint nhận callback từ Strava OAuth và lưu token cho VĐV."""
    if error:
        return RedirectResponse(f"/connect-existing?error=Lỗi ủy quyền từ Strava: {error}", status_code=303)
    if not code or not state:
        return RedirectResponse("/connect-existing?error=Thông tin xác thực không hợp lệ", status_code=303)
        
    try:
        athlete_id = int(state)
    except ValueError:
        return RedirectResponse("/connect-existing?error=ID vận động viên không hợp lệ", status_code=303)
        
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/connect-existing?error=Vận động viên không tồn tại", status_code=303)
        
    configs = get_config_dict(db)
    client_id = configs.get("strava_client_id")
    client_secret = configs.get("strava_client_secret")
    
    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code"
        }, timeout=10)
        response.raise_for_status()
        token_data = response.json()
        
        # Lưu token cá nhân vào database
        athlete.strava_access_token = token_data["access_token"]
        athlete.strava_refresh_token = token_data["refresh_token"]
        athlete.strava_expires_at = str(token_data["expires_at"])
        
        # Cập nhật thêm thông tin ID tài khoản Strava và ảnh đại diện
        strava_athlete_data = token_data.get("athlete") or {}
        strava_id = strava_athlete_data.get("id")
        if strava_id:
            athlete.strava_athlete_id = str(strava_id)
            
        profile_url = strava_athlete_data.get("profile")
        if profile_url and "avatar/athlete" not in profile_url:
            athlete.avatar_url = profile_url
            
        db.commit()
        
        # Đồng bộ và thay thế tức thì dữ liệu cào Club bằng API cá nhân cho VĐV vừa liên kết
        try:
            from backend.sync_engine import sync_single_athlete_all_events
            sync_single_athlete_all_events(db, athlete)
        except Exception as sync_err:
            print(f"Error triggering instant sync for athlete {athlete.id}: {sync_err}")
        
        # Chuyển hướng VĐV về trang cá nhân của họ kèm thông báo thành công
        return RedirectResponse(f"/profile/{athlete.id}?success=Đã liên kết tài khoản Strava thành công!", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/connect-existing?error=Lỗi khi kết nối tài khoản: {str(e)}", status_code=303)

@app.get("/exchange_token")
def exchange_token(request: Request, code: str = None, error: str = None, db: Session = Depends(get_db)):
    """
    Endpoint tiếp nhận mã chuyển hướng OAuth từ Strava.
    """
    if error:
        return RedirectResponse(f"/admin?error=Loi xac thuc Strava: {error}", status_code=303)
    if not code:
        return RedirectResponse("/admin?error=Khong co Authorization Code tu Strava", status_code=303)

    configs = get_config_dict(db)
    client_id = configs.get("strava_client_id")
    client_secret = configs.get("strava_client_secret")

    try:
        response = requests.post("https://www.strava.com/oauth/token", data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code"
        }, timeout=10)
        response.raise_for_status()
        token_data = response.json()

        # Lưu token trả về vào DB
        update_config(db, "strava_access_token", token_data["access_token"])
        update_config(db, "strava_refresh_token", token_data["refresh_token"])
        update_config(db, "strava_expires_at", str(token_data["expires_at"]))

        return RedirectResponse("/admin?success=Ket noi Strava thanh cong. San sang dong bo du lieu!", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error=Loi khi trao doi code lay Token: {str(e)}", status_code=303)

@app.post("/admin/sync")
def trigger_sync(request: Request, db: Session = Depends(get_db)):
    """API kích hoạt đồng bộ thủ công từ trang admin."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    res = sync_club_activities()
    
    # Tự động dọn dẹp hoạt động trùng lặp sau khi đồng bộ thủ công thành công
    if res.get("status") in ("success", "partial"):
        try:
            deduplicate_activities_logic(db)
        except Exception as e:
            print(f"Manual Sync: Error during auto deduplication: {e}")
            
    return JSONResponse(content=res)

@app.post("/admin/fix-timezone")
def fix_timezone_endpoint(request: Request, db: Session = Depends(get_db)):
    """API sửa đổi múi giờ UTC -> GMT+7 cho các hoạt động bị lệch."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    import datetime
    from backend.calculations import get_mets_value, calculate_kcal, get_multiplier_for_date
    from backend.sync_engine import convert_utc_to_gmt7
    
    # 1. Tìm các hoạt động cần sửa
    acts = db.query(Activity).filter(
        Activity.activity_date >= "2026-06-15",
        ~Activity.athlete_name_raw.in_(["David Schultz", "Rhiannon Bailey", "Jason Reckelhoff"])
    ).all()
    
    fixed_count = 0
    for a in acts:
        # Chỉ sửa các hoạt động do Scraper cào về (ID dạng băm SHA256 dài 64 ký tự)
        # Loại bỏ hoàn toàn các hoạt động đồng bộ bằng API Club cũ (ID số nguyên Strava ngắn)
        if len(str(a.id)) != 64:
            continue
            
        name_lower = (a.name or "").lower()
        time_str = a.activity_time
        if not time_str:
            continue
            
        try:
            h, m = map(int, time_str.split(":"))
        except ValueError:
            continue
            
        is_mismatch = False
        if ("sáng" in name_lower or "morning" in name_lower or "trưa" in name_lower or "lunch" in name_lower or "bơi" in name_lower or "walk" in name_lower or "run" in name_lower or "workout" in name_lower):
            if (17 <= h <= 23) or (0 <= h <= 4):
                is_mismatch = True
                
        if a.athlete_name_raw == "TRINH BUI VAN" and time_str == "02:58":
            is_mismatch = True
            
        if is_mismatch:
            # Cộng 7 tiếng
            old_dt_str = f"{a.activity_date} {time_str}:00"
            try:
                dt = datetime.datetime.strptime(old_dt_str, "%Y-%m-%d %H:%M:%S")
                dt_gmt7 = dt + datetime.timedelta(hours=7)
                new_date_str = dt_gmt7.strftime("%Y-%m-%d")
                new_time_str = dt_gmt7.strftime("%H:%M")
                
                a.activity_date = new_date_str
                a.activity_time = new_time_str
                
                athlete = db.query(Athlete).filter(Athlete.id == a.athlete_id).first()
                weight = athlete.weight if athlete else 60.0
                speed_kmh = 0.0
                if a.moving_time_min > 0:
                    speed_kmh = a.distance_km / (a.moving_time_min / 60.0)
                    
                mets_value = get_mets_value(a.sport_type, speed_kmh, db, a.distance_km, a.elevation_gain_m, event_id=a.event_id)
                a.mets_value = mets_value
                
                mult = get_multiplier_for_date(new_date_str, a.event_id, db)
                a.multiplier = mult
                
                if a.athlete_id is not None:
                    a.kcal_burned = calculate_kcal(mets_value, weight, a.moving_time_min, a.elevation_gain_m, a.sport_type, multiplier=mult)
                
                fixed_count += 1
            except Exception as e:
                print(f"Fix Timezone: Error fixing activity {a.id}: {e}")
                
    if fixed_count > 0:
        try:
            db.commit()
            return JSONResponse(content={"status": "success", "message": f"Sửa lệch múi giờ thành công cho {fixed_count} hoạt động."})
        except Exception as commit_err:
            db.rollback()
            return JSONResponse(status_code=500, content={"error": f"Lỗi lưu CSDL: {str(commit_err)}"})
            
    return JSONResponse(content={"status": "success", "message": "Không phát hiện hoạt động nào bị lệch múi giờ."})

@app.post("/admin/unlink-mismatched-athletes")
def unlink_mismatched_athletes(request: Request, db: Session = Depends(get_db)):
    """API quét và hủy liên kết Strava cho những VĐV có token không trùng khớp/không hợp lệ với ID/Secret hiện tại."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập quyền Admin"})
        
    configs = get_config_dict(db)
    client_id = configs.get("strava_client_id")
    client_secret = configs.get("strava_client_secret")
    
    if not client_id or not client_secret:
        return JSONResponse(status_code=400, content={"error": "Chưa cấu hình Client ID hoặc Client Secret trong hệ thống."})
        
    athletes = db.query(Athlete).filter(
        Athlete.strava_refresh_token != None,
        Athlete.strava_refresh_token != ""
    ).all()
    
    checked = 0
    unlinked = 0
    kept = 0
    
    for ath in athletes:
        checked += 1
        try:
            res = requests.post("https://www.strava.com/oauth/token", data={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "refresh_token",
                "refresh_token": ath.strava_refresh_token
            }, timeout=8)
            
            # Nếu trả về 400 Bad Request hoặc 401 Unauthorized, nghĩa là Client ID/Secret không khớp hoặc bị hết hiệu lực
            if res.status_code in [400, 401]:
                ath.strava_access_token = None
                ath.strava_refresh_token = None
                ath.strava_expires_at = None
                ath.strava_athlete_id = None
                unlinked += 1
            elif res.status_code == 200:
                # Cập nhật luôn token mới nếu thành công
                token_data = res.json()
                ath.strava_access_token = token_data.get("access_token")
                ath.strava_refresh_token = token_data.get("refresh_token")
                ath.strava_expires_at = str(token_data.get("expires_at"))
                kept += 1
            else:
                # Các lỗi khác (ví dụ: 429 rate limit, 500,...) giữ nguyên để tránh hủy nhầm khi Strava lỗi mạng
                kept += 1
        except Exception as e:
            print(f"Verify token error for {ath.full_name}: {e}")
            kept += 1
            
    try:
        db.commit()
        return JSONResponse(content={
            "status": "success",
            "message": f"Đã quét xong {checked} VĐV. Giữ lại {kept} VĐV hợp lệ. Đã hủy liên kết {unlinked} VĐV có token không trùng khớp với API hiện tại."
        })
    except Exception as commit_err:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi lưu CSDL: {str(commit_err)}"})

@app.post("/admin/cleanup-old-numeric-ids")
def cleanup_old_numeric_ids_endpoint(request: Request, db: Session = Depends(get_db)):
    """API dọn dẹp các hoạt động có ID số thuần túy cũ (chỉ dành cho Admin)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    try:
        to_delete = []
        
        # 1. Tìm các hoạt động dùng ID số cũ (từ đợt quét lỗi trước)
        all_acts = db.query(Activity).all()
        for act in all_acts:
            if act.id.isdigit() and len(act.id) < 25:
                to_delete.append(act.id)
                
        # 2. Tìm các hoạt động nằm ngoài khoảng thời gian diễn ra của giải đấu đang hoạt động
        out_of_bounds_acts = db.query(Activity).join(
            CompetitionEvent,
            Activity.event_id == CompetitionEvent.id
        ).filter(
            CompetitionEvent.is_active == True,
            (Activity.activity_date < CompetitionEvent.start_date) |
            ((CompetitionEvent.end_date != None) & (Activity.activity_date > CompetitionEvent.end_date))
        ).all()
        
        for act in out_of_bounds_acts:
            if act.id not in to_delete:
                to_delete.append(act.id)
                
        if to_delete:
            import json
            import os
            backup_file = "static/uploads/deleted_activities_backup.jsonl"
            os.makedirs(os.path.dirname(backup_file), exist_ok=True)
            
            # Ghi log backup trước khi xóa
            with open(backup_file, "a", encoding="utf-8") as f:
                for act_id in to_delete:
                    act_item = db.query(Activity).filter(Activity.id == act_id).first()
                    if act_item:
                        act_dict = {
                            "id": act_item.id,
                            "athlete_id": act_item.athlete_id,
                            "event_id": act_item.event_id,
                            "athlete_name_raw": act_item.athlete_name_raw,
                            "name": act_item.name,
                            "type": act_item.type,
                            "sport_type": act_item.sport_type,
                            "distance_km": act_item.distance_km,
                            "moving_time_min": act_item.moving_time_min,
                            "elapsed_time_min": act_item.elapsed_time_min,
                            "pace_min_km": act_item.pace_min_km,
                            "elevation_gain_m": act_item.elevation_gain_m,
                            "activity_date": act_item.activity_date,
                            "activity_time": act_item.activity_time,
                            "kcal_burned": act_item.kcal_burned,
                            "mets_value": act_item.mets_value,
                            "is_suspicious": act_item.is_suspicious,
                            "suspicion_reason": act_item.suspicion_reason,
                            "distance_km_raw": act_item.distance_km_raw,
                            "kcal_burned_raw": act_item.kcal_burned_raw,
                            "multiplier": act_item.multiplier,
                            "backup_time": datetime.utcnow().isoformat(),
                            "reason": "Dọn dẹp ID số cũ hoặc ngoài khoảng thời gian giải đấu"
                        }
                        f.write(json.dumps(act_dict, ensure_ascii=False) + "\n")
            
            # Xóa các hoạt động khỏi DB
            db.query(Activity).filter(Activity.id.in_(to_delete)).delete(synchronize_session=False)
            db.commit()
            return JSONResponse(content={"status": "success", "message": f"Đã dọn dẹp và sao lưu thành công {len(to_delete)} hoạt động (ID số cũ hoặc ngoài khoảng thời gian giải)."})
        else:
            return JSONResponse(content={"status": "success", "message": "Không phát hiện hoạt động rác hoặc sai ngày nào cần dọn dẹp."})
            
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi dọn dẹp ID cũ: {str(e)}"})

@app.get("/admin/db/backup/download")
def download_db_backup(request: Request, db: Session = Depends(get_db)):
    """API tải bản sao lưu CSDL hiện tại dành cho Admin."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    db_url = os.getenv("DATABASE_URL", "sqlite:///SSO_HC.db")
    db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else "SSO_HC.db"
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail=f"File co so du lieu khong ton tai tai {db_path}")
        
    import shutil
    os.makedirs("static/uploads", exist_ok=True)
    backup_temp_path = "static/uploads/SSO_HC_temp_backup.db"
    try:
        shutil.copyfile(db_path, backup_temp_path)
        from fastapi.responses import FileResponse
        return FileResponse(
            path=backup_temp_path,
            filename=f"SSO_HC_backup_{APP_VERSION}_{int(time.time())}.db",
            media_type="application/octet-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Loi khi tao ban sao luu: {str(e)}")

# --- QUẢN LÝ VẬN ĐỘNG VIÊN TRÊN ADMIN ---

@app.post("/admin/athlete/add")
def admin_add_athlete(
    request: Request,
    full_name: str = Form(...),
    gender: str = Form(...),
    department: str = Form(...),
    weight: float = Form(...),
    strava_name: str = Form(...),
    event_id: Optional[int] = Form(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    full_name = full_name.strip()
    strava_name = strava_name.strip()
    
    # Kiểm tra xem tên Strava đã được đăng ký chưa (hỗ trợ nhiều tên cách nhau bằng dấu phẩy)
    new_names = [n.strip().lower() for n in strava_name.split(",") if n.strip()]
    exists = None
    athletes = db.query(Athlete).all()
    for a in athletes:
        if a.strava_name:
            existing_names = [n.strip().lower() for n in a.strava_name.split(",") if n.strip()]
            if set(new_names) & set(existing_names):
                exists = a
                break
    if exists:
        return RedirectResponse(f"/admin?error=Ten Strava {strava_name} da ton tai", status_code=303)
        
    athlete = Athlete(
        full_name=full_name,
        gender=gender,
        department=department,
        weight=weight,
        strava_name=strava_name,
        is_active=True
    )
    db.add(athlete)
    db.commit()
    db.refresh(athlete)
    
    if event_id:
        reg = CompetitionRegistration(athlete_id=athlete.id, event_id=event_id)
        db.add(reg)
        db.commit()
        
    link_unlinked_activities(db, athlete)
    
    return RedirectResponse(f"/admin?success=Them thanh vien moi thanh cong&event_id={event_id or ''}#tab-athletes", status_code=303)

@app.post("/admin/athlete/edit/{athlete_id}")
def admin_edit_athlete(
    athlete_id: int,
    request: Request,
    full_name: str = Form(...),
    gender: str = Form(...),
    department: str = Form(...),
    weight: float = Form(...),
    strava_name: str = Form(...),
    is_active: bool = Form(True),
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/admin?error=Khong tim thay thanh vien", status_code=303)
        
    full_name = full_name.strip()
    strava_name = strava_name.strip()
    
    # Kiểm tra trùng strava_name với người khác (hỗ trợ nhiều tên cách nhau bằng dấu phẩy)
    new_names = [n.strip().lower() for n in strava_name.split(",") if n.strip()]
    exists = None
    athletes = db.query(Athlete).filter(Athlete.id != athlete_id).all()
    for a in athletes:
        if a.strava_name:
            existing_names = [n.strip().lower() for n in a.strava_name.split(",") if n.strip()]
            if set(new_names) & set(existing_names):
                exists = a
                break
    if exists:
        return RedirectResponse(f"/admin?error=Ten Strava {strava_name} da bi trung&event_id={event_id or ''}#tab-athletes", status_code=303)
        
    try:
        # Nếu thay đổi strava_name hoặc cân nặng, cần tính toán lại hoạt động cũ
        recalculate = (athlete.strava_name != strava_name or athlete.weight != weight)
        
        athlete.full_name = full_name
        athlete.gender = gender
        athlete.department = department
        athlete.weight = weight
        athlete.strava_name = strava_name
        athlete.is_active = is_active
        db.commit()
        
        if recalculate:
            # Liên kết lại và tính toán lại KCAL
            link_unlinked_activities(db, athlete)
            # Quét lại toàn bộ hoạt động hiện tại của VĐV để cập nhật lại KCAL theo cân nặng mới
            acts = db.query(Activity).filter(Activity.athlete_id == athlete.id).all()
            for act in acts:
                dist_raw = act.distance_km_raw if act.distance_km_raw is not None else act.distance_km
                speed_kmh = 0.0
                if act.moving_time_min > 0:
                    speed_kmh = dist_raw / (act.moving_time_min / 60.0)
                actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
                
                from backend.calculations import get_mets_value, calculate_kcal
                mets_val = get_mets_value(act.sport_type, speed_kmh, db, dist_raw, act.elevation_gain_m, event_id=act.event_id)
                act.mets_value = mets_val
                mult = get_multiplier_for_date(act.activity_date, act.event_id, db)
                kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m, act.sport_type)
                act.kcal_burned_raw = kcal_raw
                act.kcal_burned = round(kcal_raw * mult)
                act.multiplier = mult
                act.distance_km_raw = dist_raw
                act.distance_km = round(dist_raw * mult, 2)
            db.commit()
            
        return RedirectResponse(f"/admin?success=Cap nhat thanh vien thanh cong&event_id={event_id or ''}#tab-athletes", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error=Loi khi cap nhat thanh vien: {str(e)}&event_id={event_id or ''}#tab-athletes", status_code=303)

@app.post("/admin/athlete/delete/{athlete_id}")
def admin_delete_athlete(
    athlete_id: int,
    request: Request,
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/admin?error=Khong tim thay thanh vien", status_code=303)
        
    try:
        parsed_event_id = None
        if event_id and event_id.strip():
            try:
                parsed_event_id = int(event_id)
            except ValueError:
                pass
                
        if parsed_event_id:
            # 1. Hủy liên kết hoạt động của VĐV trong GIẢI ĐẤU NÀY
            db.query(Activity).filter(
                Activity.athlete_id == athlete_id,
                Activity.event_id == parsed_event_id
            ).update({Activity.athlete_id: None})
            
            # 2. Xóa bản ghi đăng ký của VĐV trong giải đấu này
            db.query(CompetitionRegistration).filter(
                CompetitionRegistration.athlete_id == athlete_id,
                CompetitionRegistration.event_id == parsed_event_id
            ).delete()
            
            # 3. Kiểm tra xem VĐV có còn đăng ký giải đấu nào khác không
            remaining_regs = db.query(CompetitionRegistration).filter(
                CompetitionRegistration.athlete_id == athlete_id
            ).count()
            
            # Nếu không còn đăng ký giải đấu nào khác, xóa hoàn toàn tài khoản VĐV
            if remaining_regs == 0:
                db.delete(athlete)
        else:
            # Xóa toàn bộ (toàn cục) khi không có giải đấu cụ thể được chọn
            db.query(Activity).filter(Activity.athlete_id == athlete_id).update({Activity.athlete_id: None})
            # Xóa sạch các đăng ký của VĐV này trong các giải đấu trước khi xóa tài khoản VĐV
            db.query(CompetitionRegistration).filter(CompetitionRegistration.athlete_id == athlete_id).delete()
            db.delete(athlete)
            
        db.commit()
        return RedirectResponse(f"/admin?success=Da xoa thanh vien khoi giai chay&event_id={event_id or ''}#tab-athletes", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi khi xoa: {str(e)}&event_id={event_id or ''}#tab-athletes", status_code=303)

@app.post("/admin/athlete/bulk-update-department")
def bulk_update_department(
    request: Request,
    old_department: str = Form(...),
    new_department: str = Form(...),
    event_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    old_dept = old_department.strip()
    new_dept = new_department.strip()
    
    if not old_dept or not new_dept:
        return RedirectResponse(f"/admin?error=Phòng ban cũ và mới không được trống&event_id={event_id or ''}#tab-athletes", status_code=303)
        
    try:
        query = db.query(Athlete)
        
        target_event_id = None
        if event_id and event_id.strip():
            try:
                target_event_id = int(event_id.strip())
            except ValueError:
                pass
                
        if not target_event_id:
            return RedirectResponse(f"/admin?error=Vui lòng chọn một giải đấu cụ thể để thực hiện chuyển phòng ban hàng loạt nhằm tránh ảnh hưởng đến các giải đấu khác&event_id={event_id or ''}#tab-athletes", status_code=303)
            
        # Lọc chính xác VĐV thuộc giải đấu và phòng ban được chọn
        athletes = query.join(
            CompetitionRegistration,
            Athlete.id == CompetitionRegistration.athlete_id
        ).filter(
            CompetitionRegistration.event_id == target_event_id,
            Athlete.department == old_dept
        ).all()
            
        count = 0
        for ath in athletes:
            ath.department = new_dept
            count += 1
            
        db.commit()
        
        event_info = f"trong giải đấu hiện tại" if target_event_id else "trên toàn hệ thống"
        return RedirectResponse(f"/admin?success=Đã chuyển thành công {count} thành viên {event_info} từ phòng ban '{old_dept}' sang '{new_dept}'&event_id={event_id or ''}#tab-athletes", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi chuyển phòng ban hàng loạt: {str(e)}&event_id={event_id or ''}#tab-athletes", status_code=303)

# --- QUẢN LÝ METS & GIẢI THƯỞNG TRÊN ADMIN ---

from typing import Optional

@app.get("/admin/api/rules")
def get_rules_api(
    request: Request,
    event_id: str = None,
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        raise HTTPException(status_code=401, detail="Chưa đăng nhập")

    ev_id = None
    if event_id and event_id.strip():
        try:
            ev_id = int(event_id)
        except ValueError:
            pass

    # Lấy thông tin event
    reward_type = "milestone"
    reward_linear_kcal = 100.0
    reward_linear_amount = 5000.0
    if ev_id:
        event_obj = db.query(CompetitionEvent).filter(CompetitionEvent.id == ev_id).first()
        if event_obj:
            reward_type = event_obj.reward_type or "milestone"
            reward_linear_kcal = event_obj.reward_linear_kcal or 100.0
            reward_linear_amount = event_obj.reward_linear_amount or 5000.0

    # METs Rules
    mets_rules = []
    if ev_id:
        mets_rules = db.query(MetsRule).filter(MetsRule.event_id == ev_id).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
    if not mets_rules:
        mets_rules = db.query(MetsRule).filter(MetsRule.event_id == None).order_by(MetsRule.sport_type, MetsRule.min_speed).all()

    # Reward Rules
    reward_rules = []
    if ev_id:
        reward_rules = db.query(RewardRule).filter(RewardRule.event_id == ev_id).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
        # Chỉ fallback về mốc mặc định nếu giải đấu là milestone và chưa cấu hình mốc nào
        if not reward_rules and reward_type == "milestone":
            reward_rules = db.query(RewardRule).filter(RewardRule.event_id == None).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
    else:
        reward_rules = db.query(RewardRule).filter(RewardRule.event_id == None).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()

    # Badge Rules
    from backend.database import BadgeRule
    badge_rules = []
    if ev_id:
        badge_rules = db.query(BadgeRule).filter(BadgeRule.event_id == ev_id).order_by(BadgeRule.id).all()
    if not badge_rules:
        badge_rules = db.query(BadgeRule).filter(BadgeRule.event_id == None).order_by(BadgeRule.id).all()

    return {
        "reward_type": reward_type,
        "reward_linear_kcal": reward_linear_kcal,
        "reward_linear_amount": reward_linear_amount,
        "mets": [
            {
                "sport_type": m.sport_type,
                "min_speed": m.min_speed,
                "max_speed": m.max_speed,
                "met_value": m.met_value
            } for m in mets_rules
        ],
        "rewards": [
            {
                "gender": r.gender,
                "kcal_threshold": r.kcal_threshold,
                "reward_amount": r.reward_amount
            } for r in reward_rules
        ],
        "badges": [
            {
                "id": b.badge_key or b.id,
                "name": b.name,
                "description": b.description,
                "icon": b.icon,
                "color": b.color,
                "threshold": b.threshold,
                "unit": b.unit
            } for b in badge_rules
        ]
    }
@app.post("/admin/mets/edit")
def edit_mets_rules(
    request: Request,
    id: list[int] = Form(None),
    sport_type: list[str] = Form(...),
    min_speed: list[float] = Form(...),
    max_speed: list[float] = Form(...),
    met_value: list[float] = Form(...),
    event_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        ev_id = int(event_id) if event_id and str(event_id).strip() else None
        
        # Xóa các quy tắc METs cũ thuộc giải đấu được chọn (hoặc mặc định)
        db.query(MetsRule).filter(MetsRule.event_id == ev_id).delete()
        
        for i in range(len(sport_type)):
            if not sport_type[i].strip():
                continue
            rule = MetsRule(
                event_id=ev_id,
                sport_type=sport_type[i].strip(),
                min_speed=min_speed[i],
                max_speed=max_speed[i],
                met_value=met_value[i]
            )
            db.add(rule)
        db.commit()
        return RedirectResponse(f"/admin?success=Cap nhat he so METs thanh cong&event_id={event_id or ''}#tab-mets", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi cap nhat METs: {str(e)}&event_id={event_id or ''}#tab-mets", status_code=303)

@app.post("/admin/rewards/edit")
def edit_rewards_rules(
    request: Request,
    gender: Optional[list[str]] = Form(default=[]),
    kcal_threshold: Optional[list[float]] = Form(default=[]),
    reward_amount: Optional[list[float]] = Form(default=[]),
    reward_linear_kcal: Optional[float] = Form(None),
    reward_linear_amount: Optional[float] = Form(None),
    event_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        ev_id = int(event_id) if event_id and str(event_id).strip() else None
        
        # Nếu giải đấu chọn có kiểu tính thưởng là quy đổi tuyến tính (linear)
        is_linear = False
        if ev_id:
            comp = db.query(CompetitionEvent).filter(CompetitionEvent.id == ev_id).first()
            if comp and comp.reward_type == "linear":
                is_linear = True
                if reward_linear_kcal is not None:
                    comp.reward_linear_kcal = reward_linear_kcal
                if reward_linear_amount is not None:
                    comp.reward_linear_amount = reward_linear_amount
                db.commit()

        # Luôn xoá các quy tắc Rewards mốc cũ thuộc giải đấu được chọn (hoặc mặc định)
        db.query(RewardRule).filter(RewardRule.event_id == ev_id).delete()
        
        # Chỉ thêm quy tắc mốc nếu không phải là giải đấu dạng tuyến tính
        if not is_linear and gender:
            for i in range(len(gender)):
                if not gender[i].strip():
                    continue
                rule = RewardRule(
                    event_id=ev_id,
                    gender=gender[i].strip(),
                    kcal_threshold=kcal_threshold[i],
                    reward_amount=reward_amount[i]
                )
                db.add(rule)
        
        db.commit()
        return RedirectResponse(f"/admin?success=Cap nhat cau hinh giai thuong thanh cong&event_id={event_id or ''}#tab-rewards", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi cap nhat giai thuong: {str(e)}&event_id={event_id or ''}#tab-rewards", status_code=303)

@app.post("/admin/badges/edit")
def edit_badges_rules(
    request: Request,
    id: list[str] = Form(...), # badge_key
    name: list[str] = Form(...),
    description: list[str] = Form(...),
    icon: list[str] = Form(...),
    color: list[str] = Form(...),
    threshold: list[float] = Form(...),
    unit: list[str] = Form(...),
    event_id: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        from backend.database import BadgeRule
        ev_id = int(event_id) if event_id and str(event_id).strip() else None
        
        # Xóa các quy tắc Badges cũ thuộc giải đấu được chọn (hoặc mặc định)
        db.query(BadgeRule).filter(BadgeRule.event_id == ev_id).delete()
        
        for i in range(len(id)):
            badge_key = id[i].strip()
            if not badge_key:
                continue
            new_id = f"{badge_key}_{ev_id}" if ev_id else badge_key
            rule = BadgeRule(
                id=new_id,
                badge_key=badge_key,
                event_id=ev_id,
                name=name[i].strip(),
                description=description[i].strip(),
                icon=icon[i].strip(),
                color=color[i].strip(),
                threshold=threshold[i],
                unit=unit[i].strip()
            )
            db.add(rule)
        db.commit()
        return RedirectResponse(f"/admin?success=Cap nhat cau hinh huy hieu thanh cong&event_id={event_id or ''}#tab-badges", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi cap nhat huy hieu: {str(e)}&event_id={event_id or ''}#tab-badges", status_code=303)

# ============== API QUẢN LÝ HỆ SỐ NHÂN THÀNH TÍCH (EventMultiplier) ==============

@app.get("/admin/api/multipliers")
def get_multipliers_api(request: Request, event_id: str = None, db: Session = Depends(get_db)):
    """Lấy danh sách hệ số nhân của giải đấu."""
    admin = get_admin_session(request, db)
    if not admin:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
    
    ev_id = int(event_id) if event_id and event_id.strip() else None
    if not ev_id:
        return JSONResponse(content={"status": "success", "day_of_week": [], "special_dates": []})
    
    multipliers = db.query(EventMultiplier).filter(EventMultiplier.event_id == ev_id).all()
    
    dow_list = []
    special_list = []
    for m in multipliers:
        item = {
            "id": m.id,
            "multiplier": m.multiplier,
            "description": m.description or ""
        }
        if m.special_date:
            item["special_date"] = m.special_date
            special_list.append(item)
        elif m.day_of_week is not None:
            item["day_of_week"] = m.day_of_week
            dow_list.append(item)
    
    return JSONResponse(content={"status": "success", "day_of_week": dow_list, "special_dates": special_list})

@app.post("/admin/multipliers/edit")
async def edit_multipliers(request: Request, db: Session = Depends(get_db)):
    """Lưu cấu hình hệ số nhân cho giải đấu."""
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
    
    form = await request.form()
    event_id_str = form.get("event_id", "")
    ev_id = int(event_id_str) if event_id_str and event_id_str.strip() else None
    
    if not ev_id:
        return RedirectResponse("/admin?error=Vui long chon giai dau", status_code=303)
    
    try:
        # Xóa tất cả multiplier cũ của giải đấu này
        db.query(EventMultiplier).filter(EventMultiplier.event_id == ev_id).delete()
        db.flush()
        
        # Lưu hệ số theo ngày trong tuần (0-6)
        for dow in range(7):
            mult_val = form.get(f"dow_mult_{dow}", "1.0")
            desc_val = form.get(f"dow_desc_{dow}", "")
            mult_float = float(mult_val) if mult_val else 1.0
            
            if mult_float != 1.0:  # Chỉ lưu nếu khác 1.0 (tiết kiệm DB)
                rule = EventMultiplier(
                    event_id=ev_id,
                    day_of_week=dow,
                    special_date=None,
                    multiplier=mult_float,
                    description=desc_val.strip() if desc_val else None
                )
                db.add(rule)
        
        # Lưu hệ số ngày đặc biệt
        special_dates = form.getlist("special_date")
        special_mults = form.getlist("special_mult")
        special_descs = form.getlist("special_desc")
        
        for i in range(len(special_dates)):
            sd = special_dates[i].strip() if special_dates[i] else ""
            sm = float(special_mults[i]) if i < len(special_mults) and special_mults[i] else 1.0
            sdesc = special_descs[i].strip() if i < len(special_descs) and special_descs[i] else ""
            
            if sd and sm != 1.0:
                rule = EventMultiplier(
                    event_id=ev_id,
                    day_of_week=None,
                    special_date=sd,
                    multiplier=sm,
                    description=sdesc or None
                )
                db.add(rule)
        
        db.commit()
        return RedirectResponse(f"/admin?success=Luu he so nhan thanh cong&event_id={ev_id}#tab-multipliers", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi luu he so nhan: {str(e)}&event_id={ev_id}#tab-multipliers", status_code=303)

@app.post("/admin/multipliers/recalculate")
def recalculate_multipliers(request: Request, event_id: int = Form(...), db: Session = Depends(get_db)):
    """Tính lại KCAL cho tất cả hoạt động của giải đấu dựa trên multiplier mới."""
    admin = get_admin_session(request, db)
    if not admin:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
    
    try:
        from backend.calculations import get_mets_value, calculate_kcal
        
        activities = db.query(Activity).filter(Activity.event_id == event_id).all()
        updated = 0
        
        for act in activities:
            # Tìm athlete để lấy cân nặng
            athlete = db.query(Athlete).filter(Athlete.id == act.athlete_id).first() if act.athlete_id else None
            weight = athlete.weight if athlete else 60.0
            
            dist_raw = act.distance_km_raw if act.distance_km_raw is not None else act.distance_km
            speed_kmh = 0.0
            if act.moving_time_min and act.moving_time_min > 0:
                speed_kmh = dist_raw / (act.moving_time_min / 60.0)
            actual_time_min = act.elapsed_time_min if (act.moving_time_min or 0) < 1.0 else act.moving_time_min
            
            mets_val = get_mets_value(act.sport_type, speed_kmh, db, dist_raw, act.elevation_gain_m, event_id=event_id)
            kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m or 0, act.sport_type)
            mult = get_multiplier_for_date(act.activity_date, event_id, db)
            
            act.mets_value = mets_val
            act.kcal_burned_raw = kcal_raw
            act.kcal_burned = round(kcal_raw * mult)
            act.multiplier = mult
            act.distance_km_raw = dist_raw
            act.distance_km = round(dist_raw * mult, 2)
            updated += 1
        
        db.commit()
        return JSONResponse(content={"status": "success", "updated": updated})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.post("/admin/import-historical")
async def trigger_historical_import(
    request: Request,
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db)
):
    """API kích hoạt import danh sách file Excel tải lên từ trình duyệt."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
    
    # Lấy event_id từ form data nếu có
    form = await request.form()
    event_id_str = form.get("event_id", None)
    event_id = int(event_id_str) if event_id_str and event_id_str.strip() else None
        
    res = await import_excel_files(files, db, event_id=event_id)
    
    # Tự động liên kết các hoạt động lịch sử vừa import với các vận động viên tương ứng trong DB
    try:
        athletes = db.query(Athlete).all()
        for athlete in athletes:
            link_unlinked_activities(db, athlete)
    except Exception as e:
        print(f"Error linking historical activities: {e}")
        
    return JSONResponse(content=res)

@app.post("/admin/api/migrate-registrations")
def admin_migrate_registrations(
    request: Request,
    target_event_id: int = Form(...),
    hours_threshold: float = Form(...),
    apply: str = Form("false"),
    db: Session = Depends(get_db)
):
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    is_apply = (apply.lower() == "true")
    
    try:
        # Check target event
        target_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == target_event_id).first()
        if not target_event:
            return JSONResponse(status_code=404, content={"error": f"Không tìm thấy giải chạy đích ID {target_event_id}"})
            
        time_limit = datetime.utcnow() - timedelta(hours=hours_threshold)
        
        # Query registrations in event 1 created recently
        regs_to_migrate = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.event_id == 1,
            CompetitionRegistration.registered_at >= time_limit
        ).all()
        
        details = []
        for r in regs_to_migrate:
            ath = db.query(Athlete).filter(Athlete.id == r.athlete_id).first()
            details.append({
                "athlete_id": r.athlete_id,
                "name": ath.full_name if ath else "Không rõ",
                "registered_at": r.registered_at.strftime("%Y-%m-%d %H:%M:%S")
            })
            
        if not is_apply:
            return JSONResponse(content={
                "dry_run": True,
                "message": f"Tìm thấy {len(regs_to_migrate)} đăng ký mới ở giải cũ. Chưa thực hiện thay đổi nào.",
                "details": details
            })
            
        moved_count = 0
        deleted_dup_count = 0
        
        for r in regs_to_migrate:
            exists_in_target = db.query(CompetitionRegistration).filter(
                CompetitionRegistration.athlete_id == r.athlete_id,
                CompetitionRegistration.event_id == target_event_id
            ).first()
            
            if exists_in_target:
                db.delete(r)
                deleted_dup_count += 1
            else:
                r.event_id = target_event_id
                moved_count += 1
                
        db.commit()
        
        # Link unlinked activities for these migrated athletes
        for r in regs_to_migrate:
            ath = db.query(Athlete).filter(Athlete.id == r.athlete_id).first()
            if ath:
                link_unlinked_activities(db, ath)
                
        return JSONResponse(content={
            "dry_run": False,
            "message": f"Di chuyển thành công {moved_count} VĐV sang giải '{target_event.title}'. Đã xóa {deleted_dup_count} đăng ký trùng lặp.",
            "details": details
        })
        
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi xử lý: {str(e)}"})

@app.post("/admin/api/merge-duplicate-athletes")
def admin_merge_duplicate_athletes(
    request: Request,
    new_event_id: int = Form(...),
    apply: str = Form("false"),
    db: Session = Depends(get_db)
):
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    is_apply = (apply.lower() == "true")
    
    try:
        # Lấy tất cả VĐV đã đăng ký giải mới (new_event_id)
        regs_new_event = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.event_id == new_event_id
        ).all()
        
        details = []
        merged_count = 0
        
        for reg in regs_new_event:
            athlete_new = db.query(Athlete).filter(Athlete.id == reg.athlete_id).first()
            if not athlete_new:
                continue
            
            # Chuẩn hóa tên để đối chiếu
            name_normalized = athlete_new.full_name.strip().lower()
            
            # Tìm VĐV khác ở giải cũ (ID = 1) có cùng Họ Tên nhưng khác ID
            other_athlete = db.query(Athlete).join(
                CompetitionRegistration,
                Athlete.id == CompetitionRegistration.athlete_id
            ).filter(
                Athlete.id != athlete_new.id,
                func.lower(func.trim(Athlete.full_name)) == name_normalized,
                CompetitionRegistration.event_id == 1
            ).first()
            
            if other_athlete:
                details.append({
                    "full_name": athlete_new.full_name,
                    "new_athlete_id": athlete_new.id,
                    "new_strava_name": athlete_new.strava_name,
                    "old_athlete_id": other_athlete.id,
                    "old_strava_name": other_athlete.strava_name
                })
                
                if is_apply:
                    # THỰC HIỆN HỢP NHẤT (Merge)
                    # 1. Đăng ký tài khoản cũ (other_athlete) vào giải mới (new_event_id) nếu chưa có
                    exists_reg = db.query(CompetitionRegistration).filter(
                        CompetitionRegistration.athlete_id == other_athlete.id,
                        CompetitionRegistration.event_id == new_event_id
                    ).first()
                    
                    if not exists_reg:
                        new_reg = CompetitionRegistration(
                            athlete_id=other_athlete.id,
                            event_id=new_event_id
                        )
                        db.add(new_reg)
                    
                    # 2. Chuyển toàn bộ hoạt động (Activities) từ tài khoản mới (athlete_new) sang tài khoản cũ (other_athlete)
                    db.query(Activity).filter(
                        Activity.athlete_id == athlete_new.id
                    ).update({Activity.athlete_id: other_athlete.id})
                    
                    # 3. Xóa tài khoản mới (athlete_new) khỏi bảng athletes
                    # Cascade delete sẽ tự động xóa bản ghi đăng ký của tài khoản mới này ở bảng competition_registrations
                    db.delete(athlete_new)
                    
                    merged_count += 1
        
        if is_apply and merged_count > 0:
            db.commit()
            
            # Chạy lại liên kết hoạt động cho các tài khoản cũ vừa được hợp nhất
            for d in details:
                ath = db.query(Athlete).filter(Athlete.id == d["old_athlete_id"]).first()
                if ath:
                    link_unlinked_activities(db, ath)
                    
        message = ""
        if is_apply:
            message = f"Hợp nhất thành công {merged_count} VĐV trùng họ tên. Tên Strava đã được đồng bộ về tên cũ chính xác."
        else:
            message = f"Tìm thấy {len(details)} VĐV trùng họ tên ở giải mới và giải cũ nhưng khác tên Strava. Chưa thực hiện thay đổi nào."
            
        return JSONResponse(content={
            "dry_run": not is_apply,
            "message": message,
            "details": details
        })
        
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi xử lý: {str(e)}"})


@app.post("/admin/activity/delete/{activity_id}")
def delete_activity(activity_id: str, request: Request, db: Session = Depends(get_db)):
    """API xóa hoạt động, chỉ dành cho Admin."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return JSONResponse(status_code=404, content={"error": "Không tìm thấy hoạt động"})
        
    try:
        db.delete(activity)
        db.commit()
        return JSONResponse(content={"status": "success", "message": "Xóa hoạt động thành công"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi xóa hoạt động: {str(e)}"})

@app.get("/admin/api/logs")
def get_admin_logs(request: Request, db: Session = Depends(get_db)):
    """API lấy nhật ký sao lưu và thay thế dữ liệu từ file jsonl (chỉ dành cho Admin)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    import os
    import json
    
    backup_file = "static/uploads/deleted_activities_backup.jsonl"
    logs = []
    if os.path.exists(backup_file):
        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line.strip())
                            logs.append(data)
                        except Exception:
                            pass
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": f"Lỗi đọc nhật ký: {str(e)}"})
            
    # Sắp xếp nhật ký theo thời gian backup mới nhất lên trước
    logs = sorted(logs, key=lambda x: x.get("backup_time", ""), reverse=True)
    return JSONResponse(content={"logs": logs})

@app.get("/admin/api/activities")
def get_activities_api(
    request: Request,
    page: int = 1,
    limit: int = 50,
    search: str = "",
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """API lấy danh sách hoạt động có phân trang và tìm kiếm (chỉ dành cho Admin)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    ev_id = None
    if event_id and event_id.strip():
        try:
            ev_id = int(event_id)
        except ValueError:
            pass

    query = db.query(Activity)
    if ev_id:
        query = query.filter(Activity.event_id == ev_id)
        
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            (Activity.athlete_name_raw.ilike(search_filter)) |
            (Activity.name.ilike(search_filter)) |
            (Activity.sport_type.ilike(search_filter))
        )
        
    total = query.count()
    activities = query.order_by(Activity.activity_date.desc(), Activity.id.desc())\
        .offset((page - 1) * limit)\
        .limit(limit)\
        .all()
        
    res = []
    for act in activities:
        res.append({
            "id": act.id,
            "athlete_id": act.athlete_id,
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
            "kcal_burned_raw": act.kcal_burned_raw,
            "multiplier": act.multiplier,
            "mets_value": act.mets_value,
            "is_suspicious": act.is_suspicious,
            "suspicion_reason": act.suspicion_reason
        })
        
    return {
        "status": "success",
        "total": total,
        "page": page,
        "limit": limit,
        "activities": res
    }

@app.post("/admin/activity/edit/{activity_id}")
def edit_activity(
    activity_id: str,
    request: Request,
    name: str = Form(...),
    sport_type: str = Form(...),
    distance_km: float = Form(...),
    moving_time_min: float = Form(...),
    elapsed_time_min: float = Form(...),
    elevation_gain_m: float = Form(...),
    activity_date: str = Form(...),
    activity_time: str = Form(None),
    kcal_burned: float = Form(None),
    db: Session = Depends(get_db)
):
    """API sửa hoạt động, chỉ dành cho Admin."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    activity = db.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        return JSONResponse(status_code=404, content={"error": "Không tìm thấy hoạt động"})
        
    try:
        activity.name = name.strip()
        activity.sport_type = sport_type.strip()
        activity.distance_km = distance_km
        activity.moving_time_min = moving_time_min
        activity.elapsed_time_min = elapsed_time_min
        activity.elevation_gain_m = elevation_gain_m
        activity.activity_date = activity_date.strip()
        activity.activity_time = activity_time.strip() if activity_time else None
        
        # Xác định cự ly gốc (distance_km_raw) trước khi tính toán lại hệ số nhân
        # Nếu cự ly gửi lên khác cự ly hiển thị hiện tại trong DB, nghĩa là Admin đã sửa cự ly.
        # Ta cần tính toán lại cự ly gốc bằng cách chia cho multiplier hiện tại.
        old_multiplier = activity.multiplier if (activity.multiplier and activity.multiplier > 0) else 1.0
        
        if distance_km != activity.distance_km:
            distance_km_raw = distance_km / old_multiplier
        else:
            distance_km_raw = activity.distance_km_raw if activity.distance_km_raw is not None else (distance_km / old_multiplier)

        # Tính toán lại hệ số nhân của ngày mới
        from backend.calculations import get_mets_value, calculate_kcal, get_multiplier_for_date
        new_mult = get_multiplier_for_date(activity_date.strip(), activity.event_id, db)

        # Tính lại METs dựa trên cự ly gốc để tốc độ (speed_kmh) chính xác
        athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
        weight = athlete.weight if athlete else 60.0
        
        speed_kmh = distance_km_raw / (moving_time_min / 60.0) if moving_time_min > 0 else 0.0
        actual_time_min = elapsed_time_min if moving_time_min < 1.0 else moving_time_min
        
        mets_val = get_mets_value(sport_type.strip(), speed_kmh, db, distance_km_raw, elevation_gain_m, event_id=activity.event_id)
        activity.mets_value = mets_val
        
        # Nếu Admin sửa trực tiếp Calo trên form (calo gửi lên khác calo hiển thị hiện tại trong DB)
        if kcal_burned is not None and kcal_burned != activity.kcal_burned:
            # Ép hệ số nhân về 1.0 và lưu trực tiếp giá trị Admin sửa
            activity.multiplier = 1.0
            activity.distance_km = distance_km
            activity.distance_km_raw = distance_km
            activity.kcal_burned = kcal_burned
            activity.kcal_burned_raw = kcal_burned
        else:
            # Tự động tính toán lại quãng đường và calo theo hệ số nhân mới của ngày mới
            kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, elevation_gain_m, sport_type.strip())
            activity.kcal_burned_raw = kcal_raw
            activity.kcal_burned = round(kcal_raw * new_mult)
            activity.multiplier = new_mult
            activity.distance_km = round(distance_km_raw * new_mult, 2)
            activity.distance_km_raw = distance_km_raw
            
        # Tính lại pace dựa trên cự ly gốc để thông tin chính xác
        if distance_km_raw > 0:
            activity.pace_min_km = round(moving_time_min / distance_km_raw, 2)
        else:
            activity.pace_min_km = 0.0
            
        db.commit()
        return JSONResponse(content={"status": "success", "message": "Cập nhật hoạt động thành công"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi cập nhật hoạt động: {str(e)}"})

@app.post("/admin/activity/deduplicate")
def api_deduplicate_activities(request: Request, mode: str = "all", dry_run: bool = False, db: Session = Depends(get_db)):
    """API dọn dẹp dữ liệu trùng lặp trong DB, hỗ trợ sai số (dung sai) nhỏ và lệch ngày."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    try:
        res = deduplicate_activities_logic(db, mode=mode, dry_run=dry_run)
        return JSONResponse(content={
            "status": "success",
            "deleted_count": res["deleted_count"],
            "updated_count": res["updated_count"],
            "deleted_details": res["deleted_details"],
            "dry_run": dry_run,
            "message": res["message"]
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"Lỗi dọn dẹp trùng lặp: {str(e)}"})

@app.get("/admin/export-excel")
def export_excel(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    API Xuất báo cáo kết quả giải chạy ra Excel đa sheet.
    """
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)

    import io
    import pandas as pd
    from fastapi.responses import StreamingResponse
    from backend.calculations import get_award_info

    # Parse event_id safely to avoid 422 errors for empty queries like event_id=
    parsed_event_id = None
    if event_id is not None and str(event_id).strip():
        try:
            parsed_event_id = int(str(event_id).strip())
        except ValueError:
            pass

    event_id = parsed_event_id

    # 0. Xử lý khung thời gian mặc định (giống trang chủ)
    selected_event = None
    if event_id:
        selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).first()

    if not start_date or not end_date:
        if selected_event and selected_event.start_date and selected_event.end_date:
            if not start_date:
                start_date = selected_event.start_date
            if not end_date:
                end_date = selected_event.end_date
        else:
            base_query = db.query(func.max(Activity.activity_date))
            if event_id:
                base_query = base_query.filter(Activity.event_id == event_id)
            max_date_str = base_query.scalar()
            if max_date_str:
                try:
                    end_dt = datetime.strptime(max_date_str, "%Y-%m-%d")
                except ValueError:
                    end_dt = datetime.now()
            else:
                end_dt = datetime.now()
            
            start_dt = end_dt - timedelta(days=6)
            
            if not start_date:
                start_date = start_dt.strftime("%Y-%m-%d")
            if not end_date:
                end_date = end_dt.strftime("%Y-%m-%d")

    # Xây dựng bộ lọc cơ bản cho giải đấu + khoảng thời gian
    base_filters = [Activity.activity_date >= start_date, Activity.activity_date <= end_date]
    if event_id:
        base_filters.append(Activity.event_id == event_id)
        if selected_event:
            allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]
            if "All" not in allowed_sports:
                base_filters.append(Activity.sport_type.in_(allowed_sports))

    is_distance = selected_event and getattr(selected_event, "ranking_metric", "kcal") == "distance"

    # 1. Lấy dữ liệu BXH Cá nhân (chỉ các VĐV đã đăng ký giải đấu này)
    query_stats = db.query(
        Athlete.id,
        Athlete.full_name,
        Athlete.gender,
        Athlete.department,
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)
    
    if event_id:
        query_stats = query_stats.join(
            CompetitionRegistration,
            (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
        )
        
    athlete_stats_query = query_stats.filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.id)
     
    if is_distance:
        athlete_stats = athlete_stats_query.order_by(func.sum(Activity.distance_km).desc()).all()
    else:
        athlete_stats = athlete_stats_query.order_by(func.sum(Activity.kcal_burned).desc()).all()

    ranked_athletes = []
    for rank, item in enumerate(athlete_stats, 1):
        metric_value = item.total_dist if is_distance else item.total_kcal
        award_info = get_award_info(item.gender, metric_value or 0, db, event_id=event_id)
        ranked_athletes.append({
            "Hạng": rank,
            "Họ và Tên": item.full_name,
            "Giới tính": item.gender,
            "Phòng ban": item.department,
            "Quãng đường (km)": round(item.total_dist or 0, 1),
            "Thời gian (giờ)": round((item.total_time or 0) / 60.0, 1),
            "Năng lượng (KCAL)": int(item.total_kcal or 0),
            "Mức thưởng đạt được": f"{int(award_info['reward_amount']):,} VND".replace(",", ".") if award_info["has_award"] else "Chưa đạt mốc"
        })
    df_personal = pd.DataFrame(ranked_athletes)
    if df_personal.empty:
        df_personal = pd.DataFrame(columns=["Hạng", "Họ và Tên", "Giới tính", "Phòng ban", "Quãng đường (km)", "Thời gian (giờ)", "Năng lượng (KCAL)", "Mức thưởng đạt được"])

    # 2. Lấy dữ liệu BXH Phòng ban
    dept_members = get_department_members(db, start_date, end_date, event_id=event_id)
    
    dept_query = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal"),
        func.sum(Activity.distance_km).label("total_dist")
    ).join(Activity, Athlete.id == Activity.athlete_id)
    
    if event_id:
        dept_query = dept_query.join(
            CompetitionRegistration,
            (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
        )
        
    dept_stats_raw = dept_query.filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.department).all()
     
    dept_stats = []
    for item in dept_stats_raw:
        dept_name = item.department
        members = dept_members.get(dept_name, 1)
        total_k = item.total_kcal or 0
        total_d = item.total_dist or 0
        avg_k = total_k / members
        avg_d = total_d / members
        
        if is_distance:
            dept_stats.append({
                "Tên Phòng ban": dept_name,
                "Sĩ số": members,
                "Tổng KM": round(total_d, 1),
                "KM Trung bình / Người": round(avg_d, 2)
            })
        else:
            dept_stats.append({
                "Tên Phòng ban": dept_name,
                "Sĩ số": members,
                "Tổng KCAL": int(total_k),
                "KCAL Trung bình / Người": round(avg_k, 0)
            })
            
    if is_distance:
        dept_stats = sorted(dept_stats, key=lambda x: x["KM Trung bình / Người"], reverse=True)
        columns_to_keep = ["Hạng", "Tên Phòng ban", "Sĩ số", "Tổng KM", "KM Trung bình / Người"]
    else:
        dept_stats = sorted(dept_stats, key=lambda x: x["KCAL Trung bình / Người"], reverse=True)
        columns_to_keep = ["Hạng", "Tên Phòng ban", "Sĩ số", "Tổng KCAL", "KCAL Trung bình / Người"]

    for idx, d in enumerate(dept_stats, 1):
        d["Hạng"] = idx
        
    df_dept = pd.DataFrame(dept_stats)
    if not df_dept.empty:
        df_dept = df_dept[columns_to_keep]
    else:
        df_dept = pd.DataFrame(columns=columns_to_keep)

    # 3. Lấy dữ liệu BXH Theo bộ môn (Nam / Nữ)
    def get_sport_data(gender: str):
        stats_query = db.query(
            Athlete.full_name,
            Athlete.department,
            Activity.sport_type,
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.distance_km).label("total_dist")
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
             .order_by(Activity.sport_type, func.sum(Activity.kcal_burned).desc()).all()
        return stats

    sport_male = get_sport_data("Nam")
    sport_female = get_sport_data("Nữ")
    
    sport_records = []
    # Xử lý nam
    current_sport = None
    rank = 1
    for item in sport_male:
        if item.sport_type != current_sport:
            current_sport = item.sport_type
            rank = 1
        sport_records.append({
            "Bộ môn": item.sport_type,
            "Giới tính": "Nam",
            "Hạng": rank,
            "Họ và Tên": item.full_name,
            "Phòng ban": item.department,
            "Quãng đường (km)": round(item.total_dist or 0, 1),
            "Tổng KCAL": int(item.total_kcal or 0)
        })
        rank += 1
        
    # Xử lý nữ
    current_sport = None
    rank = 1
    for item in sport_female:
        if item.sport_type != current_sport:
            current_sport = item.sport_type
            rank = 1
        sport_records.append({
            "Bộ môn": item.sport_type,
            "Giới tính": "Nữ",
            "Hạng": rank,
            "Họ và Tên": item.full_name,
            "Phòng ban": item.department,
            "Quãng đường (km)": round(item.total_dist or 0, 1),
            "Tổng KCAL": int(item.total_kcal or 0)
        })
        rank += 1

    df_sport = pd.DataFrame(sport_records)
    if df_sport.empty:
        df_sport = pd.DataFrame(columns=["Bộ môn", "Giới tính", "Hạng", "Họ và Tên", "Phòng ban", "Quãng đường (km)", "Tổng KCAL"])
    else:
        df_sport = df_sport[["Bộ môn", "Giới tính", "Hạng", "Họ và Tên", "Phòng ban", "Quãng đường (km)", "Tổng KCAL"]]

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df_personal.to_excel(writer, sheet_name='BXH Cá Nhân', index=False)
        df_dept.to_excel(writer, sheet_name='Hiệu Suất Phòng Ban', index=False)
        df_sport.to_excel(writer, sheet_name='BXH Theo Bộ Môn', index=False)
        
        # Căn chỉnh độ rộng cột tự động
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for col in worksheet.columns:
                max_len = max(len(str(cell.value or '')) for cell in col)
                col_letter = col[0].column_letter
                worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output.seek(0)
    filename = f"Bao_cao_SSO_HC_{start_date}_to_{end_date}.xlsx"
    
    return StreamingResponse(
        output,
        media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )

@app.get("/admin/export-rewards-excel")
def export_rewards_excel(
    request: Request,
    event_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    API xuất báo cáo chi tiết giải thưởng của VĐV phục vụ kế toán chi trả.
    """
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)

    import io
    import time
    import pandas as pd
    from fastapi.responses import StreamingResponse
    from backend.calculations import get_award_info

    parsed_event_id = None
    if event_id is not None and str(event_id).strip():
        try:
            parsed_event_id = int(str(event_id).strip())
        except ValueError:
            pass
    event_id = parsed_event_id

    # 1. Lấy thông tin giải đấu
    selected_event = None
    if event_id:
        selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).first()

    # Lấy các bộ môn được cấu hình cho giải đấu
    allowed_sports = None
    if selected_event:
        allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]

    is_distance = selected_event and getattr(selected_event, "ranking_metric", "kcal") == "distance"
    metric_unit = "KM" if is_distance else "KCAL"
    event_title = selected_event.title if selected_event else "Tat_Ca_Giai_Dau"

    # 2. Lấy danh sách VĐV
    if event_id:
        athletes = db.query(Athlete).join(
            CompetitionRegistration,
            Athlete.id == CompetitionRegistration.athlete_id
        ).filter(CompetitionRegistration.event_id == event_id, Athlete.is_active == True).all()
    else:
        athletes = db.query(Athlete).filter(Athlete.is_active == True).all()

    # 3. Tính toán thành tích và giải thưởng
    data = []
    for ath in athletes:
        act_query = db.query(Activity).filter(Activity.athlete_id == ath.id)
        if event_id:
            act_query = act_query.filter(Activity.event_id == event_id)
            if allowed_sports and "All" not in allowed_sports:
                act_query = act_query.filter(Activity.sport_type.in_(allowed_sports))
                
        activities = act_query.all()
        
        total_kcal = sum(a.kcal_burned for a in activities) or 0.0
        total_dist = sum(a.distance_km for a in activities) or 0.0
        
        metric_value = total_dist if is_distance else total_kcal
        
        award_info = get_award_info(ath.gender, metric_value, db, event_id=event_id)
        
        data.append({
            "Mã VĐV": ath.id,
            "Họ và Tên": ath.full_name,
            "Phòng ban": ath.department or "Chưa phân phòng",
            "Giới tính": ath.gender or "Khác",
            f"Tổng thành tích ({metric_unit})": round(metric_value, 2),
            "Số tiền thưởng (VND)": int(award_info.get("reward_amount", 0.0)),
            "Trạng thái": "Có giải thưởng" if award_info.get("reward_amount", 0.0) > 0 else "Chưa đạt mốc"
        })

    # Sắp xếp danh sách nhận thưởng giảm dần theo Số tiền thưởng và Thành tích
    data = sorted(data, key=lambda x: (x["Số tiền thưởng (VND)"], x[f"Tổng thành tích ({metric_unit})"]), reverse=True)

    # Thêm cột Hạng
    for rank, item in enumerate(data, 1):
        item["Hạng"] = rank

    # Sắp xếp lại cột cho đẹp
    columns = ["Hạng", "Mã VĐV", "Họ và Tên", "Phòng ban", "Giới tính", f"Tổng thành tích ({metric_unit})", "Số tiền thưởng (VND)", "Trạng thái"]
    df = pd.DataFrame(data)
    if not df.empty:
        df = df[columns]
    else:
        df = pd.DataFrame(columns=columns)

    # Xuất ra file Excel dùng pandas BytesIO
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Báo cáo giải thưởng")
        
        # Tự động căn chỉnh độ rộng cột
        worksheet = writer.sheets["Báo cáo giải thưởng"]
        for col in worksheet.columns:
            max_len = max(len(str(cell.value or '')) for cell in col)
            col_letter = col[0].column_letter
            worksheet.column_dimensions[col_letter].width = max(max_len + 3, 12)
            
    output.seek(0)

    filename_safe = "".join(c for c in event_title if c.isalnum() or c in (' ', '_', '-')).rstrip()
    filename_safe = filename_safe.replace(' ', '_')
    
    import urllib.parse
    filename = f"Bao_cao_chi_phi_giai_thuong_{filename_safe}_{int(time.time())}.xlsx"
    encoded_filename = urllib.parse.quote(filename)

    headers = {
        'Content-Disposition': f"attachment; filename*=UTF-8''{encoded_filename}"
    }

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers=headers
    )

@app.get("/strava/webhook")
def strava_webhook_verification(request: Request):
    """
    Xác thực Webhook Subscription từ Strava (Hub Challenge).
    """
    params = request.query_params
    hub_mode = params.get("hub.mode")
    hub_challenge = params.get("hub.challenge")
    hub_verify_token = params.get("hub.verify_token")
    
    EXPECTED_VERIFY_TOKEN = os.getenv("STRAVA_WEBHOOK_VERIFY_TOKEN", "SSO_HC_VERIFY_TOKEN")
    
    if hub_mode == "subscribe" and hub_challenge:
        if hub_verify_token == EXPECTED_VERIFY_TOKEN:
            print("Strava Webhook: Verification successful.")
            return JSONResponse(content={"hub.challenge": hub_challenge})
        else:
            print("Strava Webhook: Verification failed. Invalid verify token.")
            raise HTTPException(status_code=403, detail="Invalid verify token")
            
    raise HTTPException(status_code=400, detail="Bad request")

@app.post("/strava/webhook")
async def strava_webhook_event(request: Request):
    """
    Tiếp nhận sự kiện webhook từ Strava khi có hoạt động mới, cập nhật hoặc xóa.
    """
    try:
        payload = await request.json()
        print(f"Strava Webhook: Received event payload: {payload}")
        
        object_type = payload.get("object_type")
        aspect_type = payload.get("aspect_type")
        
        if object_type == "activity":
            if aspect_type in ("create", "update"):
                print("Strava Webhook: New or updated activity event. Triggering sync thread...")
                import threading
                threading.Thread(target=run_background_sync, daemon=True).start()
                
        return HTMLResponse(content="EVENT_RECEIVED", status_code=200)
    except Exception as e:
        print(f"Strava Webhook: Error processing webhook event: {e}")
        return HTMLResponse(content="ERROR", status_code=500)

@app.post("/admin/events/add")
async def admin_add_event(
    request: Request,
    title: str = Form(...),
    video_url: str = Form(None),
    summary_text: str = Form(...),
    banner_file: UploadFile = File(...),
    gallery_files: list[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        from backend.database import ArchivedEvent
        import time
        
        # 1. Lưu ảnh banner đại diện
        banner_path = ""
        if banner_file and banner_file.filename:
            ext = os.path.splitext(banner_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif", ".jfif", ".svg", ".bmp"]:
                filename = f"event_banner_{int(time.time())}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    content = await banner_file.read()
                    f.write(content)
                banner_path = f"/static/uploads/{filename}"
                
        # 2. Lưu album ảnh gallery
        gallery_paths = []
        if gallery_files:
            if not isinstance(gallery_files, list):
                gallery_files = [gallery_files]
            import random
            idx = 0
            for g_file in gallery_files:
                if g_file.filename:
                    ext = os.path.splitext(g_file.filename)[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif", ".jfif", ".svg", ".bmp"]:
                        filename = f"event_gal_{int(time.time())}_{random.randint(100, 999)}_{idx}{ext}"
                        upload_dir = "static/uploads"
                        os.makedirs(upload_dir, exist_ok=True)
                        file_path = os.path.join(upload_dir, filename)
                        content = await g_file.read()
                        with open(file_path, "wb") as f:
                            f.write(content)
                        gallery_paths.append(f"/static/uploads/{filename}")
                        idx += 1
                        
        gallery_str = ",".join(gallery_paths) if gallery_paths else ""
        
        new_event = ArchivedEvent(
            title=title.strip(),
            banner_image=banner_path,
            video_url=video_url.strip() if video_url else None,
            summary_text=summary_text.strip(),
            gallery_images=gallery_str
        )
        db.add(new_event)
        db.commit()
        return RedirectResponse("/admin?success=Thêm sự kiện cũ thành công", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi khi thêm sự kiện: {str(e)}", status_code=303)

@app.post("/admin/events/delete/{event_id}")
def admin_delete_event(event_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        from backend.database import ArchivedEvent
        event = db.query(ArchivedEvent).filter(ArchivedEvent.id == event_id).first()
        if not event:
            return RedirectResponse("/admin?error=Không tìm thấy sự kiện", status_code=303)
            
        # Xóa các file ảnh đại diện trên đĩa
        if event.banner_image:
            path = event.banner_image.lstrip("/")
            if os.path.exists(path) and "static/uploads/" in path:
                try: os.remove(path)
                except: pass
                
        # Xóa ảnh gallery trên đĩa
        if event.gallery_images:
            paths = event.gallery_images.split(",")
            for p in paths:
                p_clean = p.lstrip("/")
                if os.path.exists(p_clean) and "static/uploads/" in p_clean:
                    try: os.remove(p_clean)
                    except: pass
                    
        db.delete(event)
        db.commit()
        return RedirectResponse("/admin?success=Đã xóa sự kiện cũ thành công", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi khi xóa: {str(e)}", status_code=303)


@app.post("/admin/events/edit/{event_id}")
async def admin_edit_event(
    event_id: int,
    request: Request,
    title: str = Form(...),
    video_url: str = Form(None),
    summary_text: str = Form(...),
    keep_existing_gallery: bool = Form(False),
    deleted_images: str = Form(""),
    banner_file: UploadFile = File(None),
    gallery_files: list[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        # Chuẩn hóa deleted_images nếu nhận đối tượng Form (do gọi trực tiếp từ test script)
        if not isinstance(deleted_images, str):
            deleted_images = ""
        from backend.database import ArchivedEvent
        import time
        
        event = db.query(ArchivedEvent).filter(ArchivedEvent.id == event_id).first()
        if not event:
            return RedirectResponse("/admin?error=Không tìm thấy sự kiện", status_code=303)
            
        event.title = title.strip()
        event.video_url = video_url.strip() if video_url else None
        event.summary_text = summary_text.strip()
        
        # Xử lý xóa các ảnh được yêu cầu xóa khỏi album
        if deleted_images and event.gallery_images:
            to_delete = [p.strip() for p in deleted_images.split(",") if p.strip()]
            current_images = event.gallery_images.split(",")
            updated_images = []
            for img in current_images:
                if img in to_delete:
                    # Xóa file vật lý trên đĩa
                    p_clean = img.lstrip("/")
                    if os.path.exists(p_clean) and "static/uploads/" in p_clean:
                        try:
                            os.remove(p_clean)
                        except Exception as ex:
                            print(f"Error removing image file: {ex}")
                else:
                    updated_images.append(img)
            event.gallery_images = ",".join(updated_images)
        
        # 1. Cập nhật banner nếu có upload mới
        if banner_file and banner_file.filename:
            ext = os.path.splitext(banner_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif", ".jfif", ".svg", ".bmp"]:
                import random
                filename = f"event_banner_{int(time.time())}_{random.randint(100, 999)}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    content = await banner_file.read()
                    f.write(content)
                
                # Xóa banner cũ
                if event.banner_image:
                    old_path = event.banner_image.lstrip("/")
                    if os.path.exists(old_path) and "static/uploads/" in old_path:
                        try: os.remove(old_path)
                        except: pass
                event.banner_image = f"/static/uploads/{filename}"
                
        # 2. Xử lý album ảnh gallery
        # Nếu chọn KHÔNG giữ ảnh cũ, xóa tất cả các ảnh cũ khỏi đĩa trước khi lưu ảnh mới
        if not keep_existing_gallery and event.gallery_images:
            paths = event.gallery_images.split(",")
            for p in paths:
                p_clean = p.lstrip("/")
                if os.path.exists(p_clean) and "static/uploads/" in p_clean:
                    try: os.remove(p_clean)
                    except: pass
            event.gallery_images = ""

        # Upload các ảnh gallery mới
        new_gallery_paths = []
        if gallery_files:
            if not isinstance(gallery_files, list):
                gallery_files = [gallery_files]
            import random
            idx = 0
            for g_file in gallery_files:
                if g_file.filename:
                    ext = os.path.splitext(g_file.filename)[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".heif", ".jfif", ".svg", ".bmp"]:
                        filename = f"event_gal_{int(time.time())}_{random.randint(100, 999)}_{idx}{ext}"
                        upload_dir = "static/uploads"
                        os.makedirs(upload_dir, exist_ok=True)
                        file_path = os.path.join(upload_dir, filename)
                        content = await g_file.read()
                        with open(file_path, "wb") as f:
                            f.write(content)
                        new_gallery_paths.append(f"/static/uploads/{filename}")
                        idx += 1
                        
        if new_gallery_paths:
            if keep_existing_gallery:
                # Giữ lại các ảnh cũ và nối thêm các ảnh mới
                old_paths = event.gallery_images.split(",") if event.gallery_images else []
                old_paths = [p for p in old_paths if p]
                all_paths = old_paths + new_gallery_paths
            else:
                # Thay thế hoàn toàn (ảnh cũ đã được xóa ở trên)
                all_paths = new_gallery_paths
            
            event.gallery_images = ",".join(all_paths) if all_paths else ""
            
        db.commit()
        return RedirectResponse("/admin?success=Cập nhật sự kiện lịch sử thành công#tab-events", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi khi cập nhật sự kiện: {str(e)}#tab-events", status_code=303)


# --- QUẢN LÝ GIẢI ĐẤU (COMPETITIONS) ---

@app.post("/admin/competitions/add")
async def admin_add_competition(
    request: Request,
    title: str = Form(...),
    strava_club_id: str = Form(""),
    start_date: str = Form(...),
    end_date: str = Form(...),
    description: str = Form(""),
    rules_description: str = Form(""),
    rules_banner_text: str = Form(""),
    rules_general_text: str = Form(""),
    is_active: bool = Form(True),
    reward_type: str = Form("milestone"),
    reward_linear_kcal: float = Form(100.0),
    reward_linear_amount: float = Form(5000.0),
    show_rewards_in_rules: bool = Form(True),
    department_members: str = Form(""),
    ranking_metric: str = Form("kcal"),
    banner_file: UploadFile = File(None),
    avatar_frame_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        # Xác thực JSON cấu hình sĩ số phòng ban nếu có
        dept_json = department_members.strip()
        if dept_json:
            try:
                import json
                parsed = json.loads(dept_json)
                if not isinstance(parsed, dict):
                    raise ValueError("Cấu hình sĩ số phải là một JSON Object (dạng key-value)")
            except Exception as e:
                return RedirectResponse(f"/admin?error=Lỗi cấu hình sĩ số phòng ban JSON: {str(e)}#tab-competitions", status_code=303)

        import time as time_mod
        # Lưu ảnh banner nếu có
        banner_path = ""
        if banner_file and banner_file.filename:
            ext = os.path.splitext(banner_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                filename = f"comp_banner_{int(time_mod.time())}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    content = await banner_file.read()
                    f.write(content)
                banner_path = f"/static/uploads/{filename}"
        
        ranking_sports_str = "All"

        new_comp = CompetitionEvent(
            title=title.strip(),
            strava_club_id=extract_strava_club_id(strava_club_id),
            start_date=start_date.strip(),
            end_date=end_date.strip(),
            is_active=is_active,
            description=description.strip(),
            banner_image=banner_path,
            rules_description=rules_description.strip(),
            rules_banner_text=rules_banner_text.strip(),
            rules_general_text=rules_general_text.strip(),
            reward_type=reward_type.strip(),
            reward_linear_kcal=reward_linear_kcal,
            reward_linear_amount=reward_linear_amount,
            show_rewards_in_rules=show_rewards_in_rules,
            department_members=dept_json if dept_json else None,
            ranking_metric=ranking_metric.strip(),
            ranking_sports=ranking_sports_str
        )
        db.add(new_comp)
        db.flush() # Sinh ID cho new_comp trước khi lưu ảnh

        # Xử lý khung viền avatar riêng nếu có tải lên
        if avatar_frame_file and avatar_frame_file.filename:
            ext = os.path.splitext(avatar_frame_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                from io import BytesIO
                from PIL import Image
                
                os.makedirs("static/uploads/frames", exist_ok=True)
                frame_filename = f"event_{new_comp.id}_frame.png"
                frame_filepath = os.path.join("static/uploads/frames", frame_filename)
                
                content = await avatar_frame_file.read()
                img = Image.open(BytesIO(content))
                
                # Gọi helper đục lỗ nếu là ảnh đặc
                processed_img = duc_lo_frame_neu_duc(img, scale=0.72)
                processed_img.save(frame_filepath, "PNG")
                
                new_comp.avatar_frame = f"/static/uploads/frames/{frame_filename}"

        db.commit()
        return RedirectResponse("/admin?success=Thêm giải đấu mới thành công#tab-competitions", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi khi thêm giải đấu: {str(e)}#tab-competitions", status_code=303)


@app.post("/admin/competitions/edit/{comp_id}")
async def admin_edit_competition(
    comp_id: int,
    request: Request,
    title: str = Form(...),
    strava_club_id: str = Form(""),
    start_date: str = Form(...),
    end_date: str = Form(...),
    description: str = Form(""),
    rules_description: str = Form(""),
    rules_banner_text: str = Form(""),
    rules_general_text: str = Form(""),
    is_active: bool = Form(True),
    reward_type: str = Form("milestone"),
    reward_linear_kcal: float = Form(100.0),
    reward_linear_amount: float = Form(5000.0),
    show_rewards_in_rules: bool = Form(True),
    department_members: str = Form(""),
    ranking_metric: str = Form("kcal"),
    banner_file: UploadFile = File(None),
    avatar_frame_file: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
    
    comp = db.query(CompetitionEvent).filter(CompetitionEvent.id == comp_id).first()
    if not comp:
        return RedirectResponse("/admin?error=Không tìm thấy giải đấu", status_code=303)
    
    try:
        # Xác thực JSON cấu hình sĩ số phòng ban nếu có
        dept_json = department_members.strip()
        if dept_json:
            try:
                import json
                parsed = json.loads(dept_json)
                if not isinstance(parsed, dict):
                    raise ValueError("Cấu hình sĩ số phải là một JSON Object (dạng key-value)")
            except Exception as e:
                return RedirectResponse(f"/admin?error=Lỗi cấu hình sĩ số phòng ban JSON: {str(e)}#tab-competitions", status_code=303)

        import time as time_mod
        ranking_sports_str = "All"

        comp.title = title.strip()
        comp.strava_club_id = extract_strava_club_id(strava_club_id)
        comp.start_date = start_date.strip()
        comp.end_date = end_date.strip()
        comp.is_active = is_active
        comp.description = description.strip()
        comp.rules_description = rules_description.strip()
        comp.rules_banner_text = rules_banner_text.strip()
        comp.rules_general_text = rules_general_text.strip()
        comp.reward_type = reward_type.strip()
        comp.reward_linear_kcal = reward_linear_kcal
        comp.reward_linear_amount = reward_linear_amount
        comp.show_rewards_in_rules = show_rewards_in_rules
        comp.department_members = dept_json if dept_json else None
        comp.ranking_metric = ranking_metric.strip()
        comp.ranking_sports = ranking_sports_str
        
        # Cập nhật banner nếu có upload mới
        if banner_file and banner_file.filename:
            ext = os.path.splitext(banner_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                filename = f"comp_banner_{int(time_mod.time())}{ext}"
                upload_dir = "static/uploads"
                os.makedirs(upload_dir, exist_ok=True)
                file_path = os.path.join(upload_dir, filename)
                with open(file_path, "wb") as f:
                    content = await banner_file.read()
                    f.write(content)
                # Xóa banner cũ nếu có
                if comp.banner_image:
                    old_path = comp.banner_image.lstrip("/")
                    if os.path.exists(old_path) and "static/uploads/" in old_path:
                        try: os.remove(old_path)
                        except: pass
                comp.banner_image = f"/static/uploads/{filename}"
        
        # Cập nhật khung viền avatar riêng nếu có tải lên mới
        if avatar_frame_file and avatar_frame_file.filename:
            ext = os.path.splitext(avatar_frame_file.filename)[1].lower()
            if ext in [".png", ".jpg", ".jpeg", ".webp"]:
                from io import BytesIO
                from PIL import Image
                
                os.makedirs("static/uploads/frames", exist_ok=True)
                frame_filename = f"event_{comp.id}_frame.png"
                frame_filepath = os.path.join("static/uploads/frames", frame_filename)
                
                content = await avatar_frame_file.read()
                img = Image.open(BytesIO(content))
                
                # Gọi helper đục lỗ
                processed_img = duc_lo_frame_neu_duc(img, scale=0.72)
                processed_img.save(frame_filepath, "PNG")
                
                comp.avatar_frame = f"/static/uploads/frames/{frame_filename}"
        
        db.commit()
        return RedirectResponse("/admin?success=Cập nhật giải đấu thành công#tab-competitions", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi cập nhật giải đấu: {str(e)}#tab-competitions", status_code=303)


@app.post("/admin/competitions/delete/{comp_id}")
def admin_delete_competition(comp_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
    
    comp = db.query(CompetitionEvent).filter(CompetitionEvent.id == comp_id).first()
    if not comp:
        return RedirectResponse("/admin?error=Không tìm thấy giải đấu", status_code=303)
    
    try:
        # Xóa banner trên đĩa
        if comp.banner_image:
            path = comp.banner_image.lstrip("/")
            if os.path.exists(path) and "static/uploads/" in path:
                try: os.remove(path)
                except: pass
        
        # 1. Hủy liên kết hoạt động thuộc giải chạy này bằng cách đặt event_id = None
        db.query(Activity).filter(Activity.event_id == comp_id).update({Activity.event_id: None}, synchronize_session=False)
        
        # 2. Xóa sạch các đăng ký của giải đấu này
        db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == comp_id).delete()
        
        # 3. Xóa sạch các cấu hình riêng liên quan đến giải đấu này
        db.query(MetsRule).filter(MetsRule.event_id == comp_id).delete()
        db.query(RewardRule).filter(RewardRule.event_id == comp_id).delete()
        
        from backend.database import BadgeRule
        db.query(BadgeRule).filter(BadgeRule.event_id == comp_id).delete()
        db.query(EventMultiplier).filter(EventMultiplier.event_id == comp_id).delete()
        
        # 4. Xóa giải đấu ra khỏi bảng competition_events
        db.delete(comp)
        db.commit()
        return RedirectResponse("/admin?success=Đã xóa giải đấu và tất cả hoạt động liên quan#tab-competitions", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi khi xóa giải đấu: {str(e)}#tab-competitions", status_code=303)


@app.post("/admin/competitions/sync/{comp_id}")
def admin_sync_competition(comp_id: int, request: Request, db: Session = Depends(get_db)):
    """API đồng bộ thủ công cho một giải đấu cụ thể."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
    
    res = sync_club_activities(event_id=comp_id)
    
    # Tự động dọn dẹp hoạt động trùng lặp sau khi đồng bộ thủ công thành công
    if res.get("status") in ("success", "partial"):
        try:
            deduplicate_activities_logic(db)
        except Exception as e:
            print(f"Manual Sync Comp: Error during auto deduplication: {e}")
            
    return JSONResponse(content=res)


# --- SUPPORT TICKETS API ---
@app.post("/api/support")
async def api_submit_support(request: Request, db: Session = Depends(get_db)):
    """API gửi phản hồi hoặc báo lỗi từ giao diện người dùng (không cần đăng nhập)."""
    try:
        data = await request.json()
        athlete_name = data.get("athlete_name", "").strip()
        contact_info = data.get("contact_info", "").strip()
        content = data.get("content", "").strip()
        
        if not content:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Nội dung phản hồi không được để trống."})
            
        ticket = SupportTicket(
            athlete_name=athlete_name,
            contact_info=contact_info,
            content=content,
            status="pending"
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return {"status": "success", "message": "Gửi phản hồi thành công! Cảm ơn bạn đã đóng góp ý kiến."}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": f"Lỗi hệ thống: {str(e)}"})

# --- ATHLETE CONNECTION STATUS API ---
@app.get("/api/athlete/status/{athlete_id}")
def get_athlete_connection_status(athlete_id: int, db: Session = Depends(get_db)):
    """API kiểm tra xem VĐV đã liên kết Strava cá nhân chưa."""
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return JSONResponse(status_code=404, content={"status": "error", "message": "Không tìm thấy vận động viên."})
    
    is_linked = bool(athlete.strava_refresh_token)
    return {
        "status": "success",
        "id": athlete.id,
        "full_name": athlete.full_name,
        "is_linked": is_linked
    }

@app.get("/api/athlete/search-connection")
def search_athlete_connection(q: str, request: Request, db: Session = Depends(get_db)):
    """API tìm kiếm VĐV theo tên để kiểm tra trạng thái liên kết Strava."""
    q = (q or "").strip()
    if not q:
        return {"status": "success", "results": []}
        
    # Tìm kiếm theo tên (không phân biệt hoa thường và tìm kiếm tương đối)
    athletes = db.query(Athlete).filter(
        Athlete.full_name.like(f"%{q}%")
    ).limit(10).all()
    
    configs = get_config_dict(db)
    client_id = configs.get("strava_client_id")
    
    # Lấy app_url để sinh redirect_uri
    app_url = APP_URL
    if not app_url:
        host = request.headers.get("host", "localhost:8080")
        scheme = "https" if request.headers.get("x-forwarded-proto") == "https" else "http"
        app_url = f"{scheme}://{host}"
    
    results = []
    for ath in athletes:
        is_linked = bool(ath.strava_refresh_token)
        auth_url = ""
        if not is_linked and client_id:
            redirect_uri = f"{app_url}/exchange_user_token"
            auth_url = f"https://www.strava.com/oauth/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=activity:read_all,profile:read_all&state={ath.id}"
            
        results.append({
            "id": ath.id,
            "full_name": ath.full_name,
            "department": ath.department or "Chưa rõ",
            "is_linked": is_linked,
            "auth_url": auth_url
        })
        
    return {"status": "success", "results": results}

@app.get("/admin/api/support")
def admin_list_support(request: Request, db: Session = Depends(get_db)):
    """API lấy danh sách các phản hồi hỗ trợ (yêu cầu admin)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
    
    tickets = db.query(SupportTicket).order_by(SupportTicket.created_at.desc()).all()
    
    # Định dạng kết quả trả về
    res = []
    for t in tickets:
        res.append({
            "id": t.id,
            "athlete_name": t.athlete_name or "Ẩn danh",
            "contact_info": t.contact_info or "",
            "content": t.content,
            "created_at": t.created_at.strftime("%Y-%m-%d %H:%M:%S") if t.created_at else "",
            "status": t.status,
            "admin_notes": t.admin_notes or "",
            "resolved_at": t.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if t.resolved_at else ""
        })
    return JSONResponse(content=res)

@app.post("/admin/api/support/{ticket_id}/resolve")
async def admin_resolve_support(ticket_id: int, request: Request, db: Session = Depends(get_db)):
    """API cập nhật trạng thái phản hồi hỗ trợ (yêu cầu admin)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
    
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        return JSONResponse(status_code=404, content={"error": "Không tìm thấy phản hồi"})
        
    try:
        data = await request.json()
        status = data.get("status", "resolved")
        admin_notes = data.get("admin_notes", "").strip()
        
        ticket.status = status
        ticket.admin_notes = admin_notes
        if status in ("resolved", "processed"):
            ticket.resolved_at = datetime.utcnow()
        else:
            ticket.resolved_at = None
            
        db.commit()
        return {"status": "success", "message": "Cập nhật phản hồi thành công."}
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi cập nhật: {str(e)}"})

@app.delete("/admin/api/support/{ticket_id}")
def admin_delete_support(ticket_id: int, request: Request, db: Session = Depends(get_db)):
    """API xóa phản hồi hỗ trợ (yêu cầu admin)."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    ticket = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
    if not ticket:
        return JSONResponse(status_code=404, content={"error": "Không tìm thấy phản hồi"})
        
    try:
        db.delete(ticket)
        db.commit()
        return {"status": "success", "message": "Xóa phản hồi thành công."}
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi khi xóa: {str(e)}"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

import os
import hashlib
import time
import json
import requests
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

from backend.database import SessionLocal, init_db, get_db, Config, Athlete, Activity, MetsRule, RewardRule, hash_password
from backend.calculations import get_award_info
from backend.sync_engine import sync_club_activities, get_config_dict, update_config, link_unlinked_activities, import_excel_files
from backend.auth import get_admin_session, COOKIE_NAME, verify_password

app = FastAPI(title="Strava SSO HC Web App")

# Đảm bảo các thư mục templates và static tồn tại
os.makedirs("templates", exist_ok=True)
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/branding", StaticFiles(directory="branding"), name="branding")
templates = Jinja2Templates(directory="templates")

scheduler = BackgroundScheduler()

def run_background_sync():
    print("Background Sync: Starting periodic sync...")
    res = sync_club_activities()
    print(f"Background Sync: Completed. Status: {res.get('status')}, New activities: {res.get('new_activities')}")

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
    if not scheduler.running:
        scheduler.start()
    print(f"Scheduler: Started periodic background sync every {interval} hours.")

@app.on_event("startup")
def startup_event():
    # Đảm bảo thư mục upload tồn tại
    os.makedirs("static/uploads", exist_ok=True)
    # Khởi tạo database và di chuyển dữ liệu cũ từ Excel nếu có
    init_db()
    # Khởi chạy Scheduler đồng bộ ngầm
    start_scheduler()
    # Đồng bộ lần đầu khi chạy ứng dụng (chạy bất đồng bộ để tránh block startup)
    import threading
    threading.Thread(target=run_background_sync, daemon=True).start()

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
        return get_config_dict(db)
    except Exception:
        return {}
    finally:
        db.close()

templates.env.globals["get_configs"] = get_global_configs

def get_department_members(db: Session, start_date: str = None, end_date: str = None) -> dict:
    """Calculate department member counts dynamically based on active registered athletes who have activities in the timeframe."""
    dept_members = {}
    try:
        query = db.query(
            Athlete.department,
            func.count(func.distinct(Athlete.id)).label("count")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .filter(Athlete.is_active == True)
         
        if start_date:
            query = query.filter(Activity.activity_date >= start_date)
        if end_date:
            query = query.filter(Activity.activity_date <= end_date)
            
        results = query.group_by(Athlete.department).all()
        for row in results:
            dept_name = row[0]
            count = row[1]
            dept_members[dept_name] = count or 1

        # Bổ sung sĩ số mặc định (số VĐV đã đăng ký) cho các phòng ban không có hoạt động trong khoảng thời gian được lọc
        all_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().all()
        for row in all_depts:
            dept_name = row[0]
            if dept_name not in dept_members:
                active_count = db.query(Athlete).filter(Athlete.department == dept_name, Athlete.is_active == True).count()
                dept_members[dept_name] = active_count or 1
    except Exception as e:
        print(f"Error resolving dynamic department members: {e}")
        
    return dept_members

# --- FRONTEND ROUTES ---
@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db)
):
    """
    Trang chủ hiển thị Bảng xếp hạng (BXH), Tìm kiếm và Thống kê tổng quan theo khung thời gian.
    """
    configs = get_config_dict(db)
    
    # Lấy cấu hình hiển thị cột của BXH Cá nhân
    col_configs = {
        "show_col_gender": configs.get("show_col_gender", "true").lower() == "true",
        "show_col_dept": configs.get("show_col_dept", "true").lower() == "true",
        "show_col_dist": configs.get("show_col_dist", "true").lower() == "true",
        "show_col_time": configs.get("show_col_time", "true").lower() == "true",
        "show_col_award": configs.get("show_col_award", "true").lower() == "true",
    }
    
    # 0. Xử lý khung thời gian mặc định (7 ngày từ ngày có hoạt động mới nhất)
    if not start_date or not end_date:
        max_date_str = db.query(func.max(Activity.activity_date)).scalar()
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

    # 1. Thống kê tổng quan (Kpi Cards) theo khung thời gian
    total_kcal = db.query(func.sum(Activity.kcal_burned))\
        .filter(Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
        .scalar() or 0
    total_dist = db.query(func.sum(Activity.distance_km))\
        .filter(Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
        .scalar() or 0
    total_athletes = db.query(Athlete).filter(Athlete.is_active == True).count()
    
    # 2. Xếp hạng cá nhân (BXH Tổng) theo KCAL
    athlete_stats = db.query(
        Athlete.id,
        Athlete.full_name,
        Athlete.gender,
        Athlete.department,
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .filter(Athlete.is_active == True, Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
     .group_by(Athlete.id)\
     .order_by(func.sum(Activity.kcal_burned).desc()).all()
     
    # Tính giải thưởng tương ứng cho từng VĐV trên BXH
    ranked_athletes = []
    for rank, item in enumerate(athlete_stats, 1):
        award_info = get_award_info(item.gender, item.total_kcal or 0, db)
        ranked_athletes.append({
            "rank": rank,
            "id": item.id,
            "full_name": item.full_name,
            "gender": item.gender,
            "department": item.department,
            "total_dist": round(item.total_dist or 0, 1),
            "total_time": round((item.total_time or 0) / 60.0, 1), # Đổi sang giờ
            "total_kcal": int(item.total_kcal or 0),
            "award": award_info["reward_amount"],
            "has_award": award_info["has_award"]
        })

    # 3. Xếp hạng theo Phòng ban (Trung bình KCAL = Tổng KCAL / Số thành viên của phòng)
    dept_members = get_department_members(db, start_date, end_date)
    
    dept_stats_raw = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .filter(Athlete.is_active == True, Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
     .group_by(Athlete.department).all()
     
    dept_stats = []
    for item in dept_stats_raw:
        dept_name = item.department
        members = dept_members.get(dept_name, 1) # Sĩ số phòng ban từ DB config, mặc định 1 nếu không định nghĩa
        total_k = item.total_kcal or 0
        avg_k = total_k / members
        dept_stats.append({
            "department": dept_name,
            "total_kcal": int(total_k),
            "members": members,
            "avg_kcal": round(avg_k, 0)
        })
    dept_stats = sorted(dept_stats, key=lambda x: x["avg_kcal"], reverse=True)
    for idx, d in enumerate(dept_stats, 1):
        d["rank"] = idx

    # 4. Xếp hạng theo Môn Thể Thao (Nam / Nữ riêng)
    def get_sport_ranking(gender: str):
        stats = db.query(
            Athlete.id,
            Athlete.full_name,
            Activity.sport_type,
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.distance_km).label("total_dist")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .filter(Athlete.is_active == True, Athlete.gender == gender, Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
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
                "total_dist": round(item.total_dist or 0, 1)
            })
            
        # Thêm thứ hạng vào danh sách
        for sport in grouped:
            for rank, ath in enumerate(grouped[sport], 1):
                ath["rank"] = rank
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
            "col_configs": col_configs
        }
    )

@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request, db: Session = Depends(get_db)):
    """Trang quy chế giải đấu."""
    configs = get_config_dict(db)
    mets = db.query(MetsRule).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
    rewards = db.query(RewardRule).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
    return templates.TemplateResponse(
        request=request,
        name="rules.html",
        context={
            "configs": configs,
            "mets": mets,
            "rewards": rewards
        }
    )

@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, db: Session = Depends(get_db)):
    """Trang đăng ký tham gia cho vận động viên."""
    db_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().order_by(Athlete.department).all()
    departments = [r[0] for r in db_depts] if db_depts else [
        "BAN GIÁM ĐỐC", "PHÒNG HÀNH CHÍNH NHÂN SỰ", "PHÒNG KỸ THUẬT", 
        "PHÒNG KINH DOANH", "PHÒNG TÀI CHÍNH KẾ TOÁN", "PHÒNG KHAI THÁC", "PHÒNG VẬN HÀNH"
    ]
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={
            "departments": departments,
            "success": None,
            "error": None
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
    is_update: str = Form("false"),
    db: Session = Depends(get_db)
):
    db_depts = db.query(Athlete.department).filter(Athlete.department != None, Athlete.department != '').distinct().order_by(Athlete.department).all()
    departments = [r[0] for r in db_depts] if db_depts else [
        "BAN GIÁM ĐỐC", "PHÒNG HÀNH CHÍNH NHÂN SỰ", "PHÒNG KỸ THUẬT", 
        "PHÒNG KINH DOANH", "PHÒNG TÀI CHÍNH KẾ TOÁN", "PHÒNG KHAI THÁC", "PHÒNG VẬN HÀNH"
    ]
    full_name = full_name.strip()
    strava_name = strava_name.strip()

    # Kiểm tra xem tên Strava đã được đăng ký chưa
    exists = db.query(Athlete).filter(Athlete.strava_name == strava_name).first()
    if exists:
        if is_update == "true":
            try:
                # Chỉ cho phép cập nhật các trường không quan trọng: Phòng ban và Cân nặng
                exists.department = department
                exists.weight = weight
                db.commit()
                
                # Cập nhật và tính toán lại lượng calo (KCAL) của các hoạt động cũ dựa theo cân nặng mới
                acts = db.query(Activity).filter(Activity.athlete_id == exists.id).all()
                for act in acts:
                    speed_kmh = 0.0
                    if act.moving_time_min > 0:
                        speed_kmh = act.distance_km / (act.moving_time_min / 60.0)
                    actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
                    
                    from backend.calculations import get_mets_value, calculate_kcal
                    mets_val = get_mets_value(act.sport_type, speed_kmh, db, act.distance_km, act.elevation_gain_m)
                    act.mets_value = mets_val
                    act.kcal_burned = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m, act.sport_type)
                db.commit()
                
                return templates.TemplateResponse(
                    request=request,
                    name="register.html",
                    context={
                        "departments": departments,
                        "success": f"Đã cập nhật thông tin thành công cho VĐV {exists.full_name} (Phòng ban: {department}, Cân nặng: {weight} kg).",
                        "error": None,
                        "already_exists": False
                    }
                )
            except Exception as e:
                db.rollback()
                return templates.TemplateResponse(
                    request=request,
                    name="register.html",
                    context={
                        "departments": departments,
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
                    "departments": departments,
                    "success": None,
                    "error": f"Tên hiển thị Strava '{strava_name}' đã được đăng ký trong hệ thống.",
                    "already_exists": True,
                    "existing_athlete": exists,
                    "form_data": {
                        "full_name": full_name,
                        "gender": gender,
                        "department": department,
                        "weight": weight,
                        "strava_name": strava_name
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
        
        # Liên kết các hoạt động cũ (chưa được liên kết trước đó) sang VĐV mới này
        link_unlinked_activities(db, new_athlete)
        
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "departments": departments,
                "success": f"Vận động viên {full_name} đã đăng ký tham gia giải chạy thành công!",
                "error": None,
                "already_exists": False
            }
        )
    except Exception as e:
        db.rollback()
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "departments": departments,
                "success": None,
                "error": f"Lỗi hệ thống: {str(e)}",
                "already_exists": False
            }
        )

@app.get("/profile/{athlete_id}", response_class=HTMLResponse)
def profile_page(request: Request, athlete_id: int, db: Session = Depends(get_db)):
    """Trang thống kê chi tiết cá nhân vận động viên."""
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id, Athlete.is_active == True).first()
    if not athlete:
        raise HTTPException(status_code=404, detail="Không tìm thấy Vận động viên.")

    # 1. Lấy danh sách hoạt động
    activities = db.query(Activity).filter(Activity.athlete_id == athlete.id)\
                   .order_by(Activity.activity_date.desc()).all()
                   
    valid_activities = activities
    
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
    award_info = get_award_info(athlete.gender, total_kcal, db)
    
    progress_percent = 100
    if award_info["next_threshold"] > 0:
        progress_percent = min(int((total_kcal / award_info["next_threshold"]) * 100), 100)

    # 4. Tạo dữ liệu cho biểu đồ
    # Biểu đồ xu hướng KCAL theo ngày
    daily_stats = {}
    for a in reversed(valid_activities):
        daily_stats[a.activity_date] = daily_stats.get(a.activity_date, 0) + a.kcal_burned
    
    # Biểu đồ tròn tỷ lệ môn thể thao
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
        db=db
    )

    # Kiểm tra quyền Admin
    is_admin = get_admin_session(request, db) is not None

    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "athlete": athlete,
            "activities": activities,
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
            "is_admin": is_admin
        }
    )

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
def admin_dashboard(request: Request, error: str = None, success: str = None, db: Session = Depends(get_db)):
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
    athletes = db.query(Athlete).order_by(Athlete.id).all()
    mets = db.query(MetsRule).order_by(MetsRule.sport_type).all()
    rewards = db.query(RewardRule).order_by(RewardRule.gender, RewardRule.kcal_threshold).all()
    
    from backend.database import BadgeRule
    badges = db.query(BadgeRule).order_by(BadgeRule.id).all()

    # Lấy danh sách thành viên Strava có hoạt động nhưng chưa đăng ký Web App
    unlinked_names = db.query(Activity.athlete_name_raw)\
        .filter(Activity.athlete_id == None)\
        .group_by(Activity.athlete_name_raw).all()
    unlinked_athletes = [name[0] for name in unlinked_names if name[0]]

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

    # --- LOGIC THỐNG KÊ PHÂN TÍCH CHO ADMIN ---
    # 1. Chỉ số KPIs tổng hợp
    total_active_athletes = db.query(Athlete).filter(Athlete.is_active == True).count()
    total_valid_activities = db.query(Activity).count()
    total_kcal_burned = db.query(func.sum(Activity.kcal_burned)).scalar() or 0.0
    total_distance = db.query(func.sum(Activity.distance_km)).scalar() or 0.0
    total_moving_time_min = db.query(func.sum(Activity.moving_time_min)).scalar() or 0.0
    total_hours = total_moving_time_min / 60.0

    # 2. Thống kê Calo theo tuần (12 tuần gần nhất) và tháng (6 tháng gần nhất)
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

    # A. Tính Calo theo tuần (12 tuần gần nhất)
    weekly_data = {}  # Monday_date_str -> total_kcal
    max_date_monday = max_date - datetime.timedelta(days=max_date.weekday())
    for i in range(12):
        w_monday = max_date_monday - datetime.timedelta(weeks=i)
        weekly_data[w_monday.strftime("%Y-%m-%d")] = 0.0

    start_week_date = max_date_monday - datetime.timedelta(weeks=11)
    start_week_date_str = start_week_date.strftime("%Y-%m-%d")
    
    week_activities = db.query(Activity.activity_date, Activity.kcal_burned)\
        .filter(Activity.activity_date >= start_week_date_str)\
        .filter(Activity.activity_date <= max_date_str)\
        .all()

    for act_date_str, kcal in week_activities:
        try:
            act_date = datetime.datetime.strptime(act_date_str, "%Y-%m-%d").date()
            act_monday = act_date - datetime.timedelta(days=act_date.weekday())
            act_monday_str = act_monday.strftime("%Y-%m-%d")
            if act_monday_str in weekly_data:
                weekly_data[act_monday_str] += kcal
        except Exception:
            continue

    sorted_weeks = sorted(weekly_data.keys())
    weekly_labels = []
    for w in sorted_weeks:
        d = datetime.datetime.strptime(w, "%Y-%m-%d").date()
        weekly_labels.append(d.strftime("Tuần %d/%m"))
    weekly_kcal = [round(weekly_data[w], 1) for w in sorted_weeks]

    # B. Tính Calo theo tháng (6 tháng gần nhất)
    monthly_data = {}  # YYYY-MM -> total_kcal
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

    month_activities = db.query(Activity.activity_date, Activity.kcal_burned)\
        .filter(Activity.activity_date >= start_month_date_str)\
        .filter(Activity.activity_date <= max_date_str)\
        .all()

    for act_date_str, kcal in month_activities:
        try:
            ym = act_date_str[:7]
            if ym in monthly_data:
                monthly_data[ym] += kcal
        except Exception:
            continue

    monthly_labels = []
    for ym in sorted_months_keys:
        y, m = ym.split("-")
        monthly_labels.append(f"Tháng {m}/{y}")
    monthly_kcal = [round(monthly_data[ym], 1) for ym in sorted_months_keys]

    # 3. Cơ cấu hoạt động theo bộ môn (Sport Type Distribution)
    sport_stats = db.query(
        Activity.sport_type,
        func.count(Activity.id).label("count"),
        func.sum(Activity.kcal_burned).label("kcal"),
        func.sum(Activity.distance_km).label("dist")
    ).group_by(Activity.sport_type).all()

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
        "kpis": {
            "total_athletes": total_active_athletes,
            "total_activities": total_valid_activities,
            "total_kcal": round(total_kcal_burned, 1),
            "total_dist": round(total_distance, 1),
            "total_hours": round(total_hours, 1)
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
            "departments": departments
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
    rules_title: str = Form(...),
    rules_version: str = Form(...),
    rules_description: str = Form(...),
    rules_banner_text: str = Form(...),
    rules_general_text: str = Form(...),
    banner_file: UploadFile = File(None),
    group_qr_file: UploadFile = File(None),
    rules_banner_mode: str = Form("version"),
    rules_banner_reset_days: str = Form("1"),
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
        update_config(db, "strava_client_id", strava_client_id)
        update_config(db, "strava_client_secret", strava_client_secret)
        update_config(db, "strava_club_id", strava_club_id)
        
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
                
                # Xóa file ảnh banner cũ để giải phóng dung lượng
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
                
                # Xóa file cũ để giải phóng dung lượng
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

        return RedirectResponse("/admin?success=Cap nhat cau hinh thanh cong", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error=Loi khi luu cau hinh: {str(e)}", status_code=303)

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
        })
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
    return JSONResponse(content=res)

# --- QUẢN LÝ VẬN ĐỘNG VIÊN TRÊN ADMIN ---

@app.post("/admin/athlete/add")
def admin_add_athlete(
    request: Request,
    full_name: str = Form(...),
    gender: str = Form(...),
    department: str = Form(...),
    weight: float = Form(...),
    strava_name: str = Form(...),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    full_name = full_name.strip()
    strava_name = strava_name.strip()
    
    exists = db.query(Athlete).filter(Athlete.strava_name == strava_name).first()
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
    link_unlinked_activities(db, athlete)
    
    return RedirectResponse("/admin?success=Them thanh vien moi thanh cong", status_code=303)

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
    
    # Kiểm tra trùng strava_name với người khác
    exists = db.query(Athlete).filter(Athlete.strava_name == strava_name, Athlete.id != athlete_id).first()
    if exists:
        return RedirectResponse(f"/admin?error=Ten Strava {strava_name} da bi trung", status_code=303)
        
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
                speed_kmh = 0.0
                if act.moving_time_min > 0:
                    speed_kmh = act.distance_km / (act.moving_time_min / 60.0)
                actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
                
                # Import dynamic calculations
                from backend.calculations import get_mets_value, calculate_kcal
                mets_val = get_mets_value(act.sport_type, speed_kmh, db, act.distance_km, act.elevation_gain_m)
                act.mets_value = mets_val
                act.kcal_burned = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m, act.sport_type)
            db.commit()
            
        return RedirectResponse("/admin?success=Cap nhat thanh vien thanh cong", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error=Loi khi cap nhat thanh vien: {str(e)}", status_code=303)

@app.post("/admin/athlete/delete/{athlete_id}")
def admin_delete_athlete(athlete_id: int, request: Request, db: Session = Depends(get_db)):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
    if not athlete:
        return RedirectResponse("/admin?error=Khong tim thay thanh vien", status_code=303)
        
    try:
        # Hủy liên kết các hoạt động trước khi xóa
        db.query(Activity).filter(Activity.athlete_id == athlete.id).update({Activity.athlete_id: None})
        db.delete(athlete)
        db.commit()
        return RedirectResponse("/admin?success=Da xoa thanh vien khoi giai chay", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi khi xoa: {str(e)}", status_code=303)

# --- QUẢN LÝ METS & GIẢI THƯỞNG TRÊN ADMIN ---

@app.post("/admin/mets/edit")
def edit_mets_rules(
    request: Request,
    id: list[int] = Form(None),
    sport_type: list[str] = Form(...),
    min_speed: list[float] = Form(...),
    max_speed: list[float] = Form(...),
    met_value: list[float] = Form(...),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        # Xóa các quy tắc METs cũ và viết lại mới
        db.query(MetsRule).delete()
        
        for i in range(len(sport_type)):
            if not sport_type[i].strip():
                continue
            rule = MetsRule(
                sport_type=sport_type[i].strip(),
                min_speed=min_speed[i],
                max_speed=max_speed[i],
                met_value=met_value[i]
            )
            db.add(rule)
        db.commit()
        return RedirectResponse("/admin?success=Cap nhat he so METs thanh cong", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi cap nhat METs: {str(e)}", status_code=303)

@app.post("/admin/rewards/edit")
def edit_rewards_rules(
    request: Request,
    gender: list[str] = Form(...),
    kcal_threshold: list[float] = Form(...),
    reward_amount: list[float] = Form(...),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        db.query(RewardRule).delete()
        for i in range(len(gender)):
            if not gender[i].strip():
                continue
            rule = RewardRule(
                gender=gender[i].strip(),
                kcal_threshold=kcal_threshold[i],
                reward_amount=reward_amount[i]
            )
            db.add(rule)
        db.commit()
        return RedirectResponse("/admin?success=Cap nhat mốc giải thưởng thành công", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi cập nhật giải thưởng: {str(e)}", status_code=303)

@app.post("/admin/badges/edit")
def edit_badges_rules(
    request: Request,
    id: list[str] = Form(...),
    name: list[str] = Form(...),
    description: list[str] = Form(...),
    icon: list[str] = Form(...),
    color: list[str] = Form(...),
    threshold: list[float] = Form(...),
    db: Session = Depends(get_db)
):
    admin = get_admin_session(request, db)
    if not admin:
        return RedirectResponse("/admin?error=Chua dang nhap", status_code=303)
        
    try:
        from backend.database import BadgeRule
        for i in range(len(id)):
            rule_id = id[i].strip()
            rule = db.query(BadgeRule).filter(BadgeRule.id == rule_id).first()
            if rule:
                rule.name = name[i].strip()
                rule.description = description[i].strip()
                rule.icon = icon[i].strip()
                rule.color = color[i].strip()
                rule.threshold = threshold[i]
        db.commit()
        return RedirectResponse("/admin?success=Cập nhật cấu hình huy hiệu thành công", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Lỗi cập nhật huy hiệu: {str(e)}", status_code=303)

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
        
    res = await import_excel_files(files, db)
    
    # Tự động liên kết các hoạt động lịch sử vừa import với các vận động viên tương ứng trong DB
    try:
        athletes = db.query(Athlete).all()
        for athlete in athletes:
            link_unlinked_activities(db, athlete)
    except Exception as e:
        print(f"Error linking historical activities: {e}")
        
    return JSONResponse(content=res)

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

@app.get("/admin/export-excel")
def export_excel(
    request: Request,
    start_date: str = None,
    end_date: str = None,
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

    # 0. Xử lý khung thời gian mặc định (giống trang chủ)
    if not start_date or not end_date:
        max_date_str = db.query(func.max(Activity.activity_date)).scalar()
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

    # 1. Lấy dữ liệu BXH Cá nhân
    athlete_stats = db.query(
        Athlete.id,
        Athlete.full_name,
        Athlete.gender,
        Athlete.department,
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .filter(Athlete.is_active == True, Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
     .group_by(Athlete.id)\
     .order_by(func.sum(Activity.kcal_burned).desc()).all()

    ranked_athletes = []
    for rank, item in enumerate(athlete_stats, 1):
        award_info = get_award_info(item.gender, item.total_kcal or 0, db)
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
    dept_members = get_department_members(db, start_date, end_date)
    
    dept_stats_raw = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .filter(Athlete.is_active == True, Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
     .group_by(Athlete.department).all()
     
    dept_stats = []
    for item in dept_stats_raw:
        dept_name = item.department
        members = dept_members.get(dept_name, 1)
        total_k = item.total_kcal or 0
        avg_k = total_k / members
        dept_stats.append({
            "Tên Phòng ban": dept_name,
            "Sĩ số": members,
            "Tổng KCAL": int(total_k),
            "KCAL Trung bình / Người": round(avg_k, 0)
        })
    dept_stats = sorted(dept_stats, key=lambda x: x["KCAL Trung bình / Người"], reverse=True)
    for idx, d in enumerate(dept_stats, 1):
        d["Hạng"] = idx
        
    df_dept = pd.DataFrame(dept_stats)
    if not df_dept.empty:
        df_dept = df_dept[["Hạng", "Tên Phòng ban", "Sĩ số", "Tổng KCAL", "KCAL Trung bình / Người"]]
    else:
        df_dept = pd.DataFrame(columns=["Hạng", "Tên Phòng ban", "Sĩ số", "Tổng KCAL", "KCAL Trung bình / Người"])

    # 3. Lấy dữ liệu BXH Theo bộ môn (Nam / Nữ)
    def get_sport_data(gender: str):
        stats = db.query(
            Athlete.full_name,
            Athlete.department,
            Activity.sport_type,
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.distance_km).label("total_dist")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .filter(Athlete.is_active == True, Athlete.gender == gender, Activity.activity_date >= start_date, Activity.activity_date <= end_date)\
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
            if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
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
            idx = 0
            for g_file in gallery_files:
                if g_file.filename:
                    ext = os.path.splitext(g_file.filename)[1].lower()
                    if ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
                        filename = f"event_gal_{int(time.time())}_{idx}{ext}"
                        upload_dir = "static/uploads"
                        file_path = os.path.join(upload_dir, filename)
                        with open(file_path, "wb") as f:
                            content = await g_file.read()
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

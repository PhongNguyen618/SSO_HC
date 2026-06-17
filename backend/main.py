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

from backend.database import SessionLocal, init_db, get_db, Config, Athlete, Activity, MetsRule, RewardRule, hash_password, CompetitionEvent, CompetitionRegistration, EventMultiplier
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
            if active_event.strava_club_id:
                configs["strava_club_id"] = active_event.strava_club_id
            configs["active_event_id"] = active_event.id
                
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
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).join(Activity, Athlete.id == Activity.athlete_id)
    
    if event_id:
        query_stats = query_stats.join(
            CompetitionRegistration,
            (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
        )
        
    athlete_stats = query_stats.filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.id)\
     .order_by(func.sum(Activity.kcal_burned).desc()).all()
     
    # Tính giải thưởng tương ứng cho từng VĐV trên BXH
    ranked_athletes = []
    for rank, item in enumerate(athlete_stats, 1):
        award_info = get_award_info(item.gender, item.total_kcal or 0, db, event_id=event_id)
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

    # 3. Xếp hạng theo Phòng ban
    dept_members = get_department_members(db, start_date, end_date, event_id=event_id)
    
    dept_query = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal")
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
        stats_query = db.query(
            Athlete.id,
            Athlete.full_name,
            Activity.sport_type,
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.distance_km).label("total_dist")
        ).join(Activity, Athlete.id == Activity.athlete_id)
        
        if event_id:
            stats_query = stats_query.join(
                CompetitionRegistration,
                (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id)
            )
            
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
            "selected_event_id": event_id
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
        if selected_event.strava_club_id:
            configs["strava_club_id"] = selected_event.strava_club_id
            
    selected_event_id = selected_event.id if selected_event else None
    
    mets = []
    if selected_event_id:
        mets = db.query(MetsRule).filter(MetsRule.event_id == selected_event_id).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
    if not mets:
        mets = db.query(MetsRule).filter(MetsRule.event_id == None).order_by(MetsRule.sport_type, MetsRule.min_speed).all()
        
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
    unlinked_athletes = [name[0] for name in unlinked_names if name[0]]

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
    full_name = full_name.strip()
    strava_name = strava_name.strip()
    
    # Lấy danh sách tên Strava chưa liên kết để hiển thị gợi ý khi xảy ra lỗi/cập nhật
    unlinked_names = db.query(Activity.athlete_name_raw)\
        .filter(Activity.athlete_id == None)\
        .group_by(Activity.athlete_name_raw).all()
    unlinked_athletes = [name[0] for name in unlinked_names if name[0]]

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
                    mets_val = get_mets_value(act.sport_type, speed_kmh, db, act.distance_km, act.elevation_gain_m, event_id=act.event_id)
                    act.mets_value = mets_val
                    mult = get_multiplier_for_date(act.activity_date, act.event_id, db)
                    kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m, act.sport_type)
                    act.kcal_burned_raw = kcal_raw
                    act.kcal_burned = round(kcal_raw * mult)
                    act.multiplier = mult
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
                
                return templates.TemplateResponse(
                    request=request,
                    name="register.html",
                    context={
                        "configs": get_config_dict(db),
                        "departments": departments,
                        "active_competitions": active_competitions,
                        "selected_event_id": event_id,
                        "unlinked_athletes": unlinked_athletes,
                        "success": f"Đã cập nhật thông tin và đăng ký giải chạy thành công cho VĐV {exists.full_name}!",
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
        
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={
                "configs": get_config_dict(db),
                "departments": departments,
                "active_competitions": active_competitions,
                "selected_event_id": event_id,
                "unlinked_athletes": unlinked_athletes,
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
    ).filter(CompetitionRegistration.athlete_id == athlete.id).order_by(CompetitionEvent.id).all()
    
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
        selected_event = registered_events[0]
        
    if not selected_event:
        # Fallback nếu chưa đăng ký giải nào, lấy giải hoạt động đầu tiên
        selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).order_by(CompetitionEvent.id).first()
        
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
        
    activities = activities_query.order_by(Activity.activity_date.desc()).all()
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
    award_info = get_award_info(athlete.gender, total_kcal, db, event_id=selected_event_id)
    
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
            "is_admin": is_admin,
            "registered_events": registered_events,
            "unregistered_events": unregistered_events,
            "selected_event": selected_event,
            "selected_event_id": selected_event_id
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

    # Lấy danh sách giải đấu để hiển thị trong tab quản lý
    all_competitions = db.query(CompetitionEvent).order_by(CompetitionEvent.id.desc()).all()

    # --- LOGIC THỐNG KÊ PHÂN TÍCH CHO ADMIN ---
    # --- LOGIC THỐNG KÊ PHÂN TÍCH CHO ADMIN ---
    # 1. Chỉ số KPIs tổng hợp
    if selected_event_id:
        total_active_athletes = db.query(Athlete).join(
            CompetitionRegistration,
            Athlete.id == CompetitionRegistration.athlete_id
        ).filter(CompetitionRegistration.event_id == selected_event_id, Athlete.is_active == True).count()
        
        total_valid_activities = db.query(Activity).filter(Activity.event_id == selected_event_id).count()
        total_kcal_burned = db.query(func.sum(Activity.kcal_burned)).filter(Activity.event_id == selected_event_id).scalar() or 0.0
        total_distance = db.query(func.sum(Activity.distance_km)).filter(Activity.event_id == selected_event_id).scalar() or 0.0
        total_moving_time_min = db.query(func.sum(Activity.moving_time_min)).filter(Activity.event_id == selected_event_id).scalar() or 0.0
    else:
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
    
    week_query = db.query(Activity.activity_date, Activity.kcal_burned)\
        .filter(Activity.activity_date >= start_week_date_str)\
        .filter(Activity.activity_date <= max_date_str)
    if selected_event_id:
        week_query = week_query.filter(Activity.event_id == selected_event_id)
    week_activities = week_query.all()

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

    month_query = db.query(Activity.activity_date, Activity.kcal_burned)\
        .filter(Activity.activity_date >= start_month_date_str)\
        .filter(Activity.activity_date <= max_date_str)
    if selected_event_id:
        month_query = month_query.filter(Activity.event_id == selected_event_id)
    month_activities = month_query.all()

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
    sport_query = db.query(
        Activity.sport_type,
        func.count(Activity.id).label("count"),
        func.sum(Activity.kcal_burned).label("kcal"),
        func.sum(Activity.distance_km).label("dist")
    )
    if selected_event_id:
        sport_query = sport_query.filter(Activity.event_id == selected_event_id)
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
            "departments": departments,
            "all_competitions": all_competitions,
            "selected_event_id": selected_event_id
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
        update_config(db, "strava_club_id", extract_strava_club_id(strava_club_id))
        
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

        return RedirectResponse("/admin?success=Cap nhat cau hinh thanh cong#tab-config", status_code=303)
    except Exception as e:
        return RedirectResponse(f"/admin?error=Loi khi luu cau hinh: {str(e)}#tab-config", status_code=303)

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
    event_id: Optional[int] = Form(None),
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
    
    # Kiểm tra trùng strava_name với người khác
    exists = db.query(Athlete).filter(Athlete.strava_name == strava_name, Athlete.id != athlete_id).first()
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
                speed_kmh = 0.0
                if act.moving_time_min > 0:
                    speed_kmh = act.distance_km / (act.moving_time_min / 60.0)
                actual_time_min = act.elapsed_time_min if act.moving_time_min < 1.0 else act.moving_time_min
                
                from backend.calculations import get_mets_value, calculate_kcal
                mets_val = get_mets_value(act.sport_type, speed_kmh, db, act.distance_km, act.elevation_gain_m, event_id=act.event_id)
                act.mets_value = mets_val
                mult = get_multiplier_for_date(act.activity_date, act.event_id, db)
                kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m, act.sport_type)
                act.kcal_burned_raw = kcal_raw
                act.kcal_burned = round(kcal_raw * mult)
                act.multiplier = mult
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
        # Hủy liên kết các hoạt động trước khi xóa
        db.query(Activity).filter(Activity.athlete_id == athlete.id).update({Activity.athlete_id: None})
        db.delete(athlete)
        db.commit()
        return RedirectResponse(f"/admin?success=Da xoa thanh vien khoi giai chay&event_id={event_id or ''}#tab-athletes", status_code=303)
    except Exception as e:
        db.rollback()
        return RedirectResponse(f"/admin?error=Loi khi xoa: {str(e)}&event_id={event_id or ''}#tab-athletes", status_code=303)

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
            
            speed_kmh = 0.0
            if act.moving_time_min and act.moving_time_min > 0:
                speed_kmh = act.distance_km / (act.moving_time_min / 60.0)
            actual_time_min = act.elapsed_time_min if (act.moving_time_min or 0) < 1.0 else act.moving_time_min
            
            mets_val = get_mets_value(act.sport_type, speed_kmh, db, act.distance_km, act.elevation_gain_m, event_id=event_id)
            kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, act.elevation_gain_m or 0, act.sport_type)
            mult = get_multiplier_for_date(act.activity_date, event_id, db)
            
            act.mets_value = mets_val
            act.kcal_burned_raw = kcal_raw
            act.kcal_burned = round(kcal_raw * mult)
            act.multiplier = mult
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
        
        # Tính lại METs & KCAL dựa trên cân nặng của vận động viên
        athlete = db.query(Athlete).filter(Athlete.id == activity.athlete_id).first()
        weight = athlete.weight if athlete else 60.0
        
        speed_kmh = distance_km / (moving_time_min / 60.0) if moving_time_min > 0 else 0.0
        actual_time_min = elapsed_time_min if moving_time_min < 1.0 else moving_time_min
        
        from backend.calculations import get_mets_value, calculate_kcal, get_multiplier_for_date
        mets_val = get_mets_value(sport_type.strip(), speed_kmh, db, distance_km, elevation_gain_m, event_id=activity.event_id)
        activity.mets_value = mets_val
        
        if kcal_burned is not None:
            activity.kcal_burned = kcal_burned
            activity.kcal_burned_raw = kcal_burned
            activity.multiplier = 1.0
        else:
            mult = get_multiplier_for_date(activity_date.strip(), activity.event_id, db)
            kcal_raw = calculate_kcal(mets_val, weight, actual_time_min, elevation_gain_m, sport_type.strip())
            activity.kcal_burned_raw = kcal_raw
            activity.kcal_burned = round(kcal_raw * mult)
            activity.multiplier = mult
            
        # Tính lại pace
        if distance_km > 0:
            activity.pace_min_km = round(moving_time_min / distance_km, 2)
        else:
            activity.pace_min_km = 0.0
            
        db.commit()
        return JSONResponse(content={"status": "success", "message": "Cập nhật hoạt động thành công"})
    except Exception as e:
        db.rollback()
        return JSONResponse(status_code=500, content={"error": f"Lỗi cập nhật hoạt động: {str(e)}"})

@app.post("/admin/activity/deduplicate")
def api_deduplicate_activities(request: Request, db: Session = Depends(get_db)):
    """API dọn dẹp dữ liệu trùng lặp trong DB, chỉ dành cho Admin."""
    admin_session = get_admin_session(request, db)
    if not admin_session:
        return JSONResponse(status_code=401, content={"error": "Chưa đăng nhập admin"})
        
    try:
        activities = db.query(Activity).all()
        seen_activities = {}
        to_delete = []
        updated_count = 0
        
        import hashlib
        
        for act in activities:
            dist_km_round = round(float(act.distance_km or 0), 2)
            mov_time_round = round(float(act.moving_time_min or 0), 1)
            ela_time_round = round(float(act.elapsed_time_min or 0), 1)
            elev_round = float(act.elevation_gain_m or 0)
            
            unique_str = f"{act.athlete_name_raw}_{act.name}_{act.sport_type}_{dist_km_round}_{mov_time_round}_{ela_time_round}_{elev_round}"
            
            if unique_str in seen_activities:
                to_delete.append(act.id)
            else:
                seen_activities[unique_str] = act.id
                
                # Đồng bộ ID của hoạt động
                new_id = hashlib.sha256(unique_str.encode("utf-8")).hexdigest()
                if act.id != new_id:
                    try:
                        exists = db.query(Activity).filter(Activity.id == new_id).first()
                        if not exists:
                            db.execute(
                                Activity.__table__.update().where(Activity.id == act.id).values(id=new_id)
                            )
                            updated_count += 1
                    except Exception:
                        pass
                        
        deleted_count = 0
        if to_delete:
            # Chuyển đổi mảng to_delete thành danh sách và xóa hàng loạt
            deleted_count = db.query(Activity).filter(Activity.id.in_(to_delete)).delete(synchronize_session=False)
            
        db.commit()
        return JSONResponse(content={
            "status": "success",
            "deleted_count": deleted_count,
            "updated_count": updated_count,
            "message": f"Đã dọn dẹp thành công {deleted_count} hoạt động trùng lặp và đồng bộ hóa {updated_count} khóa ID."
        })
    except Exception as e:
        db.rollback()
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

    base_filters = [Activity.activity_date >= start_date, Activity.activity_date <= end_date]
    if event_id:
        base_filters.append(Activity.event_id == event_id)

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
        
    athlete_stats = query_stats.filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.id)\
     .order_by(func.sum(Activity.kcal_burned).desc()).all()

    ranked_athletes = []
    for rank, item in enumerate(athlete_stats, 1):
        award_info = get_award_info(item.gender, item.total_kcal or 0, db, event_id=event_id)
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
        func.sum(Activity.kcal_burned).label("total_kcal")
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
    banner_file: UploadFile = File(None),
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
            department_members=dept_json if dept_json else None
        )
        db.add(new_comp)
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
    banner_file: UploadFile = File(None),
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
        
        db.delete(comp)  # cascade sẽ xóa activities liên quan
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
    return JSONResponse(content=res)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)

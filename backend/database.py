import os
import hashlib
import pandas as pd
import json
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from dotenv import load_dotenv

# Tải cấu hình từ file .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///SSO_HC.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# Tự động kích hoạt PRAGMA foreign_keys = ON đối với SQLite để thực thi ràng buộc khóa ngoại
from sqlalchemy.engine import Engine
from sqlalchemy import event

@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Config(Base):
    __tablename__ = "configs"
    key = Column(String, primary_key=True, index=True)
    value = Column(String, nullable=True)

class Athlete(Base):
    __tablename__ = "athletes"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String, index=True)
    department = Column(String)
    gender = Column(String) # Nam / Nữ
    weight = Column(Float)
    strava_name = Column(String, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String, nullable=True)
    strava_athlete_id = Column(String, unique=True, index=True, nullable=True)
    
    # OAuth tokens cá nhân
    strava_access_token = Column(String, nullable=True)
    strava_refresh_token = Column(String, nullable=True)
    strava_expires_at = Column(String, nullable=True)

    activities = relationship("Activity", back_populates="athlete")

class MetsRule(Base):
    __tablename__ = "mets_rules"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("competition_events.id", ondelete="CASCADE"), nullable=True)
    sport_type = Column(String, index=True) # e.g. Walk, Run, Ride, Swim, Elliptical
    min_speed = Column(Float)
    max_speed = Column(Float)
    met_value = Column(Float)

class RewardRule(Base):
    __tablename__ = "reward_rules"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("competition_events.id", ondelete="CASCADE"), nullable=True)
    gender = Column(String) # Nam / Nữ
    kcal_threshold = Column(Float)
    reward_amount = Column(Float) # VND

class BadgeRule(Base):
    __tablename__ = "badge_rules"
    id = Column(String, primary_key=True, index=True) # e.g. "fresh_start" hoặc "fresh_start_2"
    badge_key = Column(String, index=True, nullable=True) # e.g. "fresh_start"
    event_id = Column(Integer, ForeignKey("competition_events.id", ondelete="CASCADE"), nullable=True)
    name = Column(String)
    description = Column(String)
    icon = Column(String)
    color = Column(String)
    threshold = Column(Float)
    unit = Column(String) # "activities", "run_distance_km", "ride_distance_km", "total_time_hours", "total_kcal", "max_streak_days"

class ArchivedEvent(Base):
    __tablename__ = "archived_events"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True)
    banner_image = Column(String)
    video_url = Column(String, nullable=True)
    summary_text = Column(String)
    gallery_images = Column(String, nullable=True) # Danh sách ảnh ngăn cách bởi dấu phẩy

class CompetitionEvent(Base):
    __tablename__ = "competition_events"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(String, index=True)
    strava_club_id = Column(String)
    start_date = Column(String) # Format: YYYY-MM-DD
    end_date = Column(String)   # Format: YYYY-MM-DD
    is_active = Column(Boolean, default=True)
    description = Column(String, nullable=True)
    banner_image = Column(String, nullable=True)
    rules_description = Column(String, nullable=True)
    rules_banner_text = Column(String, nullable=True)
    rules_general_text = Column(String, nullable=True)
    reward_type = Column(String, default="milestone", nullable=True) # "milestone" hoặc "linear"
    reward_linear_kcal = Column(Float, default=100.0, nullable=True)
    reward_linear_amount = Column(Float, default=5000.0, nullable=True)
    show_rewards_in_rules = Column(Boolean, default=True, nullable=True)
    department_members = Column(String, nullable=True) # Cấu hình sĩ số phòng ban dạng JSON string
    ranking_metric = Column(String, default="kcal", nullable=True) # "kcal" hoặc "distance"
    ranking_sports = Column(String, default="All", nullable=True) # Mặc định là tất cả bộ môn "All"
    rules_group_qr = Column(String, nullable=True) # Đường dẫn QR code group Strava riêng của giải đấu
    avatar_frame = Column(String, nullable=True) # Đường dẫn khung viền avatar riêng của giải đấu
    flag_manual_activities = Column(Boolean, default=False, nullable=True)
    heartrate_check = Column(Boolean, default=False, nullable=True)
    max_rest_ratio = Column(Float, default=1.0, nullable=True)

    activities = relationship("Activity", back_populates="event", cascade="all, delete-orphan")
    hidden_reward_configs = relationship("HiddenRewardConfig", back_populates="event", cascade="all, delete-orphan")


class CompetitionRegistration(Base):
    __tablename__ = "competition_registrations"
    athlete_id = Column(Integer, ForeignKey("athletes.id", ondelete="CASCADE"), primary_key=True)
    event_id = Column(Integer, ForeignKey("competition_events.id", ondelete="CASCADE"), primary_key=True)
    registered_at = Column(DateTime, default=datetime.utcnow)

    athlete = relationship("Athlete")
    event = relationship("CompetitionEvent")

class EventMultiplier(Base):
    __tablename__ = "event_multipliers"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("competition_events.id", ondelete="CASCADE"), nullable=False)
    special_date = Column(String, nullable=True) # Định dạng YYYY-MM-DD
    day_of_week = Column(Integer, nullable=True) # 0-6 (0: Thứ 2, ..., 6: Chủ nhật)
    multiplier = Column(Float, default=2.0)
    description = Column(String, nullable=True)
    
    event = relationship("CompetitionEvent")

class HiddenRewardConfig(Base):
    __tablename__ = "hidden_reward_configs"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("competition_events.id", ondelete="CASCADE"), nullable=False)
    department = Column(String, nullable=False)

    event = relationship("CompetitionEvent", back_populates="hidden_reward_configs")


class SupportTicket(Base):
    __tablename__ = "support_tickets"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    athlete_name = Column(String, nullable=True)
    contact_info = Column(String, nullable=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="pending") # pending, resolved, ignored
    admin_notes = Column(String, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

class Activity(Base):
    __tablename__ = "activities"
    # id can be a SHA256 of composite key if Strava ID is missing
    id = Column(String, primary_key=True, index=True)
    athlete_id = Column(Integer, ForeignKey("athletes.id"), nullable=True)
    event_id = Column(Integer, ForeignKey("competition_events.id"), nullable=True)
    athlete_name_raw = Column(String)
    name = Column(String)
    type = Column(String)
    sport_type = Column(String)
    distance_km = Column(Float)
    moving_time_min = Column(Float)
    elapsed_time_min = Column(Float)
    pace_min_km = Column(Float)
    elevation_gain_m = Column(Float)
    activity_date = Column(String, index=True) # Format: YYYY-MM-DD
    activity_time = Column(String, nullable=True) # Format: HH:MM (giờ phút local)
    sync_date = Column(DateTime, default=datetime.utcnow)
    kcal_burned = Column(Float)
    mets_value = Column(Float)
    is_suspicious = Column(Boolean, default=False)
    suspicion_reason = Column(String, nullable=True)
    distance_km_raw = Column(Float, nullable=True)
    kcal_burned_raw = Column(Float, nullable=True)
    multiplier = Column(Float, default=1.0)
    is_manual = Column(Boolean, default=False, nullable=True)
    has_heartrate = Column(Boolean, default=False, nullable=True)
    average_heartrate = Column(Float, nullable=True)
    max_heartrate = Column(Float, nullable=True)

    athlete = relationship("Athlete", back_populates="activities")
    event = relationship("CompetitionEvent", back_populates="activities")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def init_db(excel_filepath: str = "TDTT_SSO.xlsx"):
    Base.metadata.create_all(bind=engine)
    
    # Thực hiện di trú cột event_id nếu chưa có
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    
    # Di trú cho bảng athletes
    athlete_columns = [c['name'] for c in inspector.get_columns('athletes')]
    if 'avatar_url' not in athlete_columns:
        print("Database Migration: Adding avatar_url column to athletes table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE athletes ADD COLUMN avatar_url TEXT"))
            conn.commit()
            
    if 'strava_athlete_id' not in athlete_columns:
        print("Database Migration: Adding strava_athlete_id column to athletes table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE athletes ADD COLUMN strava_athlete_id TEXT"))
            conn.commit()
            
    if 'strava_access_token' not in athlete_columns:
        print("Database Migration: Adding strava_access_token column to athletes table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE athletes ADD COLUMN strava_access_token TEXT"))
            conn.commit()

    if 'strava_refresh_token' not in athlete_columns:
        print("Database Migration: Adding strava_refresh_token column to athletes table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE athletes ADD COLUMN strava_refresh_token TEXT"))
            conn.commit()

    if 'strava_expires_at' not in athlete_columns:
        print("Database Migration: Adding strava_expires_at column to athletes table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE athletes ADD COLUMN strava_expires_at TEXT"))
            conn.commit()

    columns = [c['name'] for c in inspector.get_columns('activities')]
    if 'event_id' not in columns:
        print("Database Migration: Adding event_id column to activities table...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN event_id INTEGER REFERENCES competition_events(id)"))
            conn.commit()

    # Di trú các cột cho cự ly, calo gốc và multiplier
    if 'distance_km_raw' not in columns:
        print("Database Migration: Adding distance_km_raw column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN distance_km_raw FLOAT"))
            conn.commit()
        # Copy giá trị từ distance_km sang distance_km_raw
        with engine.connect() as conn:
            conn.execute(text("UPDATE activities SET distance_km_raw = distance_km WHERE distance_km_raw IS NULL"))
            conn.commit()
            
    if 'kcal_burned_raw' not in columns:
        print("Database Migration: Adding kcal_burned_raw column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN kcal_burned_raw FLOAT"))
            conn.commit()
        with engine.connect() as conn:
            conn.execute(text("UPDATE activities SET kcal_burned_raw = kcal_burned WHERE kcal_burned_raw IS NULL"))
            conn.commit()
            
    if 'multiplier' not in columns:
        print("Database Migration: Adding multiplier column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN multiplier FLOAT DEFAULT 1.0"))
            conn.commit()

    if 'activity_time' not in columns:
        print("Database Migration: Adding activity_time column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN activity_time TEXT"))
            conn.commit()

    if 'is_manual' not in columns:
        print("Database Migration: Adding is_manual column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN is_manual BOOLEAN DEFAULT 0"))
            conn.commit()
    if 'has_heartrate' not in columns:
        print("Database Migration: Adding has_heartrate column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN has_heartrate BOOLEAN DEFAULT 0"))
            conn.commit()
    if 'average_heartrate' not in columns:
        print("Database Migration: Adding average_heartrate column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN average_heartrate FLOAT"))
            conn.commit()
    if 'max_heartrate' not in columns:
        print("Database Migration: Adding max_heartrate column to activities...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE activities ADD COLUMN max_heartrate FLOAT"))
            conn.commit()

    # Di trú các cột cho mets_rules, reward_rules, badge_rules
    mets_columns = [c['name'] for c in inspector.get_columns('mets_rules')]
    if 'event_id' not in mets_columns:
        print("Database Migration: Adding event_id column to mets_rules...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE mets_rules ADD COLUMN event_id INTEGER REFERENCES competition_events(id)"))
            conn.commit()

    reward_columns = [c['name'] for c in inspector.get_columns('reward_rules')]
    if 'event_id' not in reward_columns:
        print("Database Migration: Adding event_id column to reward_rules...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE reward_rules ADD COLUMN event_id INTEGER REFERENCES competition_events(id)"))
            conn.commit()

    badge_columns = [c['name'] for c in inspector.get_columns('badge_rules')]
    if 'event_id' not in badge_columns:
        print("Database Migration: Adding event_id column to badge_rules...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE badge_rules ADD COLUMN event_id INTEGER REFERENCES competition_events(id)"))
            conn.commit()
            
    if 'badge_key' not in badge_columns:
        print("Database Migration: Adding badge_key column to badge_rules...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE badge_rules ADD COLUMN badge_key VARCHAR"))
            conn.commit()

    # Di trú các cột cho competition_events
    comp_columns = [c['name'] for c in inspector.get_columns('competition_events')]
    if 'reward_type' not in comp_columns:
        print("Database Migration: Adding reward_type column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN reward_type VARCHAR DEFAULT 'milestone'"))
            conn.commit()
    if 'reward_linear_kcal' not in comp_columns:
        print("Database Migration: Adding reward_linear_kcal column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN reward_linear_kcal FLOAT DEFAULT 100.0"))
            conn.commit()
    if 'reward_linear_amount' not in comp_columns:
        print("Database Migration: Adding reward_linear_amount column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN reward_linear_amount FLOAT DEFAULT 5000.0"))
            conn.commit()
    if 'show_rewards_in_rules' not in comp_columns:
        print("Database Migration: Adding show_rewards_in_rules column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN show_rewards_in_rules BOOLEAN DEFAULT 1"))
            conn.commit()
    if 'department_members' not in comp_columns:
        print("Database Migration: Adding department_members column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN department_members TEXT"))
            conn.commit()
    if 'ranking_metric' not in comp_columns:
        print("Database Migration: Adding ranking_metric column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN ranking_metric VARCHAR DEFAULT 'kcal'"))
            conn.commit()
    if 'ranking_sports' not in comp_columns:
        print("Database Migration: Adding ranking_sports column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN ranking_sports VARCHAR DEFAULT 'All'"))
            conn.commit()
    if 'rules_group_qr' not in comp_columns:
        print("Database Migration: Adding rules_group_qr column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN rules_group_qr VARCHAR"))
            conn.commit()
            
    if 'avatar_frame' not in comp_columns:
        print("Database Migration: Adding avatar_frame column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN avatar_frame TEXT"))
            conn.commit()

    if 'flag_manual_activities' not in comp_columns:
        print("Database Migration: Adding flag_manual_activities column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN flag_manual_activities BOOLEAN DEFAULT 0"))
            conn.commit()
    if 'heartrate_check' not in comp_columns:
        print("Database Migration: Adding heartrate_check column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN heartrate_check BOOLEAN DEFAULT 0"))
            conn.commit()
    if 'max_rest_ratio' not in comp_columns:
        print("Database Migration: Adding max_rest_ratio column to competition_events...")
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE competition_events ADD COLUMN max_rest_ratio FLOAT DEFAULT 1.0"))
            conn.commit()

    # Phục hồi các giải đấu đang bị giới hạn về 4 môn mặc định hoặc NULL/rỗng trở lại thành 'All' để tính calo cho tất cả các môn như ban đầu
    with engine.connect() as conn:
        conn.execute(text("UPDATE competition_events SET ranking_sports = 'All' WHERE ranking_sports = 'Run,Walk,Ride,Swim' OR ranking_sports IS NULL OR ranking_sports = ''"))
        conn.commit()

    db = SessionLocal()

    default_admin_user = os.getenv("DEFAULT_ADMIN_USER", "admin")
    default_admin_pass = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
    default_department_members = {
        "BAN GIÁM ĐỐC": 2,
        "PHÒNG HÀNH CHÍNH NHÂN SỰ": 21,
        "PHÒNG KỸ THUẬT": 4,
        "PHÒNG KINH DOANH": 22,
        "PHÒNG TÀI CHÍNH KẾ TOÁN": 4,
        "PHÒNG KHAI THÁC": 12,
        "PHÒNG VẬN HÀNH": 40
    }

    # 1. Khởi tạo cấu hình mặc định (nếu chưa có)
    default_configs = {
        "strava_client_id": os.getenv("STRAVA_CLIENT_ID", ""),
        "strava_client_secret": os.getenv("STRAVA_CLIENT_SECRET", ""),
        "strava_club_id": os.getenv("STRAVA_CLUB_ID", ""),
        "sync_interval_hours": "1",
        "admin_username": default_admin_user,
        "admin_password_hash": hash_password(default_admin_pass),
        "strava_access_token": "",
        "strava_refresh_token": "",
        "strava_expires_at": "0",
        "user_auth_banner_show": "false",
        "user_auth_banner_text": "⚠️ Chú ý: Các VĐV chưa liên kết Strava vui lòng click vào đây để kết nối tài khoản ngay!",
        "user_auth_popup_show": "true",
        "user_auth_popup_title": "KẾT NỐI STRAVA CỦA BẠN!",
        "user_auth_popup_desc": "Chào bạn! Hệ thống nhận thấy bạn chưa hoàn tất liên kết Strava cá nhân. Hãy liên kết ngay để các hoạt động chạy bộ/đi bộ được tự động ghi nhận chính xác 100% lên bảng thành tích.",
        "user_auth_popup_cooldown": "12",
        "zalo_group_qr": "",
        "rules_title": "GIẢI CHẠY BỘ SSO HC",
        "rules_version": "v1.0",
        "rules_description": "Chào mừng các Vận động viên tham gia giải chạy phong trào SSO HC! Giải đấu nhằm khuyến khích tinh thần rèn luyện sức khỏe, nâng cao sức bền và gắn kết tập thể giữa các phòng ban. Các hoạt động được đồng bộ tự động từ tài khoản Strava cá nhân đã liên kết và được quy đổi năng lượng tiêu thụ (KCAL) làm cơ sở xếp hạng thành tích.",
        "rules_banner_text": "Chào mừng các Vận động viên tham gia giải chạy phong trào SSO HC!\n\n1. Tính điểm bằng năng lượng (KCAL) tích lũy.\n2. Hệ thống chống gian lận tự động quét tốc độ hợp lệ.\n3. Các mốc giải thưởng hấp dẫn dành riêng cho Nam và Nữ.",
        "rules_banner_image": "",
        "rules_general_text": "1. Đối tượng tham gia: Toàn bộ CBNV chính thức của công ty đã đăng ký tài khoản trên hệ thống SSO HC.\n2. Thời gian ghi nhận: Các hoạt động được đồng bộ tự động từ tài khoản Strava cá nhân đã liên kết.\n3. Hoạt động hợp lệ: Các hoạt động ngoài trời hoặc trong nhà được Strava ghi nhận (Chạy bộ, Đi bộ, Đạp xe, Bơi lội...) ở trạng thái công khai (Everyone).\n4. Tính minh bạch: Hệ thống tự động quét và gắn cờ cảnh báo đối với các hoạt động có dấu hiệu bất thường (sử dụng phương tiện cơ giới, vận tốc phi thực tế...).",
        # Các cấu hình cho việc phát hiện gian lận
        "rule_run_pace_min": "2.5",
        "rule_run_pace_max": "12.0",
        "rule_run_elev_ratio": "300.0",
        "rule_ride_pace_min": "1.0",
        "rule_ride_pace_max": "6.0",
        "rule_ride_elev_ratio": "250.0",
        "rule_walk_pace_min": "6.0",
        "rule_walk_pace_max": "20.0",
        "rule_walk_elev_ratio": "400.0",
        "rule_swim_pace_100m_min": "0.75", # 45s/100m
        "rule_swim_pace_100m_max": "4.0",  # 4m/100m
        "rule_swim_elev_max": "10.0",
        "department_members": json.dumps(default_department_members, ensure_ascii=False),
        "rules_group_qr": "/branding/Group.jpg",
        "rules_banner_mode": "version",
        "rules_banner_reset_days": "1"
    }

    for key, value in default_configs.items():
        exists = db.query(Config).filter(Config.key == key).first()
        if not exists:
            db.add(Config(key=key, value=value))
    db.commit()

    # 1.5. Khởi tạo Giải đấu mặc định (nếu chưa có)
    if db.query(CompetitionEvent).count() == 0:
        print("Database Migration: Creating default CompetitionEvent...")
        rules_title_conf = db.query(Config).filter(Config.key == "rules_title").first()
        club_id_conf = db.query(Config).filter(Config.key == "strava_club_id").first()
        rules_desc_conf = db.query(Config).filter(Config.key == "rules_description").first()
        banner_text_conf = db.query(Config).filter(Config.key == "rules_banner_text").first()
        gen_text_conf = db.query(Config).filter(Config.key == "rules_general_text").first()
        banner_img_conf = db.query(Config).filter(Config.key == "rules_banner_image").first()
        
        default_title = rules_title_conf.value if rules_title_conf else "Giải Chạy Bộ SSO HC Mặc Định"
        default_club = club_id_conf.value if club_id_conf else ""
        default_desc = rules_desc_conf.value if rules_desc_conf else "Chào mừng các Vận động viên tham gia giải chạy phong trào SSO HC!"
        default_banner_text = banner_text_conf.value if banner_text_conf else ""
        default_gen_text = gen_text_conf.value if gen_text_conf else ""
        default_banner_img = banner_img_conf.value if banner_img_conf else ""
        
        default_event = CompetitionEvent(
            title=default_title,
            strava_club_id=default_club,
            start_date="2020-01-01",
            end_date="2030-12-31",
            is_active=True,
            description=default_desc,
            banner_image=default_banner_img,
            rules_description=default_desc,
            rules_banner_text=default_banner_text,
            rules_general_text=default_gen_text,
            department_members=json.dumps(default_department_members, ensure_ascii=False)
        )
        db.add(default_event)
        db.commit()
        
        # Liên kết toàn bộ hoạt động cũ chưa có event_id sang giải đấu mặc định này
        print("Database Migration: Linking existing null-event activities to default event...")
        db.query(Activity).filter(Activity.event_id == None).update({Activity.event_id: default_event.id})
        db.commit()

    # 1.7. Khởi tạo Đăng ký giải đấu mặc định & tự động (di trú dữ liệu đăng ký)
    first_event = db.query(CompetitionEvent).order_by(CompetitionEvent.id).first()
    if first_event:
        to_register = set()
        
        # Tự động gom đăng ký toàn bộ Athlete hiện tại vào giải đấu mặc định (nếu chưa có đăng ký giải nào)
        all_athletes = db.query(Athlete).all()
        for athlete in all_athletes:
            # Chỉ tự động gom đăng ký nếu VĐV chưa đăng ký bất kỳ giải đấu nào
            has_reg = db.query(CompetitionRegistration).filter(
                CompetitionRegistration.athlete_id == athlete.id
            ).first()
            if not has_reg:
                to_register.add((athlete.id, first_event.id))
        
        # Tự động gom đăng ký VĐV vào các giải đấu khác nếu họ đã có hoạt động thuộc giải đấu đó
        active_activities_events = db.query(Activity.athlete_id, Activity.event_id)\
            .filter(Activity.athlete_id != None, Activity.event_id != None)\
            .distinct().all()
        for ath_id, ev_id in active_activities_events:
            to_register.add((ath_id, ev_id))
            
        # Thêm các đăng ký chưa tồn tại trong database
        for ath_id, ev_id in to_register:
            exists = db.query(CompetitionRegistration).filter(
                CompetitionRegistration.athlete_id == ath_id,
                CompetitionRegistration.event_id == ev_id
            ).first()
            if not exists:
                db.add(CompetitionRegistration(athlete_id=ath_id, event_id=ev_id))
        db.commit()

    # 2. Khởi tạo cấu hình Giải thưởng mặc định
    default_rewards = [
        RewardRule(gender="Nam", kcal_threshold=10000.0, reward_amount=100000.0),
        RewardRule(gender="Nam", kcal_threshold=3000.0, reward_amount=50000.0),
        RewardRule(gender="Nữ", kcal_threshold=5000.0, reward_amount=100000.0),
        RewardRule(gender="Nữ", kcal_threshold=1500.0, reward_amount=50000.0)
    ]
    if db.query(RewardRule).count() == 0:
        db.add_all(default_rewards)
        db.commit()

    # 2.5. Khởi tạo cấu hình Huy hiệu mặc định
    default_badges = [
        BadgeRule(id="fresh_start", badge_key="fresh_start", name="Khởi Đầu Mới", description="Hoàn thành 1 hoạt động thể thao hợp lệ đầu tiên.", icon="fa-shoe-prints", color="#8FCDF0", threshold=1.0, unit="activities"),
        BadgeRule(id="golden_boot", badge_key="golden_boot", name="Bàn Chân Vàng", description="Hoàn thành hoạt động Chạy bộ (Run) có quãng đường dài >= 10 km.", icon="fa-person-running", color="#ff5e36", threshold=10.0, unit="run_distance_km"),
        BadgeRule(id="fire_wheel", badge_key="fire_wheel", name="Bánh Xe Lửa", description="Hoàn thành hoạt động Đạp xe (Ride) có quãng đường dài >= 25 km.", icon="fa-bicycle", color="#b554f7", threshold=25.0, unit="ride_distance_km"),
        BadgeRule(id="iron_will", badge_key="iron_will", name="Sức Bền Vô Hạn", description="Tích lũy tổng thời gian tập luyện hợp lệ đạt từ 10 giờ trở lên.", icon="fa-hourglass-half", color="#94B5DE", threshold=10.0, unit="total_time_hours"),
        BadgeRule(id="calorie_hunter", badge_key="calorie_hunter", name="Thợ Săn Calo", description="Đốt cháy lượng năng lượng tích lũy đạt từ 5.000 KCAL trở lên.", icon="fa-fire", color="#ffc107", threshold=5000.0, unit="total_kcal"),
        BadgeRule(id="perseverance", badge_key="perseverance", name="Chiến Binh Bền Bỉ", description="Duy trì tần suất tập luyện liên tục trong ít nhất 5 ngày.", icon="fa-calendar-check", color="#20c997", threshold=5.0, unit="max_streak_days")
    ]
    if db.query(BadgeRule).count() == 0:
        db.add_all(default_badges)
        db.commit()
        
    # Điền badge_key cho các huy hiệu mặc định cũ nếu chưa có
    db.query(BadgeRule).filter(BadgeRule.badge_key == None).update({BadgeRule.badge_key: BadgeRule.id}, synchronize_session=False)
    db.commit()

    # 2.7. Khởi tạo Archived Events (Giải chạy quá khứ) mặc định
    default_events = [
        ArchivedEvent(
            title="Giải Chạy Bộ Phong Trào SSO HC 2025",
            banner_image="/branding/LOGO_A2.png",
            video_url="https://www.youtube.com/embed/dQw4w9WgXcQ",
            summary_text="Giải chạy bộ SSO HC 2025 đã kết thúc thành công rực rỡ với tinh thần thể thao hết mình của toàn thể CBNV. Tổng cộng có hơn 50 VĐV đăng ký tham gia, đóng góp quãng đường tích lũy hơn 1.200 km.\n\nKết quả vinh danh chung cuộc:\n- Giải Nhất Nam: Nguyễn Văn A (Phòng Kỹ Thuật)\n- Giải Nhất Nữ: Trần Thị B (Phòng Hành Chính Nhân Sự)",
            gallery_images=""
        )
    ]
    if db.query(ArchivedEvent).count() == 0:
        db.add_all(default_events)
        db.commit()

    # 3. Di chuyển dữ liệu từ Excel (DS & METs)
    if os.path.exists(excel_filepath):
        try:
            xl = pd.ExcelFile(excel_filepath)
            
            # A. Di chuyển danh sách nhân viên (DS)
            if "DS" in xl.sheet_names and db.query(Athlete).count() == 0:
                print("Importing athletes from Excel...")
                df_ds = pd.read_excel(excel_filepath, sheet_name="DS")
                for _, row in df_ds.iterrows():
                    # Tránh import dữ liệu trống
                    if pd.isna(row.get("HỌ VÀ TÊN")) or pd.isna(row.get("Name_strava")):
                        continue
                    
                    full_name = str(row["HỌ VÀ TÊN"]).strip()
                    dept = str(row.get("PHÒNG", "KHÁC")).strip()
                    gender = str(row.get("Giới tính", "Nam")).strip()
                    weight = float(row.get("Cân nặng", 60.0))
                    strava_name = str(row["Name_strava"]).strip()
                    
                    # Tránh trùng lặp tên strava
                    exists = db.query(Athlete).filter(Athlete.strava_name == strava_name).first()
                    if not exists:
                        athlete = Athlete(
                            full_name=full_name,
                            department=dept,
                            gender=gender,
                            weight=weight,
                            strava_name=strava_name,
                            is_active=True
                        )
                        db.add(athlete)
                db.commit()
                print("Athletes imported successfully.")

            # B. Di chuyển bảng hệ số METs
            if "METs" in xl.sheet_names and db.query(MetsRule).count() == 0:
                print("Importing METs rules from Excel...")
                df_mets = pd.read_excel(excel_filepath, sheet_name="METs")
                for _, row in df_mets.iterrows():
                    sport_type = str(row["Hoạt động"]).strip()
                    met_val = float(row["METs"])
                    min_speed = float(row.get("Tốc độ min(km/h)", 0.0))
                    max_speed = float(row.get("Tốc độ max(km/h)", 999.0))
                    
                    # Xử lý NaN
                    if pd.isna(min_speed): min_speed = 0.0
                    if pd.isna(max_speed): max_speed = 999.0

                    rule = MetsRule(
                        sport_type=sport_type,
                        min_speed=min_speed,
                        max_speed=max_speed,
                        met_value=met_val
                    )
                    db.add(rule)
                db.commit()
                print("METs rules imported successfully.")
                
        except Exception as e:
            print(f"Error migrating Excel data: {e}")
            db.rollback()
    else:
        # Nếu không có Excel, tự thêm các dòng METs mẫu cơ bản
        if db.query(MetsRule).count() == 0:
            print("Adding default METs rules...")
            default_mets = [
                MetsRule(sport_type="Walk", min_speed=0.0, max_speed=4.8, met_value=3.5),
                MetsRule(sport_type="Walk", min_speed=4.8, max_speed=5.5, met_value=4.3),
                MetsRule(sport_type="Walk", min_speed=5.5, max_speed=999.0, met_value=5.0),
                MetsRule(sport_type="Run", min_speed=0.0, max_speed=8.0, met_value=6.0),
                MetsRule(sport_type="Run", min_speed=8.0, max_speed=12.0, met_value=9.0),
                MetsRule(sport_type="Run", min_speed=12.0, max_speed=999.0, met_value=11.5),
                MetsRule(sport_type="Ride", min_speed=0.0, max_speed=15.0, met_value=4.0),
                MetsRule(sport_type="Ride", min_speed=15.0, max_speed=20.0, met_value=6.0),
                MetsRule(sport_type="Ride", min_speed=20.0, max_speed=999.0, met_value=8.0),
                MetsRule(sport_type="Swim", min_speed=0.0, max_speed=999.0, met_value=7.0),
            ]
            db.add_all(default_mets)
            db.commit()

    db.close()

if __name__ == "__main__":
    init_db()
    print("Database initialized.")

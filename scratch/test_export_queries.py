"""Test the updated export logic locally via standard query simulation."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Athlete, Activity, CompetitionEvent, CompetitionRegistration, HiddenRewardConfig
from sqlalchemy import func
import pandas as pd

db = SessionLocal()
event_id = 1
selected_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).first()

if selected_event:
    print(f"Testing event: {selected_event.title}")
    is_distance = getattr(selected_event, "ranking_metric", "kcal") == "distance"
    allowed_sports = [s.strip() for s in (selected_event.ranking_sports or "All").split(",") if s.strip()]
    
    event_start = getattr(selected_event, "start_date", None) or "2020-01-01"
    event_end = getattr(selected_event, "end_date", None) or "2030-12-31"
    base_act_filters = [
        Activity.event_id == event_id,
        Activity.activity_date >= str(event_start),
        Activity.activity_date <= str(event_end),
    ]

    # Query sport stats
    sport_table_query = db.query(
        Activity.sport_type,
        func.count(Activity.id).label("cnt"),
        func.sum(Activity.distance_km).label("total_km"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).filter(*base_act_filters).group_by(Activity.sport_type).order_by(func.count(Activity.id).desc()).all()
    print(f"  - Sports: {len(sport_table_query)} rows found.")

    # Dept ranking
    dept_member_q = db.query(
        Athlete.department,
        func.count(Athlete.id).label("cnt")
    ).join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
     .filter(Athlete.is_active == True)\
     .group_by(Athlete.department).all()
    dept_member_map = {dm.department: dm.cnt for dm in dept_member_q}

    dept_stats_q = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal"),
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.count(func.distinct(Athlete.id)).label("active_members")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
     .filter(Athlete.is_active == True, *base_act_filters)\
     .group_by(Athlete.department).all()

    dept_ranking = []
    for d in dept_stats_q:
        members = dept_member_map.get(d.department, d.active_members or 1) or 1
        tk = d.total_kcal or 0
        td = d.total_dist or 0
        tt = d.total_time or 0
        dept_ranking.append({
            "Phòng ban": d.department or "Chưa rõ",
            "Thành viên": members,
            "Tham gia thực tế": d.active_members or 0,
            "Tổng KM": round(td, 1),
            "Tổng KCAL": int(tk),
            "Tổng thời gian (giờ)": round(tt / 60.0, 1),
            "TB KCAL/người": round(tk / members, 0),
            "TB KM/người": round(td / members, 2)
        })
    print(f"  - Depts: {len(dept_ranking)} rows found.")

    # Runwalk top
    run_walk_rows = []
    for gender in ["Nam", "Nữ"]:
        rw_query = db.query(
            Athlete.full_name, Athlete.department,
            func.sum(Activity.distance_km).label("total_dist"),
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.count(Activity.id).label("act_count")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
         .filter(
             Athlete.is_active == True,
             Athlete.gender == gender,
             Activity.sport_type.in_(["Run", "Walk"]),
             *base_act_filters
         ).group_by(Athlete.id)\
         .order_by(func.sum(Activity.distance_km).desc())\
         .limit(5).all()
        
        for rank, item in enumerate(rw_query, 1):
            run_walk_rows.append({
                "Giới tính": gender,
                "Hạng": rank,
                "Họ và Tên": item.full_name,
                "Phòng ban": item.department or "Chưa rõ",
                "Tổng quãng đường (KM)": round(item.total_dist or 0, 1),
                "Tổng năng lượng (KCAL)": int(item.total_kcal or 0),
                "Số buổi": item.act_count or 0
            })
    print(f"  - RunWalk: {len(run_walk_rows)} rows found.")

    # Participation
    participation_rows = []
    for dm in dept_member_q:
        dept_name = dm.department or "Chưa rõ"
        registered = dm.cnt
        active_cnt = db.query(func.count(func.distinct(Activity.athlete_id))).join(
            Athlete, Athlete.id == Activity.athlete_id
        ).filter(
            Athlete.department == dm.department,
            *base_act_filters
        ).scalar() or 0
        rate = round(active_cnt / registered * 100, 1) if registered > 0 else 0.0
        participation_rows.append({
            "Đơn vị": dept_name,
            "Số VĐV đăng ký": registered,
            "Có hoạt động thực tế": active_cnt,
            "Tỷ lệ tham gia (%)": rate
        })
    print(f"  - Participation: {len(participation_rows)} rows found.")

    print("\n✅ SQL Queries executed successfully without any errors!")
else:
    print("❌ Selected event not found in database.")

db.close()

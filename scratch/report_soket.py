"""
BÁO CÁO SƠ KẾT PHONG TRÀO THỂ THAO - DỮ LIỆU TỔNG HỢP
Trích xuất từ CSDL live trên máy local (hoặc VPS).
Bao gồm:
  1. Tổng quan giải đấu
  2. BXH cá nhân Top 3 (Nam/Nữ) theo KCAL & KM
  3. BXH phòng ban
  4. BXH chạy bộ + đi bộ (Nam/Nữ) 
  5. Tiền thưởng tổng hợp
  6. Thống kê tham gia các đơn vị
"""
import sqlite3
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Athlete, Activity, CompetitionEvent, CompetitionRegistration, RewardRule, HiddenRewardConfig
from backend.calculations import get_award_info, get_multiplier_for_date
from sqlalchemy import func

db = SessionLocal()

# ==========================================
# LẤY DANH SÁCH TẤT CẢ GIẢI ĐẤU
# ==========================================
events = db.query(CompetitionEvent).filter(CompetitionEvent.is_active == True).all()

for ev in events:
    event_id = ev.id
    start_date = ev.start_date or "2020-01-01"
    end_date = ev.end_date or "2030-12-31"
    ranking_metric = getattr(ev, "ranking_metric", "kcal") or "kcal"
    is_distance = ranking_metric == "distance"
    reward_type = getattr(ev, "reward_type", "milestone") or "milestone"
    
    print("=" * 80)
    print(f"🏆 GIẢI ĐẤU: {ev.title}")
    print(f"   ID: {event_id} | Thời gian: {start_date} → {end_date}")
    print(f"   Chỉ số xếp hạng: {'Quãng đường (KM)' if is_distance else 'Năng lượng (KCAL)'}")
    print(f"   Loại thưởng: {'Tuyến tính' if reward_type == 'linear' else 'Theo mốc'}")
    if reward_type == "linear":
        step_kcal = getattr(ev, "reward_linear_kcal", 100.0) or 100.0
        step_amount = getattr(ev, "reward_linear_amount", 5000.0) or 5000.0
        print(f"   Quy đổi: Mỗi {step_kcal:.0f} KCAL = {step_amount:,.0f} VNĐ")
    print("=" * 80)

    # Base filters
    base_filters = [
        Activity.event_id == event_id,
        Activity.activity_date >= start_date,
        Activity.activity_date <= end_date,
    ]

    # Tổng đăng ký
    total_regs = db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == event_id).count()
    
    # Tổng VĐV có hoạt động
    active_athletes = db.query(func.count(func.distinct(Activity.athlete_id))).filter(*base_filters).scalar()
    
    # Tổng hoạt động
    total_acts = db.query(func.count(Activity.id)).filter(*base_filters).scalar()
    
    # Tổng KM & KCAL toàn giải
    overall = db.query(
        func.sum(Activity.distance_km).label("total_km"),
        func.sum(Activity.kcal_burned).label("total_kcal"),
        func.sum(Activity.moving_time_min).label("total_time")
    ).filter(*base_filters).first()
    
    total_km = round(overall.total_km or 0, 1)
    total_kcal = int(overall.total_kcal or 0)
    total_hours = round((overall.total_time or 0) / 60.0, 1)
    
    print(f"\n📊 TỔNG QUAN:")
    print(f"   VĐV đăng ký: {total_regs} | VĐV có hoạt động: {active_athletes}")
    print(f"   Tổng hoạt động: {total_acts:,}")
    print(f"   Tổng quãng đường: {total_km:,.1f} km")
    print(f"   Tổng năng lượng: {total_kcal:,} KCAL")
    print(f"   Tổng thời gian: {total_hours:,.1f} giờ")
    
    # Thống kê theo loại hoạt động
    sport_stats = db.query(
        Activity.sport_type,
        func.count(Activity.id).label("cnt"),
        func.sum(Activity.distance_km).label("total_km"),
        func.sum(Activity.kcal_burned).label("total_kcal")
    ).filter(*base_filters).group_by(Activity.sport_type).order_by(func.count(Activity.id).desc()).all()
    
    print(f"\n📋 THỐNG KÊ THEO MÔN:")
    for s in sport_stats:
        print(f"   {s.sport_type:15s}: {s.cnt:4d} hoạt động | {(s.total_km or 0):>10,.1f} km | {int(s.total_kcal or 0):>10,} KCAL")
    
    # ==========================================
    # BXH CÁ NHÂN TOP 10 (TỔNG HỢP)
    # ==========================================
    print(f"\n{'─'*80}")
    print(f"🥇 BXH CÁ NHÂN TỔNG HỢP - TOP 10:")
    
    for gender in ["Nam", "Nữ"]:
        athlete_stats = db.query(
            Athlete.id, Athlete.full_name, Athlete.department, Athlete.gender,
            func.sum(Activity.distance_km).label("total_dist"),
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.moving_time_min).label("total_time")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
         .filter(Athlete.is_active == True, Athlete.gender == gender, *base_filters)\
         .group_by(Athlete.id)
        
        if is_distance:
            athlete_stats = athlete_stats.order_by(func.sum(Activity.distance_km).desc())
        else:
            athlete_stats = athlete_stats.order_by(func.sum(Activity.kcal_burned).desc())
        
        results = athlete_stats.limit(10).all()
        
        hidden_depts = {r.department for r in db.query(HiddenRewardConfig).filter(HiddenRewardConfig.event_id == event_id).all()}
        
        print(f"\n   👤 {gender.upper()}:")
        print(f"   {'Hạng':>4s} | {'Họ và Tên':30s} | {'Phòng ban':20s} | {'KM':>10s} | {'KCAL':>10s} | {'Giờ':>7s} | {'Thưởng (VNĐ)':>15s}")
        print(f"   {'─'*4} | {'─'*30} | {'─'*20} | {'─'*10} | {'─'*10} | {'─'*7} | {'─'*15}")
        
        for rank, item in enumerate(results, 1):
            metric_val = item.total_dist if is_distance else item.total_kcal
            award_info = get_award_info(gender, metric_val or 0, db, event_id=event_id)
            is_hidden = item.department in hidden_depts
            reward = 0 if is_hidden else award_info["reward_amount"]
            
            medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"  {rank}"))
            km_val = round(item.total_dist or 0, 1)
            kcal_val = int(item.total_kcal or 0)
            hours_val = round((item.total_time or 0) / 60.0, 1)
            
            print(f"   {medal:>4s} | {item.full_name:30s} | {item.department:20s} | {km_val:>10,.1f} | {kcal_val:>10,} | {hours_val:>7,.1f} | {reward:>15,.0f}")
    
    # ==========================================
    # BXH PHÒNG BAN
    # ==========================================
    print(f"\n{'─'*80}")
    print(f"🏢 BXH PHÒNG BAN (theo KCAL trung bình/người):")
    
    # Đếm số thành viên thực tế mỗi phòng ban đăng ký giải
    dept_member_counts = {}
    dept_members_query = db.query(
        Athlete.department,
        func.count(Athlete.id).label("cnt")
    ).join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
     .filter(Athlete.is_active == True)\
     .group_by(Athlete.department).all()
    for dm in dept_members_query:
        dept_member_counts[dm.department] = dm.cnt
    
    dept_stats = db.query(
        Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal"),
        func.sum(Activity.distance_km).label("total_dist"),
        func.sum(Activity.moving_time_min).label("total_time"),
        func.count(func.distinct(Athlete.id)).label("active_members")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
     .filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.department).all()
    
    dept_list = []
    for d in dept_stats:
        members = dept_member_counts.get(d.department, d.active_members or 1)
        total_k = d.total_kcal or 0
        total_d = d.total_dist or 0
        total_t = d.total_time or 0
        dept_list.append({
            "department": d.department,
            "members": members,
            "active": d.active_members,
            "total_kcal": int(total_k),
            "total_dist": round(total_d, 1),
            "total_hours": round(total_t / 60.0, 1),
            "avg_kcal": round(total_k / members, 0),
            "avg_dist": round(total_d / members, 2)
        })
    
    if is_distance:
        dept_list.sort(key=lambda x: x["avg_dist"], reverse=True)
    else:
        dept_list.sort(key=lambda x: x["avg_kcal"], reverse=True)
    
    print(f"\n   {'Hạng':>4s} | {'Phòng ban':25s} | {'TV':>3s} | {'Tham gia':>8s} | {'Tổng KM':>10s} | {'Tổng KCAL':>12s} | {'TB KCAL/ng':>12s} | {'TB KM/ng':>10s}")
    print(f"   {'─'*4} | {'─'*25} | {'─'*3} | {'─'*8} | {'─'*10} | {'─'*12} | {'─'*12} | {'─'*10}")
    for rank, d in enumerate(dept_list, 1):
        medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"  {rank}"))
        print(f"   {medal:>4s} | {d['department']:25s} | {d['members']:>3d} | {d['active']:>8d} | {d['total_dist']:>10,.1f} | {d['total_kcal']:>12,} | {d['avg_kcal']:>12,.0f} | {d['avg_dist']:>10,.2f}")
    
    # ==========================================
    # BXH CHẠY BỘ + ĐI BỘ (RUN + WALK) TOP 5
    # ==========================================
    print(f"\n{'─'*80}")
    print(f"🏃 BXH CHẠY BỘ + ĐI BỘ (Run & Walk) - TOP 5:")
    
    for gender in ["Nam", "Nữ"]:
        run_walk = db.query(
            Athlete.id, Athlete.full_name, Athlete.department,
            func.sum(Activity.distance_km).label("total_dist"),
            func.sum(Activity.kcal_burned).label("total_kcal"),
            func.sum(Activity.moving_time_min).label("total_time"),
            func.count(Activity.id).label("act_count")
        ).join(Activity, Athlete.id == Activity.athlete_id)\
         .join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
         .filter(
             Athlete.is_active == True,
             Athlete.gender == gender,
             Activity.sport_type.in_(["Run", "Walk"]),
             *base_filters
         ).group_by(Athlete.id)\
         .order_by(func.sum(Activity.distance_km).desc())\
         .limit(5).all()
        
        print(f"\n   👤 {gender.upper()} (Xếp theo KM):")
        print(f"   {'Hạng':>4s} | {'Họ và Tên':30s} | {'Phòng ban':20s} | {'KM':>10s} | {'KCAL':>10s} | {'Buổi':>5s}")
        print(f"   {'─'*4} | {'─'*30} | {'─'*20} | {'─'*10} | {'─'*10} | {'─'*5}")
        
        for rank, item in enumerate(run_walk, 1):
            medal = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else f"  {rank}"))
            print(f"   {medal:>4s} | {item.full_name:30s} | {item.department:20s} | {round(item.total_dist or 0, 1):>10,.1f} | {int(item.total_kcal or 0):>10,} | {item.act_count:>5d}")
    
    # ==========================================
    # TỔNG TIỀN THƯỞNG TOÀN GIẢI
    # ==========================================
    print(f"\n{'─'*80}")
    print(f"💰 TỔNG HỢP TIỀN THƯỞNG:")
    
    all_athletes = db.query(
        Athlete.id, Athlete.full_name, Athlete.gender, Athlete.department,
        func.sum(Activity.kcal_burned).label("total_kcal"),
        func.sum(Activity.distance_km).label("total_dist")
    ).join(Activity, Athlete.id == Activity.athlete_id)\
     .join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
     .filter(Athlete.is_active == True, *base_filters)\
     .group_by(Athlete.id).all()
    
    hidden_depts = {r.department for r in db.query(HiddenRewardConfig).filter(HiddenRewardConfig.event_id == event_id).all()}
    
    total_reward = 0.0
    count_with_reward = 0
    reward_by_dept = {}
    reward_by_gender = {"Nam": 0.0, "Nữ": 0.0}
    
    for a in all_athletes:
        metric_val = a.total_dist if is_distance else a.total_kcal
        award_info = get_award_info(a.gender, metric_val or 0, db, event_id=event_id)
        is_hidden = a.department in hidden_depts
        reward = 0 if is_hidden else award_info["reward_amount"]
        
        if reward > 0:
            total_reward += reward
            count_with_reward += 1
            reward_by_gender[a.gender] = reward_by_gender.get(a.gender, 0) + reward
            reward_by_dept[a.department] = reward_by_dept.get(a.department, 0) + reward
    
    print(f"   Tổng VĐV đạt giải thưởng: {count_with_reward}/{len(all_athletes)}")
    print(f"   Tổng tiền thưởng toàn giải: {total_reward:,.0f} VNĐ")
    print(f"   Theo giới tính:")
    for g, v in reward_by_gender.items():
        print(f"     - {g}: {v:,.0f} VNĐ")
    print(f"   Theo phòng ban:")
    for dept, v in sorted(reward_by_dept.items(), key=lambda x: x[1], reverse=True):
        print(f"     - {dept}: {v:,.0f} VNĐ")
    
    # ==========================================
    # THỐNG KÊ THAM GIA CÁC ĐƠN VỊ
    # ==========================================
    print(f"\n{'─'*80}")
    print(f"📊 THỐNG KÊ THAM GIA CÁC ĐƠN VỊ (SSO + Đơn vị ngoài):")
    
    # Phân loại đơn vị nội bộ SSO vs đơn vị ngoài
    sso_depts = []
    external_depts = []
    
    all_dept_regs = db.query(
        Athlete.department,
        func.count(Athlete.id).label("cnt")
    ).join(CompetitionRegistration, (Athlete.id == CompetitionRegistration.athlete_id) & (CompetitionRegistration.event_id == event_id))\
     .filter(Athlete.is_active == True)\
     .group_by(Athlete.department).all()
    
    for dr in all_dept_regs:
        dept_name = dr.department or "Không rõ"
        # Phân loại: đơn vị ngoài thường có tên dài hoặc không thuộc SSO
        # Danh sách phòng ban nội bộ SSO (ngắn gọn):
        sso_internal = ["BAN GIÁM ĐỐC", "ĐIỀU ĐỘ", "PHƯƠNG THỨC", "CNTT & SCADA", "TỔNG HỢP", "TÀI CHÍNH", "KẾ HOẠCH"]
        is_sso = any(s in dept_name.upper() for s in sso_internal) or dept_name.startswith("SSO")
        
        entry = {"department": dept_name, "registered": dr.cnt}
        
        # Đếm số VĐV có hoạt động
        active_cnt = db.query(func.count(func.distinct(Activity.athlete_id))).join(
            Athlete, Athlete.id == Activity.athlete_id
        ).filter(
            Athlete.department == dept_name,
            *base_filters
        ).scalar()
        entry["active"] = active_cnt or 0
        entry["participation_rate"] = f"{(entry['active'] / entry['registered'] * 100):.0f}%" if entry['registered'] > 0 else "0%"
        
        if is_sso:
            sso_depts.append(entry)
        else:
            external_depts.append(entry)
    
    if sso_depts:
        print(f"\n   🏢 ĐƠN VỊ NỘI BỘ SSO:")
        print(f"   {'Phòng ban':30s} | {'Đăng ký':>8s} | {'Tham gia':>8s} | {'Tỉ lệ':>7s}")
        print(f"   {'─'*30} | {'─'*8} | {'─'*8} | {'─'*7}")
        total_reg = sum(d["registered"] for d in sso_depts)
        total_active = sum(d["active"] for d in sso_depts)
        for d in sorted(sso_depts, key=lambda x: x["active"], reverse=True):
            print(f"   {d['department']:30s} | {d['registered']:>8d} | {d['active']:>8d} | {d['participation_rate']:>7s}")
        print(f"   {'TỔNG SSO':30s} | {total_reg:>8d} | {total_active:>8d} | {(total_active/total_reg*100 if total_reg else 0):.0f}%")
    
    if external_depts:
        print(f"\n   🌐 ĐƠN VỊ NGOÀI:")
        print(f"   {'Đơn vị':30s} | {'Đăng ký':>8s} | {'Tham gia':>8s} | {'Tỉ lệ':>7s}")
        print(f"   {'─'*30} | {'─'*8} | {'─'*8} | {'─'*7}")
        for d in sorted(external_depts, key=lambda x: x["active"], reverse=True):
            print(f"   {d['department']:30s} | {d['registered']:>8d} | {d['active']:>8d} | {d['participation_rate']:>7s}")
    
    print(f"\n{'='*80}\n")

db.close()
print("✅ HOÀN THÀNH BÁO CÁO SƠ KẾT!")

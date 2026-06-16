import re
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database import MetsRule, RewardRule, Config, EventMultiplier

def get_multiplier_for_date(activity_date: str, event_id: int, db: Session) -> float:
    """
    Tra cứu hệ số nhân thành tích cho một ngày cụ thể và giải đấu.
    Ưu tiên:
      1. Ngày đặc biệt (special_date) - ưu tiên cao nhất
      2. Ngày trong tuần (day_of_week) - ưu tiên thấp hơn
      3. Mặc định 1.0 nếu không có cấu hình
    """
    if not event_id or not activity_date:
        return 1.0
    
    # 1. Tìm theo ngày cụ thể (special_date) - ưu tiên cao nhất
    special = db.query(EventMultiplier).filter(
        EventMultiplier.event_id == event_id,
        EventMultiplier.special_date == activity_date
    ).first()
    if special:
        return special.multiplier or 1.0
    
    # 2. Tìm theo ngày trong tuần (day_of_week)
    try:
        dt = datetime.strptime(activity_date, "%Y-%m-%d")
        # Python weekday(): 0=Mon, 1=Tue, ..., 6=Sun
        dow = dt.weekday()
        dow_rule = db.query(EventMultiplier).filter(
            EventMultiplier.event_id == event_id,
            EventMultiplier.day_of_week == dow,
            EventMultiplier.special_date == None
        ).first()
        if dow_rule:
            return dow_rule.multiplier or 1.0
    except (ValueError, TypeError):
        pass
    
    return 1.0

def get_mets_value(sport_type: str, speed_kmh: float, db: Session, distance_km: float = 0.0, elevation_gain_m: float = 0.0, event_id: int = None) -> float:
    """
    Tra cứu hệ số METs động từ cơ sở dữ liệu.
    - Đối với Chạy bộ (Run) và Đi bộ (Walk): Áp dụng công thức chuẩn của Hiệp hội Y học Thể thao Hoa Kỳ (ACSM) tích hợp tốc độ và độ dốc.
    - Đối với các bộ môn khác: Áp dụng phương pháp Nội suy tuyến tính (Linear Interpolation) dựa trên các khoảng tốc độ trong DB.
    """
    # 1. Áp dụng công thức ACSM cho Run và Walk (nếu có di chuyển)
    if sport_type in ('Run', 'Walk') and speed_kmh > 0.0:
        # Tốc độ S tính bằng m/phút: 1 km/h = 1000m / 60phút = 16.6667 m/min
        S = speed_kmh * 16.6667
        
        # Độ dốc G (Grade): Độ cao (m) / Quãng đường (m). Giới hạn dốc tối đa 30% tránh nhiễu GPS
        G = 0.0
        if distance_km > 0.0:
            G = min(elevation_gain_m / (distance_km * 1000.0), 0.3)
            
        if sport_type == 'Run':
            # Công thức ACSM Running: VO2 = 0.2*S + 0.9*S*G + 3.5
            vo2 = 0.2 * S + 0.9 * S * G + 3.5
        else: # Walk
            # Công thức ACSM Walking: VO2 = 0.1*S + 1.8*S*G + 3.5
            vo2 = 0.1 * S + 1.8 * S * G + 3.5
            
        # 1 MET = 3.5 ml/kg/min VO2
        mets = vo2 / 3.5
        return max(round(mets, 2), 1.0) # Tối thiểu là 1.0 METs (nghỉ ngơi)

    # 2. Áp dụng Nội suy tuyến tính cho các bộ môn khác
    rules = None
    if event_id:
        rules = db.query(MetsRule).filter(MetsRule.sport_type.ilike(sport_type), MetsRule.event_id == event_id).order_by(MetsRule.min_speed).all()
    if not rules:
        rules = db.query(MetsRule).filter(MetsRule.sport_type.ilike(sport_type), MetsRule.event_id == None).order_by(MetsRule.min_speed).all()
    if not rules:
        return 0.0
        
    # Nếu chỉ có 1 quy tắc (Gym, Yoga...) hoặc tốc độ không hợp lệ, trả về giá trị tĩnh luôn
    if len(rules) == 1 or speed_kmh <= 0.0:
        return rules[0].met_value

    V = speed_kmh
    # Nếu tốc độ thấp hơn mốc tối thiểu của quy tắc đầu tiên
    if V <= rules[0].min_speed:
        return 1.0

    # Duyệt qua các khoảng tốc độ
    for idx, rule in enumerate(rules):
        if rule.min_speed <= V <= rule.max_speed:
            V1 = rule.min_speed
            V2 = rule.max_speed
            
            # Nếu là khoảng mở cuối cùng (ví dụ max_speed là 999.0)
            if V2 >= 999.0:
                return rule.met_value
                
            # M1 là METs tại V1 (bằng METs của khoảng trước đó, hoặc 1.0 nếu là khoảng đầu tiên)
            M1 = 1.0 if idx == 0 else rules[idx-1].met_value
            M2 = rule.met_value
            
            # Công thức nội suy tuyến tính: METs = M1 + (V - V1)/(V2 - V1) * (M2 - M1)
            mets = M1 + ((V - V1) / (V2 - V1)) * (M2 - M1)
            return round(mets, 2)
            
    return rules[-1].met_value

def calculate_kcal(mets_value: float, athlete_weight: float, moving_time_min: float, elevation_gain_m: float, sport_type: str = "Other", multiplier: float = 1.0) -> float:
    """
    Quy đổi năng lượng tiêu thụ (KCAL).
    - Đối với Chạy bộ (Run) và Đi bộ (Walk): Công thức ACSM đã bao gồm năng lượng cản dốc trong METs.
    - Đối với các môn khác (như Đạp xe): Cộng thêm năng lượng leo dốc tuyến tính ngoài METs.
    - Kết quả cuối cùng được nhân với hệ số multiplier (ví dụ: x2 vào Chủ nhật).
    """
    if not athlete_weight:
        athlete_weight = 60.0
        
    if sport_type in ('Run', 'Walk'):
        # KCAL = METs * weight * (duration_hours)
        kcal = mets_value * athlete_weight * (moving_time_min / 60.0)
    else:
        # Công thức cũ cho các môn còn lại: bao gồm hệ số bổ sung dốc
        kcal = mets_value * athlete_weight * (moving_time_min / 60.0) + athlete_weight * elevation_gain_m * 0.01
        
    return round(kcal * multiplier)

def get_award_info(gender: str, total_kcal: float, db: Session, event_id: int = None) -> dict:
    """
    Tính giải thưởng dựa trên tổng KCAL và Giới tính từ bảng reward_rules hoặc theo tỉ lệ tuyến tính của giải đấu.
    Trả về dict chứa: reward_amount (VND), next_threshold (KCAL cho mốc tiếp theo).
    """
    from backend.database import CompetitionEvent
    event = None
    if event_id:
        event = db.query(CompetitionEvent).filter(CompetitionEvent.id == event_id).first()
        
    # Nếu giải đấu áp dụng tính giải thưởng dạng tuyến tính (linear)
    if event and getattr(event, "reward_type", "milestone") == "linear":
        step_kcal = getattr(event, "reward_linear_kcal", 100.0) or 100.0
        step_amount = getattr(event, "reward_linear_amount", 5000.0) or 5000.0
        
        # Tính theo số lượng block đầy (ví dụ cứ đủ 100 kcal = 5k)
        award_amount = int(total_kcal // step_kcal) * step_amount
        next_threshold = (int(total_kcal // step_kcal) + 1) * step_kcal
        
        return {
            "reward_amount": float(award_amount),
            "next_threshold": float(next_threshold),
            "has_award": award_amount > 0
        }
        
    # Tính theo mốc cố định như cũ (milestone)
    rules = None
    if event_id:
        rules = db.query(RewardRule).filter(RewardRule.gender == gender, RewardRule.event_id == event_id).order_by(RewardRule.kcal_threshold.desc()).all()
    if not rules:
        rules = db.query(RewardRule).filter(RewardRule.gender == gender, RewardRule.event_id == None).order_by(RewardRule.kcal_threshold.desc()).all()
    
    award_amount = 0.0
    next_threshold = 0.0
    
    # Tìm mốc giải thưởng cao nhất đạt được
    for rule in rules:
        if total_kcal >= rule.kcal_threshold:
            award_amount = rule.reward_amount
            break
            
    # Tìm mốc giải thưởng tiếp theo chưa đạt được
    for rule in reversed(rules):
        if total_kcal < rule.kcal_threshold:
            next_threshold = rule.kcal_threshold
            break
            
    return {
        "reward_amount": award_amount,
        "next_threshold": next_threshold,
        "has_award": award_amount > 0
    }

def check_suspicious_activity(sport_type: str, distance_km: float, pace_min_km: float, elevation_gain_m: float, configs: dict) -> tuple[bool, str]:
    """
    Kiểm tra và đánh giá xem hoạt động có dấu hiệu nghi ngờ gian lận không.
    Trả về: (is_suspicious, reason)
    """
    reasons = []
    
    # 1. Chạy bộ (Run)
    if sport_type == 'Run':
        run_pace_min = float(configs.get('rule_run_pace_min', 2.5))
        run_pace_max = float(configs.get('rule_run_pace_max', 12.0))
        run_elev_ratio = float(configs.get('rule_run_elev_ratio', 300.0))
        
        if 0 < pace_min_km < run_pace_min:
            reasons.append(f"Run: Pace cực nhanh ({pace_min_km} min/km)")
        elif run_pace_min <= pace_min_km < 3.5:
            reasons.append(f"Run: Pace rất nhanh ({pace_min_km} min/km)")
        elif pace_min_km > run_pace_max:
            reasons.append(f"Run: Pace quá chậm ({pace_min_km} min/km)")
            
        if distance_km > 0 and (elevation_gain_m / distance_km) > run_elev_ratio:
            reasons.append(f"Run: Tỷ lệ Elevation/Quãng đường bất thường ({round(elevation_gain_m / distance_km, 1)} m/km)")
        if elevation_gain_m > 6000:
            reasons.append(f"Run: Elevation quá cao ({elevation_gain_m} m)")

    # 2. Đạp xe (Ride)
    elif sport_type == 'Ride':
        ride_pace_min = float(configs.get('rule_ride_pace_min', 1.0))
        ride_pace_max = float(configs.get('rule_ride_pace_max', 6.0))
        ride_elev_ratio = float(configs.get('rule_ride_elev_ratio', 250.0))
        
        if 0 < pace_min_km < ride_pace_min:
            reasons.append(f"Ride: Tốc độ cực nhanh ({pace_min_km} min/km)")
        elif ride_pace_min <= pace_min_km < 1.2:
            reasons.append(f"Ride: Tốc độ rất nhanh ({pace_min_km} min/km)")
        elif pace_min_km > ride_pace_max:
            reasons.append(f"Ride: Tốc độ quá chậm ({pace_min_km} min/km)")
            
        if distance_km > 0 and (elevation_gain_m / distance_km) > ride_elev_ratio:
            reasons.append(f"Ride: Tỷ lệ Elevation/Quãng đường bất thường ({round(elevation_gain_m / distance_km, 1)} m/km)")
        if elevation_gain_m > 10000:
            reasons.append(f"Ride: Elevation quá cao ({elevation_gain_m} m)")

    # 3. Đi bộ (Walk)
    elif sport_type == 'Walk':
        walk_pace_min = float(configs.get('rule_walk_pace_min', 6.0))
        walk_pace_max = float(configs.get('rule_walk_pace_max', 20.0))
        walk_elev_ratio = float(configs.get('rule_walk_elev_ratio', 400.0))
        
        if 0 < pace_min_km < walk_pace_min:
            reasons.append(f"Walk: Pace cực nhanh ({pace_min_km} min/km)")
        elif pace_min_km > walk_pace_max:
            reasons.append(f"Walk: Pace quá chậm ({pace_min_km} min/km)")
            
        if distance_km > 0 and (elevation_gain_m / distance_km) > walk_elev_ratio:
            reasons.append(f"Walk: Tỷ lệ Elevation/Quãng đường bất thường ({round(elevation_gain_m / distance_km, 1)} m/km)")
        if elevation_gain_m > 4000:
            reasons.append(f"Walk: Elevation quá cao ({elevation_gain_m} m)")

    # 4. Bơi lội (Swim)
    elif sport_type == 'Swim':
        swim_pace_min = float(configs.get('rule_swim_pace_100m_min', 0.75))
        swim_pace_max = float(configs.get('rule_swim_pace_100m_max', 4.0))
        swim_elev_max = float(configs.get('rule_swim_elev_max', 10.0))
        
        pace_min_100m = pace_min_km / 10.0
        if 0 < pace_min_100m < swim_pace_min:
            reasons.append(f"Swim: Pace cực nhanh ({pace_min_100m} min/100m)")
        elif pace_min_100m > swim_pace_max:
            reasons.append(f"Swim: Pace quá chậm ({pace_min_100m} min/100m)")
        if elevation_gain_m > swim_elev_max:
            reasons.append(f"Swim: Elevation bất thường ({elevation_gain_m} m)")

    # 5. Elliptical
    elif sport_type == 'Elliptical':
        if 0 < pace_min_km < 3.0:
            reasons.append(f"Elliptical: Pace cực nhanh ({pace_min_km} min/km)")
        elif pace_min_km > 15.0:
            reasons.append(f"Elliptical: Pace quá chậm ({pace_min_km} min/km)")
        if elevation_gain_m > 100.0:
            reasons.append(f"Elliptical: Elevation bất thường ({elevation_gain_m} m)")

    # 6. Các bộ môn phụ trợ khác (Gym, Yoga, Soccer...)
    else:
        other_sports = ['Gym', 'Yoga', 'Soccer', 'Badminton', 'Table tennis', 'Basketball', 'Tennis', 'Volleyball', 'Workout']
        if sport_type in other_sports:
            if distance_km > 5.0:
                reasons.append(f"{sport_type}: Khoảng cách bất thường ({distance_km} km)")
            if elevation_gain_m > 50.0:
                reasons.append(f"{sport_type}: Elevation bất thường ({elevation_gain_m} m)")

    if reasons:
        return True, "; ".join(reasons)
    return False, None

def get_athlete_badges(
    athlete,
    valid_activities: list,
    max_streak: int,
    total_kcal: float,
    total_time_hours: float,
    db: Session,
    event_id: int = None
) -> list:
    """
    Tính toán và xác định danh sách huy hiệu ảo mà VĐV đã đạt được dựa trên các quy tắc cấu hình động trong DB.
    """
    from backend.database import BadgeRule
    rules = None
    if event_id:
        rules = db.query(BadgeRule).filter(BadgeRule.event_id == event_id).all()
    if not rules:
        rules = db.query(BadgeRule).filter(BadgeRule.event_id == None).all()

    result = []
    for r in rules:
        achieved = False
        if r.unit == "activities":
            achieved = len(valid_activities) >= r.threshold
        elif r.unit == "run_distance_km":
            achieved = any(a.sport_type == 'Run' and a.distance_km >= r.threshold for a in valid_activities)
        elif r.unit == "ride_distance_km":
            achieved = any(a.sport_type == 'Ride' and a.distance_km >= r.threshold for a in valid_activities)
        elif r.unit == "total_time_hours":
            achieved = total_time_hours >= r.threshold
        elif r.unit == "total_kcal":
            achieved = total_kcal >= r.threshold
        elif r.unit == "max_streak_days":
            achieved = max_streak >= r.threshold

        achieved_date = ""
        if achieved:
            if r.unit == "activities" and valid_activities:
                achieved_date = min(a.activity_date for a in valid_activities)
            elif r.unit == "run_distance_km":
                qualifying_acts = [a for a in valid_activities if a.sport_type == 'Run' and a.distance_km >= r.threshold]
                if qualifying_acts:
                    achieved_date = min(a.activity_date for a in qualifying_acts)
            elif r.unit == "ride_distance_km":
                qualifying_acts = [a for a in valid_activities if a.sport_type == 'Ride' and a.distance_km >= r.threshold]
                if qualifying_acts:
                    achieved_date = min(a.activity_date for a in qualifying_acts)
            elif r.unit == "total_time_hours":
                running_hours = 0.0
                sorted_acts = sorted(valid_activities, key=lambda a: a.activity_date)
                for act in sorted_acts:
                    running_hours += act.moving_time_min / 60.0
                    if running_hours >= r.threshold:
                        achieved_date = act.activity_date
                        break
            elif r.unit == "total_kcal":
                running_kcal = 0.0
                sorted_acts = sorted(valid_activities, key=lambda a: a.activity_date)
                for act in sorted_acts:
                    running_kcal += act.kcal_burned
                    if running_kcal >= r.threshold:
                        achieved_date = act.activity_date
                        break
            elif r.unit == "max_streak_days":
                if valid_activities:
                    achieved_date = max(a.activity_date for a in valid_activities)
            
            if achieved_date:
                try:
                    dt = datetime.strptime(achieved_date, "%Y-%m-%d")
                    achieved_date = dt.strftime("%d/%m/%Y")
                except Exception:
                    pass
        
        result.append({
            "id": r.badge_key or r.id,
            "name": r.name,
            "description": r.description,
            "icon": r.icon,
            "color": r.color,
            "achieved": achieved,
            "achieved_date": achieved_date
        })
    return result

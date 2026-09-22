# -*- coding: utf-8 -*-
"""
Script liên kết tự động và triệt để 261 hoạt động mồ côi (athlete_id IS NULL)
vào đúng tài khoản Vận động viên đã đăng ký, cập nhật alias và tính lại KCAL/METs.
"""
import sys
import os

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Đảm bảo import được các module backend
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from sqlalchemy.orm import Session
from backend.database import SessionLocal, Athlete, Activity, CompetitionRegistration, CompetitionEvent
from backend.calculations import get_mets_value, calculate_kcal, get_multiplier_for_date

def link_all_orphan_activities():
    db: Session = SessionLocal()
    try:
        # Danh sách ánh xạ chính xác từ tên thô của hoạt động -> ID vận động viên
        mapping = {
            'Ngọc Báu Trần': 135,       # Trần Ngọc Báu
            'Ngọc Báu T.': 135,         # Trần Ngọc Báu
            'Nam D.': 119,              # Do Thanh Nam
            'Nguyễn Thị Thanh Minh': 98,# Nguyễn Thị Thanh Minh
            'Thanh Minh Nguyễn Thị': 98,# Nguyễn Thị Thanh Minh
            'Man Tran Minh': 30,        # Trần Minh Mẩn
            'Lê Anh Ba': 104,           # Lê Anh Ba
            'Anhba L.': 104,            # Lê Anh Ba
            'Trần Hữu Hòa': 106,        # Trần Hữu Hòa
            'Trần Hữu H.': 106,         # Trần Hữu Hòa
            'Trang Đ.': 124,            # Đỗ Trang
            'Vu Nguyen P.HCLĐ': 94,     # Nguyễn Trần Tuấn Vũ
            'Phạm Văn Điệp': 161,       # Phạm Văn Điệp
            'Thuận Đ.': 112,            # Đặng Văn Thuận
            'Thuận Đặng': 112,          # Đặng Văn Thuận
            'Фыонг Х.': 97,             # Hoàng Văn Phương
            'Фыонг Хоанг Ван': 97,      # Hoàng Văn Phương
            'Nguyễn Đình  Q.': 117,     # Nguyễn Đình Quang
            'Nguyễn Đình  Quang': 117,  # Nguyễn Đình Quang
            'Đức Hoàng Anh': 32,        # Hoàng Anh Đức
            'Vũ Ngọc Thạch': 145,       # Vũ Ngọc Thạch
            'Triết Hoàng': 29,          # Hoàng Minh Triết
            'MinhntTV': 151,            # Nguyễn Thành Minh
        }

        print("=== BẮT ĐẦU GHÉP NỐI CÁC HOẠT ĐỘNG MỒ CÔI ===")
        total_linked = 0
        total_recalculated = 0

        for raw_name, ath_id in mapping.items():
            athlete = db.query(Athlete).filter(Athlete.id == ath_id).first()
            if not athlete:
                print(f"[Cảnh báo] Không tìm thấy VĐV ID={ath_id} cho tên '{raw_name}'")
                continue

            # Lấy tất cả các hoạt động chưa liên kết có tên này
            orphan_acts = db.query(Activity).filter(
                Activity.athlete_id == None,
                Activity.athlete_name_raw == raw_name
            ).all()

            if not orphan_acts:
                continue

            # Cập nhật thêm raw_name vào strava_name của VĐV nếu chưa có
            current_aliases = [x.strip() for x in (athlete.strava_name or "").split(",") if x.strip()]
            if raw_name not in current_aliases:
                current_aliases.append(raw_name)
                athlete.strava_name = ", ".join(current_aliases)

            # Tập hợp các giải đã đăng ký để tránh trùng lặp trong phiên
            existing_regs = set(
                r[0] for r in db.query(CompetitionRegistration.event_id).filter(
                    CompetitionRegistration.athlete_id == athlete.id
                ).all()
            )

            for act in orphan_acts:
                act.athlete_id = athlete.id

                # Đảm bảo VĐV đã đăng ký giải đấu này
                if act.event_id and act.event_id not in existing_regs:
                    db.add(CompetitionRegistration(athlete_id=athlete.id, event_id=act.event_id))
                    existing_regs.add(act.event_id)

                # Tính lại KCAL và METs chuẩn xác theo cân nặng VĐV
                dist_raw = act.distance_km_raw if act.distance_km_raw is not None else (act.distance_km or 0.0)
                speed_kmh = 0.0
                if act.moving_time_min and act.moving_time_min > 0:
                    speed_kmh = dist_raw / (act.moving_time_min / 60.0)

                actual_time_min = act.elapsed_time_min if (act.moving_time_min or 0) < 1.0 else act.moving_time_min
                mets_val = get_mets_value(act.sport_type, speed_kmh, db, dist_raw, act.elevation_gain_m or 0.0, event_id=act.event_id)
                mult = get_multiplier_for_date(act.activity_date, act.event_id, db)

                act.mets_value = mets_val
                ath_weight = athlete.weight if athlete.weight and athlete.weight > 0 else 60.0
                kcal_raw = calculate_kcal(mets_val, ath_weight, actual_time_min, act.elevation_gain_m or 0.0, act.sport_type)
                act.kcal_burned_raw = kcal_raw
                act.kcal_burned = round(kcal_raw * mult)
                act.multiplier = mult
                act.distance_km_raw = dist_raw
                act.distance_km = round(dist_raw * mult, 2)

                total_linked += 1
                total_recalculated += 1

            db.commit()
            print(f"  + Đã liên kết {len(orphan_acts)} hoạt động ('{raw_name}') cho VĐV: {athlete.full_name} (ID={ath_id})")

        # Kiểm tra lại số lượng hoạt động mồ côi còn lại
        remaining = db.query(Activity).filter(Activity.athlete_id == None).count()
        print("================================================")
        print(f"Hoàn tất! Tổng số hoạt động đã liên kết: {total_linked}")
        print(f"Số hoạt động mồ côi còn lại trong DB: {remaining}")
        print("================================================")

    except Exception as e:
        db.rollback()
        print(f"[Lỗi] Quá trình liên kết gặp lỗi: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    link_all_orphan_activities()

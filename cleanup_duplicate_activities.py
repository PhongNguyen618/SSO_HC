"""
Script don dep hoat dong bi trung lap do loi grace period gan sai ngay.
Kich ban: Hoat dong Thu 7 da sync dung, nhung sync 00:15 Thu 2 tao ban sao gan ngay CN.

Su dung:
  1. Xem truoc (DRY RUN, khong xoa gi):
     python cleanup_duplicate_activities.py

  2. Xoa thuc te sau khi xac nhan:
     python cleanup_duplicate_activities.py --apply

  3. Chi quet 1 event cu the:
     python cleanup_duplicate_activities.py --event-id 2

  4. Xuat ket qua ra file CSV:
     python cleanup_duplicate_activities.py --csv duplicates_report.csv
"""
import sys
import os
import argparse
from datetime import datetime, timedelta

# Them duong dan project vao sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Fallback: neu chay tu thu muc con (vd: scratch/)
if not os.path.exists("backend"):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Activity, Athlete
from sqlalchemy import func


def find_duplicates(db, event_id=None, lookback_days=60):
    """
    Tim cac hoat dong trung lap trong DB.
    Tieu chi trung: cung athlete (hoac cung ten), cung sport_type, cung event_id,
    distance_km chenh <= 0.05, moving_time chenh <= 1.0 phut, elevation chenh <= 10m,
    nhung KHAC ngay (activity_date).
    """
    cutoff = (datetime.utcnow() + timedelta(hours=7) - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    query = db.query(Activity).filter(Activity.activity_date >= cutoff)
    if event_id is not None:
        query = query.filter(Activity.event_id == event_id)

    activities = query.order_by(Activity.activity_date.asc()).all()
    print(f"Scanning {len(activities)} activities (last {lookback_days} days)...")

    # Nhom theo (athlete_id or athlete_name_raw, event_id, sport_type)
    groups = {}
    for act in activities:
        key_athlete = act.athlete_id if act.athlete_id else f"name:{act.athlete_name_raw.lower()}"
        key = (key_athlete, act.event_id, act.sport_type)
        groups.setdefault(key, []).append(act)

    duplicate_pairs = []  # List of (keep, remove, reason)

    for key, acts in groups.items():
        if len(acts) < 2:
            continue

        # So sanh tung cap
        checked_remove_ids = set()
        for i in range(len(acts)):
            if acts[i].id in checked_remove_ids:
                continue
            for j in range(i + 1, len(acts)):
                if acts[j].id in checked_remove_ids:
                    continue

                a = acts[i]
                b = acts[j]

                # Lay distance_km_raw neu co
                dist_a = a.distance_km_raw if a.distance_km_raw is not None else a.distance_km
                dist_b = b.distance_km_raw if b.distance_km_raw is not None else b.distance_km

                dist_diff = abs((dist_a or 0.0) - (dist_b or 0.0))
                time_diff = abs((a.moving_time_min or 0.0) - (b.moving_time_min or 0.0))
                elev_diff = abs((a.elevation_gain_m or 0.0) - (b.elevation_gain_m or 0.0))

                # Kiem tra trung lap
                if dist_diff <= 0.05 and time_diff <= 1.0 and elev_diff <= 10.0:
                    # Cung ngay thi bo qua (co the la 2 session khac nhau cung ngay)
                    if a.activity_date == b.activity_date:
                        continue

                    # Xac dinh ban nao giu, ban nao xoa
                    keep, remove = _decide_keep_remove(a, b)

                    reason = (f"dist_diff={dist_diff:.3f}km, "
                              f"time_diff={time_diff:.1f}min, "
                              f"elev_diff={elev_diff:.1f}m")

                    duplicate_pairs.append((keep, remove, reason))
                    checked_remove_ids.add(remove.id)

    return duplicate_pairs


def _decide_keep_remove(a, b):
    """
    Quyet dinh giu ban nao va xoa ban nao.
    Uu tien:
    1. Giu ban co sync_date som hon (da sync truoc = dung hon)
    2. Neu cung sync_date: giu ban co ngay KHONG phai CN
    3. Fallback: giu ban dau tien
    """
    sync_a = a.sync_date
    sync_b = b.sync_date

    # So sanh sync_date: ban nao sync som hon thi dung hon
    if sync_a and sync_b:
        if sync_a < sync_b:
            return a, b
        elif sync_b < sync_a:
            return b, a

    # Neu sync_date bang nhau hoac khong co, uu tien ban KHONG phai CN
    day_a = _get_weekday(a.activity_date)
    day_b = _get_weekday(b.activity_date)

    # Neu 1 ban la CN va ban kia khong phai -> giu ban khong phai CN
    if day_a == 6 and day_b != 6:  # a la CN
        return b, a
    if day_b == 6 and day_a != 6:  # b la CN
        return a, b

    # Fallback: giu ban co ngay som hon
    if a.activity_date <= b.activity_date:
        return a, b
    return b, a


def _get_weekday(date_str):
    """Tra ve weekday: 0=Mon, ..., 6=Sun"""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").weekday()
    except (ValueError, TypeError):
        return -1


def _weekday_name(date_str):
    """Tra ve ten thu trong tuan"""
    names = ["T2", "T3", "T4", "T5", "T6", "T7", "CN"]
    wd = _get_weekday(date_str)
    return names[wd] if 0 <= wd <= 6 else "??"


def print_report(duplicate_pairs):
    """In bao cao chi tiet"""
    if not duplicate_pairs:
        print("\n=== KHONG TIM THAY HOAT DONG TRUNG LAP ===")
        return

    print(f"\n{'='*90}")
    print(f"TIM THAY {len(duplicate_pairs)} CAP HOAT DONG TRUNG LAP")
    print(f"{'='*90}")

    total_kcal_saved = 0.0
    total_dist_saved = 0.0

    for idx, (keep, remove, reason) in enumerate(duplicate_pairs, 1):
        dist_keep = keep.distance_km_raw if keep.distance_km_raw is not None else keep.distance_km
        dist_remove = remove.distance_km_raw if remove.distance_km_raw is not None else remove.distance_km

        print(f"\n--- Cap #{idx} ---")
        print(f"  VDV: {keep.athlete_name_raw}")
        print(f"  Mon: {keep.sport_type} | Ten: '{keep.name}'")
        print(f"  Match: {reason}")

        print(f"  [GIU]  Ngay {keep.activity_date} ({_weekday_name(keep.activity_date)}) | "
              f"Dist={dist_keep:.2f}km | Time={keep.moving_time_min:.1f}min | "
              f"KCAL={keep.kcal_burned:.0f} | Mult={getattr(keep, 'multiplier', 1.0)}")

        print(f"  [XOA]  Ngay {remove.activity_date} ({_weekday_name(remove.activity_date)}) | "
              f"Dist={dist_remove:.2f}km | Time={remove.moving_time_min:.1f}min | "
              f"KCAL={remove.kcal_burned:.0f} | Mult={getattr(remove, 'multiplier', 1.0)}")

        total_kcal_saved += (remove.kcal_burned or 0.0)
        total_dist_saved += (remove.distance_km or 0.0)

    print(f"\n{'='*90}")
    print(f"TONG KET:")
    print(f"  - So cap trung lap: {len(duplicate_pairs)}")
    print(f"  - Tong KCAL bi dem thua (se xoa): {total_kcal_saved:.0f} kcal")
    print(f"  - Tong Distance bi dem thua (se xoa): {total_dist_saved:.2f} km")
    print(f"{'='*90}")


def export_csv(duplicate_pairs, filepath):
    """Xuat bao cao ra file CSV"""
    import csv
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "STT", "VDV", "Sport", "Activity_Name",
            "KEEP_Date", "KEEP_Day", "KEEP_Dist_km", "KEEP_Time_min", "KEEP_KCAL", "KEEP_Mult",
            "REMOVE_Date", "REMOVE_Day", "REMOVE_Dist_km", "REMOVE_Time_min", "REMOVE_KCAL", "REMOVE_Mult",
            "Match_Reason"
        ])
        for idx, (keep, remove, reason) in enumerate(duplicate_pairs, 1):
            dk = keep.distance_km_raw if keep.distance_km_raw is not None else keep.distance_km
            dr = remove.distance_km_raw if remove.distance_km_raw is not None else remove.distance_km
            writer.writerow([
                idx, keep.athlete_name_raw, keep.sport_type, keep.name,
                keep.activity_date, _weekday_name(keep.activity_date),
                f"{dk:.2f}", f"{keep.moving_time_min:.1f}", f"{keep.kcal_burned:.0f}",
                f"{getattr(keep, 'multiplier', 1.0)}",
                remove.activity_date, _weekday_name(remove.activity_date),
                f"{dr:.2f}", f"{remove.moving_time_min:.1f}", f"{remove.kcal_burned:.0f}",
                f"{getattr(remove, 'multiplier', 1.0)}",
                reason
            ])
    print(f"\nDa xuat bao cao CSV: {filepath}")


def apply_cleanup(db, duplicate_pairs):
    """Xoa cac hoat dong trung lap (ban bi gan sai ngay)"""
    remove_ids = [remove.id for (_, remove, _) in duplicate_pairs]

    if not remove_ids:
        print("Khong co gi de xoa.")
        return

    print(f"\nDang xoa {len(remove_ids)} hoat dong trung lap...")
    deleted = db.query(Activity).filter(Activity.id.in_(remove_ids)).delete(synchronize_session=False)
    db.commit()
    print(f"DA XOA THANH CONG {deleted} hoat dong trung lap!")


def main():
    parser = argparse.ArgumentParser(description="Don dep hoat dong trung lap do loi grace period")
    parser.add_argument("--apply", action="store_true",
                        help="Thuc su xoa hoat dong trung (mac dinh chi xem truoc - dry run)")
    parser.add_argument("--event-id", type=int, default=None,
                        help="Chi quet 1 giai dau cu the (mac dinh: tat ca)")
    parser.add_argument("--days", type=int, default=60,
                        help="So ngay quet nguoc (mac dinh: 60)")
    parser.add_argument("--csv", type=str, default=None,
                        help="Xuat bao cao ra file CSV")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        print("=" * 90)
        print("CONG CU DON DEP HOAT DONG TRUNG LAP (Grace Period Bug Fix)")
        print("=" * 90)

        if not args.apply:
            print("\n>>> CHE DO XEM TRUOC (DRY RUN) - Khong xoa gi <<<")
            print(">>> Them flag --apply de thuc su xoa <<<\n")

        duplicate_pairs = find_duplicates(db, event_id=args.event_id, lookback_days=args.days)
        print_report(duplicate_pairs)

        if args.csv and duplicate_pairs:
            export_csv(duplicate_pairs, args.csv)

        if args.apply and duplicate_pairs:
            confirm = input(f"\nBan co chac chan muon XOA {len(duplicate_pairs)} hoat dong trung lap? (yes/no): ")
            if confirm.strip().lower() in ("yes", "y"):
                apply_cleanup(db, duplicate_pairs)
            else:
                print("Huy bo. Khong xoa gi.")
        elif args.apply and not duplicate_pairs:
            print("\nKhong tim thay hoat dong trung lap nao.")

    except Exception as e:
        print(f"ERROR: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()

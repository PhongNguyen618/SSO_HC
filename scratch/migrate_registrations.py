import sys
from datetime import datetime, timedelta

# UTF-8 encoding on Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.append(".")

from backend.database import SessionLocal, CompetitionRegistration, Athlete, CompetitionEvent
from backend.sync_engine import link_unlinked_activities

def migrate_registrations(target_event_id: int, hours_threshold: float = 24.0, dry_run: bool = True):
    db = SessionLocal()
    try:
        # Check if target event exists
        target_event = db.query(CompetitionEvent).filter(CompetitionEvent.id == target_event_id).first()
        if not target_event:
            print(f"Lỗi: Không tìm thấy giải chạy đích với ID = {target_event_id}")
            return
            
        print(f"Giải chạy đích: ID {target_event.id} ('{target_event.title}')")
        
        # Calculate time threshold
        now = datetime.utcnow()
        time_limit = now - timedelta(hours=hours_threshold)
        print(f"Đang tìm các đăng ký của giải cũ (ID = 1) được tạo từ: {time_limit} UTC (trong {hours_threshold} giờ qua)...")
        
        # Query registrations in event 1 created recently
        regs_to_migrate = db.query(CompetitionRegistration).filter(
            CompetitionRegistration.event_id == 1,
            CompetitionRegistration.registered_at >= time_limit
        ).all()
        
        if not regs_to_migrate:
            print("Không tìm thấy đăng ký nào thỏa mãn điều kiện thời gian.")
            return
            
        print(f"Tìm thấy {len(regs_to_migrate)} đăng ký cần xử lý:")
        for r in regs_to_migrate:
            ath = db.query(Athlete).filter(Athlete.id == r.athlete_id).first()
            name = ath.full_name if ath else "Không rõ"
            print(f" - VĐV ID: {r.athlete_id} ({name}) | Đăng ký lúc: {r.registered_at} UTC")
            
        if dry_run:
            print("\n*** ĐÂY LÀ CHẾ ĐỘ CHẠY THỬ (DRY RUN). CHƯA CÓ THAY ĐỔI NÀO ĐƯỢC LƯU VÀO DB. ***")
            print("Để thực hiện di chuyển thật, hãy chạy script và truyền thêm tham số '--apply'.")
            return
            
        print("\nĐang tiến hành di chuyển...")
        moved_count = 0
        deleted_dup_count = 0
        
        for r in regs_to_migrate:
            # Check if this athlete is already registered for the target event
            exists_in_target = db.query(CompetitionRegistration).filter(
                CompetitionRegistration.athlete_id == r.athlete_id,
                CompetitionRegistration.event_id == target_event_id
            ).first()
            
            if exists_in_target:
                # If already registered for target event, just delete the old registration to avoid duplicates
                db.delete(r)
                deleted_dup_count += 1
            else:
                # Otherwise, move the registration to target event
                r.event_id = target_event_id
                moved_count += 1
                
        db.commit()
        print(f"Đã di chuyển thành công {moved_count} đăng ký sang giải đấu mới.")
        if deleted_dup_count > 0:
            print(f"Đã xóa {deleted_dup_count} đăng ký trùng lặp ở giải đấu cũ.")
            
        # Run link_unlinked_activities for all migrated athletes to ensure their activities for the new event are linked
        print("\nĐang cập nhật lại liên kết hoạt động cho các VĐV vừa di chuyển...")
        for r in regs_to_migrate:
            ath = db.query(Athlete).filter(Athlete.id == r.athlete_id).first()
            if ath:
                link_unlinked_activities(db, ath)
                
        print("Hoàn thành cập nhật liên kết hoạt động!")
        
    except Exception as e:
        db.rollback()
        print(f"Lỗi xảy ra: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    # Target event ID defaults to 2, hours_threshold defaults to 24
    target_id = 2
    hours = 24.0
    dry = True
    
    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            if arg == "--apply":
                dry = False
            elif arg.startswith("--target="):
                try:
                    target_id = int(arg.split("=")[1])
                except ValueError:
                    pass
            elif arg.startswith("--hours="):
                try:
                    hours = float(arg.split("=")[1])
                except ValueError:
                    pass
                    
    migrate_registrations(target_event_id=target_id, hours_threshold=hours, dry_run=dry)

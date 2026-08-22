import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, '.')

from backend.database import SessionLocal, CompetitionEvent, ArchivedEvent
from backend.main import archive_competition_event, generate_event_analytics_summary

db = SessionLocal()

try:
    print("--- TESTING AUTO-ARCHIVE EVENT FEATURE ---")
    
    # 1. Tim mot giai dau dang co
    comp = db.query(CompetitionEvent).order_by(CompetitionEvent.id.desc()).first()
    if not comp:
        print("Không tìm thấy giải đấu nào trong DB để test!")
        sys.exit(0)
        
    print(f"Giải đấu được chọn test: ID={comp.id}, Title='{comp.title}', is_active={comp.is_active}")
    
    # 2. Sinh thu van ban tong hop analytics summary
    summary_text = generate_event_analytics_summary(db, comp)
    print("\n--- VAN BAN VINH DANH TAP HOP TU DONG ---")
    print(summary_text)
    print("-------------------------------------------\n")
    
    # 3. Test goi ham archive_competition_event
    archived = archive_competition_event(db, comp)
    print(f"Lưu vào Sự kiện Lịch sử thành công: ArchivedEvent ID={archived.id}, Title='{archived.title}'")
    print(f"Trạng thái is_active của giải đấu sau khi lưu: {comp.is_active}")
    
    # Check ArchivedEvent in DB
    check_archived = db.query(ArchivedEvent).filter(ArchivedEvent.id == archived.id).first()
    assert check_archived is not None, "ArchivedEvent không tồn tại trong DB!"
    assert len(check_archived.summary_text) > 50, "Summary text quá ngắn hoặc trống!"
    assert "SƠ KẾT PHONG TRÀO THỂ THAO" in check_archived.summary_text, "Văn bản không đúng định dạng!"
    
    print("\n✅ TẤT CẢ TEST PASS THÀNH CÔNG!")
finally:
    db.close()

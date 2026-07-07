import sqlite3
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_db():
    conn = sqlite3.connect("SSO_HC_backup_v1.4.0_1783059852.db")
    cursor = conn.cursor()
    
    # 1. Xem danh sách giải đấu (events) và ngày bắt đầu của chúng
    print("=== EVENTS IN DATABASE ===")
    cursor.execute("SELECT id, title, start_date, end_date, is_active FROM competition_events")
    events = cursor.fetchall()
    for ev in events:
        print(f"ID: {ev[0]}, Title: {ev[1]}, Start: {ev[2]}, End: {ev[3]}, Active: {ev[4]}")
        
    # 2. Xem các hoạt động trước ngày 16/6/2026
    print("\n=== ACTIVITIES BEFORE 2026-06-16 ===")
    cursor.execute("""
        SELECT id, athlete_name_raw, name, activity_date, activity_time, distance_km, event_id 
        FROM activities 
        WHERE activity_date < '2026-06-16' 
        ORDER BY activity_date DESC 
        LIMIT 20
    """)
    acts = cursor.fetchall()
    for act in acts:
        print(f"ID: {act[0]}, Name: {act[1]}, ActName: {act[2]}, Date: {act[3]}, Time: {act[4]}, Dist: {act[5]} km, EventID: {act[6]}")
        
    # 3. Đếm số lượng hoạt động trước ngày 16/6/2026 theo từng event_id
    print("\n=== COUNT OF ACTIVITIES BEFORE 2026-06-16 BY EVENT ===")
    cursor.execute("""
        SELECT event_id, COUNT(*) 
        FROM activities 
        WHERE activity_date < '2026-06-16' 
        GROUP BY event_id
    """)
    counts = cursor.fetchall()
    for cnt in counts:
        print(f"Event ID: {cnt[0]} -> {cnt[1]} activities")
        
    conn.close()

if __name__ == "__main__":
    check_db()

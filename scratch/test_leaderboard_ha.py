import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_leaderboard_query_for_athlete_51():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # 1. Truy vấn cấu hình giải 2
    cur.execute("SELECT id, title, start_date, end_date, ranking_metric, ranking_sports FROM competition_events WHERE id = 2")
    event = cur.fetchone()
    print("=== THÔNG TIN GIẢI 2 ===")
    print(f"ID: {event[0]} | Tên: {event[1]} | Từ: {event[2]} đến {event[3]} | Metric: {event[4]} | Sports: {event[5]}")
    
    # Giả lập các biến lọc ngày
    start_date = event[2]
    end_date = event[3]
    event_id = event[0]
    
    # 2. Chạy câu truy vấn BXH cá nhân y hệt trong main.py
    # Lấy BXH theo KCAL
    query = """
        SELECT 
            a.id, 
            a.full_name, 
            a.gender, 
            a.department,
            SUM(act.distance_km) as total_dist,
            SUM(act.moving_time_min) as total_time,
            SUM(act.kcal_burned) as total_kcal
        FROM athletes a
        JOIN activities act ON a.id = act.athlete_id
        JOIN competition_registrations r ON a.id = r.athlete_id AND r.event_id = ?
        WHERE a.is_active = 1
          AND act.activity_date >= ?
          AND act.activity_date <= ?
          AND act.event_id = ?
        GROUP BY a.id
        ORDER BY total_kcal DESC
    """
    
    cur.execute(query, (event_id, start_date, end_date, event_id))
    results = cur.fetchall()
    
    print(f"\n=== BẢNG XẾP HẠNG CÁ NHÂN GIẢI 2 (Tổng cộng {len(results)} VĐV có thành tích) ===")
    found = False
    for rank, r in enumerate(results, 1):
        uid, name, gender, dept, dist, time_min, kcal = r
        if uid == 51:
            found = True
            print(f"👉 Hạng {rank} | ID: {uid} | Tên: {name} ({dept}) | Cự ly: {dist:.2f} km | Calo: {kcal:.1f} kcal | Thời gian: {time_min/60.0:.1f} giờ")
        elif rank <= 5 or uid in [102, 123]: # In top 5 và một số người liên quan
            print(f"   Hạng {rank} | ID: {uid} | Tên: {name} ({dept}) | Cự ly: {dist:.2f} km | Calo: {kcal:.1f} kcal")
            
    if not found:
        print("\n❌ CẢNH BÁO: HOÀNG THỊ HÀ (ID=51) KHÔNG XUẤT HIỆN TRÊN BXH GIẢI 2!")
        
    conn.close()

if __name__ == "__main__":
    test_leaderboard_query_for_athlete_51()

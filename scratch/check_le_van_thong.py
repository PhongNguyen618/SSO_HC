"""Kiểm tra VĐV Lê Văn Thông trong backup mới nhất + live DB"""
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783388501.db"
live_db = "SSO_HC.db"

for db_name, db_file in [("BACKUP (1783388501)", backup_db), ("LIVE (SSO_HC.db)", live_db)]:
    print(f"\n{'='*80}")
    print(f"📂 DATABASE: {db_name}")
    print(f"{'='*80}")
    
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Tìm VĐV Lê Văn Thông
    cur.execute("SELECT id, full_name, strava_name, strava_athlete_id, strava_refresh_token FROM athletes WHERE full_name LIKE '%Thông%' OR full_name LIKE '%Thong%'")
    athletes = cur.fetchall()
    
    if not athletes:
        print("  ❌ Không tìm thấy VĐV nào có tên chứa 'Thông'")
        conn.close()
        continue
    
    for ath in athletes:
        aid, name, strava_name, strava_id, token = ath
        has_token = "✅ CÓ" if token else "❌ KHÔNG"
        print(f"\n  👤 ID={aid} | Tên: {name} | Strava: {strava_name} | Strava ID: {strava_id}")
        print(f"     Token: {has_token}")
        
        # Đăng ký giải
        cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (aid,))
        regs = [r[0] for r in cur.fetchall()]
        print(f"     Đăng ký giải: {regs}")
        
        # Tất cả hoạt động
        cur.execute("""
            SELECT id, event_id, activity_date, activity_time, distance_km, name, type, sport_type
            FROM activities 
            WHERE athlete_id = ? 
            ORDER BY activity_date DESC, activity_time DESC
        """, (aid,))
        acts = cur.fetchall()
        
        print(f"\n     📊 Tổng hoạt động: {len(acts)}")
        
        # Hiển thị hoạt động theo ngày
        if acts:
            print(f"\n     {'ID':<20} {'Event':>5} {'Ngày':>12} {'Giờ':>8} {'KM':>8} {'Loại':<10} {'Tên hoạt động'}")
            print(f"     {'-'*100}")
            for act in acts:
                act_id, event_id, date, time, dist, act_name, act_type, sport = act
                short_id = act_id[:16] + "..." if len(str(act_id)) > 16 else act_id
                print(f"     {short_id:<20} {event_id:>5} {date or 'N/A':>12} {time or 'N/A':>8} {dist or 0:>8.2f} {act_type or 'N/A':<10} {act_name or 'N/A'}")
        
        # Kiểm tra đặc biệt ngày 5/7
        cur.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE athlete_id = ? AND activity_date LIKE '2026-07-05%'
        """, (aid,))
        count_jul5 = cur.fetchone()[0]
        print(f"\n     🔍 Hoạt động ngày 05/07/2026: {count_jul5}")
        
        # Kiểm tra tháng 7
        cur.execute("""
            SELECT COUNT(*) FROM activities 
            WHERE athlete_id = ? AND activity_date LIKE '2026-07%'
        """, (aid,))
        count_jul = cur.fetchone()[0]
        print(f"     🔍 Hoạt động tháng 07/2026: {count_jul}")
    
    conn.close()

# Kiểm tra event dates
print(f"\n{'='*80}")
print(f"📅 KIỂM TRA KHOẢNG THỜI GIAN GIẢI ĐẤU")
print(f"{'='*80}")
conn = sqlite3.connect(live_db)
cur = conn.cursor()
cur.execute("SELECT id, name, start_date, end_date FROM events")
events = cur.fetchall()
for ev in events:
    print(f"  Event {ev[0]}: {ev[1]} | {ev[2]} → {ev[3]}")
conn.close()

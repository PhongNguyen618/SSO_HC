"""Kiểm tra Lê Văn Thông trong live DB local"""
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

live_db = "SSO_HC.db"
conn = sqlite3.connect(live_db)
cur = conn.cursor()

# Tìm Thông
cur.execute("SELECT id, full_name, strava_name, strava_athlete_id, strava_refresh_token, department FROM athletes WHERE full_name LIKE '%Thông%' OR full_name LIKE '%Thong%'")
results = cur.fetchall()

print(f"🔍 Tìm VĐV 'Thông/Thong' trong live DB ({live_db}):")
if not results:
    print("  ❌ KHÔNG TÌM THẤY - VĐV này không tồn tại trong live DB!")
    
    # Kiểm tra tổng VĐV
    cur.execute("SELECT COUNT(*) FROM athletes")
    total = cur.fetchone()[0]
    print(f"\n  📊 Tổng VĐV trong live DB: {total}")
    
    # Liệt kê vài VĐV
    cur.execute("SELECT id, full_name, department FROM athletes ORDER BY id LIMIT 10")
    print(f"\n  Mẫu VĐV:")
    for r in cur.fetchall():
        print(f"    [{r[0]}] {r[1]} - {r[2]}")
else:
    for r in results:
        has_token = "✅ CÓ" if r[4] else "❌ KHÔNG"
        print(f"  [{r[0]}] {r[1]} | Strava: {r[2]} | ID: {r[3]} | Token: {has_token} | PB: {r[5]}")
        
        # Đếm hoạt động
        cur.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ?", (r[0],))
        act_count = cur.fetchone()[0]
        print(f"       Tổng hoạt động: {act_count}")
        
        # Đăng ký giải
        cur.execute("SELECT event_id FROM competition_registrations WHERE athlete_id = ?", (r[0],))
        regs = [x[0] for x in cur.fetchall()]
        print(f"       Đăng ký giải: {regs}")

conn.close()

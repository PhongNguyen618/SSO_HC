"""
KIỂM TRA TOÀN DIỆN: Tại sao Lê Văn Thông mất hoạt động ngày 5/7
Bao gồm:
1. Xem token và nguồn dữ liệu
2. Phân tích khoảng cách giữa các hoạt động 
3. Kiểm tra logic bỏ qua (distance==0 && time==0)
4. Kiểm tra date range filter
"""
import sqlite3
import sys
import io
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783388501.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# 1. Kiểm tra tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"📋 Tables: {tables}")

# 2. Kiểm tra event date range
if 'competition_events' in tables:
    cur.execute("SELECT * FROM competition_events")
    events = cur.fetchall()
    # Lấy tên cột
    cols = [desc[0] for desc in cur.description]
    print(f"\n📅 GIẢI ĐẤU (cột: {cols}):")
    for ev in events:
        print(f"  {dict(zip(cols, ev))}")

# 3. VĐV Lê Văn Thông
print(f"\n{'='*80}")
cur.execute("SELECT * FROM athletes WHERE id = 118")
cols = [desc[0] for desc in cur.description]
row = cur.fetchone()
if row:
    ath_data = dict(zip(cols, row))
    print(f"👤 {ath_data.get('full_name')} (ID={ath_data.get('id')})")
    print(f"   strava_name: {ath_data.get('strava_name')}")
    print(f"   strava_athlete_id: {ath_data.get('strava_athlete_id')}")
    print(f"   strava_refresh_token: {'CÓ' if ath_data.get('strava_refresh_token') else '❌ KHÔNG CÓ'}")
    print(f"   strava_access_token: {'CÓ' if ath_data.get('strava_access_token') else '❌ KHÔNG CÓ'}")

# 4. Hoạt động chi tiết ngày 3-7/7
print(f"\n📊 HOẠT ĐỘNG NGÀY 3-7/7:")
cur.execute("""
    SELECT id, activity_date, activity_time, distance_km, moving_time_min, name, type, sport_type
    FROM activities 
    WHERE athlete_id = 118 AND activity_date >= '2026-07-03' AND activity_date <= '2026-07-07'
    ORDER BY activity_date, activity_time
""")
acts = cur.fetchall()
for a in acts:
    id_short = a[0][:20] + "..." if len(str(a[0])) > 20 else a[0]
    print(f"  {a[1]} {a[2]} | {a[3]:.2f}km | {a[4]:.1f}min | {a[5]} | type={a[6]} sport={a[7]}")
    print(f"    ID: {a[0]}")

# 5. Kiểm tra hoạt động nào bị lọc bởi distance==0 && time==0
print(f"\n🔍 KIỂM TRA: hoạt động có distance=0 VÀ time=0 (bị skip bởi scraper)?")
cur.execute("""
    SELECT id, activity_date, distance_km, moving_time_min, name
    FROM activities
    WHERE athlete_id = 118 AND (distance_km = 0 OR distance_km IS NULL) AND (moving_time_min = 0 OR moving_time_min IS NULL)
""")
zero_acts = cur.fetchall()
if zero_acts:
    for za in zero_acts:
        print(f"  ⚠️  {za[1]} | {za[4]} | dist={za[2]} time={za[3]}")
else:
    print("  ✅ Không có hoạt động distance=0 && time=0")

# 6. Kiểm tra GAP giữa các ngày hoạt động
print(f"\n📅 TẤT CẢ ngày hoạt động riêng biệt:")
cur.execute("""
    SELECT DISTINCT activity_date FROM activities 
    WHERE athlete_id = 118 
    ORDER BY activity_date
""")
dates = [r[0] for r in cur.fetchall()]
for i, d in enumerate(dates):
    gap = ""
    if i > 0:
        from datetime import datetime
        d1 = datetime.strptime(dates[i-1], "%Y-%m-%d")
        d2 = datetime.strptime(d, "%Y-%m-%d")
        diff = (d2 - d1).days
        if diff > 1:
            gap = f" ⚠️ GAP {diff} ngày (thiếu: {', '.join([(d1 + __import__('datetime').timedelta(days=j)).strftime('%d/%m') for j in range(1, diff)])})"
    print(f"  {d}{gap}")

# 7. Tìm xem trong TOÀN BỘ backup có ai trên Strava tên "Thong" có hoạt động ngày 5/7 không
print(f"\n🔍 Tìm hoạt động ngày 5/7 của bất kỳ ai có athlete_name_raw chứa 'Thong' hoặc 'Thông':")
cur.execute("""
    SELECT id, athlete_id, athlete_name_raw, activity_date, activity_time, distance_km, name
    FROM activities 
    WHERE activity_date = '2026-07-05' AND (athlete_name_raw LIKE '%Thong%' OR athlete_name_raw LIKE '%Thông%')
""")
results = cur.fetchall()
if results:
    for r in results:
        print(f"  ✅ athlete_id={r[1]}, raw_name={r[2]}, {r[3]} {r[4]}, {r[5]:.2f}km, {r[6]}")
else:
    print(f"  ❌ Không có bất kỳ hoạt động ngày 5/7 nào của VĐV có tên 'Thong/Thông'")
    print(f"     → Scraper KHÔNG thu thập được hoạt động này từ Strava Club feed")

# 8. Thống kê tổng hoạt động ngày 5/7 vs các ngày khác
print(f"\n📊 SỐ LƯỢNG HOẠT ĐỘNG THEO NGÀY (tháng 7/2026):")
cur.execute("""
    SELECT activity_date, COUNT(*) 
    FROM activities 
    WHERE activity_date LIKE '2026-07%'
    GROUP BY activity_date
    ORDER BY activity_date
""")
for d, c in cur.fetchall():
    marker = " ⬅️ NGÀY CẦN KIỂM TRA" if d == "2026-07-05" else ""
    print(f"  {d}: {c} hoạt động{marker}")

conn.close()

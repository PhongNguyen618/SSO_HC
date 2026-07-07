"""Kiểm tra chi tiết: tại sao ngày 5/7 không có hoạt động trong backup"""
import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783388501.db"

conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Kiểm tra bảng nào tồn tại
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"📋 Bảng trong backup: {tables}")

# Kiểm tra events
for tbl in ['events', 'event', 'competition_events']:
    if tbl in tables:
        cur.execute(f"SELECT * FROM {tbl} LIMIT 5")
        print(f"\n📅 Bảng {tbl}: {cur.fetchall()}")
        break

# Lê Văn Thông - athlete ID = 118
print(f"\n{'='*80}")
print("👤 LÊ VĂN THÔNG (ID=118)")

# Token info
cur.execute("SELECT strava_refresh_token, strava_access_token, strava_expires_at, strava_athlete_id FROM athletes WHERE id = 118")
row = cur.fetchone()
if row:
    has_refresh = "CÓ" if row[0] else "KHÔNG"
    has_access = "CÓ" if row[1] else "KHÔNG"
    print(f"  Refresh token: {has_refresh}")
    print(f"  Access token: {has_access}")
    print(f"  Expires at: {row[2]}")
    print(f"  Strava ID: {row[3]}")

# Hoạt động ngày 4, 5, 6, 7 tháng 7
print(f"\n📊 Hoạt động từ 03/07 đến 07/07:")
cur.execute("""
    SELECT id, activity_date, activity_time, distance_km, name 
    FROM activities 
    WHERE athlete_id = 118 AND activity_date >= '2026-07-03' AND activity_date <= '2026-07-07'
    ORDER BY activity_date, activity_time
""")
acts = cur.fetchall()
for a in acts:
    print(f"  {a[1]} {a[2]} | {a[3]:.2f} km | {a[4]}")

if not acts:
    print("  (Không có hoạt động nào)")

# Kiểm tra thời gian backup được tạo
import os
fsize = os.path.getsize(backup_db)
print(f"\n📦 Backup file size: {fsize/1024:.0f} KB")
print(f"   Timestamp trong tên: 1783388501")

# Convert timestamp
import datetime
try:
    ts = 1783388501
    dt = datetime.datetime.fromtimestamp(ts)
    print(f"   Thời gian tạo backup: {dt.strftime('%Y-%m-%d %H:%M:%S')}")
except:
    print(f"   Không parse được timestamp")

# Kiểm tra tất cả hoạt động ngày 5/7 trong toàn bộ DB
print(f"\n{'='*80}")
print("🔍 TẤT CẢ hoạt động ngày 05/07/2026 trong backup (mọi VĐV):")
cur.execute("""
    SELECT a.id, a.athlete_id, ath.full_name, a.activity_date, a.activity_time, a.distance_km, a.name
    FROM activities a
    JOIN athletes ath ON a.athlete_id = ath.id
    WHERE a.activity_date = '2026-07-05'
    ORDER BY a.activity_time
""")
acts_jul5 = cur.fetchall()
print(f"  Tổng: {len(acts_jul5)} hoạt động")
for a in acts_jul5:
    print(f"  VĐV [{a[1]}] {a[2]} | {a[3]} {a[4]} | {a[5]:.2f} km | {a[6]}")

# Kiểm tra hoạt động mới nhất trong backup là ngày nào
print(f"\n🕐 Hoạt động MỚI NHẤT trong backup:")
cur.execute("""
    SELECT a.activity_date, a.activity_time, ath.full_name, a.distance_km, a.name
    FROM activities a
    JOIN athletes ath ON a.athlete_id = ath.id
    ORDER BY a.activity_date DESC, a.activity_time DESC
    LIMIT 5
""")
for a in cur.fetchall():
    print(f"  {a[0]} {a[1]} | {a[2]} | {a[3]:.2f} km | {a[4]}")

conn.close()

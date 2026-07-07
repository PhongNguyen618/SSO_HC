"""
Phân tích CHÍNH XÁC: So sánh hoạt động trong LIVE DB vs BACKUP DB
để tìm ra VĐV nào đang bị THIẾU hoạt động (live < backup).
Đây chính là 11 VĐV mà user nói.
"""
import sqlite3
import sys
import io
import unicodedata
import re
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def normalize_old(name):
    if not name:
        return ""
    name_nfc = unicodedata.normalize("NFC", name)
    return name_nfc.replace("*", "").strip().lower()

def normalize_new(name):
    if not name:
        return ""
    name_lower = unicodedata.normalize("NFC", name).lower()
    nfkd_form = unicodedata.normalize('NFKD', name_lower)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', only_ascii)

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
live_db = os.path.join(base_dir, "sso_hc.db")

# Tìm tất cả backup files
all_backups = [f for f in os.listdir(base_dir) if f.endswith('.db') and 'backup' in f.lower()]
all_backups.sort()

print("=== BACKUP FILES ===")
for f in all_backups:
    fpath = os.path.join(base_dir, f)
    print(f"  {f} ({os.path.getsize(fpath)/1024:.0f} KB)")

# Dùng backup nhiều data nhất (mới nhất / lớn nhất)
backup_db = os.path.join(base_dir, all_backups[-1]) if all_backups else None

if not backup_db:
    print("❌ Không có backup nào!")
    sys.exit(1)

print(f"\n🔍 Backup: {os.path.basename(backup_db)}")

# --- Live DB: đếm hoạt động event_id=1, trước 16/06 cho mỗi VĐV ---
conn_live = sqlite3.connect(live_db)
cur_live = conn_live.cursor()
cur_live.execute("SELECT id, full_name FROM athletes")
live_athletes = {aid: name for aid, name in cur_live.fetchall()}

cur_live.execute("""
    SELECT athlete_id, COUNT(*) 
    FROM activities 
    WHERE event_id = 1 AND activity_date < '2026-06-16'
    GROUP BY athlete_id
""")
live_act_counts = dict(cur_live.fetchall())
conn_live.close()

# --- Backup DB ---
conn_bak = sqlite3.connect(backup_db)
cur_bak = conn_bak.cursor()
cur_bak.execute("SELECT id, full_name FROM athletes")
bak_athletes = cur_bak.fetchall()

cur_bak.execute("""
    SELECT athlete_id, COUNT(*) 
    FROM activities 
    WHERE event_id = 1 AND activity_date < '2026-06-16'
    GROUP BY athlete_id
""")
bak_act_counts = dict(cur_bak.fetchall())
conn_bak.close()

# Build name maps
live_name_map_old = {}
live_name_map_new = {}
for aid, name in live_athletes.items():
    live_name_map_old[normalize_old(name)] = aid
    live_name_map_new[normalize_new(name)] = aid

print(f"\n📊 Live DB: {len(live_athletes)} VĐV")
print(f"📊 Backup DB: {len(bak_athletes)} VĐV")

# --- So sánh ---
print(f"\n{'='*90}")
print(f"{'Tên VĐV (Backup)':<30} {'Backup':>8} {'Live':>8} {'Thiếu':>8} {'Match CŨ':>10} {'Match MỚI':>10}")
print(f"{'='*90}")

missing_old = []  # Thiếu khi dùng hàm cũ
missing_new = []  # Thiếu khi dùng hàm mới
total_missing_acts = 0

for bak_id, bak_name in bak_athletes:
    bak_count = bak_act_counts.get(bak_id, 0)
    if bak_count == 0:
        continue
    
    norm_old = normalize_old(bak_name)
    norm_new = normalize_new(bak_name)
    
    # Tìm live ID
    live_id_old = live_name_map_old.get(norm_old)
    live_id_new = live_name_map_new.get(norm_new)
    
    live_count_old = live_act_counts.get(live_id_old, 0) if live_id_old else 0
    live_count_new = live_act_counts.get(live_id_new, 0) if live_id_new else 0
    
    match_old_ok = "✅" if live_id_old else "❌"
    match_new_ok = "✅" if live_id_new else "❌"
    
    # Kiểm tra thiếu khi dùng hàm CŨ
    if not live_id_old or live_count_old < bak_count:
        deficit = bak_count - live_count_old
        missing_old.append((bak_id, bak_name, bak_count, live_count_old, deficit, live_id_old))
        total_missing_acts += deficit
        print(f"  {bak_name:<28} {bak_count:>8} {live_count_old:>8} {deficit:>8} {match_old_ok:>10} {match_new_ok:>10}")
    
    # Kiểm tra thiếu khi dùng hàm MỚI
    if not live_id_new:
        missing_new.append((bak_id, bak_name, bak_count))

print(f"\n{'='*90}")
print(f"\n📊 KẾT QUẢ PHÂN TÍCH:")
print(f"  - VĐV bị THIẾU hoạt động (hàm CŨ): {len(missing_old)} người")
print(f"  - VĐV bị THIẾU hoạt động (hàm MỚI): {len(missing_new)} người")
print(f"  - Tổng hoạt động bị thiếu: {total_missing_acts}")

# Chi tiết VĐV không match hàm CŨ nhưng match hàm MỚI
saved_by_new = []
for bak_id, bak_name, bak_count, live_count, deficit, live_id in missing_old:
    norm_new = normalize_new(bak_name)
    live_id_new = live_name_map_new.get(norm_new)
    if not live_id and live_id_new:
        saved_by_new.append((bak_id, bak_name, bak_count, live_athletes.get(live_id_new, '?')))

if saved_by_new:
    print(f"\n🎯 VĐV ĐƯỢC CỨU nhờ hàm normalize MỚI ({len(saved_by_new)} người):")
    for bak_id, bak_name, bak_count, live_name in saved_by_new:
        print(f"  ✅ '{bak_name}' → '{live_name}' ({bak_count} hoạt động)")

# Chi tiết VĐV HOÀN TOÀN KHÔNG match
still_missing = []
for bak_id, bak_name, bak_count, live_count, deficit, live_id in missing_old:
    norm_new = normalize_new(bak_name)
    if norm_new not in live_name_map_new:
        still_missing.append((bak_id, bak_name, bak_count))

if still_missing:
    print(f"\n❌ VĐV VẪN KHÔNG MATCH (cả hàm CŨ lẫn MỚI) ({len(still_missing)} người):")
    for bak_id, bak_name, bak_count in still_missing:
        print(f"  ❌ [{bak_id}] '{bak_name}' ({bak_count} hoạt động) - VĐV ĐÃ XÓA KHỎI LIVE DB?")

# VĐV match nhưng vẫn thiếu dữ liệu
still_deficit = []
for bak_id, bak_name, bak_count, live_count, deficit, live_id in missing_old:
    norm_new = normalize_new(bak_name)
    live_id_new = live_name_map_new.get(norm_new)
    if live_id_new and live_act_counts.get(live_id_new, 0) < bak_count:
        live_c = live_act_counts.get(live_id_new, 0)
        print(f"  ⚠️  [{bak_id}] '{bak_name}' → Live ID={live_id_new}: backup={bak_count}, live={live_c}, thiếu={bak_count - live_c}")

"""
Phân tích: So sánh tên VĐV trong backup vs live DB
Dùng cả hàm normalize CŨ (chỉ NFC) và MỚI (khử dấu + loại ký tự đặc biệt)
để xác định chính xác 11 VĐV nào bị thiếu và tại sao.
"""
import sqlite3
import sys
import io
import unicodedata
import re
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# --- 2 hàm normalize ---
def normalize_old(name):
    """Hàm normalize CŨ - chỉ NFC + lowercase + bỏ *"""
    if not name:
        return ""
    name_nfc = unicodedata.normalize("NFC", name)
    return name_nfc.replace("*", "").strip().lower()

def normalize_new(name):
    """Hàm normalize MỚI - khử dấu tiếng Việt + loại bỏ ký tự đặc biệt"""
    if not name:
        return ""
    name_lower = unicodedata.normalize("NFC", name).lower()
    nfkd_form = unicodedata.normalize('NFKD', name_lower)
    only_ascii = nfkd_form.encode('ASCII', 'ignore').decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', only_ascii)


# Tìm file backup
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backup_dir = os.path.join(base_dir, "backups")
live_db = os.path.join(base_dir, "sso_hc.db")

# Tìm backup file phù hợp
backup_files = []
if os.path.exists(backup_dir):
    backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.db')]
    backup_files.sort(reverse=True)

# Cũng kiểm tra file backup ở thư mục gốc
root_backups = [f for f in os.listdir(base_dir) if f.endswith('.db') and 'backup' in f.lower()]

print("=== FILE BACKUP TÌM THẤY ===")
if backup_files:
    for f in backup_files[:5]:
        fpath = os.path.join(backup_dir, f)
        print(f"  📁 backups/{f} ({os.path.getsize(fpath)/1024:.0f} KB)")
if root_backups:
    for f in root_backups[:5]:
        fpath = os.path.join(base_dir, f)
        print(f"  📁 {f} ({os.path.getsize(fpath)/1024:.0f} KB)")

# Dùng file backup gần nhất
if backup_files:
    backup_db = os.path.join(backup_dir, backup_files[0])
elif root_backups:
    backup_db = os.path.join(base_dir, root_backups[0])
else:
    print("❌ Không tìm thấy file backup nào!")
    sys.exit(1)

print(f"\n🔍 Sử dụng backup: {backup_db}")
print(f"🔍 Live DB: {live_db}")

# --- Đọc live DB ---
conn_live = sqlite3.connect(live_db)
cur_live = conn_live.cursor()
cur_live.execute("SELECT id, full_name FROM athletes")
live_athletes = cur_live.fetchall()
conn_live.close()

live_name_map_old = {normalize_old(name): (aid, name) for aid, name in live_athletes}
live_name_map_new = {normalize_new(name): (aid, name) for aid, name in live_athletes}

print(f"\n📊 Live DB: {len(live_athletes)} VĐV")
print(f"   - Map CŨ (NFC): {len(live_name_map_old)} entries")
print(f"   - Map MỚI (khử dấu): {len(live_name_map_new)} entries")

# --- Đọc backup DB ---
conn_bak = sqlite3.connect(backup_db)
cur_bak = conn_bak.cursor()
cur_bak.execute("SELECT id, full_name FROM athletes")
bak_athletes = cur_bak.fetchall()

# Đếm hoạt động event_id=1, trước 16/06 cho mỗi VĐV trong backup
cur_bak.execute("""
    SELECT athlete_id, COUNT(*) 
    FROM activities 
    WHERE event_id = 1 AND activity_date < '2026-06-16'
    GROUP BY athlete_id
""")
bak_act_counts = dict(cur_bak.fetchall())
conn_bak.close()

print(f"📊 Backup DB: {len(bak_athletes)} VĐV, {sum(bak_act_counts.values())} hoạt động (event_id=1, trước 16/06)")

# --- So sánh ---
print(f"\n{'='*80}")
print("PHÂN TÍCH SO KHỚP TÊN VĐV (Backup → Live)")
print(f"{'='*80}")

matched_old = 0
matched_new = 0
unmatched_both = []
matched_new_only = []  # Match với hàm mới nhưng KHÔNG match với hàm cũ

for bak_id, bak_name in bak_athletes:
    acts = bak_act_counts.get(bak_id, 0)
    if acts == 0:
        continue  # Bỏ qua VĐV không có hoạt động cần restore
    
    norm_old = normalize_old(bak_name)
    norm_new = normalize_new(bak_name)
    
    old_match = norm_old in live_name_map_old
    new_match = norm_new in live_name_map_new
    
    if old_match:
        matched_old += 1
    if new_match:
        matched_new += 1
    
    if not old_match and not new_match:
        unmatched_both.append((bak_id, bak_name, acts, norm_old, norm_new))
    elif not old_match and new_match:
        live_info = live_name_map_new[norm_new]
        matched_new_only.append((bak_id, bak_name, acts, norm_old, norm_new, live_info))

print(f"\n📈 VĐV có hoạt động cần restore: {sum(1 for _, _, a in [(bid, bn, bak_act_counts.get(bid, 0)) for bid, bn in bak_athletes] if a > 0)}")
print(f"  ✅ Match bằng hàm CŨ (NFC): {matched_old}")
print(f"  ✅ Match bằng hàm MỚI (khử dấu): {matched_new}")

if matched_new_only:
    print(f"\n🎯 VĐV ĐƯỢC CỨU NHỜ HÀM MỚI ({len(matched_new_only)} người):")
    for bak_id, bak_name, acts, norm_old, norm_new, live_info in matched_new_only:
        live_id, live_name = live_info
        print(f"  ✅ Backup: [{bak_id}] '{bak_name}' → Live: [{live_id}] '{live_name}'")
        print(f"     Norm CŨ: '{norm_old}' vs Live CŨ: KHÔNG CÓ")
        print(f"     Norm MỚI: '{norm_new}' → MATCH!")
        print(f"     📦 Có {acts} hoạt động cần restore")

if unmatched_both:
    print(f"\n❌ VĐV KHÔNG MATCH ĐƯỢC CẢ 2 HÀM ({len(unmatched_both)} người):")
    for bak_id, bak_name, acts, norm_old, norm_new in unmatched_both:
        print(f"  ❌ Backup: [{bak_id}] '{bak_name}' ({acts} activities)")
        print(f"     Norm CŨ: '{norm_old}'")
        print(f"     Norm MỚI: '{norm_new}'")
        # Tìm tên gần giống nhất trong live DB
        for live_norm, (live_id, live_name) in live_name_map_new.items():
            if norm_new[:5] == live_norm[:5] or bak_name.split()[0] == live_name.split()[0]:
                print(f"     🔎 Gợi ý: Live [{live_id}] '{live_name}' (norm: '{live_norm}')")
                break

if not matched_new_only and not unmatched_both:
    print("\n✅ TẤT CẢ VĐV đều match được bằng cả 2 hàm normalize!")

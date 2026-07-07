import sqlite3
import sys

# Thiết lập utf-8 cho stdout trên Windows
if sys.platform.startswith('win'):
    sys.stdout.reconfigure(encoding='utf-8')

def check_db():
    conn = sqlite3.connect("SSO_HC.db")
    cursor = conn.cursor()
    
    # Xem số lượng hoạt động trong bảng activities
    cursor.execute("SELECT COUNT(*) FROM activities")
    total = cursor.fetchone()[0]
    print(f"Tong so hoat dong trong database: {total}")
    
    # Xem 15 hoạt động gần nhất
    cursor.execute("""
        SELECT id, athlete_name_raw, name, type, distance_km, activity_date, activity_time, multiplier, kcal_burned, sync_date 
        FROM activities 
        ORDER BY sync_date DESC 
        LIMIT 15
    """)
    rows = cursor.fetchall()
    print("\n15 hoat dong gan nhat:")
    for row in rows:
        print(f"ID: {row[0][:8]}... | Ten: {row[1]} | Hoat dong: {row[2]} | Loai: {row[3]} | Quang duong: {row[4]} km | Ngay: {row[5]} | Gio: {row[6]} | He so: {row[7]} | Kcal: {row[8]} | Dong bo luc: {row[9]}")
        
    # Xem số lượng hoạt động có activity_time không phải None
    cursor.execute("SELECT COUNT(*) FROM activities WHERE activity_time IS NOT NULL")
    with_time = cursor.fetchone()[0]
    print(f"\nSo hoat dong co gio chay (activity_time): {with_time}")
    
    conn.close()

if __name__ == "__main__":
    check_db()

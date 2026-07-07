import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

# Lấy thử 5 bản ghi và in giá trị trường activity_date
cur.execute("SELECT id, activity_date FROM activities LIMIT 5")
print("=== ĐỊNH DẠNG TRƯỜNG ACTIVITY_DATE TRONG DB ===")
for r in cur.fetchall():
    print(f"ID: {r[0]} | Ngày (Raw): '{r[1]}' | Kiểu dữ liệu: {type(r[1])}")

# Thử nghiệm so sánh trong SQL
cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date < '2026-06-16'")
count = cur.fetchone()[0]
print(f"\nSố lượng hoạt động trước 16/06: {count}")

conn.close()

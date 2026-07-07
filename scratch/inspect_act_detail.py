import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

backup_db = "SSO_HC_backup_v1.4.0_1783262525.db"
conn = sqlite3.connect(backup_db)
cur = conn.cursor()

cur.execute("SELECT * FROM activities WHERE id = '19028650701_2'")
row = cur.fetchone()
col_names = [desc[0] for desc in cur.description]
print("=== CHI TIẾT HOẠT ĐỘNG 19028650701_2 ===")
for col, val in zip(col_names, row):
    print(f"{col}: {val}")

conn.close()

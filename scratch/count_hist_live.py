import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def count_total_historical_live():
    db_file = "SSO_HC_backup_v1.4.0_1783345876.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM activities WHERE activity_date < '2026-06-16'")
    count = cur.fetchone()[0]
    print(f"Tổng số hoạt động lịch sử trước 16/06 trong CSDL mới gửi: {count}")
    
    conn.close()

if __name__ == "__main__":
    count_total_historical_live()

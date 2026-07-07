import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_admin_dup_token_logic():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    try:
        # Giả lập câu query trong main.py
        # Tìm các token bị trùng (không phải NULL và không phải rỗng)
        cur.execute("""
            SELECT strava_refresh_token, COUNT(*) 
            FROM athletes 
            WHERE strava_refresh_token IS NOT NULL AND strava_refresh_token != ''
            GROUP BY strava_refresh_token 
            HAVING COUNT(*) > 1
        """)
        dup_tokens = cur.fetchall()
        print("Các token bị trùng lặp:", dup_tokens)
        
        dup_token_alerts = []
        for token, count in dup_tokens:
            cur.execute("""
                SELECT id, full_name, department 
                FROM athletes 
                WHERE strava_refresh_token = ?
            """, (token,))
            athletes = cur.fetchall()
            
            names = [f"{ath[1]} ({ath[2]})" for ath in athletes]
            dup_token_alerts.append({
                "token": token,
                "athletes": names,
                "ids": [ath[0] for ath in athletes]
            })
            
        print("\nKết quả dup_token_alerts:")
        for alert in dup_token_alerts:
            print(f"Token: {alert['token'][:10]}... | VĐV: {', '.join(alert['athletes'])}")
            
        print("\n=> TRUY VẤN SQL HOÀN TOÀN HỢP LỆ!")
    except Exception as e:
        print("\n❌ LỖI TRUY VẤN SQL:", str(e))
        
    conn.close()

if __name__ == "__main__":
    test_admin_dup_token_logic()

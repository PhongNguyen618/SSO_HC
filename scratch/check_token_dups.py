import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_token_duplication():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, full_name, strava_athlete_id, strava_access_token, strava_refresh_token 
        FROM athletes 
        WHERE strava_refresh_token IS NOT NULL
    """)
    rows = cur.fetchall()
    
    print("=== KIỂM TRA TRÙNG LẶP TOKEN TRONG CSDL ===")
    
    seen_access = {}
    seen_refresh = {}
    
    for r in rows:
        aid, name, strava_id, access, refresh = r
        
        if access in seen_access:
            seen_access[access].append((aid, name))
        else:
            seen_access[access] = [(aid, name)]
            
        if refresh in seen_refresh:
            seen_refresh[refresh].append((aid, name))
        else:
            seen_refresh[refresh] = [(aid, name)]
            
    # In ra các access token bị trùng
    dup_access = {k: v for k, v in seen_access.items() if len(v) > 1}
    print(f"\nTìm thấy {len(dup_access)} Access Token bị dùng chung bởi nhiều VĐV:")
    for token, users in dup_access.items():
        print(f"Token: {token[:15]}... dùng bởi:")
        for uid, uname in users:
            print(f"  - ID={uid}: {uname}")
            
    # In ra các refresh token bị trùng
    dup_refresh = {k: v for k, v in seen_refresh.items() if len(v) > 1}
    print(f"\nTìm thấy {len(dup_refresh)} Refresh Token bị dùng chung bởi nhiều VĐV:")
    for token, users in dup_refresh.items():
        print(f"Token: {token[:15]}... dùng bởi:")
        for uid, uname in users:
            print(f"  - ID={uid}: {uname}")

    conn.close()

if __name__ == "__main__":
    check_token_duplication();

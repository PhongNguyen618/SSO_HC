import sqlite3
import requests
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_athlete_api_directly():
    db_path = "SSO_HC_backup_v1.4.0_1783262525.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT id, full_name, strava_access_token, strava_refresh_token, strava_expires_at
        FROM athletes 
        WHERE id = 102
    """)
    athlete = cur.fetchone()
    conn.close()
    
    if not athlete:
        print("Không tìm thấy VĐV Nguyễn Minh Tú trong backup!")
        return
        
    aid, name, access_token, refresh_token, expires_at = athlete
    print(f"VDV: {name}")
    print(f"Access Token: {access_token[:10]}... (Expires at: {expires_at})")
    
    url = "https://www.strava.com/api/v3/athlete/activities"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    after_timestamp = 1781542800 
    params = {
        "after": after_timestamp,
        "page": 1,
        "per_page": 10
    }
    
    print("\n--- GOI API THU NGHIEM ---")
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        scopes_header = response.headers.get("X-OAuth-Scopes", "")
        print(f"Quyen han thuc te cua Token (X-OAuth-Scopes): {scopes_header}")
        
        if response.status_code == 200:
            activities = response.json()
            print(f"So luong hoat dong tra ve: {len(activities)}")
            if len(activities) > 0:
                for act in activities[:3]:
                    print(f"  - Hoat dong: {act.get('name')} | Ngay: {act.get('start_date_local')} | Khoang cach: {act.get('distance')}m")
            else:
                print("  => Strava tra ve DANH SACH RONG []. Tai khoan nay thuc su khong co hoat dong nao tu 16/6/2026.")
        else:
            print(f"Loi phan hoi tu Strava: {response.text}")
            
    except Exception as e:
        print(f"Loi ket noi API: {e}")

if __name__ == "__main__":
    test_athlete_api_directly()

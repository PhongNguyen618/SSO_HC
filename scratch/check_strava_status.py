import sqlite3
import requests
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_athletes_on_strava():
    db_file = "SSO_HC_backup_v1.4.0_1783313355.db"
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # Danh sách các ID cần kiểm tra
    target_ids = [97, 102, 105, 123, 133, 141, 159, 160, 164, 165]
    
    placeholders = ",".join("?" for _ in target_ids)
    cur.execute(f"""
        SELECT id, full_name, strava_access_token, strava_refresh_token, strava_athlete_id, strava_name
        FROM athletes
        WHERE id IN ({placeholders})
    """, target_ids)
    
    athletes = cur.fetchall()
    conn.close()
    
    url = "https://www.strava.com/api/v3/athlete/activities"
    # Mốc thời gian 2026-06-16 00:00:00 GMT+7
    after_timestamp = 1781542800
    
    print("=== KIỂM TRA LỖI API GỌI STRAVA TRỰC TIẾP ===")
    for ath in athletes:
        aid, name, access_token, refresh_token, strava_id, s_name = ath
        print(f"\n* VĐV: {name} (ID={aid}) | Strava ID: {strava_id} | Tên Strava: {s_name}")
        
        if not access_token:
            print("  => Lỗi: Không có Access Token trong database!")
            continue
            
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"after": after_timestamp, "page": 1, "per_page": 50}
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            status = res.status_code
            scopes = res.headers.get("X-OAuth-Scopes", "")
            
            print(f"  - Status Code: {status}")
            print(f"  - Quyền hạn thực tế (X-OAuth-Scopes): '{scopes}'")
            
            if status == 200:
                acts = res.json()
                print(f"  - API trả về: {len(acts)} hoạt động từ ngày 16/06.")
                if len(acts) > 0:
                    print("    Ví dụ 3 hoạt động đầu tiên:")
                    for a in acts[:3]:
                        print(f"      + Tên: {a.get('name')} | Ngày: {a.get('start_date_local')} | Kiểu: {a.get('type')} | KC: {a.get('distance')}m")
                else:
                    print("    => TÀI KHOẢN KHÔNG CÓ HOẠT ĐỘNG NÀO TỪ 16/06 TRÊN STRAVA THẬT.")
            elif status == 401:
                print("  => LỖI 401 (Unauthorized): Token đã bị vô hiệu hóa hoặc không hợp lệ.")
            elif status == 403:
                print("  => LỖI 403 (Forbidden): Lỗi quyền truy cập.")
            else:
                print(f"  => Lỗi phản hồi khác: {res.text}")
        except Exception as e:
            print(f"  - Lỗi kết nối API: {e}")

if __name__ == "__main__":
    check_athletes_on_strava()

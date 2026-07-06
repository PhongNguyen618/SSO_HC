import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def clear_duplicate_tokens():
    db_file = "SSO_HC.db"
    import os
    if not os.path.exists(db_file):
        db_file = "SSO_HC_backup_v1.4.0_1783313355.db" # Fallback test
        
    print(f"Đang xử lý dọn dẹp trên file: {db_file}")
    conn = sqlite3.connect(db_file)
    cur = conn.cursor()
    
    # 1. Tìm các refresh token bị trùng lặp
    cur.execute("""
        SELECT strava_refresh_token, COUNT(*) 
        FROM athletes 
        WHERE strava_refresh_token IS NOT NULL 
        GROUP BY strava_refresh_token 
        HAVING COUNT(*) > 1
    """)
    dup_tokens = [r[0] for r in cur.fetchall()]
    
    if not dup_tokens:
        print("Không tìm thấy bất kỳ token trùng lặp nào cần dọn dẹp!")
        conn.close()
        return
        
    print(f"Tìm thấy {len(dup_tokens)} nhóm token bị trùng lặp.")
    
    total_cleared = 0
    for token in dup_tokens:
        # Lấy danh sách VĐV dùng chung token này
        cur.execute("SELECT id, full_name FROM athletes WHERE strava_refresh_token = ?", (token,))
        users = cur.fetchall()
        print(f"\nNhóm trùng lặp dùng chung token '{token[:15]}...':")
        for uid, name in users:
            print(f"  - ID={uid}: {name}")
            
        # Ta sẽ HỦY LIÊN KẾT tất cả các VĐV trong nhóm trùng lặp này
        # để buộc họ phải thực hiện liên kết lại từ đầu bằng tài khoản chính xác của họ
        cur.execute("""
            UPDATE athletes 
            SET strava_access_token = NULL,
                strava_refresh_token = NULL,
                strava_expires_at = NULL,
                strava_athlete_id = NULL
            WHERE strava_refresh_token = ?
        """, (token,))
        total_cleared += cur.rowcount
        
    conn.commit()
    print(f"\n=> Đã xóa thông tin liên kết lỗi của {total_cleared} VĐV thành công. Họ sẽ cần thực hiện liên kết lại bằng tài khoản Strava chính xác của mình.")
    conn.close()

if __name__ == "__main__":
    clear_duplicate_tokens()

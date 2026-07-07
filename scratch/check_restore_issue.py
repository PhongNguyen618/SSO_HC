import sqlite3
import os

def check_restore_issue():
    """Kiểm tra chi tiết tại sao khôi phục chỉ hoạt động cho Ha Hoang mà không cho người khác."""
    
    # 1. Kiểm tra DB live
    live_db = "SSO_HC.db"
    conn_live = sqlite3.connect(live_db)
    cur_live = conn_live.cursor()
    
    cur_live.execute("SELECT COUNT(*) FROM activities WHERE event_id = 1 AND activity_date < '2026-06-16'")
    print(f"=== LIVE DB ===")
    print(f"SSO HC (event_id=1) hoat dong truoc 16/6: {cur_live.fetchone()[0]}")
    
    cur_live.execute("SELECT COUNT(*) FROM activities WHERE event_id = 1 AND activity_date >= '2026-06-16'")
    print(f"SSO HC (event_id=1) hoat dong tu 16/6: {cur_live.fetchone()[0]}")
    
    cur_live.execute("SELECT COUNT(DISTINCT athlete_id) FROM activities WHERE event_id = 1 AND activity_date < '2026-06-16'")
    print(f"So VDV co hoat dong truoc 16/6: {cur_live.fetchone()[0]}")
    
    # Xem danh sach VDV dang ky SSO HC
    cur_live.execute("""
        SELECT a.id, a.full_name, a.strava_refresh_token IS NOT NULL as is_linked
        FROM athletes a
        JOIN competition_registrations cr ON a.id = cr.athlete_id
        WHERE cr.event_id = 1
        ORDER BY a.full_name
    """)
    live_athletes = cur_live.fetchall()
    print(f"\nSo VDV dang ky SSO HC: {len(live_athletes)}")
    
    for a_id, name, linked in live_athletes:
        cur_live.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ? AND event_id = 1 AND activity_date < '2026-06-16'", (a_id,))
        cnt_before = cur_live.fetchone()[0]
        cur_live.execute("SELECT COUNT(*) FROM activities WHERE athlete_id = ? AND event_id = 1 AND activity_date >= '2026-06-16'", (a_id,))
        cnt_after = cur_live.fetchone()[0]
        linked_str = "LINKED" if linked else "no"
        safe_name = name.encode('ascii', 'replace').decode('ascii')
        print(f"  {safe_name} (id={a_id}): truoc_16/6={cnt_before}, tu_16/6={cnt_after}, strava={linked_str}")
    
    conn_live.close()
    
    # 2. Kiem tra cac ban backup
    print(f"\n=== BACKUP FILES ===")
    
    # Tim cac file backup
    root_dir = os.path.dirname(os.path.abspath(__file__))
    # Go up from scratch/ to project root
    root_dir = os.path.dirname(root_dir)
    
    db_files = []
    for f in os.listdir(root_dir):
        if f.endswith(".db") and f != "SSO_HC.db" and f != "test_sync_grace.db":
            db_files.append(os.path.join(root_dir, f))
    
    backups_dir = os.path.join(root_dir, "static", "uploads", "backups")
    if os.path.exists(backups_dir):
        for f in os.listdir(backups_dir):
            if f.endswith(".db"):
                db_files.append(os.path.join(backups_dir, f))
    
    for db_path in db_files:
        try:
            conn_b = sqlite3.connect(db_path)
            cur_b = conn_b.cursor()
            
            cur_b.execute("SELECT COUNT(*) FROM activities WHERE event_id = 1 AND activity_date < '2026-06-16'")
            cnt_b16 = cur_b.fetchone()[0]
            
            cur_b.execute("SELECT COUNT(*) FROM activities WHERE event_id = 1")
            cnt_total = cur_b.fetchone()[0]
            
            cur_b.execute("SELECT COUNT(DISTINCT athlete_id) FROM activities WHERE event_id = 1 AND activity_date < '2026-06-16'")
            cnt_vdv = cur_b.fetchone()[0]
            
            print(f"\n{os.path.basename(db_path)}:")
            print(f"  Event 1 total acts: {cnt_total}, truoc 16/6: {cnt_b16}, so VDV truoc 16/6: {cnt_vdv}")
            
            # Xem chi tiet cac VDV
            cur_b.execute("""
                SELECT a.id, a.full_name, COUNT(act.id) as act_count
                FROM athletes a
                JOIN activities act ON a.id = act.athlete_id
                WHERE act.event_id = 1 AND act.activity_date < '2026-06-16'
                GROUP BY a.id, a.full_name
                ORDER BY act_count DESC
            """)
            vdv_detail = cur_b.fetchall()
            for v_id, v_name, v_cnt in vdv_detail:
                safe_v = v_name.encode('ascii', 'replace').decode('ascii')
                print(f"    {safe_v} (id={v_id}): {v_cnt} acts truoc 16/6")
            
            conn_b.close()
        except Exception as e:
            print(f"  Error reading {os.path.basename(db_path)}: {e}")

if __name__ == "__main__":
    check_restore_issue()

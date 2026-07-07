import sqlite3
import os

def compare_backup_vs_live():
    """So sanh du lieu giua backup lon nhat va DB live de tim hoat dong bi thieu."""
    
    live_db = "SSO_HC.db"
    backup_db = "SSO_HC_backup_v1.4.0_1783161208.db"  # Backup lon nhat (2652 acts for event 1)
    
    # Doc backup
    conn_b = sqlite3.connect(backup_db)
    cur_b = conn_b.cursor()
    
    cur_b.execute("""
        SELECT a.id, a.full_name, COUNT(act.id) as act_count
        FROM athletes a
        JOIN activities act ON a.id = act.athlete_id
        WHERE act.event_id = 1 AND act.activity_date < '2026-06-16'
        GROUP BY a.id
        ORDER BY act_count DESC
    """)
    backup_athletes = cur_b.fetchall()
    
    # Doc live
    conn_l = sqlite3.connect(live_db)
    cur_l = conn_l.cursor()
    
    cur_l.execute("""
        SELECT a.id, a.full_name, 
               a.strava_refresh_token IS NOT NULL AND a.strava_refresh_token != '' as is_linked,
               COUNT(act.id) as act_count
        FROM athletes a
        LEFT JOIN activities act ON a.id = act.athlete_id AND act.event_id = 1 AND act.activity_date < '2026-06-16'
        JOIN competition_registrations cr ON a.id = cr.athlete_id AND cr.event_id = 1
        GROUP BY a.id
    """)
    live_data = {row[1].strip().lower(): (row[0], row[1], row[2], row[3]) for row in cur_l.fetchall()}
    
    print("=== SO SANH BACKUP vs LIVE (Event 1 - SSO HC, truoc 16/6) ===\n")
    print(f"{'VDV (Backup)':<35} {'Backup':>6} {'Live':>6} {'Thieu':>6} {'Strava':>8}")
    print("-" * 70)
    
    total_missing = 0
    missing_athletes = []
    
    for b_id, b_name, b_cnt in backup_athletes:
        safe_name = b_name.strip()
        key = safe_name.lower()
        
        if key in live_data:
            l_id, l_name, is_linked, l_cnt = live_data[key]
            missing = b_cnt - l_cnt
            linked_str = "DA LINK" if is_linked else "-"
            
            # Chi hien thi VDV bi thieu hoat dong
            if missing > 0:
                total_missing += missing
                missing_athletes.append((safe_name, b_cnt, l_cnt, missing, linked_str))
                try:
                    print(f"  {safe_name:<33} {b_cnt:>6} {l_cnt:>6} {missing:>6} {linked_str:>8}")
                except:
                    print(f"  ID={b_id:<30} {b_cnt:>6} {l_cnt:>6} {missing:>6} {linked_str:>8}")
        else:
            try:
                print(f"  {safe_name:<33} {b_cnt:>6} {'N/A':>6} {'???':>6} {'NOT REG':>8}")
            except:
                print(f"  ID={b_id:<30} {b_cnt:>6} {'N/A':>6} {'???':>6} {'NOT REG':>8}")
    
    print(f"\nTONG SO HOAT DONG BI THIEU: {total_missing}")
    print(f"SO VDV BI THIEU HOAT DONG: {len(missing_athletes)}")
    
    conn_b.close()
    conn_l.close()

if __name__ == "__main__":
    compare_backup_vs_live()

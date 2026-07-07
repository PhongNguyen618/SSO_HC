import sqlite3

def check_dist():
    db_path = "SSO_HC_backup_v1.4.0_1783161208.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT a.id, a.full_name, a.strava_name, SUM(act.distance_km), COUNT(act.id)
        FROM athletes a
        LEFT JOIN activities act ON a.id = act.athlete_id
        WHERE a.id = 51
        GROUP BY a.id, a.full_name, a.strava_name
    """)
    r = cur.fetchone()
    if r:
        safe_name = r[1].encode('ascii', 'ignore').decode('ascii')
        print(f"Athlete ID 51 | Name: {safe_name} | Strava: {r[2]} | Total Dist: {r[3]:.2f} km | Count: {r[4]}")
    conn.close()

if __name__ == "__main__":
    check_dist()

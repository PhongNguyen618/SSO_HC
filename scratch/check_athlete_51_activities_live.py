import sqlite3

def check_athlete_activities():
    db_path = "SSO_HC.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    # Check athlete 51 general info
    cur.execute("SELECT id, full_name, strava_name, is_active FROM athletes WHERE id = 51")
    ath = cur.fetchone()
    if ath:
        safe_name = ath[1].encode('ascii', 'ignore').decode('ascii')
        print(f"Athlete ID 51 | Name: {safe_name} | Strava: {ath[2]} | Active: {ath[3]}")
    
    # Check count by event_id
    print("\nActivities by Event ID:")
    cur.execute("""
        SELECT event_id, COUNT(*), SUM(distance_km), SUM(distance_km_raw)
        FROM activities
        WHERE athlete_id = 51
        GROUP BY event_id
    """)
    for r in cur.fetchall():
        print(f"  Event ID: {r[0]} | Count: {r[1]} | Dist: {r[2]} km | Dist Raw: {r[3]} km")
        
    # Check count by sport_type
    print("\nActivities by Sport Type (Event ID 1):")
    cur.execute("""
        SELECT sport_type, COUNT(*), SUM(distance_km)
        FROM activities
        WHERE athlete_id = 51 AND event_id = 1
        GROUP BY sport_type
    """)
    for r in cur.fetchall():
        print(f"  Sport: {r[0]} | Count: {r[1]} | Dist: {r[2]} km")
        
    # Check count of suspicious activities
    print("\nSuspicious activities:")
    cur.execute("""
        SELECT is_suspicious, COUNT(*)
        FROM activities
        WHERE athlete_id = 51
        GROUP BY is_suspicious
    """)
    for r in cur.fetchall():
        print(f"  is_suspicious: {r[0]} | Count: {r[1]}")
        
    # Print the ranking rules for Event ID 1
    print("\nEvent ID 1 ranking rules:")
    cur.execute("SELECT id, title, ranking_metric, ranking_sports, is_active FROM competition_events WHERE id = 1")
    ev = cur.fetchone()
    if ev:
        safe_title = ev[1].encode('ascii', 'ignore').decode('ascii')
        print(f"  ID: {ev[0]} | Title: {safe_title} | Metric: {ev[2]} | Sports: {ev[3]} | Active: {ev[4]}")
        
    conn.close()

if __name__ == "__main__":
    check_athlete_activities()

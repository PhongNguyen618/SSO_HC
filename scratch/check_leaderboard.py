import sqlite3
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def check_leaderboard():
    db_path = "SSO_HC.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    print("=== Top 10 Athletes by Distance in Live DB ===")
    cur.execute("""
        SELECT a.id, a.full_name, a.strava_name, SUM(act.distance_km) as total_dist, COUNT(act.id) as act_count
        FROM athletes a
        JOIN activities act ON a.id = act.athlete_id
        GROUP BY a.id, a.full_name, a.strava_name
        ORDER BY total_dist DESC
        LIMIT 15
    """)
    for idx, r in enumerate(cur.fetchall()):
        print(f"{idx+1}. ID: {r[0]} | Name: {r[1]} | Strava: {r[2]} | Dist: {r[3]:.2f} km | Count: {r[4]}")
        
    conn.close()

if __name__ == "__main__":
    check_leaderboard()

import sqlite3

def main():
    conn = sqlite3.connect('SSO_HC.db')
    cursor = conn.cursor()
    
    # Select recent activities
    cursor.execute('SELECT id, name, activity_date, activity_time, distance_km, athlete_name_raw FROM activities ORDER BY activity_date DESC LIMIT 50')
    rows = cursor.fetchall()
    
    with open('scratch/list_recent_activities.txt', 'w', encoding='utf-8') as f:
        f.write("Recent 50 activities in DB:\n")
        for row in rows:
            f.write(f"ID={row[0][:8]}... Name={repr(row[1])} Date={row[2]} Time={row[3]} Dist={row[4]} Athlete={row[5]}\n")
        
    conn.close()
    print("Done writing to scratch/list_recent_activities.txt")

if __name__ == "__main__":
    main()

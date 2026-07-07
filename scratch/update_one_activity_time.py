import sqlite3

def main():
    conn = sqlite3.connect('SSO_HC.db')
    cursor = conn.cursor()
    
    # Get the first activity id
    cursor.execute('SELECT id, athlete_name_raw, activity_date FROM activities LIMIT 1')
    row = cursor.fetchone()
    if not row:
        print("No activities found in DB!")
        return
        
    act_id, athlete_name, act_date = row
    print(f"Found activity: ID={act_id}, Athlete={athlete_name}, Date={act_date}")
    
    # Update its activity_time to 08:30
    cursor.execute('UPDATE activities SET activity_time = "08:30" WHERE id = ?', (act_id,))
    conn.commit()
    print("Updated activity_time to '08:30'")
    
    # Query it back
    cursor.execute('SELECT id, athlete_name_raw, activity_date, activity_time FROM activities WHERE id = ?', (act_id,))
    updated_row = cursor.fetchone()
    print("Updated row in DB:", updated_row)
    
    conn.close()

if __name__ == "__main__":
    main()

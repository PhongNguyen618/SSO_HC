import sqlite3

conn = sqlite3.connect("SSO_HC.db")
cursor = conn.cursor()

# Get column names of activities table
cursor.execute("PRAGMA table_info(activities)")
cols = [row[1] for row in cursor.fetchall()]
print("Columns of activities:", cols)

# Check for NULL in critical fields
print("\nChecking for NULL values in activities:")
cursor.execute("""
    SELECT id, athlete_id, athlete_name_raw, name, distance_km, moving_time_min, kcal_burned, activity_date
    FROM activities
    WHERE athlete_name_raw IS NULL 
       OR name IS NULL 
       OR distance_km IS NULL 
       OR moving_time_min IS NULL 
       OR kcal_burned IS NULL
""")
null_rows = cursor.fetchall()
print(f"Number of rows with some NULL values: {len(null_rows)}")
for r in null_rows[:10]:
    print(r)

# Check if there are values that might cause errors in JS (e.g. NaN or None)
cursor.execute("SELECT COUNT(*) FROM activities WHERE distance_km IS NULL")
print("Null distance_km count:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM activities WHERE moving_time_min IS NULL")
print("Null moving_time_min count:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM activities WHERE kcal_burned IS NULL")
print("Null kcal_burned count:", cursor.fetchone()[0])

cursor.execute("SELECT COUNT(*) FROM activities WHERE athlete_name_raw IS NULL")
print("Null athlete_name_raw count:", cursor.fetchone()[0])

conn.close()

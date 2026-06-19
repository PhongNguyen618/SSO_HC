import sqlite3

conn = sqlite3.connect("SSO_HC.db")
cursor = conn.cursor()

# Lấy schema của bảng athletes
cursor.execute("PRAGMA table_info(athletes)")
print("Table athletes info:")
for col in cursor.fetchall():
    print(col)

# Lấy schema của bảng competition_registrations
cursor.execute("PRAGMA table_info(competition_registrations)")
print("\nTable competition_registrations info:")
for col in cursor.fetchall():
    print(col)

conn.close()

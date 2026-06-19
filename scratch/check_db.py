import sqlite3

conn = sqlite3.connect("SSO_HC.db")
cursor = conn.cursor()

# Lay 10 VDV gan nhat
cursor.execute("SELECT id, full_name, avatar_url, is_active FROM athletes ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()
print("10 VDV gan nhat:")
for r in rows:
    # Bo dau tieng Viet tam thoi de in
    name = r[1].encode('ascii', 'ignore').decode('ascii')
    print(f"ID: {r[0]}, Name: {name}, Avatar: {r[2]}, Active: {r[3]}")

# Kiem tra xem co lien ket dang ky giai dau khong
cursor.execute("SELECT athlete_id, event_id FROM competition_registrations LIMIT 5")
regs = cursor.fetchall()
print("\n5 dang ky giai chay gan nhat:")
for reg in regs:
    print(f"Athlete ID: {reg[0]}, Event ID: {reg[1]}")

conn.close()

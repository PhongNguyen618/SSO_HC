"""Group and sum rewards by SSO vs non-SSO departments on the latest backup DB."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

db_file = "SSO_HC_backup_v1.4.0_1784081151.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

event_id = 2  # The SSO50 event

# Get event info
cursor.execute("SELECT id, title, ranking_metric, ranking_sports, reward_type, reward_linear_kcal, reward_linear_amount FROM competition_events WHERE id = ?", (event_id,))
ev = cursor.fetchone()
print(f"Event: {ev[1]} (ID: {ev[0]}), Metric: {ev[2]}")

# Get hidden departments
cursor.execute("SELECT department FROM hidden_reward_configs WHERE event_id = ?", (event_id,))
hidden_depts = {r[0] for r in cursor.fetchall()}

# Get reward rules
cursor.execute("SELECT gender, kcal_threshold, reward_amount FROM reward_rules WHERE event_id = ?", (event_id,))
rules = cursor.fetchall()

def get_reward(gender, val):
    if ev[4] == "linear":
        step_kcal = ev[5] or 100.0
        step_amount = ev[6] or 5000.0
        award_amount = int(val // step_kcal) * step_amount
        return award_amount
    return 0.0

# Get active registered athletes
cursor.execute("""
    SELECT a.id, a.full_name, a.department, a.gender 
    FROM athletes a
    JOIN competition_registrations r ON a.id = r.athlete_id
    WHERE r.event_id = ? AND a.is_active = 1
""", (event_id,))
athletes = cursor.fetchall()

print(f"\nGrouping athletes who got rewards (reward > 0):")

sso_sum = 0
non_sso_sum = 0

sso_list = []
non_sso_list = []

allowed_sports = [s.strip() for s in (ev[3] or "All").split(",") if s.strip()]
is_distance = (ev[2] == "distance")

for ath_id, name, dept, gender in athletes:
    dept_name = dept or ""
    # Query activities
    cursor.execute("SELECT kcal_burned, distance_km FROM activities WHERE athlete_id = ? AND event_id = ?", (ath_id, event_id))
    acts = cursor.fetchall()
    
    total_kcal = sum(a[0] for a in acts) or 0.0
    total_dist = sum(a[1] for a in acts) or 0.0
    
    metric_value = total_dist if is_distance else total_kcal
    amt = get_reward(gender, metric_value)
    
    if amt > 0:
        is_sso = dept_name.strip().upper().startswith("SSO")
        is_hidden = dept_name in hidden_depts
        
        # Check if hidden
        status = "HIDDEN" if is_hidden else "VISIBLE"
        
        if is_sso:
            sso_sum += amt
            sso_list.append((name, dept_name, amt, status))
        else:
            non_sso_sum += amt
            non_sso_list.append((name, dept_name, amt, status))

print(f"\n--- SSO DEPARTMENTS (Sum: {sso_sum:,} VND) ---")
for name, dept, amt, status in sso_list:
    print(f"  - {name} ({dept}) [{status}]: {amt:,} VND")

print(f"\n--- NON-SSO DEPARTMENTS (Sum: {non_sso_sum:,} VND) ---")
for name, dept, amt, status in non_sso_list:
    print(f"  - {name} ({dept}) [{status}]: {amt:,} VND")

conn.close()

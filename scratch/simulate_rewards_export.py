"""Simulate export_rewards_excel logic and inspect the calculated values."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3
import pandas as pd

db_file = "SSO_HC_backup_v1.4.0_1784081151.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

event_id = 2  # The SSO50 event

# Get event info
cursor.execute("SELECT id, title, ranking_metric, ranking_sports FROM competition_events WHERE id = ?", (event_id,))
ev = cursor.fetchone()
print(f"Event: {ev[1]} (ID: {ev[0]}), Metric: {ev[2]}, Sports: {ev[3]}")

# Get hidden departments
cursor.execute("SELECT department FROM hidden_reward_configs WHERE event_id = ?", (event_id,))
hidden_depts = {r[0] for r in cursor.fetchall()}
print(f"Hidden departments: {hidden_depts}")

# Get reward rules
cursor.execute("SELECT gender, kcal_threshold, reward_amount FROM reward_rules WHERE event_id = ?", (event_id,))
rules = cursor.fetchall()
print(f"Rules:")
for r in rules:
    print(f"  - {r[0]} threshold: {r[1]} -> {r[2]} VND")

def get_reward(gender, value):
    applicable_rules = [r for r in rules if r[0] == gender]
    applicable_rules.sort(key=lambda x: x[1], reverse=True)
    for g, thresh, amt in applicable_rules:
        if value >= thresh:
            return amt
    return 0.0

# Query registered athletes
cursor.execute("""
    SELECT a.id, a.full_name, a.department, a.gender 
    FROM athletes a
    JOIN competition_registrations r ON a.id = r.athlete_id
    WHERE r.event_id = ? AND a.is_active = 1
""", (event_id,))
athletes = cursor.fetchall()
print(f"\nNumber of active registered athletes: {len(athletes)}")

# Calculate df_rewards data
data = []
for ath_id, name, dept, gender in athletes:
    # Query activities
    cursor.execute("SELECT kcal_burned, distance_km FROM activities WHERE athlete_id = ? AND event_id = ?", (ath_id, event_id))
    acts = cursor.fetchall()
    
    total_kcal = sum(a[0] for a in acts) or 0.0
    total_dist = sum(a[1] for a in acts) or 0.0
    
    metric_value = total_dist if ev[2] == "distance" else total_kcal
    amt = get_reward(gender, metric_value)
    
    data.append({
        "Mã VĐV": ath_id,
        "Họ và Tên": name,
        "Phòng ban": dept,
        "Giới tính": gender,
        "Thành tích": metric_value,
        "Số tiền thưởng (VND)": int(amt),
        "Trạng thái": "Có giải thưởng" if amt > 0 else "Chưa đạt mốc"
    })

df_rewards = pd.DataFrame(data)
sum_rewards_sheet = df_rewards["Số tiền thưởng (VND)"].sum()
print(f"\nSum of rewards in sheet: {sum_rewards_sheet:,} VND")

# Calculate total_reward_val (the overview KPI)
total_reward_val = 0.0
for ath_id, name, dept, gender in athletes:
    # Query activities
    cursor.execute("SELECT kcal_burned, distance_km FROM activities WHERE athlete_id = ? AND event_id = ?", (ath_id, event_id))
    acts = cursor.fetchall()
    
    total_kcal = sum(a[0] for a in acts) or 0.0
    total_dist = sum(a[1] for a in acts) or 0.0
    
    metric_value = total_dist if ev[2] == "distance" else total_kcal
    amt = get_reward(gender, metric_value)
    
    is_hidden = dept in hidden_depts
    # Let's count how much each athlete adds to total_reward_val
    added = 0.0 if is_hidden else amt
    total_reward_val += added

print(f"Total reward val in overview: {total_reward_val:,} VND")

# Wait! Let's check if the mismatch is because of another event_id or if there is another logic?
# Let's check how many athletes belong to hidden departments and how much reward they earned.
print("\nRewards for athletes in hidden departments:")
hidden_sum = 0
for ath_id, name, dept, gender in athletes:
    if dept in hidden_depts:
        cursor.execute("SELECT kcal_burned, distance_km FROM activities WHERE athlete_id = ? AND event_id = ?", (ath_id, event_id))
        acts = cursor.fetchall()
        total_kcal = sum(a[0] for a in acts) or 0.0
        total_dist = sum(a[1] for a in acts) or 0.0
        metric_value = total_dist if ev[2] == "distance" else total_kcal
        amt = get_reward(gender, metric_value)
        if amt > 0:
            print(f"  - {name} ({dept}): {amt:,} VND")
            hidden_sum += amt
print(f"Sum of hidden rewards: {hidden_sum:,} VND")
print(f"Sum of non-hidden rewards: {sum_rewards_sheet - hidden_sum:,} VND")

conn.close()

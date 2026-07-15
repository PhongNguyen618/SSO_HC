"""Simulate export_rewards_excel logic directly on the latest backup database file."""
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
print(f"Event: {ev[1]} (ID: {ev[0]}), Metric: {ev[2]}, Sports: {ev[3]}, Reward Type: {ev[4]}, Linear KCAL: {ev[5]}, Linear Amt: {ev[6]}")

# Get hidden departments
cursor.execute("SELECT department FROM hidden_reward_configs WHERE event_id = ?", (event_id,))
hidden_depts = {r[0] for r in cursor.fetchall()}
print(f"Hidden departments: {list(hidden_depts)}")

# Get reward rules
cursor.execute("SELECT gender, kcal_threshold, reward_amount FROM reward_rules WHERE event_id = ?", (event_id,))
rules = cursor.fetchall()

def get_award_info(gender, val):
    if ev[4] == "linear":
        step_kcal = ev[5] or 100.0
        step_amount = ev[6] or 5000.0
        award_amount = int(val // step_kcal) * step_amount
        return {"reward_amount": float(award_amount), "has_award": award_amount > 0}
        
    applicable_rules = [r for r in rules if r[0] == gender]
    applicable_rules.sort(key=lambda x: x[1], reverse=True)
    for g, thresh, amt in applicable_rules:
        if val >= thresh:
            return {"reward_amount": amt, "has_award": True}
    return {"reward_amount": 0.0, "has_award": False}

# Get registered active athletes
cursor.execute("""
    SELECT a.id, a.full_name, a.department, a.gender 
    FROM athletes a
    JOIN competition_registrations r ON a.id = r.athlete_id
    WHERE r.event_id = ? AND a.is_active = 1
""", (event_id,))
athletes = cursor.fetchall()
print(f"Number of active registered athletes: {len(athletes)}")

# Calculate
rewards_sum_all = 0
rewards_sum_non_hidden = 0
rewards_sum_hidden = 0

hidden_reward_list = []
non_hidden_reward_list = []

allowed_sports = [s.strip() for s in (ev[3] or "All").split(",") if s.strip()]
is_distance = (ev[2] == "distance")

for ath_id, name, dept, gender in athletes:
    query = "SELECT kcal_burned, distance_km FROM activities WHERE athlete_id = ? AND event_id = ?"
    params = [ath_id, event_id]
    if allowed_sports and "All" not in allowed_sports:
        placeholders = ",".join("?" for _ in allowed_sports)
        query += f" AND sport_type IN ({placeholders})"
        params.extend(allowed_sports)
    cursor.execute(query, params)
    acts = cursor.fetchall()
    
    total_kcal = sum(a[0] for a in acts) or 0.0
    total_dist = sum(a[1] for a in acts) or 0.0
    
    metric_value = total_dist if is_distance else total_kcal
    aw_info = get_award_info(gender, metric_value)
    amt = aw_info["reward_amount"]
    
    rewards_sum_all += amt
    
    is_hidden = dept in hidden_depts
    if is_hidden:
        rewards_sum_hidden += amt
        if amt > 0:
            hidden_reward_list.append((name, dept, amt, metric_value))
    else:
        rewards_sum_non_hidden += amt
        if amt > 0:
            non_hidden_reward_list.append((name, dept, amt, metric_value))

print(f"\nCalculated sum of ALL rewards (Chi tiết nhận thưởng): {rewards_sum_all:,.0f} VND")
print(f"Calculated sum of NON-HIDDEN rewards (overview cost): {rewards_sum_non_hidden:,.0f} VND")
print(f"Calculated sum of HIDDEN rewards (excluded from overview): {rewards_sum_hidden:,.0f} VND")

print(f"\nTop 10 non-hidden athletes earning rewards:")
non_hidden_reward_list.sort(key=lambda x: x[2], reverse=True)
for name, dept, amt, mv in non_hidden_reward_list[:10]:
    print(f"  - {name} ({dept}): {amt:,.0f} VND (Metric: {mv:,.1f})")

print(f"\nAll hidden athletes earning rewards:")
hidden_reward_list.sort(key=lambda x: x[2], reverse=True)
for name, dept, amt, mv in hidden_reward_list:
    print(f"  - {name} ({dept}): {amt:,.0f} VND (Metric: {mv:,.1f})")

conn.close()

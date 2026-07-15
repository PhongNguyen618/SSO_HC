"""Inspect the SSO_HC.db to find the difference between overview total reward and detailed sum."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

db_file = "SSO_HC.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get selected_event_id (the active competition or any competition in registrations)
cursor.execute("SELECT id, title, ranking_metric, ranking_sports FROM competition_events")
events = cursor.fetchall()
print(f"Competitions in DB:")
for e in events:
    print(f"- ID: {e[0]}, Title: '{e[1]}', Metric: '{e[2]}', Sports: '{e[3]}'")

# Let's inspect for each competition
for ev_id, ev_title, metric, sports in events:
    print(f"\n==========================================")
    print(f"Analyzing Competition: {ev_title} (ID: {ev_id})")
    
    # Get hidden departments
    cursor.execute("SELECT department FROM hidden_reward_configs WHERE event_id = ?", (ev_id,))
    hidden_depts = [r[0] for r in cursor.fetchall()]
    print(f"Hidden departments: {hidden_depts}")
    
    # Let's mock the award calculation just like in main.py
    # First get athletes registered for this competition
    cursor.execute("""
        SELECT a.id, a.full_name, a.department, a.gender 
        FROM athletes a 
        JOIN competition_registrations r ON a.id = r.athlete_id 
        WHERE r.event_id = ? AND a.is_active = 1
    """, (ev_id,))
    athletes = cursor.fetchall()
    print(f"Number of active registered athletes: {len(athletes)}")
    
    # Get sport restriction
    allowed_sports = [s.strip() for s in (sports or "All").split(",") if s.strip()]
    is_distance = (metric == "distance")
    
    # Get award rules
    cursor.execute("SELECT gender, kcal_threshold, reward_amount FROM reward_rules WHERE event_id = ?", (ev_id,))
    rules = cursor.fetchall()
    print(f"Reward rules (Gender, Threshold, Reward):")
    for r in rules:
        print(f"  * {r[0]}: {r[1]} -> {r[2]:,} VND")
        
    def get_reward(gender, value):
        applicable_rules = [r for r in rules if r[0] == gender]
        # Sort by threshold descending
        applicable_rules.sort(key=lambda x: x[1], reverse=True)
        for g, thresh, amt in applicable_rules:
            if value >= thresh:
                return amt
        return 0
        
    # Calculate rewards for all athletes
    total_reward_all = 0
    total_reward_non_hidden = 0
    
    hidden_details = []
    non_hidden_details = []
    
    for ath_id, name, dept, gender in athletes:
        # Get activities for this athlete and event
        # Also filter by allowed sports
        query = "SELECT kcal_burned, distance_km FROM activities WHERE athlete_id = ? AND event_id = ?"
        params = [ath_id, ev_id]
        if allowed_sports and "All" not in allowed_sports:
            placeholders = ",".join("?" for _ in allowed_sports)
            query += f" AND sport_type IN ({placeholders})"
            params.extend(allowed_sports)
            
        cursor.execute(query, params)
        acts = cursor.fetchall()
        
        total_kcal = sum(a[0] for a in acts) or 0.0
        total_dist = sum(a[1] for a in acts) or 0.0
        
        mv = total_dist if is_distance else total_kcal
        amt = get_reward(gender, mv)
        
        is_hidden = dept in hidden_depts
        
        total_reward_all += amt
        if not is_hidden:
            total_reward_non_hidden += amt
            non_hidden_details.append((name, dept, amt))
        else:
            if amt > 0:
                hidden_details.append((name, dept, amt))
                
    print(f"Sum of ALL rewards (including hidden depts): {total_reward_all:,} VND")
    print(f"Sum of NON-HIDDEN rewards (overview cost): {total_reward_non_hidden:,} VND")
    
    if hidden_details:
        print(f"\nAthletes in HIDDEN departments who earned rewards:")
        for name, dept, amt in hidden_details:
            print(f"  - {name} ({dept}): {amt:,} VND")

conn.close()

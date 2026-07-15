"""Scan all SQLite databases in the workspace to find the one matching the user's reward figures."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

# Traverse all files in workspace
db_files = []
for root, dirs, files in os.walk('.'):
    for f in files:
        if f.endswith('.db'):
            db_files.append(os.path.join(root, f))

print(f"Scanning {len(db_files)} database files...")

for db_path in db_files:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if required tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reward_rules'")
        if not cursor.fetchone():
            conn.close()
            continue
            
        # Get events
        cursor.execute("SELECT id, title, ranking_metric, ranking_sports FROM competition_events")
        events = cursor.fetchall()
        
        for ev_id, ev_title, metric, sports in events:
            # Get hidden departments
            cursor.execute("SELECT department FROM hidden_reward_configs WHERE event_id = ?", (ev_id,))
            hidden_depts = [r[0] for r in cursor.fetchall()]
            
            # Get active registered athletes
            cursor.execute("""
                SELECT a.id, a.full_name, a.department, a.gender 
                FROM athletes a 
                JOIN competition_registrations r ON a.id = r.athlete_id 
                WHERE r.event_id = ? AND a.is_active = 1
            """, (ev_id,))
            athletes = cursor.fetchall()
            
            if not athletes:
                continue
                
            # Get rules
            cursor.execute("SELECT gender, kcal_threshold, reward_amount FROM reward_rules WHERE event_id = ?", (ev_id,))
            rules = cursor.fetchall()
            
            if not rules:
                continue
                
            def get_reward(gender, value):
                applicable_rules = [r for r in rules if r[0] == gender]
                applicable_rules.sort(key=lambda x: x[1], reverse=True)
                for g, thresh, amt in applicable_rules:
                    if value >= thresh:
                        return amt
                return 0
                
            allowed_sports = [s.strip() for s in (sports or "All").split(",") if s.strip()]
            is_distance = (metric == "distance")
            
            total_all = 0
            total_non_hidden = 0
            
            for ath_id, name, dept, gender in athletes:
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
                
                total_all += amt
                if dept not in hidden_depts:
                    total_non_hidden += amt
            
            # Print if it has any rewards
            if total_all > 0:
                print(f"\n📂 Database: {db_path}")
                print(f"   Event: {ev_title} (ID: {ev_id})")
                print(f"   Sum of ALL rewards: {total_all:,.0f} VND")
                print(f"   Sum of NON-HIDDEN:  {total_non_hidden:,.0f} VND")
                print(f"   Hidden departments: {hidden_depts}")
                
        conn.close()
    except Exception as e:
        pass

"""Print table schemas of reward tables."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import sqlite3

db_file = "SSO_HC_backup_v1.4.0_1784021166.db"
conn = sqlite3.connect(db_file)
cursor = conn.cursor()

# Get columns of reward_rules
cursor.execute("PRAGMA table_info(reward_rules)")
print("reward_rules columns:")
for col in cursor.fetchall():
    print(col)

# Get columns of hidden_reward_configs
cursor.execute("PRAGMA table_info(hidden_reward_configs)")
print("\nhidden_reward_configs columns:")
for col in cursor.fetchall():
    print(col)

conn.close()

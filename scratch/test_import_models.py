import sqlite3
import os
import sys
import io
from sqlalchemy.orm import Session
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Setup system path to import from backend
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal, Athlete, Activity, CompetitionEvent, CompetitionRegistration, RewardRule
from backend.calculations import get_award_info

db = SessionLocal()

print("--- TESTING REWARD AND METRIC AGGREGATION ---")

events = db.query(CompetitionEvent).all()
for ev in events:
    print(f"\nEvent ID: {ev.id} | Title: {ev.title} | Start: {ev.start_date} | End: {ev.end_date} | Metric: {ev.ranking_metric}")
    
    # Get all registrations
    regs = db.query(CompetitionRegistration).filter(CompetitionRegistration.event_id == ev.id).all()
    print(f"Total registrations: {len(regs)}")
    
    # Get all activities for this event
    # We should exclude suspicious activities unless they are approved? 
    # Let's check how main.py queries activities for leaderboard.
    # Usually it filters: Activity.event_id == ev.id and (Activity.is_suspicious == False or Activity.is_suspicious == None)
    # Let's check main.py.
    
db.close()

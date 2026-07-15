"""Render admin.html with realistic data and save it to inspect CSS/styles in the detailed report."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jinja2 import Environment, FileSystemLoader

class MockURL:
    path = '/admin'

class MockRequest:
    url = MockURL()
    query_params = {"event_id": "1"}

env = Environment(loader=FileSystemLoader('templates'))

def currency_filter(val):
    if val is None: return "0đ"
    return f"{int(val):,}đ"
env.filters['currency'] = currency_filter

def mock_get_configs():
    return {
        "global_avatar_frame": "/static/uploads/frame.png",
        "rules_title": "Rules",
        "rules_banner_image": "/branding/BANNER.png",
        "rules_banner_text": "Welcome",
        "show_rewards_in_rules": True
    }
env.globals['get_configs'] = mock_get_configs

# Mock stats_data with sport_table defined so the detailed report renders
mock_stats_data = {
    "metric": "kcal",
    "kpis": {
        "total_athletes": 18,
        "total_activities": 100,
        "total_kcal": 50000.0,
        "total_dist": 200.0,
        "total_hours": 15.0,
        "total_reward": 500000.0
    },
    "weekly": {"labels": ["W1"], "kcal": [1000]},
    "monthly": {"labels": ["M1"], "kcal": [4000]},
    "sports": {"labels": ["Run"], "kcal": [4000], "counts": [80], "dists": [150]},
    "sport_table": [
        {"sport_type": "Run", "count": 80, "total_km": 150.0, "total_kcal": 4000}
    ],
    "run_walk_top": {
        "Nam": [{"rank": 1, "full_name": "Nam Athlete", "department": "SSO", "total_km": 50.0, "total_kcal": 2000, "act_count": 10}],
        "Nữ": [{"rank": 1, "full_name": "Nu Athlete", "department": "SSO", "total_km": 40.0, "total_kcal": 1500, "act_count": 8}]
    },
    "dept_ranking": [
        {"rank": 1, "department": "SSO", "members": 5, "active": 4, "total_km": 100.0, "total_kcal": 5000, "avg_kcal": 1000, "avg_km": 20.0}
    ],
    "participation": [
        {"department": "SSO", "registered": 5, "active": 4, "rate": 80.0}
    ],
    "reward_athletes_with": 2,
    "reward_gender": {"Nam": 300000, "Nữ": 200000},
    "reward_by_dept": [{"department": "SSO", "count": 2, "total": 500000}]
}

mock_context = {
    "request": MockRequest(),
    "configs": mock_get_configs(),
    "all_competitions": [{"id": 1, "title": "SSO's HC", "is_active": True}],
    "selected_event_id": 1,
    "selected_event": {"id": 1, "title": "SSO's HC", "ranking_metric": "kcal"},
    "stats_data": mock_stats_data,
    "logged_in": True,
    "all_athletes": [],
    "active_competitions": [],
    "unlinked_athletes": [],
    "events": [],
    "active_events": [],
    "archived_events": [],
    "mets_rules": [],
    "reward_rules": [],
    "badge_rules": []
}

template = env.get_template("admin.html")
rendered = template.render(mock_context)

# Save to scratch file for inspection
output_file = "scratch/rendered_admin_inspect.html"
with open(output_file, "w", encoding="utf-8") as f:
    f.write(rendered)

print(f"Rendered HTML saved to: {output_file}")

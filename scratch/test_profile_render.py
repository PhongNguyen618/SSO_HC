import sys
import os
sys.path.append(r"c:\Users\PC\Desktop\SSO_HC")

from jinja2 import Environment, FileSystemLoader

class MockRequest:
    class MockUrl:
        def __init__(self, path="/profile/1"):
            self.path = path
    def __init__(self, query_params, path="/profile/1"):
        self.query_params = query_params
        self.url = self.MockUrl(path)

def test_profile_rendering():
    env = Environment(loader=FileSystemLoader("templates"))
    env.filters['currency'] = lambda x: f"{x} VND"
    env.filters['string'] = str
    
    # Mock template global configs
    env.globals.update({
        "get_configs": lambda: {
            "zalo_group_qr": "/static/uploads/zalo_group_qr_1783059645.png",
            "strava_club_id": "12345"
        }
    })
    
    # Load template
    template = env.get_template("profile.html")
    
    # Mock context variables
    context = {
        "request": MockRequest({"success": "Đã liên kết tài khoản Strava thành công!"}),
        "athlete": type("Athlete", (), {"id": 1, "full_name": "Nguyen Van A", "department": "HR", "gender": "Nam", "weight": 70, "strava_name": "nva", "avatar_url": None}),
        "activities": [],
        "current_page": 1,
        "total_pages": 1,
        "total_activities_count": 0,
        "total_kcal": 0,
        "total_dist": 0.0,
        "total_time": 0.0,
        "max_streak": 0,
        "award_info": type("AwardInfo", (), {"has_award": False, "next_threshold": 100.0, "reward_amount": 0}),
        "progress_percent": 0.0,
        "chart_dates": [],
        "chart_kcal": [],
        "chart_sports": [],
        "chart_sport_dists": [],
        "badges": [],
        "is_admin": False,
        "registered_events": [],
        "unregistered_events": [],
        "selected_event": type("Event", (), {"id": 2, "title": "SSO50", "rules_group_qr": "/static/uploads/group_qr_1781930464.jpg"}),
        "selected_event_id": 2,
        "metric_value": 0.0,
        "metric_unit": "km"
    }
    
    rendered = template.render(context)
    
    # Kiểm tra xem có chứa chữ "KẾT NỐI STRAVA THÀNH CÔNG!"
    if "KẾT NỐI STRAVA THÀNH CÔNG!" in rendered:
        print("[OK] Success message is rendered correctly!")
    else:
        print("[ERROR] Success message was not found in render output!")
        
    # Kiểm tra xem có chứa Zalo QR
    if "/static/uploads/zalo_group_qr_1783059645.png" in rendered:
        print("[OK] Zalo QR image path is rendered correctly!")
    else:
        print("[ERROR] Zalo QR image path was not found in render output!")
        
    # Kiểm tra xem có chứa Club QR
    if "/static/uploads/group_qr_1781930464.jpg" in rendered:
        print("[OK] Strava Club QR image path is rendered correctly!")
    else:
        print("[ERROR] Strava Club QR image path was not found in render output!")

if __name__ == "__main__":
    test_profile_rendering()

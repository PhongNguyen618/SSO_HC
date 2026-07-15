import sys
from jinja2 import Environment, FileSystemLoader

class MockURL:
    path = '/'

class MockRequest:
    url = MockURL()
    query_params = {}

try:
    env = Environment(loader=FileSystemLoader('templates'))
    
    # Đăng ký filter currency tùy chỉnh như trong main.py
    def currency_filter(val):
        if val is None:
            return "0đ"
        try:
            return f"{int(val):,}đ"
        except Exception:
            return f"{val}đ"
    env.filters['currency'] = currency_filter
    
    # Mock hàm get_configs toàn cục
    def mock_get_configs():
        return {
            "global_avatar_frame": "/static/uploads/frame.png",
            "rules_title": "Thể lệ giải chạy",
            "rules_banner_image": "/branding/BANNER.png",
            "rules_banner_text": "Chào mừng...",
            "rules_description": "Mô tả quy chế",
            "rules_banner_text_custom": "Thể lệ chi tiết",
            "rules_general_text": "Quy định chung",
            "show_rewards_in_rules": True
        }
    
    env.globals['get_configs'] = mock_get_configs
    
    # Tạo mock data cực kỳ đầy đủ để tránh các lỗi Undefined giả lập
    mock_context = {
        "request": MockRequest(),
        "configs": mock_get_configs(),
        "all_athletes": [
            {"id": 1, "full_name": "Nguyễn Văn A", "department": "Phòng Kỹ Thuật", "avatar_url": "/static/uploads/avatars/1.png"},
            {"id": 2, "full_name": "Trần Thị B", "department": "Phòng Nhân Sự", "avatar_url": None}
        ],
        "athlete": {
            "id": 1,
            "full_name": "Nguyễn Văn A",
            "department": "Phòng Kỹ Thuật",
            "gender": "Nam",
            "weight": 70.0,
            "strava_name": "nguyenvana",
            "avatar_url": "/static/uploads/avatars/1.png"
        },
        "avatar_frame_url": "/static/uploads/frame.png?t=12345678",
        "registered_events": [
            {"id": 1, "title": "Giải Chạy Mùa Xuân 2026"}
        ],
        "unregistered_events": [],
        "selected_event_id": 1,
        "selected_event": {
            "id": 1,
            "title": "Giải Chạy Mùa Xuân 2026",
            "ranking_metric": "kcal",
            "rules_description": "Mô tả...",
            "rules_banner_text": "Thể lệ...",
            "rules_general_text": "Chung...",
            "show_rewards_in_rules": True,
            "rules_group_qr": "/static/uploads/qr.png",
            "reward_type": "milestone",
            "reward_linear_kcal": 100,
            "reward_linear_amount": 5000
        },
        "events": [
            {"id": 1, "title": "Giải Chạy Mùa Xuân 2026", "is_active": True}
        ],
        "active_events": [
            {"id": 1, "title": "Giải Chạy Mùa Xuân 2026"}
        ],
        "archived_events": [],
        "mets_rules": [],
        "reward_rules": [],
        "badge_rules": [],
        "active_tab": "tab-config",
        "error": None,
        "success": None,
        "strava_connected": False,
        "strava_login_url": "#",
        
        # Bổ sung các biến cụ thể cho từng trang
        "event": {
            "id": 1,
            "title": "Giải Chạy Mùa Xuân 2026",
            "ranking_metric": "kcal",
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "description": "Mô tả...",
            "banner_image": "/branding/BANNER.png",
            "rules_description": "Quy chế...",
            "show_rewards_in_rules": True,
            "reward_type": "milestone",
            "reward_linear_kcal": 100,
            "reward_linear_amount": 5000,
            "rules_group_qr": "/static/uploads/qr.png"
        },
        "award_info": {
            "total_reward": 150000.0,
            "reached_milestones": [],
            "next_milestone": None,
            "next_needed_kcal": 0,
            "next_threshold": 200.0
        },
        
        # Biến cho index.html
        "athletes_ranking": [
            {
                "rank": 1,
                "athlete": {
                    "id": 1,
                    "full_name": "Nguyễn Văn A",
                    "department": "Phòng Kỹ Thuật",
                    "avatar_url": "/static/uploads/avatars/1.png"
                },
                "total_kcal": 500.0,
                "total_distance": 15.5,
                "total_time_hours": 2.5,
                "avg_pace": 6.5,
                "activity_count": 5
            }
        ],
        "departments_ranking": [
            {
                "rank": 1,
                "department": "Phòng Kỹ Thuật",
                "total_kcal": 500.0,
                "total_distance": 15.5,
                "total_time_hours": 2.5,
                "athlete_count": 1,
                "avg_kcal": 500.0,
                "avg_distance": 15.5,
                "avg_time": 2.5
            }
        ],
        "latest_activities": [
            {
                "athlete_name": "Nguyễn Văn A",
                "sport_type": "Run",
                "distance_km": 5.0,
                "moving_time_min": 30.0,
                "activity_date": "2026-06-20",
                "kcal_burned": 100.0
            }
        ],
        "daily_stats": [
            {
                "activity_date": "2026-06-20",
                "distance_km": 5.0,
                "kcal_burned": 100.0
            }
        ],
        "total_active_athletes": 1,
        "total_distance_km": 15.5,
        "total_kcal_all": 500.0,
        "total_time_hours": 2.5,
        "total_kcal": 500.0,
        "total_dist": 15.5,
        "search_query": "",
        
        # Cấu hình hiển thị cột
        "col_configs": {
            "col_gender": True,
            "col_weight": True,
            "col_activities_count": True,
            "col_distance": True,
            "col_moving_time": True,
            "col_avg_pace": True,
            "col_kcal": True
        },
        
        # Biến cho profile.html
        "metric_value": 150.0,
        "chart_dates": [],
        "chart_kcal": [],
        "chart_sports": [],
        "chart_sport_dists": [],
        
        # Biến cho index.html nam/nữ/chung từng môn dạng dict
        "sport_rank_male": {
            "Walk": [],
            "Run": [],
            "Ride": []
        },
        "sport_rank_female": {
            "Walk": [],
            "Run": [],
            "Ride": []
        },
        "sport_rank_overall": [],
        
        # Biến tojson trong index.html
        "ranked_athletes": [],
        "dept_stats": []
    }

    templates_to_test = [
        "index.html",
        "rules.html",
        "register.html",
        "avatar.html",
        "profile.html",
        "event_detail.html",
        "admin.html"
    ]
    
    all_ok = True
    for template_name in templates_to_test:
        try:
            template = env.get_template(template_name)
            rendered_html = template.render(mock_context)
            print(f"SUCCESS: {template_name} rendered successfully! ({len(rendered_html)} bytes)")
        except Exception as e:
            print(f"FAILED to render {template_name}: {e}")
            all_ok = False
            
    if not all_ok:
        sys.exit(1)
except Exception as e:
    print(f"FAILED to run render check: {e}")
    sys.exit(1)

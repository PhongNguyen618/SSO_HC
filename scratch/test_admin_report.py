"""Test: Render chỉ phần analytics của admin.html (isolated snippet)."""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from jinja2 import Environment, BaseLoader

# Extract only tab-analytics section
with open("templates/admin.html", "r", encoding="utf-8") as f:
    content = f.read()

# Find the analytics tab content
start_marker = '<div id="tab-analytics" class="tab-pane">'
end_marker = '<!-- TAB: QUẢN LÝ THÀNH VIÊN -->'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1 or end_idx == -1:
    print("❌ Could not find tab-analytics section!")
    sys.exit(1)

snippet = content[start_idx:end_idx]
print(f"📋 Extracted analytics snippet: {len(snippet)} chars")

env = Environment(loader=BaseLoader())
template = env.from_string(snippet)

stats_data = {
    "metric": "kcal",
    "kpis": {
        "total_athletes": 57,
        "total_activities": 4989,
        "total_kcal": 1691175,
        "total_dist": 14996.9,
        "total_hours": 4521.7,
        "total_reward": 3300000
    },
    "weekly": {"labels": ["Tuần 1"], "kcal": [100]},
    "monthly": {"labels": ["Tháng 7/2025"], "kcal": [1000]},
    "sports": {"labels": ["Run"], "kcal": [653562], "counts": [1595], "dists": [9074.1]},
    "sport_table": [
        {"sport_type": "Run", "count": 1595, "total_km": 9074.1, "total_kcal": 653562},
        {"sport_type": "Walk", "count": 1368, "total_km": 3503.1, "total_kcal": 188250},
        {"sport_type": "Tennis", "count": 280, "total_km": 394.2, "total_kcal": 215615},
        {"sport_type": "Swim", "count": 146, "total_km": 160.2, "total_kcal": 31518},
        {"sport_type": "Yoga", "count": 85, "total_km": 0, "total_kcal": 26250},
    ],
    "run_walk_top": {
        "Nam": [
            {"rank": 1, "full_name": "Nguyễn Mạnh Tùng", "department": "BAN GIÁM ĐỐC", "total_km": 1824.0, "total_kcal": 112665, "act_count": 200},
            {"rank": 2, "full_name": "Lê Văn Thái", "department": "TỔNG HỢP", "total_km": 1628.4, "total_kcal": 122352, "act_count": 180},
            {"rank": 3, "full_name": "Cao Xuân Trường", "department": "PHƯƠNG THỨC", "total_km": 1485.3, "total_kcal": 123375, "act_count": 160},
        ],
        "Nữ": [
            {"rank": 1, "full_name": "Hoàng Thị Hà", "department": "KẾ HOẠCH", "total_km": 2739.1, "total_kcal": 190334, "act_count": 350},
            {"rank": 2, "full_name": "Uông Thị Minh Thư", "department": "TỔNG HỢP", "total_km": 337.5, "total_kcal": 43092, "act_count": 120},
        ]
    },
    "dept_ranking": [
        {"rank": 1, "department": "BAN GIÁM ĐỐC", "members": 2, "active": 2, "total_km": 2684.4, "total_kcal": 157854, "total_hours": 500, "avg_kcal": 78927, "avg_km": 1342.22},
        {"rank": 2, "department": "KẾ HOẠCH", "members": 3, "active": 3, "total_km": 3148.2, "total_kcal": 208329, "total_hours": 600, "avg_kcal": 69443, "avg_km": 1049.41},
        {"rank": 3, "department": "TỔNG HỢP", "members": 4, "active": 4, "total_km": 1987.7, "total_kcal": 170407, "total_hours": 450, "avg_kcal": 42602, "avg_km": 496.93},
    ],
    "reward_by_dept": [
        {"department": "ĐIỀU ĐỘ", "count": 17, "total": 1700000},
        {"department": "CNTT & SCADA", "count": 4, "total": 400000},
        {"department": "TỔNG HỢP", "count": 4, "total": 400000},
    ],
    "reward_athletes_with": 33,
    "reward_gender": {"Nam": 2500000, "Nữ": 800000},
    "participation": [
        {"department": "ĐIỀU ĐỘ", "registered": 18, "active": 18, "rate": 100},
        {"department": "PHƯƠNG THỨC", "registered": 13, "active": 11, "rate": 85},
        {"department": "CNTT & SCADA", "registered": 8, "active": 6, "rate": 75},
        {"department": "CSO - ĐIỀU ĐỘ", "registered": 1, "active": 0, "rate": 0},
    ]
}

try:
    html = template.render(
        stats_data=stats_data,
        selected_event_id=1,
        all_competitions=[],
    )

    checks = {
        "Section 1 - Sport Table": "Thống Kê Theo Môn Thể Thao" in html,
        "Sport icon Run": "fa-person-running" in html,
        "Sport icon Swim": "fa-person-swimming" in html,
        "Sport count format": "1,595" in html,
        "Section 2 - Run Walk Nam": "BXH Chạy" in html,
        "Medal emoji": "🥇" in html,
        "Athlete name": "Nguyễn Mạnh Tùng" in html,
        "Section 3 - Dept Ranking": "Bảng Xếp Hạng Phòng Ban" in html,
        "Dept avg kcal": "78,927" in html,
        "Section 4 - Reward": "Tiền Thưởng Theo Phòng Ban" in html,
        "Reward amount": "1,700,000" in html,
        "Reward gender Nam": "2,500,000" in html,
        "Section 5 - Participation": "Tỷ Lệ Tham Gia" in html,
        "Participation 100%": "100%" in html,
        "Participation 0%": "0%" in html,
        "Progress bar": "width: 85%" in html,
        "TỔNG CỘNG row": "TỔNG CỘNG" in html,
    }

    all_pass = True
    for name, result in checks.items():
        status = "✅" if result else "❌"
        if not result:
            all_pass = False
        print(f"  {status} {name}")

    if all_pass:
        print(f"\n🎉 TẤT CẢ {len(checks)} KIỂM TRA ĐỀU PASS!")
    else:
        failed = sum(1 for v in checks.values() if not v)
        print(f"\n⚠️ {failed} kiểm tra THẤT BẠI!")

except Exception as e:
    print(f"❌ RENDER ERROR: {e}")
    import traceback
    traceback.print_exc()

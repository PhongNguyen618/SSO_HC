# SSO_HC Sport Web App - Project Knowledge Map & Developer Guide

Ứng dụng Web quản lý và thống kê thành tích thể thao từ nhóm Strava Club, phục vụ cho giải chạy nội bộ SSO_HC. 

Ứng dụng được xây dựng theo **Giải pháp A**: Chạy hoàn toàn bằng **Python (FastAPI + Jinja2 Templates)**, không yêu cầu cài đặt Node.js/NPM, sử dụng cơ sở dữ liệu **SQLite** và giao diện tùy biến bằng **Vanilla CSS (Glassmorphism)**.

---

## 1. Bản đồ Kiến trúc & Luồng dữ liệu (Knowledge Map)

```
             ┌─────────────────────────────────────────┐
             │               Strava API                │
             └────────────────────┬────────────────────┘
                                  │ (Tải hoạt động ngầm)
                                  ▼
             ┌─────────────────────────────────────────┐
             │       Sync Engine (APScheduler)         │
             └────────────────────┬────────────────────┘
                                  │
                                  ▼ (Tính METs & KCAL)
┌──────────────┐             ┌────────┐             ┌─────────────────┐
│  Form Đăng ký│ ──────────> │ SQLite │ <────────── │   Trang Admin   │
└──────────────┘ (Lưu VĐV)   │ Database│ (Lưu Cấu   └─────────────────┘
                             └────────┘  hình & Rules)
                                  │
                                  ▼ (Truy vấn)
             ┌─────────────────────────────────────────┐
             │            FastAPI Backend              │
             └────────────────────┬────────────────────┘
                                  │
                                  ▼ (Render HTML/CSS/JS)
             ┌─────────────────────────────────────────┐
             │          Giao diện Web Trực quan        │
             └─────────────────────────────────────────┘
```

---

## 2. Cấu trúc thư mục dự án

```
SSO_HC/
├── .venv/                      # Môi trường ảo Python
├── backend/
│   ├── __init__.py
│   ├── auth.py                 # Xử lý phiên đăng nhập Admin (Session cookie)
│   ├── calculations.py         # Quy đổi KCAL, METs, Giải thưởng & Thuật toán gian lận
│   ├── database.py             # SQLite Schema & Import dữ liệu cũ từ Excel
│   ├── main.py                 # FastAPI Web Server & Background Scheduler
│   └── sync_engine.py          # Đồng bộ dữ liệu hoạt động từ Strava Club API
├── templates/                  # Giao diện HTML (Jinja2 Templates)
│   ├── base.html               # Khung sườn chung (Navbar, Footer, Search)
│   ├── index.html              # Trang chủ: Thống kê KPI & Bảng xếp hạng (Leaderboards)
│   ├── profile.html            # Trang cá nhân: Chi tiết thành tích & Biểu đồ Chart.js
│   ├── register.html           # Trang đăng ký thành viên mới
│   └── admin.html              # Bảng cấu hình quản trị (API, METs, Awards, Anti-cheat)
├── static/                     # Tệp tĩnh phục vụ giao diện
│   └── css/
│       └── style.css           # Vanilla CSS phong cách Glassmorphism
├── requirements.txt            # Danh sách thư viện Python phụ thuộc
├── SSO_HC.db                   # File Cơ sở dữ liệu SQLite (Tự động sinh khi chạy)
├── setup.bat                   # File script cài đặt môi trường ảo & DB (cho Windows)
└── run.bat                     # File script khởi chạy Web Server (cho Windows)
```

---

## 3. Bản thiết kế Cơ sở dữ liệu (SQLite Schema)

*   **Bảng `configs`:** Lưu trữ các khóa cấu hình động (Client ID, Client Secret, Club ID, tần suất đồng bộ, tài khoản admin, ngưỡng chống gian lận).
*   **Bảng `athletes`:** Danh sách nhân viên đăng ký tham gia (Họ tên, Giới tính, Phòng ban, Cân nặng, Tên Strava).
*   **Bảng `mets_rules`:** Hệ số METs động theo bộ môn và phạm vi tốc độ (km/h) dùng để tính toán năng lượng tiêu thụ.
*   **Bảng `reward_rules`:** Các mốc giải thưởng theo Giới tính và Ngưỡng KCAL đạt được.
*   **Bảng `activities`:** Lưu trữ chi tiết tất cả hoạt động đã đồng bộ (khoảng cách, pace, kcal, trạng thái hợp lệ/nghi ngờ gian lận).

---

## 4. Hướng dẫn phát triển & Vận hành

### Yêu cầu hệ thống
*   Python 3.10 trở lên.
*   Tài khoản Strava API (đăng ký tại [Strava API Settings](https://www.strava.com/settings/api)).

### Khởi chạy môi trường phát triển (Local Development)
1.  **Cài đặt:** Chạy file `setup.bat` để tự động tạo `.venv`, cài đặt thư viện và khởi tạo Database từ Excel `TDTT_SSO.xlsx` cũ.
2.  **Khởi chạy Server:** Chạy file `run.bat`. Server sẽ chạy tại địa chỉ [http://127.0.0.1:8000](http://127.0.0.1:8000).
3.  **Thay đổi mã nguồn:** Lưu file Python/HTML, server sẽ tự động reload lại thay đổi nhờ cấu hình `--reload` trong uvicorn.

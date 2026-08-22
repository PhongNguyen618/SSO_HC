# SSO_HC - Fix Report (2026-08-22)

## Phạm vi sửa

Bản này xử lý các lỗi được phát hiện trong đợt rà soát mã nguồn, tập trung vào bảo mật quyền VĐV/Admin, OAuth Strava, tính toàn vẹn điểm số, backup/restore SQLite, đồng bộ nền và CI.

## Các lỗi chính đã xử lý

- Khóa thao tác hồ sơ, avatar, đăng ký giải và unlink Strava theo phiên sở hữu VĐV hoặc Admin.
- Phiên sở hữu VĐV chỉ được cấp sau khi OAuth Strava xác minh thành công; không còn nhận activity chỉ bằng tên trước OAuth.
- OAuth Strava dùng signed state + browser nonce, có hạn dùng; ngăn liên kết nhầm/cướp Strava ID đã thuộc VĐV khác.
- OAuth Strava toàn hệ thống yêu cầu phiên Admin hợp lệ.
- Sửa unlink Strava xóa đúng các field `strava_athlete_id`, `strava_access_token`, `strava_refresh_token`, `strava_expires_at`; giữ nguyên lịch sử activity.
- Sửa `/admin/logout`: request ẩn danh không còn có thể revoke phiên Admin đang hoạt động.
- Mật khẩu Admin mới dùng PBKDF2-HMAC-SHA256 + salt; hash SHA-256 cũ vẫn đăng nhập được và tự nâng cấp sau lần đăng nhập hợp lệ.
- Bỏ fallback cố định `admin/admin`; DB mới sinh mật khẩu ngẫu nhiên nếu biến môi trường chưa được cấu hình.
- Đổi mật khẩu Admin sẽ revoke session cũ.
- Thêm rate-limit cho đăng nhập Admin, webhook, đăng ký VĐV, hỗ trợ và API remove-background.
- Activity `is_suspicious=True` không còn cộng BXH/KPI/phần thưởng/báo cáo; Admin có nút duyệt false-positive để đưa activity trở lại tính điểm.
- Sửa lỗi Admin chỉnh cự ly làm multiplier có thể dùng lại cự ly cũ.
- Backup SQLite chuyển sang SQLite Backup API để nhất quán khi DB đang hoạt động.
- Backup/audit/restore-temp được chuyển ra khỏi `/static`, lưu cạnh DB; permission thư mục/file được siết khi hệ điều hành hỗ trợ.
- Tự di chuyển backup/audit legacy từng nằm dưới `static/uploads` sang vùng private khi startup.
- Upload restore DB có giới hạn 512 MiB, đọc theo chunk, kiểm tra SQLite header và mở DB nguồn ở read-only/query-only.
- Backup lấy đúng đường dẫn từ `DATABASE_URL`, tương thích Docker `/app/data/SSO_HC.db`.
- Thêm lock chống sync chạy chồng; deduplicate hậu xử lý dùng cùng lock.
- Bỏ mốc ngày sync/restore hard-code `2026-06-16`; dùng `start_date`/`end_date` của từng giải.
- Webhook yêu cầu verify token được cấu hình; có thể khóa theo subscription ID.
- Dependencies được pin version; Docker/ignore cập nhật; CI chạy compile + regression tests trước build.
- Sửa harness của các test multiplier/linear reward để tự tạo DB tạm, không còn báo lỗi thiếu bảng giả.
- Thay các chỗ `datetime.utcnow()` ở runtime chính bằng cách lấy UTC tương thích Python mới.

## Kiểm tra đã chạy

- `python -m compileall -q .` - PASS.
- Parse Jinja: 9/9 template - PASS.
- Security regression: 14/14 - PASS.
- Event multiplier test - PASS.
- Linear reward test - PASS.
- Run/Walk ranking test - PASS.
- Advanced anti-cheat test: 4/4 - PASS.
- Import smoke `backend.main`: PASS, 81 routes.
- Endpoint smoke: Admin login, athlete owner session, unlink giữ activity, Admin approve suspicious, anonymous logout không revoke Admin - PASS.

## Lưu ý khi triển khai

1. Copy `.env.example` thành `.env` và đặt giá trị thật cho `DEFAULT_ADMIN_PASSWORD`, Strava credentials, `APP_URL`, `STRAVA_WEBHOOK_VERIFY_TOKEN`.
2. Với DB cũ, mật khẩu Admin SHA-256 sẽ được tự nâng cấp sau lần đăng nhập thành công đầu tiên.
3. VĐV cũ cần xác minh Strava một lần để trình duyệt nhận phiên sở hữu trước khi tự sửa hồ sơ/avatar/unlink.
4. Activity bị gắn cờ nghi vấn vẫn được giữ để audit nhưng không tính thành tích cho đến khi Admin duyệt.
5. Backup mới nằm trong thư mục `backups` cạnh file SQLite; audit nằm trong `audit`; Docker tương ứng dưới `/app/data`.

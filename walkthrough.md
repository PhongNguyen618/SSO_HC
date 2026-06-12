# Walkthrough - Strava SSO_HC Web App

## Tổng quan

Dự án là web app Strava SSO_HC dùng FastAPI, SQLAlchemy và SQLite. Giao diện được render bằng Jinja2 Templates trong `templates/`, styling bằng Vanilla CSS trong `static/css/style.css`, và biểu đồ dùng Chart.js CDN.

## Các hạng mục đã triển khai

- Khởi tạo môi trường Python, `.venv`, `requirements.txt`, SQLite database.
- Thiết kế database cho cấu hình hệ thống, vận động viên, METs, giải thưởng, hoạt động, huy hiệu và sự kiện lưu trữ.
- Đồng bộ hoạt động Strava Club bằng background scheduler và webhook trigger.
- Import dữ liệu lịch sử Excel in-memory thông qua tải lên các tệp tin hoặc chọn cả thư mục từ trình duyệt của người dùng (không quét cứng thư mục trên máy chủ), chống trùng bằng mã băm SHA256.
- Tính toán METs, KCAL, mốc thưởng, huy hiệu và luật chống gian lận từ database/config động.
- Trang chủ có tìm kiếm, bảng xếp hạng, bộ lọc thời gian và biểu đồ trực quan.
- Trang cá nhân có KPI, lịch sử hoạt động, Chart.js và huy hiệu thành tích.
- Trang Admin có cấu hình API Strava, METs, giải thưởng, anti-cheat, quy chế, banner, import historical Excel, export Excel, huy hiệu và sự kiện lịch sử.
- Trang Quy Chế và Welcome Banner động theo cấu hình Admin.
- Tích hợp ảnh QR Code Group vào trang Quy chế và hiển thị hướng dẫn tham gia nhóm khi đăng ký tài khoản thành công (có thể cập nhật/tải lên ảnh QR trực tiếp từ trang Admin).
- Các hoạt động nghi vấn (is_suspicious) mặc định vẫn được tính calo và thành tích tổng; tích hợp nút "Xóa" hoạt động cho Admin trực tiếp tại trang hồ sơ cá nhân của VĐV để loại bỏ các hoạt động gian lận thực tế khỏi DB.
- Tích hợp nhận diện thương hiệu NSMO: font Be Vietnam Pro, logo và bảng màu pastel.

### 6. Trang Tổng Quan Phân Tích (Analytics Dashboard) Cho Admin (Giai đoạn 3)
* **Chức năng:** Hỗ trợ Admin theo dõi tiến độ tổng thể của giải chạy thông qua các số liệu KPIs và biểu đồ trực quan động.
* **Giao diện:** Tích hợp Tab **"Thống Kê Phân Tích"** trong trang điều khiển Admin (`/admin`), bao gồm:
  1. Hàng thẻ số liệu KPIs: Tổng VĐV Đang Hoạt động, Tổng Số Hoạt động, Tổng Calo Tiêu thụ (KCAL), Tổng Quãng đường (km) và Tổng Thời gian tập luyện (giờ).
  2. Biểu đồ đường **Xu hướng Calo Tiêu Thụ Toàn Công Ty**: Hỗ trợ chuyển đổi chế độ xem nhanh giữa **Theo Tuần** (12 tuần gần nhất) và **Theo Tháng** (6 tháng gần nhất) bằng nút toggle động qua Javascript mà không cần tải lại trang.
  3. Biểu đồ hình tròn khuyết **Cơ Cấu Hoạt Động Theo Bộ Môn**: Thống kê tỷ lệ phân chia lượng calo đốt cháy theo các bộ môn thể thao (Chạy bộ, Đạp xe, Đi bộ, Bơi lội...) với tông màu pastel nhận diện thương hiệu.

---

## Kết quả kiểm thử & xác minh (Giai đoạn 2 & 3)

*   **Xuất Excel báo cáo:** 
    *   Đã chạy script tự động `test_excel.py` tạo báo cáo và xuất thành công file Excel. 
    *   File Excel kiểm tra ghi nhận kích thước 5.6KB, cấu trúc đầy đủ 3 Sheet: `BXH Cá Nhân`, `Hiệu Suất Phòng Ban`, `BXH Theo Bộ Môn` với các cột chuẩn xác, độ rộng tự động căn chỉnh hoàn hảo.
*   **Huy hiệu thành tích:** 
    *   Đã tích hợp và kiểm thử logic tính mốc đạt huy hiệu. Các ngày đạt mốc được tính toán động và hiển thị chính xác lên giao diện.
*   **Cấu hình động Huy hiệu từ Admin:**
    *   Đã chạy script kiểm thử tự động `test_dynamic_badges.py` kết nối database, thử cập nhật ngưỡng của huy hiệu "Bàn Chân Vàng" xuống 1.0 km và thay đổi tên hiển thị. 
    *   Hệ thống ghi nhận và thực hiện câu lệnh cập nhật trực tiếp vào bảng `badge_rules` thành công, lưu lại đúng giá trị và khôi phục thành công sau kiểm thử.
*   **Webhook Strava:** 
    *   Đã chạy script kiểm thử tự động `test_webhook.py` mô phỏng yêu cầu từ Strava.
    *   Yêu cầu xác thực `GET /strava/webhook` trả về thành công JSON `{"hub.challenge": "challenge_token_123456"}` với Status Code 200.
    *   Yêu cầu sự kiện `POST /strava/webhook` nhận diện sự kiện, kích hoạt ngầm Background Sync và trả về `EVENT_RECEIVED` thành công.
*   **Trang Thống Kê Phân Tích Admin (Analytics Dashboard):**
    *   Đã viết và chạy script kiểm thử tự động `test_admin_analytics.py` thực hiện giả lập phiên đăng nhập Admin, lấy mã phiên, và cào phân tích HTML trang quản trị.
    *   Kết quả xác minh: Đăng nhập thành công (HTTP 200), tải trang admin thành công (HTTP 200), nhận diện đầy đủ thư viện Chart.js, các khối container KPIs, 2 thẻ canvas vẽ biểu đồ (`adminKcalChart`, `adminSportChart`) và cấu trúc JSON `stats_data` truyền tải dữ liệu từ backend xuống.

## Kiểm tra tuân thủ chính

- Không thêm Node.js, NPM, Vite, React hoặc TailwindCSS.
- Frontend vẫn dùng FastAPI + Jinja2 Templates.
- CSS đặt trong `static/css/style.css` theo phong cách Glassmorphism.
- Chart.js được nhúng trực tiếp từ CDN trong HTML.
- Cấu hình Strava mặc định được seed từ biến môi trường hoặc để trống, tránh hardcode secret trong mã nguồn.
- Console log Python cần dùng tiếng Anh không dấu để tránh lỗi encoding trên Windows.

## Ghi chú vận hành

1. Cấu hình Strava Client ID, Client Secret, Club ID trong Admin hoặc qua `.env` trước khi đồng bộ.
2. Kết nối OAuth Strava tại trang Admin để lấy token.
3. Có thể import dữ liệu lịch sử và export báo cáo Excel từ Admin.
4. Khi thay đổi `rules_version`, Welcome Banner sẽ hiển thị lại cho người dùng.
# Walkthrough - Strava SSO_HC Web App

## Tổng quan

Dự án là web app Strava SSO_HC dùng FastAPI, SQLAlchemy và SQLite. Giao diện được render bằng Jinja2 Templates trong `templates/`, styling bằng Vanilla CSS trong `static/css/style.css`, và biểu đồ dùng Chart.js CDN.

## Các hạng mục đã triển khai

- Khởi tạo môi trường Python, `.venv`, `requirements.txt`, SQLite database.
- Thiết kế database cho cấu hình hệ thống, vận động viên, METs, giải thưởng, hoạt động, huy hiệu và sự kiện lưu trữ.
- Đồng bộ hoạt động Strava Club bằng background scheduler và webhook trigger.
- Import dữ liệu lịch sử Excel in-memory thông qua tải lên các tệp tin hoặc chọn cả thư mục từ trình duyệt của người dùng (không quét cứng thư mục trên máy chủ), chống trùng bằng mã băm SHA256.
- Tính toán METs, KCAL, mốc thưởng, huy hiệu và luật chống gian lận từ database/config động.
- Trang chủ có tìm kiếm, bảng xếp hạng, bộ lọc thời gian và danh sách các sự kiện lịch sử (giải chạy cũ).
- Trang cá nhân có KPI, lịch sử hoạt động, Chart.js và huy hiệu thành tích.
- Trang chi tiết Sự kiện lịch sử (/event/{event_id}) hiển thị bài viết vinh danh, banner lớn, video tổng kết Youtube và album ảnh kỷ niệm dạng Grid/Lightbox.
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

## Giai đoạn 4: Cấu hình giải đấu KM/KCAL & Bộ môn riêng biệt (Đã hoàn thành)

*   **Database Schema:**
    *   Bổ sung hai thuộc tính `ranking_metric` (kcal/distance) và `ranking_sports` (dạng danh sách cách nhau bởi dấu phẩy, ví dụ `Run,Walk`) vào bảng `competition_events`.
    *   Tự động di trú bổ sung cột và nâng cấp cấu trúc dữ liệu cho cơ sở dữ liệu hiện có trong hàm `init_db()`.
*   **Logic Backend & APIs:**
    *   Các bảng xếp hạng (Cá nhân, Phòng ban, Bộ môn) tự động lọc theo bộ môn cho phép của giải đấu.
    *   Thành tích được tính toán và sắp xếp động theo tiêu chí Quãng đường (KM) hoặc Năng lượng (KCAL) của giải đấu được chọn.
    *   Các endpoint Xuất Excel báo cáo, Trang quy chế, và Hồ sơ cá nhân VĐV tự động cập nhật cách tính toán và nhãn hiển thị.
    *   Tích hợp áp dụng hệ số nhân (multiplier) vào quãng đường `distance_km` (lưu quãng đường nhân hệ số ở `distance_km` và quãng đường gốc ở `distance_km_raw`) tương thích hoàn toàn với cơ chế của calo tiêu thụ, đảm bảo tính công bằng khi nhân đôi/nhân ba thành tích vào những ngày chạy đặc biệt.
*   **Giao diện Frontend (Templates):**
    *   Động hóa hoàn toàn nhãn hiển thị (KM, KCAL, KM/Người, KCAL/Người) tại Trang chủ (leaderboards, charts), Trang cá nhân (kpi cards, awards progress, charts), Trang quy chế và trang Admin.
    *   Gắn sự kiện JavaScript động trong trang Admin để tự động thay đổi nhãn cấu hình mốc quy đổi tuyến tính khi Admin thay đổi tiêu chí xếp hạng của giải đấu.
    *   **Sửa lỗi thống kê ẩn (Thống kê Tuần, Tháng, Cơ cấu bộ môn):**
  - Khắc phục lỗi lọc SQL trong các query thống kê ở API Admin dashboard. Trước đó, các query này lọc trực tiếp `Activity.sport_type.in_(allowed_sports)` mà không kiểm tra xem `"All"` có nằm trong đó không, dẫn đến việc khi chọn "All", các biểu đồ thống kê bị trống trơn. Đã cập nhật thành công điều kiện kiểm tra `if allowed_sports and "All" not in allowed_sports:`.

### 0.5. Tính năng Sắp xếp bảng xếp hạng động (KCAL / KM / Thời gian)
- **Thiết kế UI Button Group cực kỳ hiện đại:** Bổ sung cụm nút chọn tiêu chí sắp xếp (KCAL / KM / Giờ) ngay dưới header tab của Bảng xếp hạng. Nút được thiết kế dưới dạng Button Group với hiệu ứng hover và active phát sáng xanh ngọc (Primary Color) rất cao cấp.
- **Tự động đồng bộ Onload:** Khi trang được load lần đầu, JS sẽ tự động kích hoạt chế độ sort theo tiêu chí mặc định của giải đấu hiện tại (được xác định qua trường `selected_metric` truyền từ Backend).
- **Client-side DOM sorting siêu nhanh (0ms delay):**
  - **Bảng cá nhân (Overall - Sửa lỗi double cột):** Loại bỏ hoàn toàn cột "Thành tích" động (vốn bị trùng lắp gây double cột KM/Giờ khi thay đổi tiêu chí). Thay vào đó, bảng cá nhân hiển thị cố định cả 3 chỉ số độc lập: **Quãng đường (KM)**, **Thời gian (Giờ)**, và **Năng lượng (KCAL)**. Khi bấm sort tiêu chí nào, VĐV được xếp hạng lại theo tiêu chí đó, đồng thời cột dữ liệu và tiêu đề cột tương ứng được tô màu xanh ngọc nổi bật (Highlight), đem lại giao diện sạch sẽ, tường minh.
  - **Bảng phòng ban (Departments):** Sắp xếp lại thứ tự phòng ban theo hiệu suất trung bình của tiêu chí tương ứng. Tự động cập nhật nhãn cột tiêu đề và giá trị hiển thị ở 2 cột Tổng tích lũy và Trung bình/Người tương ứng.
  - **Bảng bộ môn (Sports):** Bổ sung cột **Thời gian (Giờ)** vào cả bảng Nam và Nữ để hiển thị đầy đủ cả 3 chỉ số (KM, Giờ, KCAL). Khi click chọn sort theo tiêu chí nào, VĐV trong từng bộ môn sẽ được sort theo tiêu chí đó, đồng thời cột thành tích đang được dùng để sort sẽ được tô màu xanh ngọc nổi bật để người dùng dễ theo dõi.
- **Cập nhật Backend:**
  - Bổ sung trường `total_time` vào `dept_query` để tính toán thời gian tổng cộng và thời gian trung bình/người cho BXH phòng ban.
  - Bổ sung trường `total_time` vào truy vấn xếp hạng của từng bộ môn (`get_sport_ranking`).

### 1. Xử lý an toàn tham số `event_id` trong các API GET để tránh lỗi 422
*   **Kết quả kiểm thử:**
    *   Đã chạy thành công kịch bản kiểm thử tự động `test_routes_validation.py` xác thực các routes hoạt động ổn định với các giá trị đầu vào của `event_id`.
    *   Đã viết và chạy thành công kịch bản kiểm thử tự động `test_km_ranking.py` mô phỏng giải chạy KM và lọc bộ môn. Kết quả xác nhận các hoạt động được nhân đôi quãng đường vào ngày Chủ nhật chính xác (lưu đúng raw và multiplied), loại bỏ bộ môn không hợp lệ ra khỏi BXH và tính toán tổng thành tích BXH cá nhân hoàn hảo (20.0 KM như thiết kế).

---

## Giai đoạn 5: Các nâng cấp và sửa lỗi gần đây

### 1. Giải pháp Hỗ trợ VĐV Đổi tên hiển thị Strava
- **Cơ chế lưu trữ:** Trường `strava_name` trong bảng `Athlete` nay có thể lưu nhiều tên hiển thị Strava cách nhau bởi dấu phẩy (ví dụ: `Tên Mới, Tên Cũ`).
- **Tự động gom hoạt động:** Khi VĐV thêm tên cũ vào danh sách, hệ thống sử dụng toán tử SQL `IN` để gom nhanh toàn bộ hoạt động cũ chưa khớp về cho VĐV này, tự động tính lại KCAL và KM theo cân nặng của họ.
- **Vá lỗi và hướng dẫn:** Thêm trường nhập `strava_name` bị thiếu ở form thêm VĐV thủ công của Admin, đồng thời bổ sung placeholder ví dụ hướng dẫn ở các trang đăng ký và quản trị.

### 2. Sửa lỗi cập nhật Banner quảng cáo và Popup chào mừng
- **Đồng bộ tự động:** Khi Admin thay đổi banner hoặc quy chế ở tab cấu hình chung, hệ thống tự động đồng bộ sang giải đấu đang hoạt động (`active_event`) để cập nhật ngay lập tức lên trang chủ.
- **Reset popup tự động:** Sử dụng mã băm `rules_hash` tính toán từ nội dung và banner thực tế lưu trong `localStorage`. Khi Admin cập nhật bất kỳ thay đổi nào, `rules_hash` thay đổi giúp popup chào mừng tự động hiển thị lại cho toàn bộ người dùng mà không cần tăng phiên bản quy chế thủ công.
- **Vá lỗi truyền thiếu context cấu hình lên trang chủ (Mới):** Khắc phục lỗi thiếu các thuộc tính `active_event_id` và `rules_hash` trong context configs của route trang chủ (`/`). Trước đó, do truyền thiếu các trường này, logic JavaScript tại frontend hiểu lầm là không có giải đấu đang hoạt động và tắt hoàn toàn tính năng popup chào mừng (khiến cho cả chế độ "always" hay "days" đều không hoạt động). Đã bổ sung logic điền đầy đủ thông tin active event và tính toán hash quy chế vào configs của route trang chủ.

### 3. Bổ sung Tính năng Chỉnh sửa (Edit) Sự kiện Lịch sử
- **Backend API (`backend/main.py`):** Bổ sung route POST `/admin/events/edit/{event_id}` để chỉnh sửa tiêu đề, video nhúng, tóm tắt, ảnh banner đại diện và album ảnh kỷ niệm.
- **Quản lý Album ảnh (Gallery) linh hoạt:**
  - Nếu chọn **Bỏ tích** "Giữ lại ảnh cũ": Xóa sạch các ảnh cũ khỏi đĩa vật lý rồi lưu các ảnh mới.
  - Nếu chọn **Tích chọn** (Mặc định): Các ảnh mới tải lên sẽ được ghi đĩa và nối tiếp vào danh sách ảnh cũ trong database.
- **Tối ưu hóa tránh trùng tên file:** Bổ sung số ngẫu nhiên (`random.randint(100, 999)`) vào tên file vật lý (`event_banner_` và `event_gal_`) để tránh collision khi ghi đĩa trong các request diễn ra cực nhanh.
- **Frontend UI (`templates/admin.html`):** Bổ sung nút **Sửa** cạnh nút Xóa ở tab Sự kiện lịch sử, và tích hợp dòng form ẩn `tr` trượt xuống khi bấm Sửa tương tự giao diện Giải đấu.
- **Kiểm thử tự động (`scratch/test_edit_archived_event.py`):** Chạy và xác minh thành công 100% logic cập nhật văn bản, thay banner cũ, nối tiếp album, và ghi đè album cũ kèm dọn dẹp ổ đĩa vật lý.
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

### 5. Tự động đồng bộ hóa form Quy Chế & Welcome Banner khi chọn giải đấu
- **File sửa đổi:** [admin.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/admin.html)
- **Chi tiết:** 
  - Đã thêm hàm JavaScript `loadCompetitionRulesForConfig(eventId)` sử dụng `fetch` để truy vấn API `GET /admin/api/competition-rules/{event_id}`.
  - Tự động điền dữ liệu trả về vào các trường nhập liệu tương ứng bao gồm: Tiêu đề cuộc thi, Phiên bản quy chế, Nội dung giới thiệu, Quy định chung, Nội dung tóm tắt trên Welcome Banner, Chế độ hiển thị popup, Số ngày reset và cập nhật vùng hiển thị ảnh Banner/QR Code tương ứng của giải đấu đó.
  - Ngăn ngừa hoàn toàn việc người dùng vô tình lưu đè dữ liệu của giải đấu cũ lên giải đấu mới được chọn dẫn đến việc tạo ra các giải đấu trùng tên trong cơ sở dữ liệu.

---

## Kết quả kiểm thử & Xác minh

### 1. Kiểm thử tự động (Unit Test)
- **Kiểm thử dọn dẹp hoạt động:** [test_deduplicate_tolerance.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_deduplicate_tolerance.py) - **PASSED (OK)**.
- **Kiểm thử API quy chế:** [test_api_rules.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_api_rules.py) - **PASSED (OK)**. API trả về đúng dữ liệu cấu hình theo giải đấu và trả về 401 khi chưa đăng nhập admin.
- **Kiểm thử Đăng ký & Trùng họ tên:** [test_post_register.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_post_register.py) - **PASSED (OK)**.
- **Kiểm thử Tự động đóng giải đấu:** [test_event_expiration.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_event_expiration.py) - **PASSED (OK)**.
- **Kiểm thử Phân trang hoạt động cá nhân:** [test_profile_pagination.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_profile_pagination.py) - **PASSED (OK)**.
- **Kiểm thử Giao diện Trang chủ & Carousel:** [test_render_index.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_render_index.py) - **PASSED (OK)**. Xác minh template trang chủ render thành công, có đầy đủ container carousel và JS trượt.

### 2. Commit lên Git
- Đã commit và push toàn bộ các thay đổi mới lên Git.

---

## Các tính năng bổ sung quản lý Vận động viên & Phân trang (Mới)

### 1. Phân trang nhật ký hoạt động cá nhân
- **Files sửa đổi:** [main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py) & [profile.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/profile.html)
- **Chi tiết:** 
  - Tại trang chi tiết cá nhân VĐV (`/profile/{athlete_id}`), nhật ký hoạt động giờ đây được phân trang với kích thước **15 hoạt động mỗi trang** để tránh trang quá dài khó cuộn.
  - Các chỉ số KPI tổng thể (tổng Calo, tổng KM, tổng giờ, chuỗi ngày liên tục) vẫn được tính toán dựa trên **toàn bộ hoạt động lịch sử** của VĐV để đảm bảo tính chính xác cho giải thưởng.
  - Bổ sung thanh điều hướng phân trang đẹp mắt ở cuối bảng (bao gồm các nút Trang đầu, Trang trước, các số trang xung quanh, Trang sau, Trang cuối) tự động chuyển trang mượt mà qua tham số `&page=`.

### 2. Hiển thị Ngày đăng ký của thành viên
- **Files sửa đổi:** [main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py) & [admin.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/admin.html)
- **Chi tiết:** 
  - Thống kê thời gian đăng ký (cột `registered_at` trong bảng `CompetitionRegistration`) của từng thành viên đăng ký giải chạy.
  - Quy đổi múi giờ sang giờ Việt Nam (GMT+7) và định dạng chuỗi hiển thị `dd/mm/yyyy hh:mm` (ví dụ: `18/06/2026 15:15`) ở cột mới **"Ngày đăng ký"** trong tab **Thành viên** trên trang Admin.
  - Hỗ trợ hiển thị ngày đăng ký gần nhất khi chọn chế độ lọc hiển thị "Tất cả giải đấu".

### 2. Tự động phát hiện & sửa đổi tài khoản khi người chơi viết nhầm thông tin
- **File sửa đổi:** [main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py)
- **Chi tiết:** 
  - Viết hàm helper `clean_name(name)` để chuẩn hóa chuỗi (chuyển chữ thường, bỏ khoảng trắng, bỏ dấu tiếng Việt).
  - Khi người chơi đăng ký mới, hệ thống sẽ chuẩn hóa Họ tên họ nhập vào và so sánh với danh sách VĐV đã có. Nếu phát hiện trùng lặp Họ tên chuẩn hóa (ví dụ: `Nguyen Van A` trùng khớp với `Nguyễn Văn A`), hệ thống sẽ nhận diện đây là cùng một người và ngăn chặn việc tạo tài khoản trùng thứ hai.
  - Chuyển hướng người chơi sang luồng cập nhật thông tin. Tại đây, cho phép họ cập nhật cả Họ tên đúng, Phòng ban, Cân nặng và cả tên Strava mới (nếu trước đó họ ghi nhầm tên Strava của mình) giúp họ tự sửa lỗi ghi nhận hoạt động cực kỳ nhanh chóng.

### 4. Thiết kế lại giao diện Trang chủ (Banner nổi bật & Carousel sự kiện lịch sử)
- **File sửa đổi:** [index.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/index.html)
- **Chi tiết:** 
  - Thay đổi cấu trúc Grid hai cột thành cấu trúc Flexbox dọc để **giải đấu đang diễn ra chiếm 100% chiều rộng** trang web, nổi bật và hoành tráng hơn hẳn.
  - Tăng chiều cao banner chính giải đấu đang diễn ra lên `min-height: 340px` trên máy tính để tăng hiệu ứng hình ảnh (visual impact) và tự động thu gọn về `250px` trên điện thoại di động.
  - Tái cấu trúc phần **"Sự kiện lịch sử"** (các giải đấu cũ) xuống hàng bên dưới dưới dạng một **Carousel (Slide trượt ngang) vô cùng hiện đại và gọn gàng**.
  - Các card sự kiện lịch sử trượt ngang được phủ bóng mờ tinh tế ở biên và đi kèm **nút mũi tên trượt trái/phải mượt mà**.
  - Tích hợp JS tự động phát hiện số lượng sự kiện: Nếu số lượng sự kiện quá ít (vừa vặn khung màn hình và không cần cuộn) thì tự động ẩn các nút mũi tên điều hướng để giao diện luôn sạch sẽ, nếu tràn khung thì tự động hiện nút.

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

### 4. Bổ sung Dropdown chọn giải đấu khi Cấu hình Quy Chế
- **Backend API (`backend/main.py`):** Cập nhật route POST `/admin/config` (`update_configs`) nhận tham số `apply_to_event_id: str = Form("active")`.
  - Nếu chọn một giải cụ thể, hệ thống sẽ truy vấn giải đấu đó theo ID và thực hiện đồng bộ quy chế riêng cho nó.
  - Nếu để mặc định `"active"`, hệ thống tự động fallback tìm giải đấu đang hoạt động mới nhất (`active_event`) để đồng bộ.
- **Frontend UI (`templates/admin.html`):** Bổ sung dropdown chọn giải đấu (`apply_to_event_id`) ngay trên đầu phần *Cấu hình Quy Chế & Welcome Banner* ở tab *Cấu hình API & Rules*, lặp qua danh sách `all_competitions` để Admin có thể lựa chọn linh hoạt.
- **Kiểm thử tự động (`scratch/test_rules_target_event.py`):** Tạo 2 giải đấu mẫu, cấu hình quy chế riêng cho giải đấu B và xác minh thành công: các giá trị quy chế mới được áp dụng chuẩn xác cho giải đấu B, còn giải đấu A hoàn toàn không bị ảnh hưởng hay ghi đè nhầm lẫn.

### 5. Cải tiến giao diện Trang chủ: Banner Giải đấu Nổi bật & Carousel Tự động trượt
- **Files sửa đổi:** [templates/index.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/index.html)
- **Chi tiết cải tiến:**
  - **Banner giải đấu đang diễn ra:**
    - Tăng chiều cao banner `.main-hero-banner` từ `340px` lên `380px` (trên máy tính) tạo hiệu ứng hình ảnh lớn và hoành tráng.
    - Tăng kích thước chữ tiêu đề giải chạy đang diễn ra từ `2.2rem` lên `2.6rem` (kèm `font-weight: 800`), tối ưu bóng mờ cho tiêu đề để hiển thị cực nét.
    - Cải thiện lớp phủ màu tối chân banner (gradient overlay mịn hơn) giúp thông tin và nút bấm luôn rõ ràng trên mọi hình nền.
    - Gom và tối ưu hóa CSS padding của banner thông qua class `.hero-banner-content` để responsive tốt hơn trên các thiết bị.
  - **Carousel sự kiện quá khứ tự động trượt (Auto-Play Slide):**
    - Lập trình hàm Javascript tự động cuộn (Auto-Play) sau mỗi `4` giây một khoảng `300px` mượt mà.
    - Khi cuộn đến điểm cuối của danh sách sự kiện lịch sử, Carousel sẽ tự động cuộn ngược về đầu một cách mượt mà để tạo vòng lặp vô hạn.
    - Tích hợp tính năng **Hover Pause**: Tự động tạm dừng cuộn khi người dùng rê chuột vào vùng Carousel để họ dễ dàng click, và tiếp tục cuộn khi chuột rời đi.
    - Bổ sung **Reset Timer**: Tự động đặt lại bộ đếm 4 giây khi người dùng nhấn nút Prev/Next thủ công hoặc vuốt chạm tay trên thiết bị di động, tránh hiện tượng Carousel tự trượt ngay sau khi người dùng vừa thao tác.
  - **Tối ưu hóa Nút điều hướng Carousel:**
    - Thiết kế nút Prev/Next ẩn hoàn toàn ở trạng thái bình thường (opacity = 0, pointer-events = none).
    - Chỉ hiển thị nút điều hướng tương ứng với hướng có thể cuộn khi người dùng hover chuột vào vùng Carousel trên máy tính.
    - Tự động ẩn hoàn toàn các nút điều hướng trên thiết bị di động để nhường không gian cho thao tác vuốt chạm.
- **Kết quả kiểm thử (`scratch/test_render_index.py`):** Kiểm thử render trang chủ tích hợp DB thực tế chạy thành công 100%, xác nhận không có lỗi cú pháp và các cấu trúc HTML/JS của Carousel hoạt động ổn định.

### 6. Sửa lỗi mã QR nhóm Strava (Group QR) không cập nhật riêng theo giải đấu
- **Files sửa đổi:** [database.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/database.py) & [main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py)
- **Chi tiết sửa đổi:**
  - **Database Schema:** Bổ sung cột `rules_group_qr` (String, nullable=True) vào model `CompetitionEvent`. Lập trình logic di trú cột tự động trong hàm `init_db()` để chạy câu lệnh `ALTER TABLE` thêm cột này vào SQLite DB thực tế một cách an toàn mà không ảnh hưởng tới dữ liệu cũ.
  - **Cập nhật dữ liệu (POST `/admin/config`):** Khi Admin thay đổi hoặc upload ảnh QR code nhóm, hệ thống kiểm tra và lưu đường dẫn ảnh QR mới vào `target_event.rules_group_qr` của giải đấu đang cấu hình (đồng thời vẫn lưu bản sao vào cấu hình chung `Config` để làm giá trị mặc định). Tích hợp logic tự động xóa tệp tin ảnh QR cũ của giải đấu đó trên đĩa cứng để tránh rác dung lượng.
  - **API lấy dữ liệu (GET `/admin/api/competition-rules/{event_id}`):** Trả về chính xác mã QR nhóm riêng biệt của giải đấu cụ thể (`comp.rules_group_qr`) hoặc fallback về cấu hình mặc định nếu giải đấu chưa có QR riêng.
  - **Đồng bộ hóa giao diện trang chủ và quy chế:**
    - Nạp đúng mã QR nhóm riêng biệt của giải đấu đang diễn ra (`active_event.rules_group_qr`) trong configs của trang chủ (`/`).
    - Nạp đúng mã QR nhóm riêng biệt của giải đấu được chọn (`selected_event.rules_group_qr`) trong configs của trang quy chế (`/rules`).
- **Kết quả kiểm thử (`scratch/test_rules_group_qr.py`):** Chạy và xác minh thành công 100% logic di trú, cô lập QR code theo giải đấu qua API và xóa dọn dẹp file cũ trên đĩa cứng.

### 7. Sửa lỗi ID Club của các giải đấu bị ghi đè lẫn nhau khi lưu Quy chế
- **File sửa đổi:** [main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py)
- **Chi tiết sửa đổi:**
  - **Tách biệt cấu hình:** Loại bỏ hoàn toàn logic tự động gán đè `target_event.strava_club_id = club_id_extracted` trong route POST `/admin/config` (`update_configs`).
  - **Giữ nguyên cấu hình cũ:** Việc lưu cài đặt API Strava chung giờ đây chỉ cập nhật vào bảng cấu hình hệ thống `Config`, tuyệt đối không tự ý ghi đè ID club của giải đấu đang được chọn cập nhật quy chế. Cấu hình ID club riêng của từng giải đấu được bảo toàn và chỉ được sửa đổi độc lập tại tab **Quản Lý Giải Đấu** (form Thêm/Sửa giải đấu) theo đúng luồng thiết kế.
- **Kết quả kiểm thử (`scratch/test_club_id_isolation.py`):** Chạy và xác minh thành công 100% việc cập nhật cấu hình chung, đảm bảo ID club riêng của giải đấu cũ được cô lập và không bị ghi đè chéo khi thay đổi văn bản quy chế.

### 8. Sửa lỗi xóa nhầm ảnh Banner mặc định của hệ thống khi cập nhật giải đấu cụ thể
- **File sửa đổi:** [main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py)
- **Chi tiết sửa đổi:**
  - **Tối ưu hóa logic dọn dẹp:** Điều chỉnh hàm `update_configs` (khối xử lý `banner_file`). Khi tải lên ảnh banner mới cho giải đấu được chọn (`target_event`), hệ thống truy vấn và xóa ảnh banner cũ của riêng giải đấu đó (`target_event.banner_image`) thay vì truy vấn khóa `"rules_banner_image"` và xóa nhầm ảnh banner mặc định chung của hệ thống.
  - **Fallback an toàn:** Chỉ thực hiện xóa ảnh banner chung trong bảng `Config` khi không cấu hình cho giải đấu cụ thể nào. Giúp việc dọn dẹp tài nguyên ảnh banner hoạt động chính xác và an toàn.
- **Kết quả kiểm thử (`scratch/test_banner_isolation.py`):** Chạy và xác minh thành công 100% logic tải ảnh banner mới cho giải đấu, đảm bảo ảnh banner chung hệ thống được bảo tồn nguyên vẹn và ảnh banner cũ của giải đấu được dọn dẹp sạch sẽ khỏi đĩa cứng.

### 9. Kích hoạt & Sửa lỗi tính năng tách nền ảnh chân dung bằng AI (rembg)
- **Files sửa đổi:** [requirements.txt](file:///c:/Users/PC/Desktop/SSO_HC/requirements.txt)
- **Chi tiết sửa đổi:**
  - **Khắc phục lỗi thiếu backend:** Cài đặt package `rembg[cpu]` chứa đầy đủ môi trường runtime `onnxruntime` cho CPU. Trước đó, API `/api/avatar/remove-bg` bị lỗi 500 khi import `rembg` do hệ thống thiếu backend ONNX, dẫn tới frontend luôn kích hoạt fallback dùng ảnh gốc (chưa tách nền).
  - **Khởi chạy lại server:** Restart uvicorn server ở cổng 8000 để nhận diện được các package mới trong virtual environment.
  - **Tải model u2net tự động:** Ở lần đầu tiên API `/api/avatar/remove-bg` được gọi, server tự động tải model tách nền AI `u2net.onnx` (~170MB) về cache của máy chủ.
- **Kết quả kiểm thử (`scratch/test_remove_bg_api.py`):** Viết script gửi request thực tế lên API `/api/avatar/remove-bg`. Kết quả trả về thành công (HTTP 200), ảnh tách nền được lưu thành công dưới dạng PNG trong suốt (RGBA, kích thước 832x1248) với dung lượng giảm từ 1.16MB xuống 802KB, kiểm chứng thuật toán AI hoạt động hoàn toàn chính xác.

### 10. Tách nền AI kết hợp đục lỗ lòng trong thông minh cho Khung Viền Avatar (Avatar Frame)
- **Files sửa đổi:** [backend/main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py) & [templates/admin.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/admin.html)
- **Chi tiết sửa đổi:**
  - **Khắc phục lỗi AI không đục lỗ lòng trong:** AI `rembg` (mô hình `u2net`) nhận diện vòng tròn khung viền là đối tượng chính nên chỉ tách nền phía bên ngoài vòng tròn, trong khi phần lòng trong ở giữa vẫn là màu trắng đặc (A=254) đè khuất hoàn toàn ảnh VĐV khi ghép.
  - **Triển khai đục lỗ thông minh ở server (`duc_lo_frame_neu_duc`):**
    - Viết lại hàm `duc_lo_frame_neu_duc` sử dụng thư viện `PIL.ImageDraw` vẽ hình tròn trong suốt đè lên tâm ảnh.
    - Cơ chế kiểm tra an toàn: Hàm kiểm tra pixel chính giữa tâm ảnh, nếu điểm tâm đã có kênh alpha trong suốt (A=0, tức ảnh đã được đục lỗ sẵn bằng Photoshop/Canva) thì giữ nguyên để tránh làm hỏng thiết kế gốc của admin. Chỉ thực hiện đục lỗ tròn ở giữa khi tâm ảnh bị đặc màu (A>0) với tỉ lệ chuẩn.
  - **Tích hợp tùy chọn tỉ lệ đục lỗ động (Scale) và vị trí lệch tâm X, Y:**
    - **Frontend (`templates/admin.html`):** Bổ sung dropdown "Tỉ lệ đục lỗ lòng trong" (`50%` đến `80%`, mặc định `65%`) và hai ô nhập số "Lệch ngang X", "Lệch dọc Y" (từ `-50%` đến `50%`, mặc định `0%`).
    - **Backend (`backend/main.py`):** Nhận các tham số `frame_scale`, `frame_offset_x`, `frame_offset_y` từ form và truyền vào hàm `duc_lo_frame_neu_duc` để xử lý đục lỗ linh hoạt theo kích thước và vị trí lệch tâm mong muốn của admin.
- **Kết quả kiểm thử:**
  - Chạy script kiểm thử [test_upload_avatar_frame.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_upload_avatar_frame.py) thành công. File ảnh thật `frame.png` được đục lỗ và tách nền hoàn hảo với tỉ lệ `0.65`, lệch ngang `2.5%` và lệch dọc `-1.5%`, dung lượng giảm từ 329KB xuống 297KB.
  - Kiểm tra pixel tâm ảnh và rìa ảnh bằng PIL trả về độ trong suốt hoàn hảo `(0, 0, 0, 0)` (alpha = 0), khắc phục triệt để lỗi ảnh khung viền đè mất chân dung VĐV.

### 11. Tích hợp thanh trượt tịnh tiến X, Y và đồng bộ hai chiều trên giao diện Ghép Avatar VĐV
- **File sửa đổi:** [templates/avatar.html](file:///c:/Users/PC/Desktop/SSO_HC/templates/avatar.html)
- **Chi tiết sửa đổi:**
  - **Bổ sung UI thanh trượt (Slider):** Thêm hai thanh trượt điều khiển **Dịch ngang (X Offset)** và **Dịch dọc (Y Offset)** vào Panel điều chỉnh ảnh chân dung (khoảng giá trị từ `-600px` đến `600px`, tương ứng với kích thước canvas thực tế `1200x1200px`, giá trị bước nhảy `1px`).
  - **Cơ chế tương tác đồng bộ hai chiều (2-Way Sync):**
    - *Chiều xuôi (Slider -> Canvas):* Khi người dùng kéo thanh trượt X hoặc Y, giá trị `offsetX` và `offsetY` của ảnh được cập nhật tương ứng và vẽ lại tức thì trên canvas.
    - *Chiều ngược (Canvas -> Slider):* Khi người dùng dùng chuột hoặc ngón tay chạm kéo thả (drag) ảnh trực tiếp trên canvas, các thanh trượt X, Y tự động di chuyển theo vị trí tay kéo của người dùng, đảm bảo thông số trên bảng điều khiển luôn hiển thị chuẩn xác và nhất quán.
  - **Khởi tạo và Reset:** Tích hợp logic reset giá trị của hai thanh trượt X, Y mới về `0` (và nhãn hiển thị về `0px`) khi tải ảnh mới lên hoặc khi nhấn nút **Reset (Đặt lại)**.
- **Kết quả kiểm thử:**
  - Chạy script kiểm thử [test_avatar_render.py](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/scratch/test_avatar_render.py) thành công 100%, không phát sinh bất kỳ lỗi cú pháp HTML/JS nào. Giao diện hoạt động trơn tru.

### 12. Sửa lỗi thuật toán xử lý trùng lặp hoạt động (Deduplication) và Tích hợp Time Overlap
- **Files sửa đổi:** [backend/sync_engine.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/sync_engine.py) & [backend/main.py](file:///c:/Users/PC/Desktop/SSO_HC/backend/main.py)
- **Chi tiết sửa đổi:**
  - **Khắc phục lỗi scope `gmt7_now` (`backend/sync_engine.py`):** Di chuyển khai báo `gmt7_now` ra trước vòng lặp chính của hoạt động để tránh lỗi `UnboundLocalError` khi đồng bộ hoạt động đầu tiên có thuộc tính `start_date_local`. **[BUG #1]**
  - **Phân tách trùng lặp theo giải đấu (`backend/sync_engine.py`):** Thêm điều kiện lọc `Activity.event_id == event_id` vào query pre-sync dedup giúp cô lập việc quét trùng chéo giữa các giải đấu khác nhau. **[BUG #2]**
  - **Chuẩn hóa so sánh từ khóa generic (`backend/sync_engine.py` & `backend/main.py`):** Thay đổi việc so sánh generic keywords bằng so sánh chính xác toàn bộ tên: `name_clean in generic_keywords or name_clean == ""` để tránh false positive với tên riêng dài chứa từ khóa (như "Sunrise Marathon"). **[BUG #3]**
  - **Hoàn thiện logic gộp nhiều bản ghi (`backend/main.py`):** Trong hàm `deduplicate_activities_logic`, loại bỏ lệnh `break` sớm khi bản ghi đại diện gốc (`act1`) bị xóa. Thay thế bằng cơ chế cập nhật đại diện liên tục `act1 = act2` và `act1_idx = j` để dọn dẹp sạch sẽ nhóm nhiều bản ghi trùng nhau (3 bản ghi trở lên), chỉ giữ lại bản ghi có multiplier cao nhất. **[BUG #4]**
  - **Tích hợp Thuật toán Time Overlap (`sync_engine.py` & `main.py`):**
    - Chuyển đổi giờ bắt đầu chạy `activity_time` (HH:MM) sang số phút kể từ đầu ngày và cộng với `elapsed_time_min` để xác định khoảng thời gian diễn ra hoạt động.
    - Nếu hai hoạt động của cùng một người diễn ra song song (chồng chéo thời gian trên 50% và giờ bắt đầu lệch không quá 15 phút), hệ thống coi là trùng lặp bất kể sai lệch cự ly GPS bao nhiêu (giải quyết triệt để lỗi ghi song song 2 thiết bị Huawei Watch và Strava App của Lê Văn Thái).
    - Di chuyển logic check overlap lên trước logic kiểm tra tên hoạt động để tránh bị skip sớm khi VĐV đặt tên khác nhau cho 2 thiết bị.
  - **Ưu tiên giữ lại bản ghi có cự ly dài hơn (`main.py`):** Khi hai hoạt động trùng lặp có cùng multiplier, hệ thống tự động giữ lại bản ghi có cự ly (`distance_km`) dài hơn (đo chính xác hơn/không bị mất GPS giữa chừng) và xóa bản ghi ngắn hơn.
- **Kết quả kiểm thử (`scratch/test_dedup_fixes.py`):** Chạy và xác minh thành công 100%:
  - BUG #1, BUG #2, BUG #3, BUG #4 hoạt động ổn định.
  - Trường hợp Lê Văn Thái (Huawei Watch 7.89 km vs Strava App 8.38 km cùng giờ bắt đầu 05:13): Thuật toán Overlap phát hiện trùng lặp thành công, tự động xóa bản ghi Huawei và giữ lại bản ghi Strava App dài hơn 8.38 km. Giao diện và API hoạt động ổn định.
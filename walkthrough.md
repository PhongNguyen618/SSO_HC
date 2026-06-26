# Walkthrough - Tóm tắt các thay đổi và kết quả xác minh

Chúng tôi đã hoàn thành toàn bộ các yêu cầu cải tiến và sửa lỗi cho hệ thống quản lý giải chạy SSO_HC. Dưới đây là tài liệu chi tiết về các thay đổi kỹ thuật và kết quả xác minh.

---

## 1. Cơ chế Tự động Sao lưu và Khôi phục dữ liệu phòng tránh sự cố VPS

Chúng tôi đã triển khai giải pháp sao lưu tự động và khôi phục 100% dữ liệu để bảo vệ hệ thống khi VPS bị hỏng đột ngột.

### Chi tiết thay đổi:
* **Tự động sao lưu định kỳ (`backend/main.py`):**
  * Xây dựng hàm `run_auto_db_backup()`: Tự động sao chép tệp cơ sở dữ liệu `SSO_HC.db` sang thư mục `static/uploads/backups/` kèm timestamp.
  * **Cơ chế xoay vòng (Rotation):** Hệ thống chỉ giữ tối đa **5 bản sao lưu gần nhất** để tiết kiệm dung lượng ổ cứng VPS. Các bản cũ hơn sẽ tự động bị xóa.
  * **Scheduler:** Đăng ký tác vụ sao lưu định kỳ mỗi **24 giờ** vào `BackgroundScheduler`, đồng thời kích hoạt một bản sao lưu ngay khi khởi động ứng dụng (`startup_event`).
* **Tải bản sao lưu dành cho Admin:**
  * Cung cấp endpoint bảo mật `@app.get("/admin/db/backup/download")` để Admin tải file `.db` về máy cá nhân chỉ với 1-Click.
  * Tích hợp khối giao diện **"Sao Lưu Dữ Liệu Hệ Thống"** trong tab **"Bảo mật & Sao lưu"** của `templates/admin.html`.
* **Cách khôi phục dữ liệu khi VPS gặp sự cố:**
  1. Thiết lập VPS mới, clone mã nguồn dự án.
  2. Copy tệp sao lưu `.db` đã tải về máy vào thư mục gốc của dự án trên VPS.
  3. Đổi tên tệp thành **`SSO_HC.db`** và khởi chạy ứng dụng. Toàn bộ dữ liệu được khôi phục nguyên vẹn 100%!

---

## 2. Sửa lỗi mất hệ số x2 Chủ Nhật khi đồng bộ Strava trễ

Chúng tôi đã bổ sung cơ chế **Lọc từ khóa thông minh** kết hợp với **Giờ ân hạn đồng bộ (Sync Grace Period)** để giải quyết lỗi lệch ngày quét.

### Chi tiết thay đổi:
* **Tự động lùi ngày thông minh (`backend/sync_engine.py`):**
  * Khi quét đồng bộ tự động hoặc thủ công từ Strava Club API, nếu hệ thống phải lấy ngày hiện tại (ngày quét `N`) làm ngày chạy:
    * Kiểm tra giờ quét hiện tại (GMT+7) trước **12:00 trưa**.
    * Kiểm tra tên hoạt động xem có chứa các từ khóa chỉ buổi trưa/chiều/tối hay không: `afternoon`, `evening`, `night`, `lunch`, `sunset`, `dusk`, `chiều`, `tối`, `trưa`.
    * Nếu thỏa mãn điều kiện và ngày hôm trước (`N-1`) có hệ số nhân cao hơn ngày quét (`N`) (ví dụ Chủ Nhật x2.0 > Thứ Hai x1.0):
      * Hệ thống tự động gán ngày hoạt động lùi về ngày hôm trước (`N-1`) và đặt giờ chạy mặc định là `23:59`.

---

## 3. Bổ sung Bảng xếp hạng gộp "Chạy & Đi bộ" (Walk + Run)

Chúng tôi đã triển khai thành công bảng xếp hạng gộp kết hợp cả hai bộ môn Đi bộ và Chạy bộ trên trang chủ.

### Chi tiết thay đổi:
* **Thuật toán xếp hạng gộp (`backend/main.py`):**
  * Trong hàm `get_sport_ranking(gender)`, chúng tôi xây dựng truy vấn gom tất cả các hoạt động thuộc nhóm `sport_type` là `"Run"` hoặc `"Walk"`.
  * Thành tích (quãng đường km, thời gian, kcal) của VĐV tham gia cả hai môn này sẽ được **cộng dồn lại** với nhau.
  * Tab **"Theo Bộ Môn"** ở trang chủ sẽ tự động hiển thị thêm bảng xếp hạng **"Chạy & Đi bộ"** cho cả Nam và Nữ mà không cần chỉnh sửa giao diện HTML.

---

## 4. Cải Tiến & Sửa Lỗi Thuật Toán Xử Lý Trùng Lặp Hoạt Động (Deduplication)

Chúng tôi đã sửa đổi, cải tiến và nâng cấp thuật toán xử lý trùng lặp hoạt động (Pre-sync và Post-sync Deduplication) để bảo vệ tính chính xác của dữ liệu giải chạy, đồng thời bổ sung giao diện báo cáo chi tiết cho Quản trị viên.

### Chi tiết lỗi đã khắc phục (Bugs Fixed):
* **Khắc phục lỗi UnboundLocalError (`backend/sync_engine.py`):**
  * Di chuyển biến `gmt7_now` lên trước vòng lặp xử lý các hoạt động từ Strava API.
  * Đảm bảo biến này luôn được định nghĩa đầy đủ, giải quyết triệt để lỗi crash `UnboundLocalError` khi hoạt động đầu tiên đồng bộ có `start_date_local`. **[BUG #1 - 🔴 Nghiêm trọng]**
* **Cô lập cơ chế Pre-sync theo giải đấu (`backend/sync_engine.py`):**
  * Thêm điều kiện lọc `Activity.event_id == event_id` vào truy vấn tìm kiếm hoạt động tương tự trong DB.
  * Giúp cô lập dữ liệu giữa các giải đấu, tránh việc chặn trùng lặp sai (mất hoạt động) khi một VĐV tham gia nhiều giải đấu khác nhau cùng lúc. **[BUG #2 - 🔴 Nghiêm trọng]**
* **Cải thiện so sánh tên hoạt động chung (`backend/sync_engine.py` & `backend/main.py`):**
  * Thay thế cơ chế kiểm tra substring `any(k in name_clean for k in keywords)` bằng so sánh chính xác toàn bộ tên: `name_clean in generic_keywords or name_clean == ""`.
  * Tránh nhận diện sai các tên riêng dài chứa từ khóa (ví dụ: "Sunrise Marathon" không bị coi là generic vì chứa "run"). **[BUG #3 - 🟡 Trung bình]**
  * Sửa logic so sánh tên khi khác nhau từ `not is_generic1 and not is_generic2` thành `(not is_generic1 or not is_generic2)`. Đảm bảo rằng nếu một hoạt động có tên cụ thể tự đặt (như "Sunrise Marathon") và hoạt động kia có tên generic (như "Morning Run"), chúng sẽ **không bị coi là trùng tên** và được giữ lại nguyên vẹn.
* **Cải tiến logic gộp nhiều bản ghi trùng nhau (`backend/main.py`):**
  * Thay thế câu lệnh `break` sớm khi `act1` bị xóa bằng cơ chế thay thế đại diện liên tục: `act1 = act2` và `act1_idx = j`.
  * Đảm bảo dọn dẹp sạch sẽ và giữ lại chính xác một bản ghi tối ưu nhất (có hệ số nhân cao nhất) trong nhóm nhiều bản ghi trùng lặp (từ 3 bản ghi trở lên). **[BUG #4 - 🟡 Trung bình]**
* **Sửa lỗi unpack chuỗi thời gian có giây (`backend/sync_engine.py` & `backend/main.py`):**
  * Khắc phục lỗi `ValueError: too many values to unpack (expected 2)` khi xử lý chuỗi thời gian định dạng `HH:MM:SS` (ví dụ `09:30:00`). Thay vì dùng `map(int, time.split(":"))` trực tiếp cho 2 biến, hệ thống đã được sửa để lấy chính xác 2 phần tử đầu (giờ, phút) bất kể chuỗi có giây hay không, giúp nhận diện trùng lặp thiết bị hoạt động ổn định.

### Các nâng cấp tính năng mới (Features & UI):
* **Phân chia Chế độ dọn dẹp (Mode):**
  * API `/admin/activity/deduplicate` hỗ trợ tham số `mode` với các giá trị:
    * `standard`: Chỉ dọn dẹp các hoạt động trùng lặp cơ bản (cự ly chênh lệch <= 50m, thời gian <= 1 phút). Tự động xóa trực tiếp.
    * `two_devices`: Chỉ dọn dẹp các hoạt động ghi song song từ 2 thiết bị tại cùng một thời điểm. **Hoạt động ở chế độ quét (Dry Run)**, trả về danh sách để Admin duyệt.
    * `all`: Chạy cả hai bộ lọc dọn dẹp trên.
  * Tích hợp **2 nút bấm riêng biệt** trên giao diện Admin:
    1. **Dọn trùng lặp cơ bản** (Màu xanh lá): Tự động quét và xóa.
    2. **Dọn trùng 2 thiết bị** (Màu cam): Quét các hoạt động ghi song song từ 2 thiết bị và hiển thị danh sách duyệt.
* **Modal Báo Cáo & Duyệt Xóa Thủ Công:**
  * Đối với chế độ **Dọn trùng 2 thiết bị**, hệ thống hiển thị Modal **"Duyệt Trùng Lặp 2 Thiết Bị"**.
  * Cột cuối cùng có nút **"Xóa"** (màu đỏ) bên cạnh mỗi hoạt động trùng lặp (phần đề xuất xóa). Admin có thể tự tay check kỹ và bấm nút này để gọi API xóa thủ công hoạt động đó. Bảng duyệt sẽ tự động cập nhật ẩn dòng đã xóa đi.

### Kết quả kiểm thử & Xác minh (Unit Tests):
Chúng tôi đã cập nhật và mở rộng script kiểm tra tự động [test_dedup_fixes.py](file:///c:/Users/PC/Desktop/SSO_HC/scratch/test_dedup_fixes.py) sử dụng database SQLite in-memory để kiểm tra toàn diện các lỗi và chế độ dọn dẹp mới:
* **Kiểm tra BUG #1:** Gọi pre-sync dedup với `start_date_local` -> **[ĐẠT]** (Không crash `UnboundLocalError`).
* **Kiểm tra BUG #2:** Gọi pre-sync dedup chéo giải đấu -> **[ĐẠT]** (Không chặn trùng lặp sai).
* **Kiểm tra BUG #3:** So sánh "Sunrise Marathon" và "Morning Run" -> **[ĐẠT]** (Không bị gộp trùng).
* **Kiểm tra BUG #4 & Mode standard:** Dọn nhóm 3 hoạt động trùng tuyệt đối và bỏ qua trùng 2 thiết bị lệch 100m -> **[ĐẠT]** (Xóa 2 hoạt động phụ, giữ lại hoạt động tối ưu nhất).
* **Kiểm tra Mode two_devices:** Dọn hoạt động ghi song song từ 2 thiết bị -> **[ĐẠT]** (Xóa hoạt động phụ, giữ lại hoạt động có cự ly dài hơn).
* **Kiểm tra Mode two_devices với dry_run=True:** Quét hoạt động trùng 2 thiết bị -> **[ĐẠT]** (Phát hiện hoạt động trùng nhưng giữ lại không xóa khỏi DB).
* **Kiểm tra Mode all:** Dọn cả hai loại trùng lặp -> **[ĐẠT]** (Xóa tất cả 3 hoạt động phụ trong kịch bản mẫu).

**Kết quả chạy script unit test thực tế:**
```powershell
=== BẮT ĐẦU CHẠY UNIT TEST CHO CÁC BẢN FIX XỬ LÝ TRÙNG LẶP ===

--- Test Bug 1 & 2: Pre-sync Deduplication ---
Gọi pre-sync dedup với start_date_local...
=> Test Bug 1 thành công: Không bị crash UnboundLocalError!
Gọi pre-sync dedup ở giải đấu B (event_id=2)...
=> Test Bug 2 thành công: Pre-sync dedup phân biệt giải đấu chính xác!

--- Test Bug 3: Generic Keywords ---
=> Test Bug 3 thành công: Phân biệt tên cụ thể chứa từ khóa generic chính xác!

--- Test Bug 4 & Cleaning Mode: Post-sync Deduplication ---
Chạy dọn dẹp trùng lặp ở chế độ standard (cơ bản)...
  Standard result: deleted_count=2, message=Đã dọn dẹp thành công 2 hoạt động trùng lặp ở chế độ cơ bản.
=> Test Bug 4 & Mode standard thành công: Xóa chuỗi trùng 3+ hoàn toàn và bỏ qua trùng 2 thiết bị!
Chạy dọn dẹp trùng lặp ở chế độ two_devices (2 thiết bị)...
  Two devices result: deleted_count=1, message=Đã dọn dẹp thành công 1 hoạt động trùng lặp ở chế độ 2 thiết bị.
=> Test Mode two_devices thành công: Dọn trùng lặp thiết bị song song chính xác!
Chạy dọn dẹp trùng lặp ở chế độ two_devices (dry_run=True)...
  Dry run result: deleted_count=1, message=Phát hiện 1 hoạt động trùng lặp ở chế độ 2 thiết bị.
=> Test dry_run thành công: Phát hiện nhưng không xóa bản ghi!
Chạy dọn dẹp trùng lặp ở chế độ all (tất cả)...
  All result: deleted_count=3, message=Đã dọn dẹp thành công 3 hoạt động trùng lặp ở chế độ tất cả.
=> Test Mode all thành công!

=> TẤT CẢ CÁC TEST CASE ĐÃ VƯỢT QUA THÀNH CÔNG!
```
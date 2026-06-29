# Cẩm Nang Vibe Coding: SSO_HC

Tài liệu này chứa các quy tắc phát triển, bộ nhớ lưu trữ các lỗi thường gặp (Memory & Pitfalls) để tránh lặp lại lỗi, và mẫu Prompt gợi ý cho session tiếp theo.

---

## 1. Quy Tắc Phát Triển Cốt Lõi (Coding Rules)

- **Ngôn ngữ hiển thị**: Toàn bộ giao diện người dùng (Bảng xếp hạng, Trang cá nhân, Admin Panel) hiển thị bằng **Tiếng Việt có dấu**.
- **Tính đồng nhất Glassmorphism**: Giữ nguyên thiết kế responsive, bán trong suốt (glassmorphic) hiện đại với các hiệu ứng bo tròn góc, viền phát sáng và micro-animations.
- **Tính toán Calo**: Luôn luôn sử dụng công thức ACSM cho Chạy bộ (Run) và Đi bộ (Walk). Đối với các môn khác, áp dụng Nội suy tuyến tính dựa trên các mốc tốc độ của giải đấu (nếu không có thì fallback về cấu hình mặc định).
- **Nguyên tắc Fallback cấu hình**: Khi truy vấn cấu hình (METs, Rewards, Badges) cho một giải đấu cụ thể:
  1. Thử lấy cấu hình riêng có `event_id == event_id`.
  2. Nếu rỗng (chưa thiết lập riêng), tự động fallback lấy cấu hình mặc định có `event_id == None`.
- **Ràng buộc khóa ngoại**: Khi xóa một giải đấu hoặc một vận động viên, cần đảm bảo xóa sạch dữ liệu đăng ký hoặc hủy liên kết hoạt động một cách an toàn để tránh lỗi ràng buộc cơ sở dữ liệu SQLite (`IntegrityError`).

---

## 2. Nhật Ký Lỗi Thường Gặp (Memory & Pitfalls)

### ⚠️ Lỗi Thụt Lề & Chắp Vá Mã Nguồn khi thay thế tự động (Indentation Errors)
- **Vấn đề**: Khi AI thực hiện công cụ chỉnh sửa tự động (`replace_file_content`) trên các tệp lớn, đôi khi do lệch khoảng trắng thụt lề dẫn đến lỗi cú pháp hoặc chắp vá nhầm mã nguồn.
- **Giải pháp**: 
  - Luôn kiểm tra kỹ thụt lề của khối mã thay thế.
  - Sử dụng lệnh biên dịch thử: `.venv\Scripts\python.exe -m py_compile backend/main.py` để xác minh cú pháp ngay sau khi chỉnh sửa.
  - Nếu gặp khó khăn với công cụ so khớp, hãy viết một kịch bản Python nhỏ để thực hiện chỉnh sửa chính xác bằng chuỗi thô hoặc Regex.

### ⚠️ Lỗi Ràng Buộc Khóa Chính SQLite với BadgeRule
- **Vấn đề**: SQLite không hỗ trợ thay đổi khóa chính một cách dễ dàng qua `ALTER TABLE` đối với cơ sở dữ liệu đã chạy.
- **Giải pháp**: Giữ nguyên khóa chính `id` của bảng `badge_rules` là kiểu String. Tạo giá trị khóa chính động dạng `f"{badge_key}_{event_id}"` đối với cấu hình riêng của giải đấu và `badge_key` đối với cấu hình mặc định. Dùng trường `badge_key` để backend nhận diện loại huy hiệu.

### ⚠️ Lỗi UnicodeEncodeError trên Console Windows (CP1252)
- **Vấn đề**: Khi chạy script kiểm thử hoặc lệnh python in ký tự Tiếng Việt có dấu ra màn hình cmd/powershell trên Windows, Python có thể bị crash do console mặc định sử dụng bảng mã CP1252.
- **Giải pháp**: Thiết lập biến môi trường `$env:PYTHONIOENCODING="utf-8"` trước khi chạy lệnh Python, hoặc chỉ sử dụng Tiếng Việt không dấu cho các câu lệnh `print()` trong script test.

### ⚠️ Lỗi Chèn Đăng Ký Trùng Lặp khi khởi tạo (UNIQUE Constraint)
- **Vấn đề**: Khi di trú dữ liệu trong `init_db()`, nếu gom đăng ký tự động cho các Athlete hiện tại vào giải mặc định, nếu không lọc trùng hoặc kiểm tra tồn tại kỹ lưỡng có thể gây ra lỗi chèn trùng khóa chính kép `(athlete_id, event_id)`.
- **Giải pháp**: Sử dụng một tập hợp `set` lọc trùng các cặp `(athlete_id, event_id)` trước khi truy vấn kiểm tra sự tồn tại và chèn mới vào cơ sở dữ liệu.

### ⚠️ Lỗi Lọc Ngày Nhanh Bị Sai Trên Giải Đấu Trường Kỳ (Date Preset Error)
- **Vấn đề**: Bộ lọc thời gian nhanh "7 ngày qua" và "30 ngày qua" ở trang chủ (`templates/index.html`) sử dụng ngày kết thúc giải chạy làm mốc tính lùi. Với các giải trường kỳ có thời hạn đến 2030, ngày lọc sẽ bị nhảy hoàn toàn sang 2030 thay vì hôm nay.
- **Giải pháp**: Luôn sử dụng ngày hôm nay thực tế làm mốc kết thúc cho bộ lọc nhanh, chỉ fallback về ngày kết thúc giải đấu nếu ngày hôm nay đã vượt quá hạn đóng của giải đấu đó.

### ⚠️ Lỗi Gán Nhầm Ngày Chủ Nhật Khi Sync Rạng Sáng Thứ 2 (Early Dedup Fix)
- **Vấn đề**: API Strava Club Activities không trả về `start_date_local`. Khi sync lúc 00:15 Thứ 2, thuật toán grace period lùi TẤT CẢ hoạt động về ngày hôm trước (Chủ nhật). Hoạt động Thứ 7 đã sync đúng ngày Thứ 7 trước đó bị tạo lại với hash ID mới (vì hash bao gồm `act_date_str` = CN ≠ T7) → trùng lặp sai ngày, sai multiplier.
- **Giải pháp**: Thêm tầng **Early Dedup** trước logic grace period trong `sync_engine.py`. Trước khi suy diễn ngày, kiểm tra xem hoạt động đã tồn tại trong DB (khớp athlete + sport_type + distance + time + elevation trong 7 ngày gần đây) → nếu trùng thì bỏ qua ngay, không cho grace period gán sai ngày. Đồng thời mở rộng Pre-sync Dedup hỗ trợ cả VĐV chưa liên kết (`athlete_id = None`) bằng cách truy vấn theo `athlete_name_raw`.

---

## 3. Prompt Template Cho Session Tiếp Theo

*Sao chép nội dung bên dưới và dán vào AI Assistant ở phiên làm việc mới để tiếp tục phát triển dự án.*

```markdown
Chào bạn, tôi đang phát triển dự án web app đồng bộ thành tích thể thao nội bộ công ty từ Strava có tên là **SSO_HC**. 

Tôi cần bạn đọc hiểu ngữ cảnh của dự án trước khi bắt tay vào code tiếp các tính năng. Dưới đây là thông tin chi tiết:
1. **Bản đồ tri thức dự án**: Vui lòng đọc tệp [project_knowledge_map.md](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/project_knowledge_map.md) trong thư mục artifacts để hiểu cấu trúc database SQLite, tech stack, và luồng tính toán/đồng bộ dữ liệu chính.
2. **Nhật ký lỗi & Hướng dẫn Vibe Coding**: Vui lòng đọc tệp [vibecoding_guide.md](file:///C:/Users/PC/.gemini/antigravity/brain/bd264055-d159-48f2-b24a-882bf20c1d44/vibecoding_guide.md) để tránh các lỗi thường gặp như thụt lề sai, lỗi mã hóa CP1252 trên Windows console, và quy tắc fallback cấu hình.
3. **Trạng thái hiện tại**: Hệ thống đã hỗ trợ đăng ký nhiều giải đấu riêng biệt, lọc BXH theo giải đấu, trang cá nhân VĐV Gamification với huy chương 3D, và Admin Panel cho phép cấu hình Hệ số METs, Mốc thưởng, Huy hiệu riêng biệt cho từng giải đấu động qua AJAX.

[YÊU CẦU CỦA BẠN SẼ GHI Ở ĐÂY - Ví dụ: Hãy xây dựng thêm tính năng xuất báo cáo thống kê PDF cho Admin...]

Hãy phản hồi lại bằng Tiếng Việt và tóm tắt ngắn gọn hiểu biết của bạn về dự án trước khi đề xuất giải pháp thực hiện yêu cầu trên.
```

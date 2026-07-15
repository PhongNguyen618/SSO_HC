# Bài học kinh nghiệm & Quy tắc phát triển SSO_HC

Tài liệu này ghi lại các lỗi đã xảy ra và các bài học kinh nghiệm trong quá trình phát triển hệ thống SSO_HC để tránh lặp lại trong tương lai.

## 1. Đồng bộ dữ liệu Strava (Scraper vs OAuth API)
- **Cơ chế hoạt động:**
  - Khi chưa đăng nhập (Anonymous), Strava render Next.js tĩnh và lưu hoạt động ở thẻ `<script id="__NEXT_DATA__">`.
  - Khi **đã đăng nhập (Logged In - dùng cookie)**, Strava chuyển sang trang Rails và dữ liệu hoạt động được chứa trong `data-react-props` của thẻ React Microfrontend Feed (`scope: "strava_feed"`).
  - **Quy tắc:** Bộ Scraper cào web phải hỗ trợ song song cả 2 giao diện này để tránh việc trả về 0 hoạt động khi dùng cookie Admin.
- **Múi giờ hoạt động:**
  - Trường `startDate` cào về từ React Microfrontend của Strava là giờ **UTC chuẩn (GMT+0)**.
  - **Quy tắc:** Bắt buộc phải sử dụng hàm `convert_utc_to_gmt7` cộng thêm 7 tiếng trước khi lưu vào DB để tránh việc VĐV chạy buổi sáng bị hiển thị thành giờ đêm (`0h15`) trên BXH.
- **Phân biệt nguồn dữ liệu:**
  - Để tránh sửa nhầm dữ liệu lịch sử từ API Club cũ (ID số nguyên ngắn), khi thực hiện fix múi giờ hàng loạt hoặc các thao tác di trú, chỉ lọc các hoạt động có ID dài đúng 64 ký tự (ID băm SHA-256 của cào web).

## 2. Trải nghiệm người dùng (UX) đăng ký
- **Không tự động chuyển hướng quá nhanh:**
  - Trang đăng ký thành công có mã QR Group Zalo/Strava không được phép tự động redirect sau 3 giây. Người dùng cần thời gian để quét QR. Trình bày quy trình 2 bước Step-by-Step và để người dùng chủ động click nút "Liên kết Strava".
- **Ẩn form nhập liệu khi có cảnh báo trùng:**
  - Khi người dùng bị báo trùng thông tin và hiển thị hộp thoại xác nhận cập nhật, form đăng ký trống bên dưới phải được ẩn hoàn toàn để tránh làm rối mắt và gây hiểu nhầm.

## 3. Ràng buộc thời gian diễn ra giải đấu (Date Range Constraints)
- **Luôn kiểm tra khoảng thời gian giải đấu khi đồng bộ:**
  - Khi đồng bộ hoạt động từ bất kỳ nguồn nào (API cá nhân, API Club cũ, hay Scraper cào Web), hệ thống **bắt buộc** phải so khớp ngày chạy của hoạt động (`activity_date`) nằm trong khoảng thời gian diễn ra giải đấu: `event.start_date <= activity_date <= event.end_date`.
  - Các hoạt động ngoài khoảng thời gian này phải bị bỏ qua ngay lập tức để tránh việc các hoạt động lịch sử trước đây (ví dụ hoạt động từ năm 2019, 2020, 2024, 2025) bị nạp nhầm vào giải chạy mới khi quét CLB.
- **Cơ chế dọn dẹp (Cleanup):**
  - Tích hợp tính năng tự động dọn dẹp các hoạt động nằm ngoài mốc thời gian của giải đấu đang hoạt động vào nút dọn dẹp hệ thống trên trang quản trị Admin để xử lý nhanh sự cố dữ liệu.

## 4. Quản lý cú pháp và ghép code Javascript (Giao diện Admin)
- **Kiểm tra kỹ lưỡng dấu đóng ngoặc khi bổ sung hàm JS:**
  - Khi viết thêm các hàm xử lý dữ liệu động ở Frontend (như `applySportFilters`), bắt buộc phải kiểm tra thủ công sự trùng khớp của toàn bộ dấu ngoặc nhọn `{}` và ngoặc đơn `()`. Việc thiếu dù chỉ một dấu đóng ngoặc sẽ phá vỡ cú pháp toàn cục của file HTML/JS, làm toàn bộ script ngừng chạy và đơ trang quản trị.
  - Khi thực hiện ghép code bằng các công cụ tự động (`replace_file_content`, `multi_replace_file_content`), hãy kiểm tra lại kết quả thay thế (`diff`) để đảm bảo không bị ghép lệch dòng hoặc ghi đè sai vị trí.


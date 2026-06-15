# SSO_HC - Tài Liệu Giới Thiệu Chức Năng Hệ Thống

Tài liệu này tóm tắt toàn bộ các chức năng hiện có của dự án **SSO_HC Sport Web App** (Hệ thống đồng bộ và xếp hạng thành tích thể thao phong trào).

---

## 📌 Tổng Quan Hệ Thống
**SSO_HC** là một ứng dụng Web (xây dựng trên nền tảng **FastAPI** và **SQLite**) được thiết kế để quản lý giải chạy bộ/thể thao phong trào trong nội bộ doanh nghiệp. Hệ thống tự động đồng bộ hoạt động từ nền tảng **Strava**, tính toán năng lượng tiêu thụ (KCAL) làm cơ sở xếp hạng cá nhân, phòng ban và tự động quy đổi giải thưởng thực tế.

---

## 1. Cơ Chế Đồng Bộ Hoạt Động (Strava Sync Engine)
Đây là tính năng cốt lõi giúp hệ thống tự động hóa hoàn toàn việc lấy dữ liệu từ Strava.
* **Đồng bộ tự động qua câu lạc bộ (Club Sync):** 
  * Chỉ cần tài khoản Admin duy nhất thực hiện ủy quyền (OAuth) kết nối với ứng dụng.
  * Ứng dụng sẽ dùng quyền của Admin để tự động quét toàn bộ hoạt động của các thành viên trong **Strava Club** thông qua API.
  * *Ưu điểm:* Vận động viên (VĐV) thông thường không cần bấm kết nối tài khoản cá nhân, giúp khắc phục triệt để giới hạn 25 tài khoản liên kết (connected athletes) ở chế độ phát triển (Development) của Strava API.
* **Đồng bộ thủ công (Manual Sync):** Admin có thể nhấn nút đồng bộ ngay lập tức từ trang quản trị để cập nhật dữ liệu mới nhất.
* **Xử lý hoạt động chưa liên kết (Unlinked Activities):**
  * Tự động lọc các hoạt động lấy từ Club có tên hiển thị trên Strava chưa khớp với bất kỳ VĐV nào trong hệ thống.
  * Khi VĐV mới đăng ký tài khoản hoặc cập nhật lại tên Strava, hệ thống sẽ tự động ghép nối các hoạt động cũ này vào tài khoản của họ.

---

## 2. Quy Đổi Điểm & Tính Toán Năng Lượng (Calculations & METs System)
Hệ thống sử dụng các thuật toán khoa học để quy đổi thành tích di chuyển thành năng lượng tiêu thụ (KCAL) làm căn cứ xếp hạng công bằng:
* **Hệ số METs động (Dynamic METs):**
  * **Chạy bộ (Run) & Đi bộ (Walk):** Áp dụng công thức chuẩn của **Hiệp hội Y học Thể thao Hoa Kỳ (ACSM)**, tự động tích hợp tốc độ di chuyển và độ dốc (Elevation Grade) lấy từ GPS để tính ra lượng oxy tiêu thụ (VO2) và quy đổi sang METs.
  * **Các môn khác (Đạp xe, Bơi, Gym, Yoga...):** Sử dụng phương pháp **Nội suy tuyến tính (Linear Interpolation)** dựa trên các khoảng tốc độ tối thiểu/tối đa cấu hình trong cơ sở dữ liệu.
* **Quy đổi KCAL:** Tính toán lượng calo tiêu hao cá nhân hóa dựa trên: hệ số METs của môn thể thao, cân nặng cụ thể của VĐV, thời gian di chuyển thực tế (Moving Time) và độ cao đạt được (Elevation Gain).

---

## 3. Quản Lý Người Dùng & Vận Động Viên (Athletes Management)
* **Đăng ký tài khoản VĐV:** Người dùng đăng ký nhanh chóng bằng cách điền các thông tin: Họ và tên, phòng ban, giới tính, cân nặng hiện tại và tên hiển thị chính xác trên Strava.
* **Trang cá nhân VĐV (Profile):**
  * Xem biểu đồ phân tích hoạt động gần đây (quãng đường, calo).
  * Thống kê tổng hợp cá nhân: tổng số km, tổng số giờ, tổng KCAL và tổng tiền thưởng đã đạt.
  * Hiển thị danh sách các **Huy hiệu thành tích (Badges)** đạt được.
  * Xem nhật ký chi tiết các hoạt động thể thao cá nhân.
  * Cho phép tự cập nhật cân nặng cá nhân hoặc đổi ảnh đại diện (avatar).
* **Quản lý danh sách VĐV (Admin):**
  * Xem danh sách toàn bộ VĐV, lọc theo phòng ban, trạng thái hoạt động.
  * Bật/tắt trạng thái hoạt động (`is_active`) của VĐV.
  * **Import Excel:** Hỗ trợ tải hàng loạt danh sách VĐV từ file Excel mẫu để khởi tạo nhanh hệ thống.

---

## 4. Bảng Xếp Hạng Động (Leaderboards)
Bảng xếp hạng hiển thị trực quan ngoài trang chủ với các bộ lọc thông minh:
* **Bảng xếp hạng Cá nhân:** Xếp hạng theo tổng lượng KCAL tiêu thụ. Hiển thị các thông tin: Họ tên, Phòng ban, Giới tính, Quãng đường (km), Thời gian (phút), Calo tiêu thụ (KCAL), và Dự kiến giải thưởng (VND).
* **Bảng xếp hạng Phòng ban:** 
  * Điểm phòng ban được tính bằng **trung bình cộng** của các thành viên hoạt động (`Tổng KCAL phòng ban / Sĩ số hoạt động`).
  * Cơ chế này giúp đảm bảo sự cạnh tranh công bằng giữa các phòng ban đông người và ít người.
* **Bộ lọc nâng cao:** Hỗ trợ tìm kiếm theo tên VĐV, lọc theo phòng ban, hoặc lọc thành tích theo khoảng thời gian tùy chọn (Từ ngày - Đến ngày).
* **Ẩn/Hiện cột linh hoạt:** Admin có thể bật/tắt hiển thị 5 cột chính trên bảng xếp hạng (Giới tính, Phòng ban, Quãng đường, Thời gian, Giải thưởng) tùy theo yêu cầu của từng giải chạy.

---

## 5. Phát Hiện Gian Lận & Giám Sát Hoạt Động (Anti-Cheat & Flagging)
* **Tự động quét hoạt động bất thường:** Thuật toán phân tích dữ liệu tự động gắn cờ nghi vấn (`is_suspicious`) đối với các hoạt động có dấu hiệu gian lận hoặc lỗi GPS, ví dụ:
  * Di chuyển bằng phương tiện cơ giới (vận tốc chạy bộ/đi bộ vượt quá giới hạn vật lý).
  * Tốc độ pace quá nhanh hoặc thời gian hoạt động quá ngắn bất thường.
* **Trang phê duyệt của Admin:** Hiển thị danh sách hoạt động bị nghi vấn. Admin có quyền xem bản đồ/thông tin chi tiết, sau đó lựa chọn **Duyệt (Approve)** hoặc **Từ chối (Reject)** hoạt động đó để đảm bảo tính minh bạch cho giải đấu.

---

## 6. Hệ Thống Huy Hiệu (Badges) & Giải Thưởng (Rewards)
Khuyến khích tinh thần rèn luyện bằng các phần thưởng trực quan:
* **Phần thưởng mốc thành tích (Reward Rules):** 
  * Cấu hình giải thưởng bằng tiền mặt theo từng mốc KCAL đạt được và theo giới tính (Nam / Nữ).
  * Hệ thống tự động tính toán số tiền thưởng mà mỗi VĐV xứng đáng nhận được hiển thị trực tiếp trên Bảng xếp hạng.
* **Huy hiệu danh hiệu (Badges):** Tự động trao tặng các huy hiệu độc đáo dựa trên các cột mốc thành tích, giúp tăng tính tương tác và động lực thi đấu cho CBNV.

---

## 7. Quản Lý Giải Chạy & Đóng Giải (Event Archiving)
Tính năng hỗ trợ tổ chức nhiều giải chạy liên tiếp nhau:
* **Đóng giải chạy hiện tại:** Admin có thể kết thúc giải chạy. Hệ thống sẽ tự động tổng hợp số liệu, xuất bảng xếp hạng chung cuộc và đóng gói toàn bộ dữ liệu của giải chạy đó thành một **Sự kiện lịch sử (Archived Event)**.
* **Reset mùa giải mới:** Sau khi đóng giải, hệ thống sẽ reset toàn bộ thành tích cá nhân, phòng ban về `0` để sẵn sàng bắt đầu mùa giải tiếp theo.
* **Xem lịch sử sự kiện:** Người dùng có thể dễ dàng xem lại chi tiết bảng xếp hạng, thống kê và cơ cấu giải thưởng của các giải đấu đã qua tại mục Lưu trữ.

---

## 8. Cấu Hình & Tùy Biến Giao Diện (Admin Dashboard)
Trang quản trị cho phép Admin làm chủ hoàn toàn hệ thống:
* **Branding & Layout:** Thay đổi Logo và Banner của giải đấu trực tiếp từ giao diện (upload file ảnh).
* **Quản lý quy chế:** Chỉnh sửa Tiêu đề cuộc thi, phiên bản quy chế (Rules Version), nội dung quy chế chung để hiển thị dưới dạng Welcome Banner cho người dùng ở lần đầu đăng nhập.
* **Cấu hình tham số:**
  * Tùy chỉnh chu kỳ quét dữ liệu của scheduler (từ 1 đến 24 giờ).
  * Thay đổi cấu hình các bộ quy tắc METs cho từng môn thể thao.
  * Cấu hình quy tắc tính giải thưởng (Reward Rules) cho từng nhóm giới tính.
  

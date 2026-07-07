
            document.addEventListener("DOMContentLoaded", function() {
                const deptInput = document.getElementById("department");
                const eventSelect = document.getElementById("event_id");
                
                // Tránh lỗi khi giao diện hiển thị form xác nhận (eventSelect lúc này là input hidden không có options)
                if (!deptInput || !eventSelect || !eventSelect.options) return;
                
                function filterEvents() {
                    const val = deptInput.value.trim().toUpperCase();
                    // Nếu trường phòng ban rỗng, cho phép xem tất cả; nếu không rỗng, kiểm tra xem có bắt đầu bằng 'SSO'
                    const isSSO = val === "" || val.startsWith("SSO");
                    
                    for (let i = 0; i < eventSelect.options.length; i++) {
                        const opt = eventSelect.options[i];
                        // Tìm giải đấu nội bộ qua tiêu đề (hỗ trợ cả dấu nháy đơn thường ' và nháy đơn cong ’)
                        const isSsoHcOption = opt.text.toUpperCase().includes("SSO'S HC") || opt.text.toUpperCase().includes("SSO’S HC");
                        
                        if (isSsoHcOption) {
                            if (isSSO) {
                                opt.style.display = "";
                                opt.disabled = false;
                            } else {
                                opt.style.display = "none";
                                opt.disabled = true;
                                if (eventSelect.value === opt.value) {
                                    eventSelect.value = "";
                                }
                            }
                        }
                    }
                }
                
                deptInput.addEventListener("input", filterEvents);
                deptInput.addEventListener("change", filterEvents);
                filterEvents();
            });
        
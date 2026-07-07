
        // Mở Modal tìm kiếm liên kết
        function openCheckConnectionModal() {
            const modal = document.getElementById('checkConnectionModal');
            if (modal) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
                document.getElementById('searchAthleteConnInput').value = '';
                document.getElementById('searchConnectionResults').innerHTML = '';
            }
        }

        // Đóng Modal tìm kiếm
        function closeCheckConnectionModal() {
            const modal = document.getElementById('checkConnectionModal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        }

        // Chạy tìm kiếm kết quả VĐV
        async function triggerSearchConnection() {
            const input = document.getElementById('searchAthleteConnInput');
            const resultsDiv = document.getElementById('searchConnectionResults');
            const q = input.value.trim();
            
            if (!q) {
                resultsDiv.innerHTML = '<p style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 1rem;">Vui lòng nhập tên để tìm kiếm.</p>';
                return;
            }
            
            resultsDiv.innerHTML = '<p style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 1rem;"><i class="fa-solid fa-spinner fa-spin"></i> Đang tìm kiếm...</p>';
            
            try {
                const response = await fetch(`/api/athlete/search-connection?q=${encodeURIComponent(q)}`);
                const data = await response.json();
                
                if (data.status === 'success') {
                    const results = data.results || [];
                    if (results.length === 0) {
                        resultsDiv.innerHTML = '<p style="text-align: center; color: var(--text-muted); font-size: 0.85rem; padding: 1rem;">Không tìm thấy vận động viên nào khớp với tên này.</p>';
                        return;
                    }
                    
                    let html = '';
                    results.forEach(r => {
                        html += `
                        <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.08); padding: 0.8rem; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; text-align: left;">
                            <div>
                                <strong style="color: var(--text-main); font-size: 0.9rem;">${escapeHtml(r.full_name)}</strong>
                                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;"><i class="fa-solid fa-users"></i> ${escapeHtml(r.department)}</div>
                            </div>
                            <div>
                                ${r.is_linked ? `
                                    <span style="background: rgba(40, 167, 69, 0.1); color: #28a745; border: 1px solid rgba(40, 167, 69, 0.25); padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.75rem; font-weight: 600; display: inline-flex; align-items: center; gap: 0.25rem;">
                                        <i class="fa-solid fa-circle-check"></i> Đã liên kết
                                    </span>
                                ` : `
                                    <a href="javascript:void(0)" onclick="confirmOAuthLink('${r.auth_url}', '${escapeHtml(r.full_name)}', '${escapeHtml(r.department)}')" class="btn btn-primary btn-sm" style="background: linear-gradient(135deg, #ff5e36 0%, #ff9a3c 100%); border: none; padding: 0.35rem 0.7rem; font-size: 0.75rem; font-weight: 700; border-radius: 6px; text-decoration: none; color: #fff; display: inline-flex; align-items: center; gap: 0.25rem; box-shadow: 0 4px 10px rgba(255, 94, 54, 0.3);">
                                        <i class="fa-brands fa-strava"></i> Liên kết
                                    </a>
                                `}
                            </div>
                        </div>
                        `;
                    });
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = '<p style="text-align: center; color: #ff5e36; font-size: 0.85rem; padding: 1rem;">Lỗi tìm kiếm dữ liệu.</p>';
                }
            } catch (err) {
                resultsDiv.innerHTML = '<p style="text-align: center; color: #ff5e36; font-size: 0.85rem; padding: 1rem;">Lỗi kết nối hệ thống.</p>';
            }
        }

        function escapeHtml(text) {
            return text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Đóng Smart Reminder Modal
        function closeSmartReminderModal(setCooldown = false) {
            const modal = document.getElementById('smartReminderModal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
            if (setCooldown) {
                // Đọc thời gian cooldown từ cấu hình DB (tính bằng giờ, mặc định là 12)
                const cooldownHours = parseFloat('"jinja_var"') || 12;
                localStorage.setItem('sso_reminder_cooldown', (Date.now() + cooldownHours * 60 * 60 * 1000).toString());
            }
        }

        // Tự động kiểm tra nhắc nhở khi tải trang
        window.addEventListener('DOMContentLoaded', async () => {
            const isRulesPage = window.location.pathname === '/rules';
            const isAdminPage = window.location.pathname.startsWith('/admin');
            const isRegisterPage = window.location.pathname === '/register';
            
            if (isRulesPage || isAdminPage || isRegisterPage) return;
            
            // Kiểm tra cấu hình bật/tắt popup nhắc nhở
            const isPopupEnabled = '"jinja_var"' === 'true';
            if (!isPopupEnabled) return;
            
            const athleteId = localStorage.getItem('sso_athlete_id');
            const isLinkedLocal = localStorage.getItem('sso_strava_linked');
            
            if (athleteId && isLinkedLocal === 'false') {
                // Kiểm tra cooldown
                const cooldown = localStorage.getItem('sso_reminder_cooldown');
                if (cooldown && Date.now() < parseInt(cooldown)) {
                    return;
                }
                
                try {
                    const response = await fetch(`/api/athlete/status/${athleteId}`);
                    if (!response.ok) return;
                    const data = await response.json();
                    
                    if (data.status === 'success') {
                        if (data.is_linked) {
                            localStorage.setItem('sso_strava_linked', 'true');
                        } else {
                            // Thực sự chưa liên kết, tìm auth_url để gán cho nút bấm
                            const searchResponse = await fetch(`/api/athlete/search-connection?q=${encodeURIComponent(data.full_name)}`);
                            const searchData = await searchResponse.json();
                            
                            if (searchData.status === 'success' && searchData.results && searchData.results.length > 0) {
                                const match = searchData.results.find(r => r.id.toString() === athleteId.toString());
                                if (match && match.auth_url) {
                                    const authBtn = document.getElementById('smartReminderAuthBtn');
                                    if (authBtn) {
                                        authBtn.href = match.auth_url;
                                    }
                                    
                                    // Hiển thị popup nhắc nhở sau 2 giây
                                    setTimeout(() => {
                                        const modal = document.getElementById('smartReminderModal');
                                        if (modal) {
                                            modal.classList.add('active');
                                            document.body.style.overflow = 'hidden';
                                        }
                                    }, 2000);
                                }
                            }
                        }
                    }
                } catch (err) {
                    console.error("Error during smart connection check:", err);
                }
            }
        });

        function confirmOAuthLink(authUrl, athleteName, department) {
            const msg = `⚠️ XÁC NHẬN LIÊN KẾT TÀI KHOẢN STRAVA\n\n` +
                        `Bạn đang thực hiện liên kết Strava cho VĐV:\n` +
                        `• Họ và Tên: ${athleteName}\n` +
                        `• Phòng ban: ${department}\n\n` +
                        `ĐÂY CÓ ĐÚNG LÀ TÀI KHOẢN CỦA BẠN KHÔNG?\n` +
                        `Nếu không phải bạn, vui lòng bấm HỦY và chọn đúng tên mình để tránh làm mất dữ liệu của người khác.`;
                        
            if (confirm(msg)) {
                window.location.href = authUrl;
            }
        }
    
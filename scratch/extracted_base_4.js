
        function initQuickAccess() {
            const athleteId = localStorage.getItem('sso_athlete_id');
            const athleteName = localStorage.getItem('sso_athlete_name');
            if (!athleteId || !athleteName) return;

            const bar = document.getElementById('quickAccessBar');
            const nameEl = document.getElementById('quickAccessName');
            const avatarEl = document.getElementById('quickAccessAvatar');
            const profileBtn = document.getElementById('quickAccessProfileBtn');

            nameEl.textContent = athleteName;
            avatarEl.textContent = athleteName.charAt(0).toUpperCase();
            profileBtn.href = '/profile/' + athleteId;
            bar.style.display = 'block';
            document.body.classList.add('has-quick-access');

            // Tự động highlight hàng VĐV trên BXH (nếu đang ở trang chủ)
            setTimeout(() => {
                const rows = document.querySelectorAll('tr[data-athlete-id]');
                rows.forEach(row => {
                    if (row.getAttribute('data-athlete-id') === athleteId) {
                        row.style.background = 'rgba(143, 205, 240, 0.08)';
                        row.style.borderLeft = '3px solid #8fcdf0';
                        row.style.boxShadow = '0 0 10px rgba(143, 205, 240, 0.1)';
                    }
                });
            }, 300);
        }

        function clearQuickAccess() {
            localStorage.removeItem('sso_athlete_id');
            localStorage.removeItem('sso_athlete_name');
            localStorage.removeItem('sso_strava_linked');
            const bar = document.getElementById('quickAccessBar');
            bar.style.display = 'none';
            document.body.classList.remove('has-quick-access');
            // Bỏ highlight hàng VĐV trên BXH
            document.querySelectorAll('tr[data-athlete-id]').forEach(row => {
                row.style.background = '';
                row.style.borderLeft = '';
                row.style.boxShadow = '';
            });
        }

        // Kiểm tra xem trình duyệt có phải là In-App Webview (Zalo, FB, Instagram, etc.) hay không
        function checkInAppWebview() {
            const ua = navigator.userAgent || navigator.vendor || window.opera;
            const isInApp = (
                /zalo/i.test(ua) || 
                /FBAN/i.test(ua) || 
                /FBAV/i.test(ua) || 
                /Instagram/i.test(ua) || 
                /Messenger/i.test(ua) || 
                /GSA/i.test(ua) || // Google Search App iOS
                (/iPhone|iPad|iPod/i.test(ua) && !/Safari/i.test(ua) && !/CriOS/i.test(ua)) || // iOS webview
                (/Android/i.test(ua) && /Version\/[0-9.]+/i.test(ua) && !/Chrome/i.test(ua)) // Android webview
            );
            
            if (isInApp) {
                const banner = document.getElementById('webviewWarningBanner');
                if (banner) {
                    banner.style.display = 'flex';
                }
            }
        }

        document.addEventListener('DOMContentLoaded', () => {
            initQuickAccess();
            checkInAppWebview();
        });
    

        function showRulesModal() {
            const modal = document.getElementById('rulesWelcomeModal');
            if (modal) {
                modal.classList.add('active');
                document.body.style.overflow = 'hidden';
            }
        }

        function closeRulesModal() {
            const modal = document.getElementById('rulesWelcomeModal');
            if (modal) {
                modal.classList.remove('active');
                document.body.style.overflow = '';
            }
        }

        function acceptRules() {
            localStorage.setItem('rules_accepted_' + '"jinja_var"', 'true');
            localStorage.setItem('rules_closed_time_' + '"jinja_var"', Date.now().toString());
            closeRulesModal();
        }

        window.addEventListener('DOMContentLoaded', () => {
            const isRulesPage = window.location.pathname === '/rules';
            const isAdminPage = window.location.pathname.startsWith('/admin');
            
            // Chỉ hiển thị popup chào mừng nếu có giải đấu mới đang hoạt động (active_event_id có giá trị và khác 1)
            const hasActiveNewEvent = '"jinja_var"' !== '' && '"jinja_var"' !== '1';
            
            if (!isRulesPage && !isAdminPage && hasActiveNewEvent) {
                const bannerMode = '"jinja_var"';
                const resetDays = parseFloat('"jinja_var"');
                
                if (bannerMode === 'always') {
                    setTimeout(showRulesModal, 1200);
                } else if (bannerMode === 'days') {
                    const isAccepted = localStorage.getItem('rules_accepted_' + '"jinja_var"');
                    if (isAccepted === 'true') {
                        const closedTimeStr = localStorage.getItem('rules_closed_time_' + '"jinja_var"');
                        if (closedTimeStr) {
                            const closedTime = parseInt(closedTimeStr);
                            const elapsedDays = (Date.now() - closedTime) / (1000 * 60 * 60 * 24);
                            if (elapsedDays >= resetDays) {
                                // Đã hết thời gian chờ, hiện lại banner
                                localStorage.removeItem('rules_accepted_' + '"jinja_var"');
                                setTimeout(showRulesModal, 1200);
                            }
                        } else {
                            setTimeout(showRulesModal, 1200);
                        }
                    } else {
                        setTimeout(showRulesModal, 1200);
                    }
                } else {
                    // Mặc định: version (chỉ hiện 1 lần theo phiên bản)
                    const isAccepted = localStorage.getItem('rules_accepted_' + '"jinja_var"');
                    if (!isAccepted) {
                        setTimeout(showRulesModal, 1200);
                    }
                }
            }
        });
    
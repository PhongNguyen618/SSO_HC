
                function confirmOAuthLink(authUrl, athleteName) {
                    const msg = `⚠️ XÁC NHẬN LIÊN KẾT TÀI KHOẢN STRAVA\n\n` +
                                `Bạn đang thực hiện liên kết Strava cho VĐV:\n` +
                                `• Họ và Tên: ${athleteName}\n\n` +
                                `ĐÂY CÓ ĐÚNG LÀ TÀI KHOẢN CỦA BẠN KHÔNG?\n` +
                                `Nếu không phải bạn, vui lòng bấm HỦY và chọn đúng tên mình để tránh làm mất dữ liệu của người khác.`;
                                
                    if (confirm(msg)) {
                        window.location.href = authUrl;
                    }
                }
            
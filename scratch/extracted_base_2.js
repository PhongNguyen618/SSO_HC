
        document.addEventListener('DOMContentLoaded', () => {
            const floatingSupportBtn = document.getElementById('floatingSupportBtn');
            const supportFeedbackModal = document.getElementById('supportFeedbackModal');
            const closeSupportModalBtn = document.getElementById('closeSupportModalBtn');
            const cancelSupportModalBtn = document.getElementById('cancelSupportModalBtn');
            const supportFeedbackForm = document.getElementById('supportFeedbackForm');
            const supportFormMsg = document.getElementById('supportFormMsg');

            if (floatingSupportBtn && supportFeedbackModal) {
                floatingSupportBtn.addEventListener('click', () => {
                    supportFeedbackModal.classList.add('active');
                    document.body.style.overflow = 'hidden';
                    supportFormMsg.style.display = 'none';
                    supportFeedbackForm.reset();
                });

                const closeSupport = () => {
                    supportFeedbackModal.classList.remove('active');
                    document.body.style.overflow = '';
                };

                if (closeSupportModalBtn) closeSupportModalBtn.addEventListener('click', closeSupport);
                if (cancelSupportModalBtn) cancelSupportModalBtn.addEventListener('click', closeSupport);

                // Close on clicking outside modal content
                supportFeedbackModal.addEventListener('click', (e) => {
                    if (e.target === supportFeedbackModal) {
                        closeSupport();
                    }
                });

                if (supportFeedbackForm) {
                    supportFeedbackForm.addEventListener('submit', async (e) => {
                        e.preventDefault();
                        supportFormMsg.style.display = 'none';
                        
                        const name = document.getElementById('supportAthleteName').value.trim();
                        const contact = document.getElementById('supportContactInfo').value.trim();
                        const content = document.getElementById('supportContent').value.trim();
                        
                        if (!content) {
                            supportFormMsg.className = 'support-form-msg error';
                            supportFormMsg.textContent = 'Vui lòng nhập nội dung phản hồi.';
                            supportFormMsg.style.display = 'block';
                            return;
                        }
                        
                        const submitBtn = document.getElementById('submitSupportBtn');
                        const originalBtnContent = submitBtn.innerHTML;
                        submitBtn.disabled = true;
                        submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Đang gửi...';
                        
                        try {
                            const response = await fetch('/api/support', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json'
                                },
                                body: JSON.stringify({
                                    athlete_name: name,
                                    contact_info: contact,
                                    content: content
                                })
                            });
                            
                            const result = await response.json();
                            if (response.ok && result.status === 'success') {
                                supportFormMsg.className = 'support-form-msg success';
                                supportFormMsg.textContent = result.message || 'Gửi phản hồi thành công!';
                                supportFormMsg.style.display = 'block';
                                supportFeedbackForm.reset();
                                
                                // Tự động đóng sau 2s
                                setTimeout(closeSupport, 2000);
                            } else {
                                supportFormMsg.className = 'support-form-msg error';
                                supportFormMsg.textContent = result.message || 'Gửi phản hồi thất bại. Vui lòng thử lại.';
                                supportFormMsg.style.display = 'block';
                            }
                        } catch (err) {
                            supportFormMsg.className = 'support-form-msg error';
                            supportFormMsg.textContent = 'Có lỗi kết nối mạng. Vui lòng kiểm tra lại đường truyền.';
                            supportFormMsg.style.display = 'block';
                        } finally {
                            submitBtn.disabled = false;
                            submitBtn.innerHTML = originalBtnContent;
                        }
                    });
                }
            }
        });
    
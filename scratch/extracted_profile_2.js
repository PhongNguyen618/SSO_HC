
    // Set progress bar width on load
    window.addEventListener('DOMContentLoaded', () => {
        setTimeout(() => {
            document.getElementById('awardProgressBar').style.width = '"jinja_var"%';
        }, 100);
    });

    // --- CHART.JS VISUALIZATION LOGIC ---

    // 1. Line Chart: KCAL Trend
    const kcalCtx = document.getElementById('kcalChart').getContext('2d');
    const kcalDates = "jinja_var";
    const kcalValues = "jinja_var";

    new Chart(kcalCtx, {
        type: 'line',
        data: {
            labels: kcalDates,
            datasets: [{
                label: '"jinja_var"',
                data: kcalValues,
                borderColor: '#8FCDF0',
                backgroundColor: 'rgba(143, 205, 240, 0.15)',
                borderWidth: 2,
                fill: true,
                tension: 0.3,
                pointBackgroundColor: '#F9BFBE',
                pointHoverRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                x: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#9f9cb2'
                    }
                },
                y: {
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#9f9cb2'
                    }
                }
            }
        }
    });

    // 2. Doughnut Chart: Sport Type Distribution
    const sportCtx = document.getElementById('sportChart').getContext('2d');
    const sportLabels = "jinja_var";
    const sportDists = "jinja_var";

    if (sportLabels.length > 0) {
        new Chart(sportCtx, {
            type: 'doughnut',
            data: {
                labels: sportLabels,
                datasets: [{
                    data: sportDists,
                    backgroundColor: [
                        '#8FCDF0',
                        '#F9BFBE',
                        '#94B5DE',
                        '#B8E4FA',
                        '#F48E91',
                        '#FCE7E5'
                    ],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#9f9cb2',
                            boxWidth: 12,
                            padding: 15,
                            font: {
                                size: 11
                            }
                        }
                    }
                }
            }
        });
    } else {
        // Draw empty indicator text inside canvas area
        sportCtx.font = "14px Inter";
        sportCtx.fillStyle = "#9f9cb2";
        sportCtx.textAlign = "center";
        sportCtx.fillText("Không có dữ liệu quãng đường", 150, 125);
    }

    // Hàm xóa hoạt động cho Admin
    function deleteActivity(activityId) {
        if (!confirm("Bạn có chắc chắn muốn xóa hoạt động này? Hành động này sẽ loại bỏ vĩnh viễn dữ liệu hoạt động khỏi cơ sở dữ liệu và không thể khôi phục.")) {
            return;
        }
        
        fetch(`/admin/activity/delete/${activityId}`, {
            method: 'POST'
        })
        .then(response => {
            if (response.status === 401) {
                alert("Bạn không có quyền Admin hoặc phiên đăng nhập đã hết hạn!");
                return;
            }
            return response.json();
        })
        .then(data => {
            if (data && data.status === 'success') {
                alert("Đã xóa hoạt động thành công!");
                window.location.reload();
            } else {
                alert("Lỗi khi xóa hoạt động: " + (data ? data.error : "Không rõ nguyên nhân"));
            }
        })
        .catch(err => {
            alert("Lỗi hệ thống: " + err.message);
        });
    }

    // --- LOGIC MODAL CẬP NHẬT AVATAR ---
    function openAvatarModal() {
        document.getElementById('avatarModal').style.display = 'flex';
    }

    function closeAvatarModal() {
        document.getElementById('avatarModal').style.display = 'none';
    }

    function triggerDirectUpload() {
        document.getElementById('directAvatarInput').click();
    }

    function handleDirectUpload(event) {
        const file = event.target.files[0];
        if (!file) return;
        
        if (!file.type.startsWith('image/')) {
            alert('Vui lòng chọn file ảnh hợp lệ (PNG, JPG, JPEG, WEBP).');
            return;
        }
        
        // Đóng modal và báo hiệu đang xử lý
        closeAvatarModal();
        
        const formData = new FormData();
        formData.append('athlete_id', ""jinja_var"");
        formData.append('file', file);
        
        // Gọi API tải ảnh trực tiếp
        fetch('/api/avatar/upload-direct', {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data && data.status === 'success') {
                alert('🎉 Cập nhật ảnh đại diện trực tiếp thành công!');
                window.location.reload();
            } else {
                alert('Lỗi cập nhật ảnh đại diện: ' + (data ? data.message : 'Không rõ nguyên nhân'));
            }
        })
        .catch(err => {
            alert('Lỗi hệ thống: ' + err.message);
        });
    }

    // --- LOGIC LIGHTBOX XEM ẢNH ĐẠI DIỆN ---
    function openAvatarLightbox() {
        const lightbox = document.getElementById('avatarLightboxModal');
        if (lightbox) {
            lightbox.style.display = 'flex';
            document.body.style.overflow = 'hidden';
        }
    }

    function closeAvatarLightbox() {
        const lightbox = document.getElementById('avatarLightboxModal');
        if (lightbox) {
            lightbox.style.display = 'none';
            document.body.style.overflow = '';
        }
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeAvatarModal();
            closeAvatarLightbox();
        }
    });

    // --- LOGIC HỦY LIÊN KẾT CHỦ ĐỘNG ---
    function confirmSelfUnlink() {
        if (!confirm("Bạn có chắc chắn muốn hủy liên kết tài khoản Strava cá nhân hiện tại? \nHành động này sẽ ngắt kết nối đồng bộ và dọn dẹp các hoạt động API hiện tại của bạn.")) {
            return;
        }
        
        // Tạo một Form ảo để submit POST request lên endpoint unlink
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/profile/"jinja_var"/unlink';
        document.body.appendChild(form);
        form.submit();
    }

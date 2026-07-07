
    // --- KHAI BÁO BIẾN TOÀN CỤC ---
    const canvas = document.getElementById('avatarCanvas');
    const ctx = canvas.getContext('2d');
    
    // Tạo canvas phụ trong bộ nhớ để phục vụ đục lỗ động ở client
    const offCanvas = document.createElement('canvas');
    offCanvas.width = canvas.width;
    offCanvas.height = canvas.height;
    const offCtx = offCanvas.getContext('2d');
    
    // Khung viền mặc định tải từ Server (ưu tiên ảnh thô raw chưa đục lỗ để đục lỗ động ở client)
    const frameImg = new Image();
    frameImg.crossOrigin = "anonymous";
    frameImg.src = ""jinja_var"";
    
    // Fallback nếu ảnh raw bị lỗi (chưa có file thô raw do nâng cấp hệ thống cũ)
    frameImg.onerror = function() {
        if (frameImg.src.indexOf('frame_raw.png') !== -1) {
            console.log("Không tìm thấy file frame_raw.png, tự động chuyển về fallback dùng file frame.png đã đục sẵn ở tâm.");
            frameImg.src = ""jinja_var"";
        }
    };
    
    // Ảnh người dùng tải lên
    let userImg = null;
    
    // Lưu trữ ảnh gốc và ảnh đã tách nền để chuyển đổi qua lại nhanh chóng
    let originalImageSrc = null;
    let noBgImageSrc = null;
    let currentImageFile = null;
    
    // Các tham số biến đổi ảnh của người dùng (avatar)
    let scale = 1.0;
    let rotation = 0; // Độ (0 - 360)
    let offsetX = 0;  // Dịch chuyển X so với tâm
    let offsetY = 0;  // Dịch chuyển Y so với tâm
    let brightness = 100; // Độ sáng (%)
    let contrast = 100;   // Độ tương phản (%)
    let isFlipped = false; // Trạng thái lật ngang
    
    // Các tham số hình tròn đục lỗ của khung viền (lớp trên)
    let holeScale = 0.65;
    let holeOffsetX = 0;
    let holeOffsetY = 0;
    let holeFeather = 40;
    
    // Trạng thái kéo thả ảnh (Pan) trên canvas
    let isDragging = false;
    let startX = 0;
    let startY = 0;
    
    // ID vận động viên được chọn
    let isUserBgRemoved = false;
    let selectedAthleteId = null;
    
    // --- HÀM VẼ CANVAS CHÍNH ---
    function drawCanvas() {
        // 1. Xóa sạch canvas chính
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;
        
        // Tính toán vị trí và bán kính của hình tròn đục lỗ động
        const holeX = centerX + holeOffsetX;
        const holeY = centerY + holeOffsetY;
        const holeRadius = (canvas.width / 2) * holeScale;
        
        // Độ rộng vùng làm mờ viền (feather) lấy từ biến toàn cục holeFeather
        const feather = holeFeather;
        
        // 2. Vẽ ảnh người dùng (avatar) ở lớp dưới trước (chỉ vẽ và clip sát rìa ngoài khung viền tròn)
        if (userImg) {
            ctx.save(); // [1] Lưu trạng thái để clip tròn ngoài
            
            // Clip sát rìa canvas để tránh avatar bị thò ra ngoài 4 góc của khung viền tròn
            const clipRadius = canvas.width * 0.485;
            ctx.beginPath();
            ctx.arc(centerX, centerY, clipRadius, 0, Math.PI * 2);
            ctx.clip();
            
            ctx.save(); // [2] Lưu trạng thái để dịch chuyển/xoay/lật avatar của người dùng
            // Tịnh tiến tọa độ vẽ theo vị trí kéo thả của avatar (offsetX, offsetY)
            ctx.translate(centerX + offsetX, centerY + offsetY);
            ctx.rotate((rotation * Math.PI) / 180);
            
            // Áp dụng phép lật ngang nếu được kích hoạt
            if (isFlipped) {
                ctx.scale(-1, 1);
            }
            
            // Áp dụng bộ lọc ảnh (Độ sáng & Độ tương phản) trực tiếp trên canvas
            ctx.filter = `brightness(${brightness}%) contrast(${contrast}%)`;
            
            // Tính toán kích thước hiển thị ảnh
            const drawDiameter = canvas.width * 0.7;
            let drawWidth, drawHeight;
            const imgRatio = userImg.width / userImg.height;
            
            if (userImg.width > userImg.height) {
                drawHeight = drawDiameter * scale;
                drawWidth = drawHeight * imgRatio;
            } else {
                drawWidth = drawDiameter * scale;
                drawHeight = drawWidth / imgRatio;
            }
            
            // Vẽ ảnh người dùng vào tâm đã dịch chuyển
            ctx.drawImage(
                userImg,
                -drawWidth / 2, -drawHeight / 2,
                drawWidth, drawHeight
            );
            
            ctx.restore(); // [2] Giải phóng dịch chuyển/xoay/lật
            ctx.filter = 'none';
            
            // ĐÃ LOẠI BỎ: Đường stroke đen Inner Shadow thô kệch làm hỏng sự liền mạch.
            // Hai lớp ảnh avatar và frame giờ đây sẽ tự động hòa quyện trực tiếp và mượt mà.
            
            ctx.restore(); // [1] Giải phóng clip tròn ngoài
        }
        
        // 3. Vẽ khung viền (Frame) ĐÈ LÊN PHÍA TRÊN CÙNG bằng Canvas phụ đã được đục lỗ mờ viền (feather)
        if (frameImg.complete) {
            // Xóa sạch canvas phụ
            offCtx.clearRect(0, 0, offCanvas.width, offCanvas.height);
            // Vẽ khung viền thô lên canvas phụ
            offCtx.drawImage(frameImg, 0, 0, offCanvas.width, offCanvas.height);
            
            // Đảm bảo bán kính trong của Radial Gradient không bao giờ âm
            const innerRadius = Math.max(0, holeRadius - feather);
            const outerRadius = holeRadius + feather;
            
            // Tạo Radial Gradient để đục lỗ mờ viền
            const grad = offCtx.createRadialGradient(
                holeX, holeY, innerRadius,
                holeX, holeY, outerRadius
            );
            grad.addColorStop(0, 'rgba(0, 0, 0, 1.0)'); // Đục thủng hoàn toàn ở lòng trong
            grad.addColorStop(1, 'rgba(0, 0, 0, 0.0)'); // Giữ nguyên khung viền ở ngoài
            
            // Đục lỗ bằng destination-out. Vẽ một hình chữ nhật phủ toàn canvas phụ để tránh hiện tượng răng cưa anti-aliasing.
            offCtx.save();
            offCtx.globalCompositeOperation = 'destination-out';
            offCtx.fillStyle = grad;
            offCtx.beginPath();
            offCtx.rect(0, 0, offCanvas.width, offCanvas.height);
            offCtx.fill();
            offCtx.restore();
            
            // Vẽ canvas phụ đã đục lỗ đè lên canvas chính
            ctx.drawImage(offCanvas, 0, 0);
        }
        
        // 4. Nếu chưa có ảnh người dùng, vẽ thông báo hướng dẫn đè lên trên cùng để dễ đọc
        if (!userImg) {
            ctx.save();
            ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
            ctx.beginPath();
            ctx.arc(holeX, holeY, holeRadius * 0.9, 0, Math.PI * 2);
            ctx.fill();
            
            ctx.fillStyle = '#ffffff';
            ctx.font = 'bold 36px Be Vietnam Pro, Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('TẢI ẢNH CỦA BẠN', holeX, holeY - 15);
            ctx.font = '24px Be Vietnam Pro, Inter, sans-serif';
            ctx.fillText('Ảnh sẽ hiển thị trên khung này', holeX, holeY + 30);
            ctx.restore();
        }
    }
    
    // Khi frame load xong, vẽ lại canvas
    frameImg.onload = drawCanvas;
    
    // --- XỬ LÝ SỰ KIỆN UPLOAD ẢNH ---
    const uploadZone = document.getElementById('uploadZone');
    const fileInput = document.getElementById('avatarFileInput');
    
    uploadZone.addEventListener('click', () => fileInput.click());
    
    // Drag and drop events
    uploadZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadZone.classList.add('dragover');
    });
    
    uploadZone.addEventListener('dragleave', () => {
        uploadZone.classList.remove('dragover');
    });
    
    uploadZone.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadZone.classList.remove('dragover');
        if (e.dataTransfer.files.length > 0) {
            handleImageFile(e.dataTransfer.files[0]);
        }
    });
    
    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleImageFile(e.target.files[0]);
        }
    });
    
    function handleImageFile(file) {
        if (!file.type.startsWith('image/')) {
            showAlert('danger', 'Vui lòng chọn file ảnh hợp lệ (PNG, JPG, JPEG).');
            return;
        }
        
        currentImageFile = file;
        originalImageSrc = null;
        noBgImageSrc = null;
        
        // 1. Đọc file ảnh gốc dưới dạng DataURL để lưu trữ trước
        const reader = new FileReader();
        reader.onload = function(e) {
            originalImageSrc = e.target.result;
            
            // 2. Kiểm tra trạng thái của switch Tách nền AI
            const isRemoveBgEnabled = document.getElementById('toggleRemoveBg').checked;
            if (isRemoveBgEnabled) {
                // Tiến hành gọi API xóa nền
                removeBgAndLoad(file);
            } else {
                // Không tách nền -> Load trực tiếp ảnh gốc
                showAlert('info', 'Đã tải ảnh gốc lên thành công (Không tách nền).');
                loadUserImage(originalImageSrc, false);
            }
        };
        reader.readAsDataURL(file);
    }
    
    // Gọi API xóa nền và hiển thị kết quả
    function removeBgAndLoad(file) {
        showAlert('info', '<i class="fa-solid fa-spinner fa-spin"></i> Đang tự động tách nền ảnh chân dung bằng AI, vui lòng đợi trong giây lát...');
        
        const formData = new FormData();
        formData.append('file', file);
        
        fetch('/api/avatar/remove-bg', {
            method: 'POST',
            body: formData
        })
        .then(res => {
            if (!res.ok) {
                throw new Error('Mã lỗi ' + res.status);
            }
            return res.blob();
        })
        .then(blob => {
            // Tách nền thành công, tạo URL blob ảnh PNG trong suốt
            noBgImageSrc = URL.createObjectURL(blob);
            
            // Kiểm tra xem lúc load xong người dùng có tắt switch giữa chừng không
            if (document.getElementById('toggleRemoveBg').checked) {
                loadUserImage(noBgImageSrc, true);
            } else {
                if (originalImageSrc) {
                    loadUserImage(originalImageSrc, false);
                }
            }
        })
        .catch(err => {
            console.error('Lỗi xóa nền:', err);
            // Fallback: Sử dụng ảnh gốc nếu xóa nền bị lỗi
            showAlert('warning', '<i class="fa-solid fa-triangle-exclamation"></i> Không thể tách nền tự động (Lỗi: ' + err.message + '). Hệ thống sẽ chuyển sang sử dụng ảnh gốc của bạn.');
            if (originalImageSrc) {
                loadUserImage(originalImageSrc, false);
            }
        });
    }
    
    // Đăng ký sự kiện thay đổi trạng thái Switch Tách nền
    document.getElementById('toggleRemoveBg').addEventListener('change', function() {
        if (!currentImageFile) return;
        
        if (this.checked) {
            // Chuyển sang BẬT tách nền
            if (noBgImageSrc) {
                loadUserImage(noBgImageSrc, true);
            } else {
                removeBgAndLoad(currentImageFile);
            }
        } else {
            // Chuyển sang TẮT tách nền -> Sử dụng ảnh gốc
            if (originalImageSrc) {
                loadUserImage(originalImageSrc, false);
            }
        }
    });
    
    // Hàm phụ để load ảnh vào đối tượng userImg
    function loadUserImage(src, isBgRemoved) {
        userImg = new Image();
        userImg.onload = function() {
            isUserBgRemoved = isBgRemoved;
            // Reset các thanh trượt và toạ độ khi tải ảnh mới
            scale = 1.0;
            rotation = 0;
            offsetX = 0;
            offsetY = 0;
            brightness = 100;
            contrast = 100;
            isFlipped = false;
            
            // Reset các cấu hình lỗ đục động về mặc định
            holeScale = 0.65;
            holeOffsetX = 0;
            holeOffsetY = 0;
            holeFeather = 40;
            
            document.getElementById('zoomSlider').value = 1.0;
            document.getElementById('zoomVal').innerText = '1.00x';
            document.getElementById('rotateSlider').value = 0;
            document.getElementById('rotateVal').innerText = '0°';
            document.getElementById('brightnessSlider').value = 100;
            document.getElementById('brightnessVal').innerText = '100%';
            document.getElementById('contrastSlider').value = 100;
            document.getElementById('contrastVal').innerText = '100%';
            
            document.getElementById('holeScaleSlider').value = 0.65;
            document.getElementById('holeScaleVal').innerText = '65%';
            document.getElementById('holeOffsetXSlider').value = 0;
            document.getElementById('holeOffsetXVal').innerText = '0px';
            document.getElementById('holeOffsetYSlider').value = 0;
            document.getElementById('holeOffsetYVal').innerText = '0px';
            document.getElementById('holeFeatherSlider').value = 40;
            document.getElementById('holeFeatherVal').innerText = '40px';
            
            drawCanvas();
            if (isBgRemoved) {
                showAlert('success', '🎉 Đã tự động tách nền ảnh chân dung thành công! Bạn có thể bắt đầu căn chỉnh ghép khung viền.');
            }
        };
        userImg.src = src;
    }
    
    // --- XỬ LÝ CÁC SLIDER ĐIỀU KHIỂN ---
    const zoomSlider = document.getElementById('zoomSlider');
    zoomSlider.addEventListener('input', (e) => {
        scale = parseFloat(e.target.value);
        document.getElementById('zoomVal').innerText = scale.toFixed(2) + 'x';
        drawCanvas();
    });
    
    const rotateSlider = document.getElementById('rotateSlider');
    rotateSlider.addEventListener('input', (e) => {
        rotation = parseInt(e.target.value);
        document.getElementById('rotateVal').innerText = rotation + '°';
        drawCanvas();
    });

    const brightnessSlider = document.getElementById('brightnessSlider');
    brightnessSlider.addEventListener('input', (e) => {
        brightness = parseInt(e.target.value);
        document.getElementById('brightnessVal').innerText = brightness + '%';
        drawCanvas();
    });

    const contrastSlider = document.getElementById('contrastSlider');
    contrastSlider.addEventListener('input', (e) => {
        contrast = parseInt(e.target.value);
        document.getElementById('contrastVal').innerText = contrast + '%';
        drawCanvas();
    });

    // Các sự kiện cho slider Lỗ Đục động
    const holeScaleSlider = document.getElementById('holeScaleSlider');
    holeScaleSlider.addEventListener('input', (e) => {
        holeScale = parseFloat(e.target.value);
        document.getElementById('holeScaleVal').innerText = Math.round(holeScale * 100) + '%';
        drawCanvas();
    });

    const holeOffsetXSlider = document.getElementById('holeOffsetXSlider');
    holeOffsetXSlider.addEventListener('input', (e) => {
        holeOffsetX = parseInt(e.target.value);
        document.getElementById('holeOffsetXVal').innerText = holeOffsetX + 'px';
        drawCanvas();
    });

    const holeOffsetYSlider = document.getElementById('holeOffsetYSlider');
    holeOffsetYSlider.addEventListener('input', (e) => {
        holeOffsetY = parseInt(e.target.value);
        document.getElementById('holeOffsetYVal').innerText = holeOffsetY + 'px';
        drawCanvas();
    });

    const holeFeatherSlider = document.getElementById('holeFeatherSlider');
    holeFeatherSlider.addEventListener('input', (e) => {
        holeFeather = parseInt(e.target.value);
        document.getElementById('holeFeatherVal').innerText = holeFeather + 'px';
        drawCanvas();
    });

    // --- NÚT HÀNH ĐỘNG NHANH ---
    // Nút Lật ảnh
    document.getElementById('flipBtn').addEventListener('click', () => {
        if (!userImg) {
            showAlert('danger', 'Vui lòng tải ảnh chân dung lên trước khi lật ảnh.');
            return;
        }
        isFlipped = !isFlipped;
        drawCanvas();
    });

    // Nút Reset
    document.getElementById('resetBtn').addEventListener('click', () => {
        if (!userImg) return;
        
        scale = 1.0;
        rotation = 0;
        offsetX = 0;
        offsetY = 0;
        brightness = 100;
        contrast = 100;
        isFlipped = false;
        
        holeScale = 0.65;
        holeOffsetX = 0;
        holeOffsetY = 0;
        holeFeather = 40;
        
        document.getElementById('zoomSlider').value = 1.0;
        document.getElementById('zoomVal').innerText = '1.00x';
        document.getElementById('rotateSlider').value = 0;
        document.getElementById('rotateVal').innerText = '0°';
        document.getElementById('brightnessSlider').value = 100;
        document.getElementById('brightnessVal').innerText = '100%';
        document.getElementById('contrastSlider').value = 100;
        document.getElementById('contrastVal').innerText = '100%';
        
        document.getElementById('holeScaleSlider').value = 0.65;
        document.getElementById('holeScaleVal').innerText = '65%';
        document.getElementById('holeOffsetXSlider').value = 0;
        document.getElementById('holeOffsetXVal').innerText = '0px';
        document.getElementById('holeOffsetYSlider').value = 0;
        document.getElementById('holeOffsetYVal').innerText = '0px';
        document.getElementById('holeFeatherSlider').value = 40;
        document.getElementById('holeFeatherVal').innerText = '40px';
        
        drawCanvas();
        showAlert('success', 'Đã khôi phục các thông số chỉnh ảnh về mặc định.');
    });
    
    // --- THAO TÁC KÉO THẢ (PAN/DRAG) TRÊN CANVAS ---
    // Lấy tọa độ chuột/chạm tương đối trong canvas
    function getEventCoords(e) {
        const rect = canvas.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const clientY = e.touches ? e.touches[0].clientY : e.clientY;
        
        // Quy đổi tỉ lệ vì kích thước hiển thị CSS (330x330) khác kích thước thật của canvas (1200x1200)
        return {
            x: ((clientX - rect.left) / rect.width) * canvas.width,
            y: ((clientY - rect.top) / rect.height) * canvas.height
        };
    }
    
    function startDrag(e) {
        if (!userImg) return;
        isDragging = true;
        const coords = getEventCoords(e);
        startX = coords.x - offsetX;
        startY = coords.y - offsetY;
        e.preventDefault();
    }
    
    function drag(e) {
        if (!isDragging || !userImg) return;
        const coords = getEventCoords(e);
        offsetX = coords.x - startX;
        offsetY = coords.y - startY;
        
        // Giới hạn giá trị tịnh tiến của avatar
        offsetX = Math.max(-800, Math.min(800, offsetX));
        offsetY = Math.max(-800, Math.min(800, offsetY));
        
        drawCanvas();
        e.preventDefault();
    }
    
    function stopDrag() {
        isDragging = false;
    }
    
    // Sự kiện chuột
    canvas.addEventListener('mousedown', startDrag);
    window.addEventListener('mousemove', drag);
    window.addEventListener('mouseup', stopDrag);
    
    // Sự kiện cảm ứng (cho điện thoại di động)
    canvas.addEventListener('touchstart', startDrag);
    canvas.addEventListener('touchmove', drag, { passive: false });
    canvas.addEventListener('touchend', stopDrag);
    
    // --- XỬ LÝ DOWNLOAD ẢNH ---
    document.getElementById('downloadBtn').addEventListener('click', () => {
        if (!userImg) {
            showAlert('danger', 'Vui lòng tải ảnh chân dung của bạn lên trước khi tải ảnh ghép về.');
            return;
        }
        
        // Trích xuất ảnh định dạng PNG nền trong suốt
        const dataUrl = canvas.toDataURL('image/png');
        
        const link = document.createElement('a');
        link.download = 'avatar_kyle_niem.png';
        link.href = dataUrl;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        showAlert('success', 'Đã xuất và tải ảnh ghép chất lượng cao về máy của bạn!');
    });
    
    
    // --- XỬ LÝ SEARCHABLE SELECT DROP-DOWN VĐV ---
    const searchInput = document.getElementById('athleteSearchInput');
    const resultsList = document.getElementById('searchResultsList');
    const badge = document.getElementById('selectedAthleteBadge');
    const badgeName = document.getElementById('selectedAthleteName');
    const badgeDept = document.getElementById('selectedAthleteDept');
    const searchWrapper = document.getElementById('searchDropdownWrapper');
    const syncBtn = document.getElementById('syncProfileBtn');
    
    // Tự động chọn VĐV nếu có athlete_id trên URL query parameter
    const urlParams = new URLSearchParams(window.location.search);
    const initialAthleteId = urlParams.get('athlete_id');
    if (initialAthleteId) {
        const item = resultsList.querySelector(`.search-result-item[data-id="${initialAthleteId}"]`);
        if (item) {
            selectedAthleteId = initialAthleteId;
            const name = item.getAttribute('data-name');
            const dept = item.getAttribute('data-dept');
            
            badgeName.innerText = name;
            badgeDept.innerText = dept;
            badge.style.display = 'flex';
            searchWrapper.style.display = 'none';
            resultsList.style.display = 'none';
            
            syncBtn.disabled = false;
            syncBtn.classList.remove('btn-secondary');
            syncBtn.classList.add('btn-primary');
        }
    }
    
    // Hiển thị danh sách kết quả khi focus vào input tìm kiếm
    searchInput.addEventListener('focus', () => {
        filterAthletes();
        resultsList.style.display = 'block';
    });
    
    // Tự động đóng dropdown khi click ra ngoài
    document.addEventListener('click', (e) => {
        if (!searchWrapper.contains(e.target) && e.target !== searchInput) {
            resultsList.style.display = 'none';
        }
    });
    
    // Tìm kiếm và lọc tên VĐV khi gõ
    searchInput.addEventListener('input', filterAthletes);
    
    function filterAthletes() {
        const query = searchInput.value.toLowerCase().trim();
        const items = resultsList.getElementsByClassName('search-result-item');
        let visibleCount = 0;
        
        for (let item of items) {
            const name = item.getAttribute('data-name').toLowerCase();
            const dept = item.getAttribute('data-dept').toLowerCase();
            
            if (name.includes(query) || dept.includes(query)) {
                item.style.display = 'flex';
                visibleCount++;
            } else {
                item.style.display = 'none';
            }
        }
        
        // Hiện dropdown nếu có kết quả lọc
        resultsList.style.display = visibleCount > 0 ? 'block' : 'none';
    }
    
    // Xử lý khi click chọn một VĐV từ danh sách
    resultsList.addEventListener('click', (e) => {
        const item = e.target.closest('.search-result-item');
        if (!item) return;
        
        selectedAthleteId = item.getAttribute('data-id');
        const name = item.getAttribute('data-name');
        const dept = item.getAttribute('data-dept');
        
        // Cập nhật giao diện hiển thị VĐV đã chọn
        badgeName.innerText = name;
        badgeDept.innerText = dept;
        badge.style.display = 'flex';
        searchWrapper.style.display = 'none';
        resultsList.style.display = 'none';
        
        // Kích hoạt nút Cập nhật
        syncBtn.disabled = false;
        syncBtn.classList.remove('btn-secondary');
        syncBtn.classList.add('btn-primary');
    });
    
    // Nút hủy chọn VĐV để chọn lại
    document.getElementById('btnRemoveAthlete').addEventListener('click', () => {
        selectedAthleteId = null;
        badge.style.display = 'none';
        searchWrapper.style.display = 'block';
        searchInput.value = '';
        searchInput.focus();
        
        // Vô hiệu hóa nút Cập nhật
        syncBtn.disabled = true;
        syncBtn.classList.remove('btn-primary');
        syncBtn.classList.add('btn-secondary');
    });
    
    // --- XỬ LÝ POST ĐỒNG BỘ AVATAR LÊN HỒ SƠ ---
    syncBtn.addEventListener('click', () => {
        if (!userImg) {
            showAlert('danger', 'Vui lòng tải ảnh chân dung của bạn lên trước khi cập nhật hồ sơ.');
            return;
        }
        if (!selectedAthleteId) {
            showAlert('danger', 'Vui lòng tìm và chọn đúng họ tên của bạn trong danh sách trước.');
            return;
        }
        
        // Vô hiệu hoá nút trong quá trình xử lý gửi API
        syncBtn.disabled = true;
        syncBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đồng bộ...';
        
        // Lấy ảnh dạng Base64 từ Canvas định dạng PNG nền trong suốt
        const dataUrl = canvas.toDataURL('image/png');
        
        // Gửi dữ liệu dưới dạng JSON payload thay vì Form Data để tránh giới hạn kích thước 1024KB của multipart
        fetch('/api/avatar/sync-profile', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                athlete_id: parseInt(selectedAthleteId),
                image_data: dataUrl
            })
        })
        .then(res => {
            if (!res.ok) {
                console.error('Server error status:', res.status);
            }
            return res.json();
        })
        .then(data => {
            if (data && data.status === 'success') {
                showAlert('success', '🎉 Chúc mừng! Ảnh đại diện của bạn đã được cập nhật thành công lên Bảng xếp hạng và Trang cá nhân.');
                // Cuộn trang lên đầu để xem thông báo thành công
                window.scrollTo({ top: 0, behavior: 'smooth' });
                
                // Tự động redirect về trang cá nhân sau 2.5 giây nếu có athlete_id trên URL
                const currentParams = new URLSearchParams(window.location.search);
                const athId = currentParams.get('athlete_id');
                if (athId) {
                    setTimeout(() => {
                        window.location.href = '/profile/' + athId;
                    }, 2500);
                }
            } else {
                let errorMsg = 'Không rõ lỗi.';
                if (data) {
                    if (data.message) {
                        errorMsg = data.message;
                    } else if (data.detail) {
                        errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
                    } else {
                        errorMsg = JSON.stringify(data);
                    }
                }
                showAlert('danger', 'Lỗi đồng bộ hồ sơ: ' + errorMsg);
            }
        })
        .catch(err => {
            console.error('Fetch error:', err);
            showAlert('danger', 'Lỗi hệ thống khi gửi dữ liệu: ' + err.message);
        })
        .finally(() => {
            syncBtn.disabled = false;
            syncBtn.innerHTML = '<i class="fa-solid fa-arrows-spin"></i> Cập nhật vào hồ sơ giải chạy';
        });
    });
    
    // --- HÀM TIỆN ÍCH HIỂN THỊ ALERT THÔNG BÁO ---
    function showAlert(type, message) {
        const alertEl = document.getElementById('statusAlert');
        alertEl.className = `alert alert-${type}`;
        alertEl.innerHTML = `<i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> <div>${message}</div>`;
        alertEl.style.display = 'flex';
        // Tự cuộn nhẹ đến thông báo nếu ở dưới
        alertEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }
    


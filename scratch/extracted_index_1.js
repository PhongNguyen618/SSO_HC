
    // --- PAST EVENTS CAROUSEL SCROLLING & AUTO-PLAY LOGIC ---
    let autoScrollInterval = null;
    let isMouseOverCarousel = false;
    
    function scrollCarousel(direction) {
        const carousel = document.getElementById('pastEventsCarousel');
        if (carousel) {
            carousel.scrollBy({ left: direction * 300, behavior: 'smooth' });
            resetAutoScrollTimer();
        }
    }
    
    function startAutoScroll() {
        stopAutoScroll();
        autoScrollInterval = setInterval(() => {
            if (isMouseOverCarousel) return;
            
            const carousel = document.getElementById('pastEventsCarousel');
            if (carousel) {
                const scrollLeft = carousel.scrollLeft;
                const maxScrollLeft = carousel.scrollWidth - carousel.clientWidth;
                
                if (maxScrollLeft <= 0) return;
                
                if (scrollLeft >= maxScrollLeft - 10) {
                    carousel.scrollTo({ left: 0, behavior: 'smooth' });
                } else {
                    carousel.scrollBy({ left: 300, behavior: 'smooth' });
                }
            }
        }, 4000); // Tự động trượt sau mỗi 4 giây
    }
    
    function stopAutoScroll() {
        if (autoScrollInterval) {
            clearInterval(autoScrollInterval);
            autoScrollInterval = null;
        }
    }
    
    function resetAutoScrollTimer() {
        startAutoScroll();
    }
    
    function checkCarouselScroll() {
        const carousel = document.getElementById('pastEventsCarousel');
        const prevBtn = document.querySelector('.carousel-nav-btn.prev');
        const nextBtn = document.querySelector('.carousel-nav-btn.next');
        if (carousel && prevBtn && nextBtn) {
            const scrollLeft = carousel.scrollLeft;
            const maxScrollLeft = carousel.scrollWidth - carousel.clientWidth;
            
            if (carousel.scrollWidth <= carousel.clientWidth) {
                prevBtn.classList.remove('visible');
                nextBtn.classList.remove('visible');
                return;
            }
            
            if (scrollLeft > 5) {
                prevBtn.classList.add('visible');
            } else {
                prevBtn.classList.remove('visible');
            }
            
            if (scrollLeft < maxScrollLeft - 5) {
                nextBtn.classList.add('visible');
            } else {
                nextBtn.classList.remove('visible');
            }
        }
    }
    
    window.addEventListener('DOMContentLoaded', () => {
        const carousel = document.getElementById('pastEventsCarousel');
        const wrapper = document.querySelector('.carousel-wrapper');
        
        if (carousel) {
            carousel.addEventListener('scroll', checkCarouselScroll);
            setTimeout(checkCarouselScroll, 300);
            window.addEventListener('resize', checkCarouselScroll);
            
            if (wrapper) {
                wrapper.addEventListener('mouseenter', () => {
                    isMouseOverCarousel = true;
                });
                wrapper.addEventListener('mouseleave', () => {
                    isMouseOverCarousel = false;
                });
            }
            
            carousel.addEventListener('touchstart', resetAutoScrollTimer, { passive: true });
            
            startAutoScroll();
        }
    });

    // --- SEARCH AUTOCOMPLETE LOGIC ---
    const athletes = [
        /* jinja_block */
        { id: "jinja_var", name: ""jinja_var"", dept: ""jinja_var"", strava: ""jinja_var"" },
        /* jinja_block */
    ];

    const searchInput = document.getElementById('searchInput');
    const searchResults = document.getElementById('searchResults');

    searchInput.addEventListener('input', function() {
        const query = this.value.trim().toLowerCase();
        searchResults.innerHTML = '';
        if (query.length === 0) {
            searchResults.style.display = 'none';
            return;
        }

        // Loại bỏ dấu tiếng Việt để tìm kiếm không dấu
        const removeVietnameseTones = (str) => {
            return str.normalize('NFD')
                      .replace(/[\u0300-\u036f]/g, '')
                      .replace(/đ/g, 'd').replace(/Đ/g, 'D');
        };

        const queryNoTone = removeVietnameseTones(query);

        const filtered = athletes.filter(a => {
            const nameNoTone = removeVietnameseTones(a.name.toLowerCase());
            return nameNoTone.includes(queryNoTone);
        });

        if (filtered.length > 0) {
            filtered.forEach(a => {
                const item = document.createElement('div');
                item.className = 'search-item';
                item.innerHTML = `
                    <span style="font-weight:600;">${a.name}</span>
                    <span class="athlete-dept">${a.dept}</span>
                `;
                item.addEventListener('click', () => {
                    window.location.href = `/profile/${a.id}?event_id="jinja_var"`;
                });
                searchResults.appendChild(item);
            });
            searchResults.style.display = 'block';
        } else {
            const noResult = document.createElement('div');
            noResult.className = 'search-item';
            noResult.style.color = 'var(--text-muted)';
            noResult.style.cursor = 'default';
            noResult.innerText = 'Không tìm thấy vận động viên nào';
            searchResults.appendChild(noResult);
            searchResults.style.display = 'block';
        }
    });

    // Close search dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
            searchResults.style.display = 'none';
        }
    });

    // --- TAB SYSTEM LOGIC ---
    function switchTab(evt, tabId) {
        // Hide all tab panes
        const tabPanes = document.getElementsByClassName('tab-pane');
        for (let i = 0; i < tabPanes.length; i++) {
            tabPanes[i].classList.remove('active');
        }

        // Deactivate all tab buttons
        const tabBtns = document.getElementsByClassName('tab-btn');
        for (let i = 0; i < tabBtns.length; i++) {
            tabBtns[i].classList.remove('active');
        }

        // Show the current tab pane and add active class to button
        document.getElementById(tabId).classList.add('active');
        evt.currentTarget.classList.add('active');

        // Vẽ biểu đồ khi tab hiển thị
        const sortContainer = document.getElementById('sort-controls-container');
        if (tabId === 'charts') {
            if (sortContainer) sortContainer.style.display = 'none';
            setTimeout(initCharts, 50);
        } else {
            if (sortContainer) sortContainer.style.display = 'flex';
        }
    }

    // --- CHART.JS LEADERBOARD LOGIC ---
    const rankedAthletes = "jinja_var";
    const deptStats = "jinja_var";
    
    let chartsInitialized = false;
    let topAthletesChart = null;
    let deptChart = null;

    function initCharts() {
        if (chartsInitialized) return;

        const isDistance = /* jinja_block */true/* jinja_block */false/* jinja_block */;

        // Trích xuất dữ liệu
        const top10Athletes = rankedAthletes.slice(0, 10); // Lấy top 10 VĐV
        const athleteNames = top10Athletes.map(a => `${a.rank}. ${a.full_name} (${a.department})`);
        const athleteValues = top10Athletes.map(a => isDistance ? a.total_dist : a.total_kcal);

        const deptNames = deptStats.map(d => d.department);
        const deptValues = deptStats.map(d => isDistance ? d.avg_distance : d.avg_kcal);

        // 1. Biểu đồ Top 10 cá nhân đua thành tích
        const ctx1 = document.getElementById('topAthletesChart').getContext('2d');
        const grad1 = ctx1.createLinearGradient(0, 0, ctx1.canvas.offsetWidth || 500, 0);
        grad1.addColorStop(0, '#8FCDF0'); // Màu xanh pastel thương hiệu NSMO
        grad1.addColorStop(1, '#F9BFBE'); // Màu hồng pastel thương hiệu NSMO

        topAthletesChart = new Chart(ctx1, {
            type: 'bar',
            data: {
                labels: athleteNames,
                datasets: [{
                    label: isDistance ? 'Quãng đường tích lũy (KM)' : 'Năng lượng tích lũy (KCAL)',
                    data: athleteValues,
                    backgroundColor: grad1,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return isDistance ? `Quãng đường: ${context.parsed.x.toLocaleString('vi-VN')} KM` : `Năng lượng: ${context.parsed.x.toLocaleString('vi-VN')} KCAL`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9f9cb2' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#f3f2fa', font: { family: 'Be Vietnam Pro', weight: '600', size: 11 } }
                    }
                },
                animation: {
                    duration: 2500,
                    easing: 'easeOutQuart'
                }
            }
        });

        // 2. Biểu đồ phòng ban
        const ctx2 = document.getElementById('deptPerformanceChart').getContext('2d');
        const grad2 = ctx2.createLinearGradient(0, 0, ctx2.canvas.offsetWidth || 500, 0);
        grad2.addColorStop(0, '#94B5DE'); // Màu xanh xám thương hiệu NSMO
        grad2.addColorStop(1, '#8FCDF0'); // Màu xanh pastel thương hiệu NSMO

        deptChart = new Chart(ctx2, {
            type: 'bar',
            data: {
                labels: deptNames,
                datasets: [{
                    label: isDistance ? 'Trung bình KM / người' : 'Trung bình KCAL / người',
                    data: deptValues,
                    backgroundColor: grad2,
                    borderRadius: 6,
                    borderSkipped: false
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return isDistance ? `Hiệu suất: ${context.parsed.x.toLocaleString('vi-VN')} KM/người` : `Hiệu suất: ${context.parsed.x.toLocaleString('vi-VN')} KCAL/người`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9f9cb2' }
                    },
                    y: {
                        grid: { display: false },
                        ticks: { color: '#f3f2fa', font: { family: 'Be Vietnam Pro', weight: '600', size: 11 } }
                    }
                },
                animation: {
                    duration: 2500,
                    easing: 'easeOutQuart'
                }
            }
        });

        chartsInitialized = true;
    }

    // --- DATE PRESET LOGIC ---
    window.setPresetDays = function(days) {
        const today = new Date();
        const eventEndStr = ""jinja_var"";
        const eventEndDate = new Date(eventEndStr);
        
        // Lấy mốc kết thúc là hôm nay, nếu hôm nay đã vượt quá ngày kết thúc giải đấu thì lấy ngày kết thúc giải đấu
        let endDate = today;
        if (today > eventEndDate) {
            endDate = eventEndDate;
        }
        
        const startDate = new Date(endDate);
        startDate.setDate(endDate.getDate() - (days - 1));
        
        const formatLocalDate = (date) => {
            const y = date.getFullYear();
            const m = String(date.getMonth() + 1).padStart(2, '0');
            const d = String(date.getDate()).padStart(2, '0');
            return `${y}-${m}-${d}`;
        };
        
        document.getElementById('startDateInput').value = formatLocalDate(startDate);
        document.getElementById('endDateInput').value = formatLocalDate(endDate);
        document.getElementById('dateFilterForm').submit();
    }

    // --- DYNAMIC LEADERBOARD SORTING LOGIC ---
    function formatNumber(num) {
        return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ".");
    }

    window.changeLeaderboardSort = function(metric) {
        // 1. Cập nhật nút active
        document.querySelectorAll('.sort-btn').forEach(btn => btn.classList.remove('active'));
        const activeBtn = document.getElementById('btn-sort-' + metric);
        if (activeBtn) activeBtn.classList.add('active');

        // 2. Sắp xếp Bảng cá nhân (overall)
        sortOverallLeaderboard(metric);

        // 3. Sắp xếp Bảng phòng ban (departments)
        sortDeptLeaderboard(metric);

        // 4. Sắp xếp Bảng bộ môn (sports)
        sortSportsLeaderboard(metric);
    }

    function sortOverallLeaderboard(metric) {
        const tbody = document.getElementById('overall-tbody');
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll('.athlete-row'));
        if (rows.length === 0) return;

        rows.sort((a, b) => {
            let valA, valB;
            if (metric === 'kcal') {
                valA = parseInt(a.getAttribute('data-kcal') || 0);
                valB = parseInt(b.getAttribute('data-kcal') || 0);
            } else if (metric === 'distance') {
                valA = parseFloat(a.getAttribute('data-dist') || 0);
                valB = parseFloat(b.getAttribute('data-dist') || 0);
            } else { // time
                valA = parseFloat(a.getAttribute('data-time') || 0);
                valB = parseFloat(b.getAttribute('data-time') || 0);
            }
            return valB - valA;
        });

        // Highlights headers
        const headerDist = document.getElementById('col-overall-header-dist');
        const headerTime = document.getElementById('col-overall-header-time');
        const headerKcal = document.getElementById('col-overall-header-kcal');
        if (headerDist) { headerDist.style.color = ''; headerDist.style.fontWeight = ''; }
        if (headerTime) { headerTime.style.color = ''; headerTime.style.fontWeight = ''; }
        if (headerKcal) { headerKcal.style.color = ''; headerKcal.style.fontWeight = ''; }

        if (metric === 'distance' && headerDist) {
            headerDist.style.color = 'var(--color-primary)';
            headerDist.style.fontWeight = '700';
        } else if (metric === 'time' && headerTime) {
            headerTime.style.color = 'var(--color-primary)';
            headerTime.style.fontWeight = '700';
        } else if (metric === 'kcal' && headerKcal) {
            headerKcal.style.color = 'var(--color-primary)';
            headerKcal.style.fontWeight = '700';
        }

        tbody.innerHTML = '';
        rows.forEach((row, index) => {
            const rank = index + 1;
            const badgeContainer = row.querySelector('.rank-badge-container');
            if (badgeContainer) {
                let badgeClass = 'rank-other';
                if (rank === 1) badgeClass = 'rank-1';
                else if (rank === 2) badgeClass = 'rank-2';
                else if (rank === 3) badgeClass = 'rank-3';
                badgeContainer.innerHTML = `<span class="rank-badge ${badgeClass}">${rank}</span>`;
            }

            // Highlights data cells
            const distCell = row.querySelector('.col-overall-dist');
            const timeCell = row.querySelector('.col-overall-time');
            const kcalCell = row.querySelector('.col-overall-kcal');

            if (distCell) {
                distCell.style.color = '';
                distCell.style.fontWeight = '';
            }
            if (timeCell) {
                timeCell.style.color = 'var(--text-muted)';
                timeCell.style.fontWeight = '';
            }
            if (kcalCell) {
                kcalCell.style.color = 'var(--color-orange)';
                kcalCell.style.fontWeight = '700';
            }

            if (metric === 'distance' && distCell) {
                distCell.style.color = 'var(--color-primary)';
                distCell.style.fontWeight = '700';
            } else if (metric === 'time' && timeCell) {
                timeCell.style.color = 'var(--color-primary)';
                timeCell.style.fontWeight = '700';
            } else if (metric === 'kcal' && kcalCell) {
                kcalCell.style.color = 'var(--color-primary)';
                kcalCell.style.fontWeight = '700';
            }

            tbody.appendChild(row);
        });
    }

    function sortDeptLeaderboard(metric) {
        const tbody = document.getElementById('dept-tbody');
        if (!tbody) return;
        const rows = Array.from(tbody.querySelectorAll('.dept-row'));
        if (rows.length === 0) return;

        rows.sort((a, b) => {
            let valA, valB;
            if (metric === 'kcal') {
                valA = parseFloat(a.getAttribute('data-kcal-avg') || 0);
                valB = parseFloat(b.getAttribute('data-kcal-avg') || 0);
            } else if (metric === 'distance') {
                valA = parseFloat(a.getAttribute('data-dist-avg') || 0);
                valB = parseFloat(b.getAttribute('data-dist-avg') || 0);
            } else { // time
                valA = parseFloat(a.getAttribute('data-time-avg') || 0);
                valB = parseFloat(b.getAttribute('data-time-avg') || 0);
            }
            return valB - valA;
        });

        const headerTotal = document.getElementById('col-dept-header-total');
        const headerAvg = document.getElementById('col-dept-header-avg');
        if (headerTotal && headerAvg) {
            if (metric === 'kcal') {
                headerTotal.textContent = 'Tổng KCAL';
                headerAvg.textContent = 'KCAL Trung Bình / Người';
            } else if (metric === 'distance') {
                headerTotal.textContent = 'Tổng KM';
                headerAvg.textContent = 'KM Trung Bình / Người';
            } else {
                headerTotal.textContent = 'Tổng Thời Gian';
                headerAvg.textContent = 'Giờ Trung Bình / Người';
            }
        }

        tbody.innerHTML = '';
        rows.forEach((row, index) => {
            const rank = index + 1;
            const badgeContainer = row.querySelector('.rank-badge-container');
            if (badgeContainer) {
                let badgeClass = 'rank-other';
                if (rank === 1) badgeClass = 'rank-1';
                else if (rank === 2) badgeClass = 'rank-2';
                else if (rank === 3) badgeClass = 'rank-3';
                badgeContainer.innerHTML = `<span class="rank-badge ${badgeClass}">${rank}</span>`;
            }

            const totalCell = row.querySelector('.col-dept-total');
            const avgCell = row.querySelector('.col-dept-avg');
            if (totalCell && avgCell) {
                if (metric === 'kcal') {
                    const totalVal = parseInt(row.getAttribute('data-kcal-total') || 0);
                    const avgVal = parseInt(row.getAttribute('data-kcal-avg') || 0);
                    totalCell.textContent = formatNumber(totalVal) + ' KCAL';
                    avgCell.textContent = formatNumber(avgVal) + ' KCAL';
                } else if (metric === 'distance') {
                    const totalVal = parseFloat(row.getAttribute('data-dist-total') || 0);
                    const avgVal = parseFloat(row.getAttribute('data-dist-avg') || 0);
                    totalCell.textContent = totalVal + ' KM';
                    avgCell.textContent = avgVal + ' KM';
                } else {
                    const totalVal = parseFloat(row.getAttribute('data-time-total') || 0);
                    const avgVal = parseFloat(row.getAttribute('data-time-avg') || 0);
                    totalCell.textContent = totalVal + ' giờ';
                    avgCell.textContent = avgVal + ' giờ';
                }
            }

            tbody.appendChild(row);
        });
    }

    function sortSportsLeaderboard(metric) {
        document.querySelectorAll('.sport-tbody').forEach(tbody => {
            const rows = Array.from(tbody.querySelectorAll('.sport-row'));
            if (rows.length === 0) return;

            rows.sort((a, b) => {
                let valA, valB;
                if (metric === 'kcal') {
                    valA = parseInt(a.getAttribute('data-kcal') || 0);
                    valB = parseInt(b.getAttribute('data-kcal') || 0);
                } else if (metric === 'distance') {
                    valA = parseFloat(a.getAttribute('data-dist') || 0);
                    valB = parseFloat(b.getAttribute('data-dist') || 0);
                } else { // time
                    valA = parseFloat(a.getAttribute('data-time') || 0);
                    valB = parseFloat(b.getAttribute('data-time') || 0);
                }
                return valB - valA;
            });

            tbody.innerHTML = '';
            rows.forEach((row, index) => {
                const rank = index + 1;
                const rankCol = row.querySelector('.sport-rank-col');
                if (rankCol) {
                    let badgeClass = 'rank-other';
                    if (rank === 1) badgeClass = 'rank-1';
                    else if (rank === 2) badgeClass = 'rank-2';
                    else if (rank === 3) badgeClass = 'rank-3';
                    rankCol.innerHTML = `
                        <span class="rank-badge-container">
                            <span class="rank-badge ${badgeClass}" style="width: 24px; height: 24px; font-size: 0.75rem; line-height: 24px; margin: 0 auto;">
                                ${rank}
                            </span>
                        </span>
                    `;
                }

                const distCell = row.querySelector('.col-sport-dist');
                const timeCell = row.querySelector('.col-sport-time');
                const kcalCell = row.querySelector('.col-sport-kcal');
                
                if (distCell && timeCell && kcalCell) {
                    distCell.style.color = '';
                    distCell.style.fontWeight = '';
                    timeCell.style.color = 'var(--text-muted)';
                    timeCell.style.fontWeight = '';
                    kcalCell.style.color = 'var(--color-orange)';
                    kcalCell.style.fontWeight = '600';

                    if (metric === 'distance') {
                        distCell.style.color = 'var(--color-primary)';
                        distCell.style.fontWeight = '700';
                    } else if (metric === 'time') {
                        timeCell.style.color = 'var(--color-primary)';
                        timeCell.style.fontWeight = '700';
                    } else { // kcal
                        kcalCell.style.color = 'var(--color-primary)';
                        kcalCell.style.fontWeight = '700';
                    }
                }

                tbody.appendChild(row);
            });
        });
    }

    document.addEventListener('DOMContentLoaded', () => {
        const initialMetric = ""jinja_var"";
        changeLeaderboardSort(initialMetric || 'kcal');
    });

    // --- DỰNG LOGIC ĐẾM NGƯỢC GIẢI ĐẤU ĐỘNG ---
    (function() {
        const countdownEl = document.getElementById('event-countdown');
        if (!countdownEl) return;
        
        const startDateStr = countdownEl.getAttribute('data-start');
        const endDateStr = countdownEl.getAttribute('data-end');
        if (!startDateStr || !endDateStr) return;
        
        // Quy đổi ngày bắt đầu và kết thúc sang mốc thời gian JS
        const startTime = new Date(startDateStr + 'T00:00:00').getTime();
        const endTime = new Date(endDateStr + 'T23:59:59').getTime();
        
        const labelEl = document.getElementById('countdown-label');
        const daysEl = document.getElementById('countdown-days');
        const hoursEl = document.getElementById('countdown-hours');
        const minutesEl = document.getElementById('countdown-minutes');
        const secondsEl = document.getElementById('countdown-seconds');
        
        const badgeEl = document.getElementById('eventStatusBadge');
        const pulseEl = document.getElementById('eventStatusPulse');
        const textEl = document.getElementById('eventStatusText');
        
        function updateTimer() {
            const now = new Date().getTime();
            let targetTime = 0;
            let status = ''; // 'not_started', 'running', 'ended'
            
            if (now < startTime) {
                targetTime = startTime;
                status = 'not_started';
            } else if (now >= startTime && now <= endTime) {
                targetTime = endTime;
                status = 'running';
            } else {
                status = 'ended';
            }
            
            // 1. Cập nhật nhãn trạng thái giải chạy động (Status Badge)
            if (badgeEl && textEl) {
                if (status === 'not_started') {
                    badgeEl.style.background = 'rgba(251, 191, 36, 0.2)';
                    badgeEl.style.color = '#fbbf24';
                    badgeEl.style.borderColor = 'rgba(251, 191, 36, 0.3)';
                    textEl.innerText = 'SẮP DIỄN RA';
                    if (pulseEl) {
                        pulseEl.style.background = '#fbbf24';
                        pulseEl.style.display = 'inline-block';
                    }
                } else if (status === 'running') {
                    badgeEl.style.background = 'rgba(74, 222, 128, 0.2)';
                    badgeEl.style.color = '#4ade80';
                    badgeEl.style.borderColor = 'rgba(74, 222, 128, 0.3)';
                    textEl.innerText = 'ĐANG DIỄN RA';
                    if (pulseEl) {
                        pulseEl.style.background = '#4ade80';
                        pulseEl.style.display = 'inline-block';
                    }
                } else {
                    badgeEl.style.background = 'rgba(255, 255, 255, 0.08)';
                    badgeEl.style.color = 'rgba(255, 255, 255, 0.4)';
                    badgeEl.style.borderColor = 'rgba(255, 255, 255, 0.1)';
                    textEl.innerText = 'ĐÃ KẾT THÚC';
                    if (pulseEl) {
                        pulseEl.style.display = 'none'; // Ẩn nút nháy khi đã kết thúc
                    }
                }
            }
            
            // 2. Cập nhật đồng hồ đếm ngược
            if (status === 'ended') {
                countdownEl.style.display = 'flex';
                labelEl.innerHTML = '<i class="fa-solid fa-circle-check" style="color: rgba(255,255,255,0.4);"></i> Giải đấu đã kết thúc';
                daysEl.innerText = '00';
                hoursEl.innerText = '00';
                minutesEl.innerText = '00';
                secondsEl.innerText = '00';
                secondsEl.style.color = 'rgba(255,255,255,0.4)';
                return;
            }
            
            const diff = targetTime - now;
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);
            
            if (status === 'not_started') {
                labelEl.innerHTML = '<i class="fa-solid fa-hourglass-start" style="color: #fbbf24;"></i> Giải bắt đầu sau:';
                secondsEl.style.color = '#fbbf24';
            } else {
                labelEl.innerHTML = '<i class="fa-solid fa-stopwatch" style="color: #ff5e36;"></i> Thời gian còn lại:';
                secondsEl.style.color = '#ff5e36';
            }
            
            daysEl.innerText = String(days).padStart(2, '0');
            hoursEl.innerText = String(hours).padStart(2, '0');
            minutesEl.innerText = String(minutes).padStart(2, '0');
            secondsEl.innerText = String(seconds).padStart(2, '0');
            
            countdownEl.style.display = 'flex';
        }
        
        updateTimer();
        setInterval(updateTimer, 1000);
    })();

    // --- ARCHIVED EVENT DETAIL MODAL LOGIC ---


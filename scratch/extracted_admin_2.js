
    // --- QUẢN LÝ GIẢI ĐẤU JS ---
    function toggleEditComp(compId) {
        const row = document.getElementById('edit-comp-' + compId);
        if (row) {
            row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
        }
    }
    
    function toggleEditEvent(eventId) {
        const row = document.getElementById('edit-event-' + eventId);
        if (row) {
            row.style.display = row.style.display === 'none' ? 'table-row' : 'none';
        }
    }
    
    function toggleRewardTypeFields(selectEl, prefix) {
        const value = selectEl.value;
        const fields = document.querySelectorAll('.reward-linear-fields-' + prefix);
        fields.forEach(el => {
            el.style.display = value === 'linear' ? 'block' : 'none';
        });
    }

    function updateMetricLabels(selectEl, prefix) {
        const metric = selectEl.value;
        const labelText = metric === 'distance' ? 'Mỗi mốc KM quy đổi' : 'Mỗi mốc KCAL quy đổi';
        
        let labelEl;
        if (prefix === 'create') {
            labelEl = document.querySelector('.reward-linear-fields-create label');
        } else {
            labelEl = document.querySelector('.reward-linear-fields-' + prefix + ' label');
        }
        
        if (labelEl) {
            labelEl.textContent = labelText;
        }
    }
    
    async function syncCompetition(event, compId, compTitle) {
        if (!confirm('Đồng bộ dữ liệu từ Strava cho giải đấu "' + compTitle + '"?')) return;
        
        const btn = event.target.closest('button');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đồng bộ...';
        btn.disabled = true;
        
        try {
            const res = await fetch('/admin/competitions/sync/' + compId, { method: 'POST' });
            const data = await res.json();
            
            if (data.status === 'success' || data.status === 'partial') {
                alert('✅ ' + (data.message || ('Đồng bộ thành công!\nHoạt động mới: ' + (data.new_activities || 0))));
                window.location.reload();
            } else {
                alert('❌ Lỗi: ' + (data.error || 'Không xác định'));
            }
        } catch (err) {
            alert('❌ Lỗi kết nối: ' + err.message);
        } finally {
            btn.innerHTML = originalText;
            btn.disabled = false;
        }
    }

    async function runMigrateRegistrations(e, apply = false) {
        if (e) e.preventDefault();
        
        const targetEventId = document.getElementById('migrate_target_event_id').value;
        const hoursThreshold = document.getElementById('migrate_hours_threshold').value;
        
        const resultContainer = document.getElementById('migrate-result-container');
        const resultOutput = document.getElementById('migrate-result-output');
        
        resultContainer.style.display = 'block';
        resultOutput.innerText = 'Đang thực thi... Vui lòng đợi...';
        
        try {
            const formData = new FormData();
            formData.append('target_event_id', targetEventId);
            formData.append('hours_threshold', hoursThreshold);
            formData.append('apply', apply ? 'true' : 'false');
            
            const res = await fetch('/admin/api/migrate-registrations', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (res.ok) {
                let text = `[Trạng thái: ${data.dry_run ? "Chạy thử (Dry Run)" : "Thực tế (Apply)"}]\n`;
                text += `Thông điệp: ${data.message}\n\n`;
                if (data.details && data.details.length > 0) {
                    text += `Danh sách VĐV phát hiện (${data.details.length}):\n`;
                    data.details.forEach(ath => {
                        text += ` - ID: ${ath.athlete_id} | Tên: ${ath.name} | Đăng ký lúc: ${ath.registered_at}\n`;
                    });
                } else {
                    text += `Không phát hiện đăng ký nào trong ${hoursThreshold} giờ qua ở giải cũ.`;
                }
                resultOutput.innerText = text;
            } else {
                resultOutput.innerText = '❌ Lỗi: ' + (data.error || 'Có lỗi xảy ra');
            }
        } catch (err) {
            resultOutput.innerText = '❌ Lỗi kết nối: ' + err.message;
        }
    }
    
    function confirmAndMigrate() {
        const targetSelect = document.getElementById('migrate_target_event_id');
        const targetTitle = targetSelect.options[targetSelect.selectedIndex].text;
        const hours = document.getElementById('migrate_hours_threshold').value;
        
        const msg = `CẢNH BÁO!\nBạn có chắc chắn muốn di chuyển THẬT các đăng ký ở GIẢI CŨ trong ${hours} giờ qua sang "${targetTitle}"?\n\nThao tác này sẽ làm thay đổi cơ sở dữ liệu!`;
        if (confirm(msg)) {
            runMigrateRegistrations(null, true);
        }
    }

    async function runMergeAthletes(e, apply = false) {
        if (e) e.preventDefault();
        
        const newEventId = document.getElementById('merge_new_event_id').value;
        const resultContainer = document.getElementById('merge-result-container');
        const resultOutput = document.getElementById('merge-result-output');
        
        resultContainer.style.display = 'block';
        resultOutput.innerText = 'Đang thực thi quét trùng lặp... Vui lòng đợi...';
        
        try {
            const formData = new FormData();
            formData.append('new_event_id', newEventId);
            formData.append('apply', apply ? 'true' : 'false');
            
            const res = await fetch('/admin/api/merge-duplicate-athletes', {
                method: 'POST',
                body: formData
            });
            const data = await res.json();
            
            if (res.ok) {
                let text = `[Trạng thái: ${data.dry_run ? "Chạy thử (Dry Run)" : "Thực tế (Apply)"}]\n`;
                text += `Thông điệp: ${data.message}\n\n`;
                if (data.details && data.details.length > 0) {
                    text += `Danh sách VĐV phát hiện (${data.details.length}):\n`;
                    data.details.forEach(d => {
                        text += ` - Họ Tên: ${d.full_name}\n`;
                        text += `   + Tài khoản trùng gõ sai: ID ${d.new_athlete_id} | Strava = '${d.new_strava_name}'\n`;
                        text += `   + Tài khoản gốc từ giải cũ: ID ${d.old_athlete_id} | Strava = '${d.old_strava_name}'\n`;
                    });
                } else {
                    text += `Không tìm thấy VĐV nào trùng Họ Tên nhưng khác tên Strava ở giải mới này.`;
                }
                resultOutput.innerText = text;
            } else {
                resultOutput.innerText = '❌ Lỗi: ' + (data.error || 'Có lỗi xảy ra');
            }
        } catch (err) {
            resultOutput.innerText = '❌ Lỗi kết nối: ' + err.message;
        }
    }
    
    function confirmAndMerge() {
        const targetSelect = document.getElementById('merge_new_event_id');
        const targetTitle = targetSelect.options[targetSelect.selectedIndex].text;
        
        const msg = `CẢNH BÁO HỢP NHẤT TÀI KHOẢN!\nBạn có chắc chắn muốn HỢP NHẤT và ĐỒNG BỘ THẬT tên Strava của các VĐV trùng Họ Tên ở giải "${targetTitle}"?\n\n• Tài khoản trùng gõ sai ở giải mới sẽ bị XÓA.\n• Hoạt động và đăng ký của giải mới sẽ được chuyển sang tài khoản gốc.\n• Tên Strava của VĐV ở giải mới sẽ tự động dùng lại tên cũ chuẩn.\n\nThao tác này KHÔNG THỂ HOÀN TÁC! Bạn có chắc chắn muốn thực hiện?`;
        if (confirm(msg)) {
            runMergeAthletes(null, true);
        }
    }

    // --- ADMIN TAB TRANSITION LOGIC ---
    function switchAdminTab(evt, tabId) {
        const tabPanes = document.querySelectorAll('.tab-pane');
        tabPanes.forEach(pane => pane.classList.remove('active'));

        const tabBtns = document.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => btn.classList.remove('active'));

        document.getElementById(tabId).classList.add('active');
        evt.currentTarget.classList.add('active');
        
        if (tabId === 'tab-activities') {
            loadActivities(1);
        } else if (tabId === 'tab-support') {
            loadSupportTickets();
        } else if (tabId === 'tab-logs') {
            loadAdminLogs();
        }
    }

    // --- NHẬT KÝ HỆ THỐNG JS LOGIC ---
    function loadAdminLogs() {
        const tbody = document.getElementById('logs-table-body');
        tbody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                    <i class="fa-solid fa-spinner fa-spin"></i> Đang tải dữ liệu nhật ký thay thế...
                </td>
            </tr>
        `;
        
        fetch('/admin/api/logs')
            .then(res => res.json())
            .then(data => {
                const logs = data.logs || [];
                if (logs.length === 0) {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                                Chưa ghi nhận lịch sử thay thế/sao lưu nào.
                            </td>
                        </tr>
                    `;
                    return;
                }
                
                let html = '';
                logs.forEach(log => {
                    // Định dạng thời gian backup: 2026-07-03T11:45:30.123456 -> 03/07/2026 11:45:30 (Giờ VN)
                    let formattedBackupTime = 'N/A';
                    if (log.backup_time) {
                        try {
                            const dateObj = new Date(log.backup_time + 'Z'); // Parse as UTC
                            // Cộng thêm 7 tiếng chuyển sang giờ Việt Nam
                            const localDate = new Date(dateObj.getTime() + 7 * 60 * 60 * 1000);
                            
                            const day = String(localDate.getDate()).padStart(2, '0');
                            const month = String(localDate.getMonth() + 1).padStart(2, '0');
                            const year = localDate.getFullYear();
                            const hours = String(localDate.getHours()).padStart(2, '0');
                            const minutes = String(localDate.getMinutes()).padStart(2, '0');
                            const seconds = String(localDate.getSeconds()).padStart(2, '0');
                            
                            formattedBackupTime = `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
                        } catch (e) {
                            formattedBackupTime = log.backup_time;
                        }
                    }
                    
                    const name = log.name || 'N/A';
                    const distance = log.distance_km != null ? log.distance_km.toFixed(2) + ' km' : 'N/A';
                    const time = log.moving_time_min != null ? log.moving_time_min.toFixed(1) + ' phút' : 'N/A';
                    const type = log.sport_type || log.type || 'Run';
                    
                    const activityDetails = `<span style="font-weight:600; color:var(--text-color);">${name}</span><br>` +
                                           `<span style="font-size:0.78rem; color:var(--text-muted);">${type} • ${distance} • ${time}</span>`;
                    
                    const actTime = log.activity_time ? `${log.activity_date} ${log.activity_time}` : log.activity_date;
                    const reason = log.reason || 'Dọn dẹp hoạt động trùng lặp';
                    
                    html += `
                        <tr>
                            <td style="font-family: monospace; color: var(--color-orange);">${formattedBackupTime}</td>
                            <td style="font-weight: 600;">${log.athlete_name_raw || 'N/A'}</td>
                            <td>${activityDetails}</td>
                            <td>${actTime}</td>
                            <td>
                                <span class="badge" 
                                      style="padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 600; 
                                             background: ${log.reason ? 'rgba(60, 186, 146, 0.15)' : 'rgba(255, 123, 87, 0.15)'}; 
                                             color: ${log.reason ? 'var(--color-green)' : 'var(--color-orange)'};">
                                    ${reason}
                                </span>
                                <br>
                                <span style="font-size:0.72rem; color:var(--text-muted); font-family: monospace;">ID cũ: ${log.id ? log.id.substring(0, 12) + '...' : 'N/A'}</span>
                            </td>
                        </tr>
                    `;
                });
                tbody.innerHTML = html;
            })
            .catch(err => {
                console.error(err);
                tbody.innerHTML = `
                    <tr>
                        <td colspan="5" style="text-align: center; color: var(--color-red); padding: 2rem;">
                            Lỗi khi tải nhật ký: ${err.message}
                        </td>
                    </tr>
                `;
            });
    }

    // --- QUẢN LÝ HOẠT ĐỘNG (TAB ACTIVITIES) JS LOGIC ---
    let currentActivitiesPage = 1;
    let searchActivityQuery = '';
    let searchActivityTimeout = null;
    let currentActivitiesList = [];

    function loadActivities(page) {
        currentActivitiesPage = page;
        const tbody = document.getElementById('activities-table-body');
        tbody.innerHTML = `
            <tr>
                <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                    <i class="fa-solid fa-spinner fa-spin"></i> Đang tải danh sách hoạt động...
                </td>
            </tr>
        `;
        
        // Lấy event_id hiện tại từ dropdown giải đấu của activities
        const eventSelect = document.querySelector('.event-config-select[data-type="activities"]');
        const eventId = eventSelect ? eventSelect.value : '';
        
        fetch(`/admin/api/activities?page=${page}&limit=20&search=${encodeURIComponent(searchActivityQuery)}&event_id=${eventId}`)
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    renderActivitiesTable(data);
                } else {
                    tbody.innerHTML = `
                        <tr>
                            <td colspan="9" style="text-align: center; color: var(--color-orange); padding: 2rem;">
                                <i class="fa-solid fa-triangle-exclamation"></i> Lỗi: ${data.error || 'Không thể tải dữ liệu'}
                            </td>
                        </tr>
                    `;
                }
            })
            .catch(err => {
                tbody.innerHTML = `
                    <tr>
                        <td colspan="9" style="text-align: center; color: var(--color-orange); padding: 2rem;">
                            <i class="fa-solid fa-triangle-exclamation"></i> Lỗi kết nối server: ${err}
                        </td>
                    </tr>
                `;
            });
    }

    function renderActivitiesTable(data) {
        const tbody = document.getElementById('activities-table-body');
        const paginationContainer = document.getElementById('activities-pagination-btns');
        const infoDiv = document.getElementById('activities-page-info');
        
        tbody.innerHTML = '';
        currentActivitiesList = data.activities || [];
        
        if (currentActivitiesList.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" style="text-align: center; color: var(--text-muted); padding: 2rem;">
                        Không tìm thấy hoạt động nào phù hợp.
                    </td>
                </tr>
            `;
            paginationContainer.innerHTML = '';
            infoDiv.innerText = 'Hiển thị 0 - 0 trong tổng số 0 hoạt động';
            return;
        }
        
        // Quét để phát hiện các hoạt động trùng lặp bằng thuật toán so khớp chéo (cho phép lệch ngày chạy tối đa 2 ngày)
        const dupFlags = new Array(currentActivitiesList.length).fill(false);
        for (let i = 0; i < currentActivitiesList.length; i++) {
            const act1 = currentActivitiesList[i];
            const mult1 = act1.multiplier && act1.multiplier > 0 ? act1.multiplier : 1.0;
            const distRaw1 = act1.distance_km_raw !== null && act1.distance_km_raw !== undefined ? act1.distance_km_raw : (act1.distance_km / mult1);
            
            for (let j = i + 1; j < currentActivitiesList.length; j++) {
                const act2 = currentActivitiesList[j];
                
                // 1. Phải cùng VĐV
                if ((act1.athlete_name_raw || '').toLowerCase().trim() !== (act2.athlete_name_raw || '').toLowerCase().trim()) continue;
                
                // 2. Phải cùng loại thể thao
                if ((act1.sport_type || '').toLowerCase().trim() !== (act2.sport_type || '').toLowerCase().trim()) continue;
                
                // 3. Cự ly lệch cực nhỏ (<= 0.05 km)
                const mult2 = act2.multiplier && act2.multiplier > 0 ? act2.multiplier : 1.0;
                const distRaw2 = act2.distance_km_raw !== null && act2.distance_km_raw !== undefined ? act2.distance_km_raw : (act2.distance_km / mult2);
                const distDiff = Math.abs(distRaw1 - distRaw2);
                if (distDiff > 0.05) continue;
                
                // 4. Thời gian di chuyển lệch cực nhỏ (<= 1.0 phút)
                const timeDiff = Math.abs((act1.moving_time_min || 0) - (act2.moving_time_min || 0));
                if (timeDiff > 1.0) continue;
                
                // 5. Khoảng cách ngày chạy lệch không quá 2 ngày (xử lý lệch múi giờ/đồng bộ trễ)
                let dateDiff = 999;
                if (act1.activity_date && act2.activity_date) {
                    try {
                        const d1 = new Date(act1.activity_date);
                        const d2 = new Date(act2.activity_date);
                        dateDiff = Math.abs((d1 - d2) / (1000 * 60 * 60 * 24));
                    } catch (e) {}
                }
                if (dateDiff > 2) continue;
                
                // Đạt điều kiện -> Đánh dấu trùng lặp cả hai
                dupFlags[i] = true;
                dupFlags[j] = true;
            }
        }
        
        currentActivitiesList.forEach((act, index) => {
            const isDup = dupFlags[index];

            const tr = document.createElement('tr');
            if (isDup) {
                // Highlight bằng màu nền cam nhạt và border cam đậm bên trái để báo hiệu trùng lặp
                tr.style.backgroundColor = 'rgba(255, 111, 0, 0.08)';
                tr.style.borderLeft = '4px solid #ff6f00';
            }
            
            let statusBadge = '';
            if (act.is_suspicious) {
                statusBadge = `<span style="background: rgba(239, 83, 80, 0.15); color: #ef5350; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;" title="${act.suspicion_reason || 'Nghi vấn gian lận'}"><i class="fa-solid fa-triangle-exclamation"></i> Nghi vấn</span>`;
            } else {
                statusBadge = `<span style="background: rgba(76, 175, 80, 0.15); color: #4caf50; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem;"><i class="fa-solid fa-circle-check"></i> Hợp lệ</span>`;
            }

            if (isDup) {
                statusBadge += ` <span style="background: rgba(255, 111, 0, 0.15); color: #ff6f00; padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.75rem; margin-top: 4px; display: inline-block;" title="Có hoạt động khác có thông số cự ly/thời gian giống hệt nhưng khác ID trong danh sách"><i class="fa-solid fa-clone"></i> Trùng lặp</span>`;
            }
            
            tr.innerHTML = `
                <td><strong>${act.athlete_name_raw || 'Không tên'}</strong></td>
                <td>${act.name || 'Hoạt động không tên'}</td>
                <td><span class="badge badge-info" style="font-size:0.75rem; background: rgba(0, 188, 212, 0.15); color: #00bcd4; border: 1px solid rgba(0, 188, 212, 0.2); padding: 0.2rem 0.5rem; border-radius: 4px;">${act.sport_type || 'Run'}</span></td>
                <td style="text-align: right; font-weight: 600;">
                    ${(act.distance_km || 0).toFixed(2)} km
                    ${act.multiplier && act.multiplier > 1.0 ? `
                        <div style="font-size: 0.75rem; color: #ffc107; margin-top: 2px;" title="Hệ số nhân: x${act.multiplier} (Quãng đường gốc: ${(act.distance_km_raw || (act.distance_km / act.multiplier)).toFixed(2)} km)">
                            <i class="fa-solid fa-bolt"></i> x${act.multiplier}
                        </div>
                    ` : ''}
                </td>
                <td style="text-align: right;">${(act.moving_time_min || 0).toFixed(1)} m</td>
                <td style="text-align: right; color: var(--color-primary); font-weight:600;">
                    ${(act.kcal_burned || 0).toLocaleString('vi-VN')} KCAL
                    ${act.multiplier && act.multiplier > 1.0 ? `
                        <div style="font-size: 0.75rem; color: #ffc107; margin-top: 2px;" title="Hệ số nhân: x${act.multiplier} (KCAL gốc: ${(act.kcal_burned_raw || (act.kcal_burned / act.multiplier)).toFixed(1)} KCAL)">
                            <i class="fa-solid fa-bolt"></i> x${act.multiplier}
                        </div>
                    ` : ''}
                </td>
                <td style="text-align: center;">
                    ${act.activity_date || ''}
                    ${act.activity_time ? `<div style="font-size: 0.78rem; color: #00bcd4; margin-top: 2px;"><i class="fa-regular fa-clock"></i> ${act.activity_time}</div>` : ''}
                </td>
                <td style="text-align: center;">${statusBadge}</td>
                <td style="text-align: center;">
                    <div style="display: flex; gap: 0.3rem; justify-content: center;">
                        <button onclick="openEditActivityModal(${index})" class="btn btn-primary btn-sm" style="padding:0.3rem 0.5rem; font-size:0.75rem;" title="Sửa hoạt động"><i class="fa-solid fa-pen-to-square"></i></button>
                        <button onclick="deleteActivity('${act.id}')" class="btn btn-danger btn-sm" style="padding:0.3rem 0.5rem; font-size:0.75rem;" title="Xóa"><i class="fa-solid fa-trash-can"></i></button>
                    </div>
                </td>
            `;
            tbody.appendChild(tr);
        });
        
        const startNum = (data.page - 1) * data.limit + 1;
        const endNum = Math.min(data.page * data.limit, data.total);
        infoDiv.innerText = `Hiển thị ${startNum} - ${endNum} trong tổng số ${data.total} hoạt động`;
        
        paginationContainer.innerHTML = '';
        const totalPages = Math.ceil(data.total / data.limit);
        
        if (totalPages > 1) {
            if (data.page > 1) {
                paginationContainer.innerHTML += `<button onclick="loadActivities(1)" class="btn btn-secondary btn-sm" style="padding:0.2rem 0.5rem;"><i class="fa-solid fa-angles-left"></i></button>`;
                paginationContainer.innerHTML += `<button onclick="loadActivities(${data.page - 1})" class="btn btn-secondary btn-sm" style="padding:0.2rem 0.5rem;"><i class="fa-solid fa-angle-left"></i></button>`;
            }
            
            let startPage = Math.max(1, data.page - 2);
            let endPage = Math.min(totalPages, data.page + 2);
            
            for (let i = startPage; i <= endPage; i++) {
                const activeStyle = i === data.page ? 'background-color: var(--color-primary); border-color: var(--color-primary); color: #fff;' : '';
                paginationContainer.innerHTML += `<button onclick="loadActivities(${i})" class="btn btn-secondary btn-sm" style="padding:0.2rem 0.5rem; ${activeStyle}">${i}</button>`;
            }
            
            if (data.page < totalPages) {
                paginationContainer.innerHTML += `<button onclick="loadActivities(${data.page + 1})" class="btn btn-secondary btn-sm" style="padding:0.2rem 0.5rem;"><i class="fa-solid fa-angle-right"></i></button>`;
                paginationContainer.innerHTML += `<button onclick="loadActivities(${totalPages})" class="btn btn-secondary btn-sm" style="padding:0.2rem 0.5rem;"><i class="fa-solid fa-angles-right"></i></button>`;
            }
        }
    }

    function onSearchActivityInput(val) {
        searchActivityQuery = val;
        clearTimeout(searchActivityTimeout);
        searchActivityTimeout = setTimeout(() => {
            loadActivities(1);
        }, 400);
    }

    function openEditActivityModal(index) {
        const act = currentActivitiesList[index];
        if (!act) return;
        
        document.getElementById('edit-act-id').value = act.id;
        document.getElementById('edit-act-athlete-name').value = act.athlete_name_raw;
        document.getElementById('edit-act-name').value = act.name;
        document.getElementById('edit-act-sport-type').value = act.sport_type;
        document.getElementById('edit-act-date').value = act.activity_date;
        document.getElementById('edit-act-time').value = act.activity_time || '';
        document.getElementById('edit-act-dist').value = act.distance_km;
        document.getElementById('edit-act-mov-time').value = act.moving_time_min;
        document.getElementById('edit-act-ela-time').value = act.elapsed_time_min;
        document.getElementById('edit-act-elev').value = act.elevation_gain_m;
        document.getElementById('edit-act-kcal').value = act.kcal_burned;
        
        document.getElementById('edit-activity-modal-backdrop').style.display = 'block';
        document.getElementById('edit-activity-modal').style.display = 'block';
    }

    function closeEditActivityModal() {
        document.getElementById('edit-activity-modal-backdrop').style.display = 'none';
        document.getElementById('edit-activity-modal').style.display = 'none';
    }

    function submitEditActivityForm(event) {
        event.preventDefault();
        const form = document.getElementById('edit-activity-form');
        const actId = document.getElementById('edit-act-id').value;
        
        const formData = new FormData(form);
        
        fetch(`/admin/activity/edit/${actId}`, {
            method: 'POST',
            body: formData
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Cập nhật hoạt động thành công!');
                closeEditActivityModal();
                loadActivities(currentActivitiesPage);
            } else {
                alert('Lỗi: ' + (data.error || 'Không thể lưu thay đổi'));
            }
        })
        .catch(err => {
            alert('Lỗi kết nối: ' + err);
        });
    }

    function deleteActivity(actId) {
        if (!confirm('Bạn có chắc chắn muốn xóa hoạt động này? Thành tích sẽ bị giảm trừ tương ứng.')) {
            return;
        }
        
        fetch(`/admin/activity/delete/${actId}`, {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                alert('Xóa hoạt động thành công!');
                loadActivities(currentActivitiesPage);
            } else {
                alert('Lỗi: ' + (data.error || 'Không thể xóa hoạt động'));
            }
        })
        .catch(err => {
            alert('Lỗi kết nối: ' + err);
        });
    }

    function closeDedupResultModal() {
        document.getElementById('dedup-result-modal').style.display = 'none';
    }

    function runDeduplicateActivities(event, mode = 'all') {
        const isDryRun = mode === 'two_devices' || mode === 'sunday_dup';
        
        if (mode === 'standard') {
            if (!confirm('Bạn có chắc chắn muốn dọn dẹp trùng lặp cơ bản? (Các hoạt động trùng cự ly/thời gian tuyệt đối sẽ bị xóa tự động ngay)')) {
                return;
            }
        } else if (mode === 'two_devices') {
            if (!confirm('Hệ thống sẽ quét các hoạt động ghi song song từ 2 thiết bị để bạn tự duyệt và xóa. Tiến hành quét?')) {
                return;
            }
        } else if (mode === 'sunday_dup') {
            if (!confirm('Hệ thống sẽ quét các hoạt động bị trùng lặp do lệch ngày Chủ nhật (rạng sáng Thứ 2) để bạn tự duyệt và xóa. Tiến hành quét?')) {
                return;
            }
        }
        
        const btn = event.currentTarget;
        const originalHtml = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Đang xử lý...`;
        
        const url = `/admin/activity/deduplicate?mode=${mode}` + (isDryRun ? '&dry_run=true' : '');
        
        fetch(url, {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            
            if (data.status === 'success') {
                const modal = document.getElementById('dedup-result-modal');
                const titleEl = modal.querySelector('h3');
                const headerRow = document.getElementById('dedup-table-header-row');
                const statsDiv = document.getElementById('dedup-summary-stats');
                const detailsTbody = document.getElementById('dedup-result-details');
                
                // Cập nhật tiêu đề Modal và Header bảng dựa trên chế độ dry_run
                if (data.dry_run) {
                    titleEl.innerHTML = mode === 'sunday_dup' 
                        ? `<i class="fa-solid fa-magnifying-glass"></i> Duyệt Trùng Lặp Ngày Chủ Nhật`
                        : `<i class="fa-solid fa-magnifying-glass"></i> Duyệt Trùng Lặp 2 Thiết Bị`;
                    headerRow.innerHTML = `
                        <th>VĐV</th>
                        <th>Hoạt động trùng lặp (Đề xuất xóa)</th>
                        <th>Hoạt động giữ lại (Gốc)</th>
                        <th>Lý do gộp</th>
                        <th style="width: 100px; text-align: center;">Hành động</th>
                    `;
                    
                    statsDiv.innerHTML = `
                        <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color);">
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">Trạng thái</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #ff7b57;">Đã phát hiện</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color);">
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">Số lượng phát hiện</div>
                            <div id="dedup-stats-count" style="font-size: 1.25rem; font-weight: 700; color: #ff5e36;">${data.deleted_count}</div>
                        </div>
                    `;
                } else {
                    titleEl.innerHTML = `<i class="fa-solid fa-square-poll-horizontal"></i> Báo Cáo Kết Quả Dọn Dẹp`;
                    headerRow.innerHTML = `
                        <th>VĐV</th>
                        <th>Hoạt động bị xóa (Phụ)</th>
                        <th>Hoạt động giữ lại (Chính)</th>
                        <th>Lý do gộp</th>
                    `;
                    
                    statsDiv.innerHTML = `
                        <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color);">
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">Trạng thái</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #2b9348;">Thành công</div>
                        </div>
                        <div style="background: rgba(255,255,255,0.02); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-color);">
                            <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.25rem;">Hoạt động đã xóa</div>
                            <div style="font-size: 1.25rem; font-weight: 700; color: #ff5e36;">${data.deleted_count}</div>
                        </div>
                    `;
                }
                
                detailsTbody.innerHTML = '';
                const details = data.deleted_details || [];
                if (details.length === 0) {
                    const colSpan = data.dry_run ? 5 : 4;
                    detailsTbody.innerHTML = `<tr><td colspan="${colSpan}" style="text-align: center; color: var(--text-muted); padding: 2rem;">Không phát hiện hoạt động nào cần dọn dẹp ở chế độ này.</td></tr>`;
                } else {
                    details.forEach((item, idx) => {
                        const rowId = `dedup-row-${idx}`;
                        let actionCell = '';
                        if (data.dry_run) {
                            actionCell = `
                                <td style="text-align: center; vertical-align: middle; padding: 0.75rem 0.5rem;">
                                    <button class="btn btn-danger btn-sm" onclick="deleteActivityInDedupModal('${item.deleted.id}', '${rowId}', this)" style="background: linear-gradient(135deg, #d90429, #ef233c); border: none; padding: 0.35rem 0.6rem; font-size: 0.7rem; border-radius: 4px; display: inline-flex; align-items: center; gap: 0.25rem; cursor: pointer; transition: transform 0.1s;" onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                                        <i class="fa-solid fa-trash-can"></i> Xóa
                                    </button>
                                </td>
                            `;
                        }
                        
                        detailsTbody.innerHTML += `
                            <tr id="${rowId}">
                                <td style="font-weight:600; color: var(--text-color);">${item.athlete_name}</td>
                                <td style="color:#ff5e36; padding: 0.75rem 0.5rem;">
                                    <strong style="display:block; margin-bottom:0.25rem;">${item.deleted.name}</strong>
                                    <span style="font-size:0.75rem; color:var(--text-muted);">${item.deleted.distance} km | ${item.deleted.time} phút | Ngày: ${item.deleted.date}</span>
                                </td>
                                <td style="color:#2b9348; padding: 0.75rem 0.5rem;">
                                    <strong style="display:block; margin-bottom:0.25rem;">${item.kept.name}</strong>
                                    <span style="font-size:0.75rem; color:var(--text-muted);">${item.kept.distance} km | ${item.kept.time} phút | Ngày: ${item.kept.date}</span>
                                </td>
                                <td style="padding: 0.75rem 0.5rem;">
                                    <span class="badge" style="background: rgba(255,255,255,0.03); border: 1px solid var(--border-color); color: var(--text-muted); font-size: 0.7rem; padding: 0.2rem 0.4rem; border-radius: 4px; display: inline-block; white-space: normal; line-height: 1.2;">
                                        ${item.reason}
                                    </span>
                                </td>
                                ${actionCell}
                            </tr>
                        `;
                    });
                }
                
                modal.style.display = 'flex';
                
                if (document.getElementById('tab-activities').classList.contains('active')) {
                    loadActivities(currentActivitiesPage);
                }
            } else {
                alert('Lỗi: ' + (data.error || 'Không thể xử lý dọn dẹp'));
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = originalHtml;
            alert('Lỗi kết nối: ' + err);
        });
    }

    function deleteActivityInDedupModal(activityId, rowId, btn) {
        if (!confirm("Bạn có chắc chắn muốn xóa hoạt động này? Hành động này không thể hoàn tác.")) {
            return;
        }
        
        btn.disabled = true;
        const originalText = btn.innerHTML;
        btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i>`;
        
        fetch(`/admin/activity/delete/${activityId}`, {
            method: 'POST'
        })
        .then(res => res.json())
        .then(data => {
            if (data.status === 'success') {
                const row = document.getElementById(rowId);
                if (row) {
                    row.remove();
                }
                
                const statsCountEl = document.getElementById('dedup-stats-count');
                if (statsCountEl) {
                    let currentCount = parseInt(statsCountEl.innerText) || 0;
                    if (currentCount > 0) {
                        statsCountEl.innerText = currentCount - 1;
                    }
                }
                
                if (document.getElementById('tab-activities').classList.contains('active')) {
                    loadActivities(currentActivitiesPage);
                }
                
                const detailsTbody = document.getElementById('dedup-result-details');
                if (detailsTbody && detailsTbody.children.length === 0) {
                    detailsTbody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 2rem;">Tất cả hoạt động trùng lặp đã được xử lý xong.</td></tr>`;
                }
            } else {
                btn.disabled = false;
                btn.innerHTML = originalText;
                alert('Lỗi khi xóa: ' + (data.error || 'Không thể xóa'));
            }
        })
        .catch(err => {
            btn.disabled = false;
            btn.innerHTML = originalText;
            alert('Lỗi kết nối: ' + err);
        });
    }


    // --- AJAX EVENTS RULES LOADER ---
    function loadConfigForEvent(selectEl, type) {
        const eventId = selectEl.value;
        
        // Đồng bộ hóa tất cả các event-config-select khác
        document.querySelectorAll('.event-config-select').forEach(sel => {
            sel.value = eventId;
        });
        
        // Load lại danh sách hoạt động cho giải đấu mới chọn
        loadActivities(1);
        
        // Cập nhật tất cả event_id ẩn trong các form
        document.querySelectorAll('.hidden-event-id').forEach(input => {
            input.value = eventId;
        });
        
        // Gọi AJAX lấy cấu hình
        fetch(`/admin/api/rules?event_id=${eventId}`)
            .then(res => {
                if (res.status === 401) throw new Error('Chưa đăng nhập');
                return res.json();
            })
            .then(data => {
                // A. Cập nhật METs
                const metsList = document.getElementById('metsRulesList');
                if (metsList) {
                    const header = metsList.firstElementChild.outerHTML;
                    metsList.innerHTML = header;
                    data.mets.forEach(m => {
                        const div = document.createElement('div');
                        div.className = 'mets-row-input';
                        div.innerHTML = `
                            <input type="text" name="sport_type" class="form-control" value="${m.sport_type}" required>
                            <input type="number" step="0.1" name="min_speed" class="form-control" value="${m.min_speed}" required>
                            <input type="number" step="0.1" name="max_speed" class="form-control" value="${m.max_speed}" required>
                            <input type="number" step="0.1" name="met_value" class="form-control" value="${m.met_value}" required>
                            <button type="button" class="remove-row-btn" onclick="removeMetsRow(this)"><i class="fa-solid fa-circle-minus"></i></button>
                        `;
                        metsList.appendChild(div);
                    });
                }
                
                // B. Cập nhật Rewards
                const linearConfig = document.getElementById('linearRewardConfig');
                const rewardsList = document.getElementById('rewardsRulesList');
                const addRewardBtn = document.getElementById('btn-add-reward-row');
                
                if (data.reward_type === 'linear') {
                    if (linearConfig) linearConfig.style.display = 'block';
                    if (rewardsList) {
                        rewardsList.style.display = 'none';
                        const header = rewardsList.firstElementChild.outerHTML;
                        rewardsList.innerHTML = header;
                    }
                    if (addRewardBtn) addRewardBtn.style.display = 'none';
                    
                    document.getElementById('input_reward_linear_kcal').value = data.reward_linear_kcal || 100;
                    document.getElementById('input_reward_linear_amount').value = data.reward_linear_amount || 5000;
                } else {
                    if (linearConfig) linearConfig.style.display = 'none';
                    if (rewardsList) {
                        rewardsList.style.display = 'block';
                        const header = rewardsList.firstElementChild.outerHTML;
                        rewardsList.innerHTML = header;
                        data.rewards.forEach(r => {
                            const div = document.createElement('div');
                            div.className = 'rewards-row-input';
                            div.innerHTML = `
                                <select name="gender" class="form-control" required>
                                    <option value="Nam" ${r.gender === 'Nam' ? 'selected' : ''}>Nam</option>
                                    <option value="Nữ" ${r.gender === 'Nữ' ? 'selected' : ''}>Nữ</option>
                                </select>
                                <input type="number" step="1" name="kcal_threshold" class="form-control" value="${parseInt(r.kcal_threshold)}" required>
                                <input type="number" step="1000" name="reward_amount" class="form-control" value="${parseInt(r.reward_amount)}" required>
                                <button type="button" class="remove-row-btn" onclick="removeMetsRow(this)"><i class="fa-solid fa-circle-minus"></i></button>
                            `;
                            rewardsList.appendChild(div);
                        });
                    }
                    if (addRewardBtn) addRewardBtn.style.display = 'inline-block';
                }
                
                // C. Cập nhật Badges
                const tbody = document.querySelector('#tab-badges table tbody');
                if (tbody) {
                    tbody.innerHTML = '';
                    data.badges.forEach(b => {
                        let unitText = b.unit;
                        if (b.unit === 'activities') unitText = 'Hoạt động';
                        else if (b.unit === 'run_distance_km') unitText = 'km Chạy';
                        else if (b.unit === 'ride_distance_km') unitText = 'km Đạp xe';
                        else if (b.unit === 'total_time_hours') unitText = 'giờ';
                        else if (b.unit === 'total_kcal') unitText = 'KCAL';
                        else if (b.unit === 'max_streak_days') unitText = 'ngày liên tục';
                        
                        const tr = document.createElement('tr');
                        tr.innerHTML = `
                            <td>
                                <span style="font-family: monospace; font-weight:600; color:var(--text-muted);">${b.id}</span>
                                <input type="hidden" name="id" value="${b.id}">
                                <input type="hidden" name="unit" class="badge-unit-input" value="${b.unit}">
                            </td>
                            <td>
                                <input type="text" name="name" class="form-control" value="${b.name}" style="padding:0.4rem; font-size:0.85rem;" required>
                            </td>
                            <td>
                                <input type="text" name="description" class="form-control" value="${b.description}" style="padding:0.4rem; font-size:0.85rem;" required>
                            </td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 0.4rem;">
                                    <i class="fa-solid ${b.icon}" style="color: ${b.color}; font-size: 1.2rem; width: 20px; text-align: center;"></i>
                                    <input type="text" name="icon" class="form-control" value="${b.icon}" style="padding:0.4rem; font-size:0.85rem; font-family: monospace;" required>
                                </div>
                            </td>
                            <td style="text-align: center;">
                                <input type="color" name="color" value="${b.color}" style="width: 40px; height: 30px; border: 1px solid var(--border-color); background: none; cursor: pointer; border-radius: 4px;" required>
                            </td>
                            <td>
                                <input type="number" step="1" name="threshold" class="form-control" value="${parseInt(b.threshold)}" style="padding:0.4rem; font-size:0.85rem; text-align:right;" required>
                            </td>
                            <td>
                                <span style="font-size: 0.8rem; color: var(--text-muted); font-weight: 600;">
                                    ${unitText}
                                </span>
                            </td>
                        `;
                        tbody.appendChild(tr);
                    });
                }
            })
            .catch(err => {
                alert(`Lỗi khi tải cấu hình giải chạy: ${err.message}`);
            });
    }

    // --- DYNAMIC FORM ROWS EDITOR ---
    function addMetsRow() {
        const container = document.getElementById('metsRulesList');
        const div = document.createElement('div');
        div.className = 'mets-row-input';
        div.innerHTML = `
            <input type="text" name="sport_type" class="form-control" placeholder="e.g. Run" required>
            <input type="number" step="0.1" name="min_speed" class="form-control" value="0.0" required>
            <input type="number" step="0.1" name="max_speed" class="form-control" value="999.0" required>
            <input type="number" step="0.1" name="met_value" class="form-control" placeholder="5.0" required>
            <button type="button" class="remove-row-btn" onclick="removeMetsRow(this)"><i class="fa-solid fa-circle-minus"></i></button>
        `;
        container.appendChild(div);
    }

    function addRewardRow() {
        const container = document.getElementById('rewardsRulesList');
        const div = document.createElement('div');
        div.className = 'rewards-row-input';
        div.innerHTML = `
            <select name="gender" class="form-control" required>
                <option value="Nam">Nam</option>
                <option value="Nữ">Nữ</option>
            </select>
            <input type="number" step="1" name="kcal_threshold" class="form-control" placeholder="e.g. 5000" required>
            <input type="number" step="1000" name="reward_amount" class="form-control" placeholder="e.g. 50000" required>
            <button type="button" class="remove-row-btn" onclick="removeMetsRow(this)"><i class="fa-solid fa-circle-minus"></i></button>
        `;
        container.appendChild(div);
    }

    function removeMetsRow(btn) {
        btn.parentElement.remove();
    }

    // --- MANUAL SYNC OVER AJAX LOGIC ---
    const btnSync = document.getElementById('btnManualSync');
    if (btnSync) {
        btnSync.addEventListener('click', function() {
            btnSync.disabled = true;
            btnSync.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang đồng bộ...';
            
            fetch('/admin/sync', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnSync.disabled = false;
                btnSync.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Đồng Bộ Thủ Công Ngay';
                
                if (data.status === 'success' || data.status === 'partial') {
                    let msg = data.message || `Đồng bộ thành công! Tìm thấy ${data.new_activities || 0} hoạt động mới.`;
                    if (data.status === 'partial' && !data.message) {
                        msg += `\n(Lưu ý: ${data.error || 'Một số giải đấu đồng bộ thất bại.'})`;
                    }
                    alert(msg);
                    window.location.reload(); // Tải lại trang để cập nhật giao diện
                } else {
                    alert(`Lỗi đồng bộ: ${data.error || 'Lỗi không xác định'}`);
                    window.location.reload(); // Tải lại trang để cập nhật log lỗi trên giao diện
                }
            })
            .catch(err => {
                btnSync.disabled = false;
                btnSync.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> Đồng Bộ Thủ Công Ngay';
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- FIX TIMEZONE AJAX LOGIC ---
    const btnFix = document.getElementById('btnFixTimezone');
    if (btnFix) {
        btnFix.addEventListener('click', function() {
            if (!confirm('Bạn có chắc chắn muốn quét và sửa lệch múi giờ (UTC -> GMT+7) cho toàn bộ hoạt động trong hệ thống?')) {
                return;
            }
            
            btnFix.disabled = true;
            btnFix.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang xử lý...';
            
            fetch('/admin/fix-timezone', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnFix.disabled = false;
                btnFix.innerHTML = '<i class="fa-solid fa-clock"></i> Sửa Lệch Giờ UTC';
                
                if (data.status === 'success') {
                    alert(data.message);
                    window.location.reload();
                } else {
                    alert(`Lỗi: ${data.error || 'Lỗi không xác định'}`);
                }
            })
            .catch(err => {
                btnFix.disabled = false;
                btnFix.innerHTML = '<i class="fa-solid fa-clock"></i> Sửa Lệch Giờ UTC';
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- RESTORE BACKUP DATA AJAX LOGIC ---
    const btnRestore = document.getElementById('btnRestoreBackup');
    if (btnRestore) {
        btnRestore.addEventListener('click', function() {
            if (!confirm('Bạn có chắc chắn muốn khôi phục dữ liệu lịch sử trước ngày 16/06/2026 cho toàn bộ vận động viên từ file backup gần nhất? Dữ liệu từ ngày 16/06/2026 đến nay sẽ được giữ nguyên để đồng bộ tự động từ Strava.')) {
                return;
            }
            
            btnRestore.disabled = true;
            btnRestore.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang khôi phục...';
            
            fetch('/admin/restore-backup-data', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnRestore.disabled = false;
                btnRestore.innerHTML = '<i class="fa-solid fa-file-import"></i> Khôi Phục Dữ Liệu Lịch Sử';
                
                if (data.status === 'success') {
                    let msg = data.message;
                    if (data.backup_info && data.backup_info.all_backups_scanned) {
                        msg += "\n\nDanh sách các file backup đã quét thấy trên VPS:";
                        data.backup_info.all_backups_scanned.forEach(b => {
                            msg += `\n• ${b.file} | Số hoạt động trước 16/06: ${b.historical_activities}`;
                        });
                    }
                    alert(msg);
                    window.location.reload();
                } else {
                    alert(`Lỗi: ${data.error || 'Lỗi không xác định'}`);
                }
            })
            .catch(err => {
                btnRestore.disabled = false;
                btnRestore.innerHTML = '<i class="fa-solid fa-file-import"></i> Khôi Phục Dữ Liệu Lịch Sử';
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- FORCE SYNC ALL ATHLETES AJAX LOGIC ---
    const btnForceSync = document.getElementById('btnForceSyncAll');
    if (btnForceSync) {
        btnForceSync.addEventListener('click', function() {
            if (!confirm('Bạn có muốn quét và đồng bộ lại toàn bộ VĐV đã liên kết Strava? Quá trình này sẽ giúp gán lại các hoạt động bị gán nhầm sang đúng người.')) {
                return;
            }
            
            btnForceSync.disabled = true;
            btnForceSync.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang quét...';
            
            fetch('/admin/force-sync-all-athletes', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnForceSync.disabled = false;
                btnForceSync.innerHTML = '<i class="fa-solid fa-sync"></i> Quét Lại API VĐV';
                
                if (data.status === 'success') {
                    alert(data.message);
                    window.location.reload();
                } else {
                    alert(`Lỗi: ${data.error || 'Lỗi không xác định'}`);
                }
            })
            .catch(err => {
                btnForceSync.disabled = false;
                btnForceSync.innerHTML = '<i class="fa-solid fa-sync"></i> Quét Lại API VĐV';
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- UPLOAD AND RESTORE BACKUP AJAX LOGIC ---
    const btnUploadRestore = document.getElementById('btnUploadRestore');
    const uploadBackupInput = document.getElementById('uploadBackupInput');
    
    if (btnUploadRestore && uploadBackupInput) {
        btnUploadRestore.addEventListener('click', function() {
            uploadBackupInput.click(); // Mở hộp thoại chọn file
        });
        
        uploadBackupInput.addEventListener('change', function() {
            const file = uploadBackupInput.files[0];
            if (!file) return;
            
            if (!confirm(`Bạn có chắc chắn muốn tải lên file '${file.name}' để khôi phục dữ liệu lịch sử? Quá trình này sẽ khôi phục toàn bộ hoạt động lịch sử bị thiếu.`)) {
                uploadBackupInput.value = ''; // Reset input
                return;
            }
            
            btnUploadRestore.disabled = true;
            btnUploadRestore.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang khôi phục...';
            
            const formData = new FormData();
            formData.append('file', file);
            
            fetch('/admin/upload-restore-backup', {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnUploadRestore.disabled = false;
                btnUploadRestore.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Tải Lên & Khôi Phục DB';
                uploadBackupInput.value = ''; // Reset input
                
                if (data.status === 'success') {
                    alert(data.message);
                    window.location.reload();
                } else {
                    alert(`Lỗi: ${data.error || 'Lỗi không xác định'}`);
                }
            })
            .catch(err => {
                btnUploadRestore.disabled = false;
                btnUploadRestore.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Tải Lên & Khôi Phục DB';
                uploadBackupInput.value = ''; // Reset input
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- UNLINK MISMATCHED ATHLETES AJAX LOGIC ---
    const btnUnlink = document.getElementById('btnUnlinkMismatched');
    if (btnUnlink) {
        btnUnlink.addEventListener('click', function() {
            if (!confirm('Bạn có chắc chắn muốn quét và hủy liên kết đối với các tài khoản VĐV không trùng khớp với Client ID/Secret hiện tại? Quá trình này sẽ gọi API Strava để kiểm tra xác thực từng người.')) {
                return;
            }
            
            btnUnlink.disabled = true;
            btnUnlink.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang dọn...';
            
            fetch('/admin/unlink-mismatched-athletes', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnUnlink.disabled = false;
                btnUnlink.innerHTML = '<i class="fa-solid fa-unlink"></i> Dọn Liên Kết Sai';
                
                if (data.status === 'success') {
                    alert(data.message);
                    window.location.reload();
                } else {
                    alert(`Lỗi: ${data.error || 'Lỗi không xác định'}`);
                }
            })
            .catch(err => {
                btnUnlink.disabled = false;
                btnUnlink.innerHTML = '<i class="fa-solid fa-unlink"></i> Dọn Liên Kết Sai';
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- CLEANUP OLD NUMERIC IDS AJAX LOGIC ---
    const btnCleanupOldIds = document.getElementById('btnCleanupOldIds');
    if (btnCleanupOldIds) {
        btnCleanupOldIds.addEventListener('click', function() {
            if (!confirm('Bạn có chắc chắn muốn dọn dẹp các hoạt động sử dụng ID số cũ từ đợt quét lỗi trước? Việc này sẽ sao lưu các hoạt động cũ vào file nhật ký hệ thống để bạn quét đồng bộ lại an toàn.')) {
                return;
            }
            
            btnCleanupOldIds.disabled = true;
            btnCleanupOldIds.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang dọn...';
            
            fetch('/admin/cleanup-old-numeric-ids', {
                method: 'POST'
            })
            .then(response => {
                if (response.status === 401) {
                    throw new Error('Chưa đăng nhập quyền Admin');
                }
                return response.json();
            })
            .then(data => {
                btnCleanupOldIds.disabled = false;
                btnCleanupOldIds.innerHTML = '<i class="fa-solid fa-broom"></i> Dọn ID Số Cũ';
                
                if (data.status === 'success') {
                    alert(data.message);
                    window.location.reload();
                } else {
                    alert(`Lỗi: ${data.error || 'Lỗi không xác định'}`);
                }
            })
            .catch(err => {
                btnCleanupOldIds.disabled = false;
                btnCleanupOldIds.innerHTML = '<i class="fa-solid fa-broom"></i> Dọn ID Số Cũ';
                alert(`Lỗi hệ thống: ${err.message}`);
            });
        });
    }

    // --- HISTORICAL DATA IMPORT AJAX LOGIC ---
    function uploadHistoricalExcel(files) {
        if (!files || files.length === 0) return;
        
        // Chỉ lọc các file Excel .xlsx
        const excelFiles = Array.from(files).filter(f => f.name.endsWith('.xlsx'));
        if (excelFiles.length === 0) {
            alert("Không tìm thấy tệp Excel (.xlsx) hợp lệ nào!");
            return;
        }
        
        if (!confirm(`Bạn đã chọn ${excelFiles.length} tệp Excel. Bạn có chắc chắn muốn nạp toàn bộ thành tích từ các tệp này vào hệ thống?`)) {
            document.getElementById('importExcelFilesInput').value = '';
            document.getElementById('importExcelFolderInput').value = '';
            return;
        }
        
        // Show loading state
        const buttons = document.querySelectorAll("button[onclick*='importExcel']");
        const originalHtmls = [];
        buttons.forEach((btn, idx) => {
            btn.disabled = true;
            originalHtmls[idx] = btn.innerHTML;
            btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang nạp...';
        });
        
        const formData = new FormData();
        excelFiles.forEach(file => {
            formData.append("files", file);
        });
        
        const eventIdSelect = document.getElementById('importExcelEventId');
        if (eventIdSelect && eventIdSelect.value) {
            formData.append("event_id", eventIdSelect.value);
        }
        
        fetch('/admin/import-historical', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (response.status === 401) {
                throw new Error('Chưa đăng nhập quyền Admin');
            }
            return response.json();
        })
        .then(data => {
            // Restore buttons state
            buttons.forEach((btn, idx) => {
                btn.disabled = false;
                btn.innerHTML = originalHtmls[idx];
            });
            
            // Reset input files
            document.getElementById('importExcelFilesInput').value = '';
            document.getElementById('importExcelFolderInput').value = '';
            
            if (data.status === 'success') {
                let msg = `Nạp dữ liệu Excel thành công!\n`;
                msg += `- Đã import mới: ${data.imported_count} hoạt động.\n`;
                msg += `- Bỏ qua (đã tồn tại): ${data.skipped_count} hoạt động.`;
                if (data.errors && data.errors.length > 0) {
                    msg += `\n\nCó một số cảnh báo lỗi:\n` + data.errors.slice(0, 5).join('\n');
                    if (data.errors.length > 5) msg += `\n... và ${data.errors.length - 5} lỗi khác.`;
                }
                alert(msg);
                window.location.reload();
            } else {
                alert(`Lỗi khi nạp dữ liệu: ${data.error}`);
            }
        })
        .catch(err => {
            // Restore buttons state
            buttons.forEach((btn, idx) => {
                btn.disabled = false;
                btn.innerHTML = originalHtmls[idx];
            });
            // Reset input files
            document.getElementById('importExcelFilesInput').value = '';
            document.getElementById('importExcelFolderInput').value = '';
            alert(`Lỗi hệ thống: ${err.message}`);
        });
    }

    // --- DOWNLOAD EXCEL REPORT WITH DATE RANGE LOGIC ---
    window.addEventListener('DOMContentLoaded', () => {
        // Tự động chuyển tab theo URL Hash (ví dụ #tab-athletes)
        const hash = window.location.hash;
        if (hash) {
            const cleanHash = hash.replace('#', '');
            const tabBtn = document.querySelector(`.tab-btn[onclick*="${cleanHash}"]`);
            if (tabBtn) {
                // Kích hoạt click vào nút tab
                tabBtn.click();
            }
        }

        const startInput = document.getElementById('excel_start');
        const endInput = document.getElementById('excel_end');
        if (startInput && endInput) {
            const today = new Date();
            const lastWeek = new Date();
            lastWeek.setDate(today.getDate() - 6);
            
            const formatDate = (date) => {
                const year = date.getFullYear();
                const month = String(date.getMonth() + 1).padStart(2, '0');
                const day = String(date.getDate()).padStart(2, '0');
                return `${year}-${month}-${day}`;
            };
            
            startInput.value = formatDate(lastWeek);
            endInput.value = formatDate(today);
        }
    });

    function downloadExcelReport() {
        const start = document.getElementById('excel_start').value;
        const end = document.getElementById('excel_end').value;
        if (!start || !end) {
            alert("Vui lòng chọn đầy đủ ngày bắt đầu và ngày kết thúc!");
            return;
        }
        const urlParams = new URLSearchParams(window.location.search);
        const eventId = urlParams.get('event_id') || '';
        window.location.href = `/admin/export-excel?start_date=${start}&end_date=${end}&event_id=${eventId}`;
    }

    function downloadRewardExcelReport() {
        const urlParams = new URLSearchParams(window.location.search);
        const eventId = urlParams.get('event_id') || '';
        window.location.href = `/admin/export-rewards-excel?event_id=${eventId}`;
    }

    // --- ADMIN ANALYTICS VISUALIZATION LOGIC ---
    let adminKcalChartInstance = null;
    let adminSportChartInstance = null;
    
    // Đọc dữ liệu từ backend (chỉ khi có stats_data)
    const statsData = "jinja_var";
    
    function initAdminCharts() {
        if (!statsData) return;
        
        // 1. Biểu đồ Xu hướng Calo (Line Chart)
        const kcalCtx = document.getElementById('adminKcalChart').getContext('2d');
        const weeklyLabels = statsData.weekly.labels;
        const weeklyKcal = statsData.weekly.kcal;
        
        adminKcalChartInstance = new Chart(kcalCtx, {
            type: 'line',
            data: {
                labels: weeklyLabels,
                datasets: [{
                    label: 'Năng lượng (KCAL)',
                    data: weeklyKcal,
                    borderColor: '#8FCDF0',
                    backgroundColor: 'rgba(143, 205, 240, 0.15)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.3,
                    pointBackgroundColor: '#8FCDF0',
                    pointBorderColor: 'rgba(255,255,255,0.8)',
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return ` ${context.parsed.y.toLocaleString()} KCAL`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        grid: {
                            color: 'rgba(255,255,255,0.05)'
                        },
                        ticks: {
                            color: '#94B5DE',
                            font: {
                                family: 'Be Vietnam Pro'
                            }
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        },
                        ticks: {
                            color: '#94B5DE',
                            font: {
                                family: 'Be Vietnam Pro'
                            }
                        }
                    }
                }
            }
        });
        
        // 2. Biểu đồ Phân bổ Bộ môn (Doughnut Chart)
        const sportCtx = document.getElementById('adminSportChart').getContext('2d');
        const sportLabels = statsData.sports.labels;
        const sportKcal = statsData.sports.kcal;
        
        // Áp dụng bảng màu pastel nhận diện thương hiệu
        const backgroundColors = [
            'rgba(143, 205, 240, 0.85)', // Walk/Xanh pastel
            'rgba(255, 94, 54, 0.85)',   // Run/Cam pastel (hoặc Hồng pastel '#F9BFBE')
            'rgba(181, 84, 247, 0.85)',  // Ride/Tím pastel
            'rgba(32, 201, 151, 0.85)',  // Swim/Xanh lục
            'rgba(249, 191, 190, 0.85)', // Hồng pastel
            'rgba(148, 181, 222, 0.85)'  // Xanh xám
        ];
        
        adminSportChartInstance = new Chart(sportCtx, {
            type: 'doughnut',
            data: {
                labels: sportLabels,
                datasets: [{
                    data: sportKcal,
                    backgroundColor: backgroundColors.slice(0, sportLabels.length),
                    borderWidth: 2,
                    borderColor: 'rgba(9, 6, 21, 0.8)'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#e4e3e8',
                            font: {
                                family: 'Be Vietnam Pro',
                                size: 11
                            },
                            padding: 15
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const val = context.raw;
                                const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                                return ` ${context.label}: ${val.toLocaleString()} KCAL (${pct}%)`;
                            }
                        }
                    }
                },
                cutout: '65%'
            }
        });
    }
    
    // Hàm Toggle Tuần/Tháng
    function toggleKcalTrend(type) {
        if (!statsData || !adminKcalChartInstance) return;
        
        const btnWeek = document.getElementById('btnToggleWeek');
        const btnMonth = document.getElementById('btnToggleMonth');
        
        if (type === 'week') {
            btnWeek.classList.add('active');
            btnWeek.style.background = 'var(--color-primary)';
            btnWeek.style.color = '#fff';
            
            btnMonth.classList.remove('active');
            btnMonth.style.background = 'transparent';
            btnMonth.style.color = 'var(--text-muted)';
            
            // Cập nhật dữ liệu biểu đồ
            adminKcalChartInstance.data.labels = statsData.weekly.labels;
            adminKcalChartInstance.data.datasets[0].data = statsData.weekly.kcal;
            adminKcalChartInstance.update();
        } else {
            btnMonth.classList.add('active');
            btnMonth.style.background = 'var(--color-primary)';
            btnMonth.style.color = '#fff';
            
            btnWeek.classList.remove('active');
            btnWeek.style.background = 'transparent';
            btnWeek.style.color = 'var(--text-muted)';
            
            // Cập nhật dữ liệu biểu đồ
            adminKcalChartInstance.data.labels = statsData.monthly.labels;
            adminKcalChartInstance.data.datasets[0].data = statsData.monthly.kcal;
            adminKcalChartInstance.update();
        }
    }
    
    // Khởi tạo đồ thị
    window.addEventListener('DOMContentLoaded', () => {
        initAdminCharts();
    });
    // ===== HỆ SỐ NHÂN THÀNH TÍCH (MULTIPLIER) JS =====

    function loadMultipliers() {
        const select = document.getElementById('multiplier-event-select');
        const eventId = select.value;
        document.getElementById('multiplier-event-id').value = eventId;
        
        // Reset tất cả về 1.0
        for (let i = 0; i < 7; i++) {
            document.getElementById('dow_mult_' + i).value = '1.0';
            document.getElementById('dow_desc_' + i).value = '';
        }
        document.getElementById('special-dates-body').innerHTML = '';
        toggleNoSpecialDatesMessage();
        
        if (!eventId) return;
        
        fetch('/admin/api/multipliers?event_id=' + eventId)
            .then(r => r.json())
            .then(data => {
                if (data.status !== 'success') return;
                
                // Điền hệ số ngày trong tuần
                if (data.day_of_week) {
                    data.day_of_week.forEach(item => {
                        const dow = item.day_of_week;
                        const multInput = document.getElementById('dow_mult_' + dow);
                        const descInput = document.getElementById('dow_desc_' + dow);
                        if (multInput) multInput.value = item.multiplier;
                        if (descInput) descInput.value = item.description || '';
                    });
                }
                
                // Điền ngày đặc biệt
                if (data.special_dates && data.special_dates.length > 0) {
                    data.special_dates.forEach(item => {
                        addSpecialDateRow(item.special_date, item.multiplier, item.description);
                    });
                }
                toggleNoSpecialDatesMessage();
            })
            .catch(err => {
                console.error('Error loading multipliers:', err);
            });
    }

    function addSpecialDateRow(dateVal, multVal, descVal) {
        const tbody = document.getElementById('special-dates-body');
        const tr = document.createElement('tr');
        tr.innerHTML = `
            <td><input type="date" name="special_date" class="form-control" value="${dateVal || ''}"></td>
            <td><input type="number" step="0.1" min="0.1" max="10" name="special_mult" class="form-control" value="${multVal || '2.0'}" style="width: 80px;"></td>
            <td><input type="text" name="special_desc" class="form-control" value="${descVal || ''}" placeholder="VD: Ngày lễ 30/4"></td>
            <td><button type="button" class="btn btn-sm" style="background: #ef4444; color: #fff; padding: 4px 8px;" onclick="removeSpecialDateRow(this)"><i class="fa-solid fa-trash"></i></button></td>
        `;
        tbody.appendChild(tr);
        toggleNoSpecialDatesMessage();
    }

    function removeSpecialDateRow(btn) {
        btn.closest('tr').remove();
        toggleNoSpecialDatesMessage();
    }

    function toggleNoSpecialDatesMessage() {
        const tbody = document.getElementById('special-dates-body');
        const msg = document.getElementById('no-special-dates');
        if (msg) {
            msg.style.display = (tbody && tbody.children.length > 0) ? 'none' : 'block';
        }
    }

    function recalculateMultipliers() {
        const eventId = document.getElementById('multiplier-event-id').value;
        if (!eventId) {
            alert('Vui lòng chọn giải đấu trước!');
            return;
        }
        
        if (!confirm('Bạn có chắc muốn tính lại KCAL cho toàn bộ hoạt động của giải đấu này? Quá trình này có thể mất vài giây.')) {
            return;
        }
        
        const formData = new FormData();
        formData.append('event_id', eventId);
        
        fetch('/admin/multipliers/recalculate', {
            method: 'POST',
            body: formData
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === 'success') {
                alert(`Đã tính lại KCAL cho ${data.updated} hoạt động thành công!`);
            } else {
                alert('Lỗi: ' + (data.error || 'Không xác định'));
            }
        })
        .catch(err => {
            alert('Lỗi kết nối: ' + err.message);
        });
    }

    function loadCompetitionRulesForConfig(eventId) {
        if (!eventId) return;
        
        fetch(`/admin/api/competition-rules/${eventId}`)
            .then(res => {
                if (!res.ok) {
                    throw new Error('Không thể tải cấu hình quy chế');
                }
                return res.json();
            })
            .then(data => {
                // Điền thông tin vào các trường tương ứng
                document.getElementById('rules_title').value = data.title || '';
                document.getElementById('rules_version').value = data.rules_version || '';
                document.getElementById('rules_description').value = data.rules_description || '';
                document.getElementById('rules_general_text').value = data.rules_general_text || '';
                document.getElementById('rules_banner_text').value = data.rules_banner_text || '';
                
                // Chọn banner mode
                const bannerModeSelect = document.getElementById('rules_banner_mode');
                if (bannerModeSelect) {
                    bannerModeSelect.value = data.rules_banner_mode || 'version';
                    // Trigger toggleBannerDaysRow
                    if (typeof toggleBannerDaysRow === 'function') {
                        toggleBannerDaysRow();
                    }
                }
                
                // Reset days
                const bannerResetDaysInput = document.getElementById('rules_banner_reset_days');
                if (bannerResetDaysInput) {
                    bannerResetDaysInput.value = data.rules_banner_reset_days || '1';
                }
                
                // Hiển thị/Cập nhật preview ảnh banner
                const bannerPreviewContainer = document.getElementById('rules_banner_preview_container');
                if (bannerPreviewContainer) {
                    if (data.banner_image) {
                        bannerPreviewContainer.innerHTML = `
                            <div style="margin-top: 1.2rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 1rem; display: flex; align-items: center; gap: 1.2rem; background: rgba(255, 255, 255, 0.02);">
                                <img src="${data.banner_image}" alt="Current Active Banner" style="max-height: 80px; border-radius: 6px; object-fit: cover; border: 1px solid rgba(255,255,255,0.1);">
                                <div style="flex: 1;">
                                    <span style="font-size: 0.85rem; color: var(--color-green); font-weight: 600; display: block; margin-bottom: 2px;"><i class="fa-solid fa-circle-check"></i> Ảnh banner hiện tại đang hoạt động</span>
                                    <span style="font-size: 0.75rem; color: var(--text-muted); display: block; word-break: break-all; font-family: monospace;">${data.banner_image}</span>
                                </div>
                            </div>
                        `;
                    } else {
                        bannerPreviewContainer.innerHTML = `
                            <div style="margin-top: 1.2rem; border: 1px dashed rgba(255,255,255,0.15); border-radius: 10px; padding: 1rem; text-align: center; background: rgba(0, 0, 0, 0.1);">
                                <span style="font-size: 0.85rem; color: var(--text-muted);"><i class="fa-solid fa-circle-info"></i> Giải đấu này chưa cấu hình ảnh Banner. Bạn có thể chọn file phía trên để tải lên ảnh mới.</span>
                            </div>
                        `;
                    }
                }
                
                // Hiển thị/Cập nhật preview QR code group
                const qrPreviewContainer = document.getElementById('rules_group_qr_preview_container');
                if (qrPreviewContainer) {
                    if (data.rules_group_qr) {
                        qrPreviewContainer.innerHTML = `
                            <div style="margin-top: 1.2rem; border: 1px solid var(--border-color); border-radius: 10px; padding: 1rem; display: flex; align-items: center; gap: 1.2rem; background: rgba(255, 255, 255, 0.02); max-width: 400px;">
                                <img src="${data.rules_group_qr}" alt="Current Group QR" style="max-height: 120px; border-radius: 6px; object-fit: contain; border: 1px solid rgba(255,255,255,0.1);">
                                <div style="flex: 1;">
                                    <span style="font-size: 0.85rem; color: var(--color-primary); font-weight: 600; display: block; margin-bottom: 2px;"><i class="fa-solid fa-circle-check"></i> Ảnh QR hiện tại đang hoạt động</span>
                                    <span style="font-size: 0.75rem; color: var(--text-muted); display: block; word-break: break-all; font-family: monospace;">${data.rules_group_qr}</span>
                                </div>
                            </div>
                        `;
                    } else {
                        qrPreviewContainer.innerHTML = `
                            <div style="margin-top: 1.2rem; border: 1px dashed rgba(255,255,255,0.15); border-radius: 10px; padding: 1rem; text-align: center; background: rgba(0, 0, 0, 0.1); max-width: 400px;">
                                <span style="font-size: 0.85rem; color: var(--text-muted);"><i class="fa-solid fa-circle-info"></i> Chưa cấu hình ảnh mã QR nhóm. Bạn có thể chọn file phía trên để tải lên ảnh mới.</span>
                            </div>
                        `;
                    }
                }
            })
            .catch(err => {
                console.error('Lỗi khi tải cấu hình quy chế giải đấu:', err);
                alert('Có lỗi xảy ra khi tải cấu hình quy chế cho giải đấu này!');
            });
    }


    function markImageForDeletion(eventId, imagePath, btn) {
        if (!confirm('Bạn có chắc chắn muốn xóa ảnh này khỏi album? (Ảnh sẽ thực sự bị xóa khi bạn bấm "Lưu thay đổi")')) {
            return;
        }
        const input = document.getElementById('deleted-images-' + eventId);
        if (input) {
            let deleted = input.value ? input.value.split(',') : [];
            deleted.push(imagePath);
            input.value = deleted.join(',');
        }
        // Ẩn wrapper của ảnh
        const wrapper = btn.closest('.gallery-item-wrapper');
        if (wrapper) {
            wrapper.style.transition = 'all 0.3s ease';
            wrapper.style.opacity = '0';
            setTimeout(() => {
                wrapper.remove();
            }, 300);
        }
    }

    // --- QUẢN LÝ PHẢN HỒI HỖ TRỢ JS LOGIC ---
    let supportTicketsList = [];

    async function loadSupportTickets() {
        const tbody = document.getElementById('supportTicketsTableBody');
        if (!tbody) return;

        tbody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                    <i class="fa-solid fa-spinner fa-spin" style="font-size: 1.5rem; margin-bottom: 0.5rem;"></i><br>
                    Đang tải danh sách phản hồi...
                </td>
            </tr>
        `;

        try {
            const response = await fetch('/admin/api/support');
            if (!response.ok) {
                if (response.status === 401) {
                    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--accent-orange); padding: 2rem;">Chưa đăng nhập quyền Admin hoặc phiên làm việc hết hạn.</td></tr>`;
                    return;
                }
                throw new Error('Lỗi tải dữ liệu');
            }
            
            supportTicketsList = await response.json();
            renderSupportTickets();
        } catch (err) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--accent-orange); padding: 2rem;"><i class="fa-solid fa-triangle-exclamation"></i> Lỗi khi tải danh sách: ${err.message}</td></tr>`;
        }
    }

    function renderSupportTickets() {
        const tbody = document.getElementById('supportTicketsTableBody');
        if (!tbody) return;

        const filter = document.getElementById('supportStatusFilter').value;
        const filtered = supportTicketsList.filter(t => filter === 'all' || t.status === filter);

        if (filtered.length === 0) {
            tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 3rem;">Không tìm thấy phản hồi nào phù hợp.</td></tr>`;
            return;
        }

        tbody.innerHTML = filtered.map(t => {
            let statusText = 'Chờ xử lý';
            let statusStyle = 'background: rgba(255, 94, 54, 0.12); color: #ff5e36; border: 1px solid rgba(255, 94, 54, 0.25); font-size: 0.8rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; display: inline-block;';
            
            if (t.status === 'resolved') {
                statusText = 'Đã xử lý';
                statusStyle = 'background: rgba(40, 167, 69, 0.12); color: #28a745; border: 1px solid rgba(40, 167, 69, 0.25); font-size: 0.8rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; display: inline-block;';
            } else if (t.status === 'ignored') {
                statusText = 'Đã bỏ qua';
                statusStyle = 'background: rgba(255,255,255,0.06); color: var(--text-muted); border: 1px solid var(--border-color); font-size: 0.8rem; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 600; display: inline-block;';
            }

            return `
                <tr>
                    <td style="font-weight: 600; color: var(--text-main);">${escapeHtml(t.athlete_name)}</td>
                    <td><span style="font-family: monospace; font-size: 0.9rem;">${escapeHtml(t.contact_info) || '-'}</span></td>
                    <td>
                        <div style="max-height: 100px; overflow-y: auto; white-space: pre-wrap; font-size: 0.9rem; line-height: 1.5; color: var(--text-main);">${escapeHtml(t.content)}</div>
                        ${t.admin_notes ? `<div style="margin-top: 0.5rem; padding: 0.4rem 0.6rem; background: rgba(0, 242, 254, 0.05); border-left: 3px solid var(--color-primary); font-size: 0.82rem; border-radius: 0 4px 4px 0;"><strong style="color: var(--color-primary);">Admin trả lời:</strong> ${escapeHtml(t.admin_notes)}</div>` : ''}
                    </td>
                    <td style="font-size: 0.85rem; color: var(--text-muted);">${t.created_at}</td>
                    <td><span style="${statusStyle}">${statusText}</span></td>
                    <td>
                        <div style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            <button class="btn btn-secondary btn-sm" onclick="openAdminResolveModal(${t.id})" style="padding: 0.3rem 0.6rem; font-size: 0.8rem; border-radius: 4px; display: inline-flex; align-items: center; justify-content: center; height: auto;">
                                <i class="fa-solid fa-edit"></i> Xử lý
                            </button>
                            <button class="btn btn-danger btn-sm" onclick="deleteSupportTicket(${t.id})" style="padding: 0.3rem 0.6rem; font-size: 0.8rem; border-radius: 4px; background: rgba(255, 8, 68, 0.15); border: 1px solid rgba(255, 8, 68, 0.25); color: #ff6e87; display: inline-flex; align-items: center; justify-content: center; height: auto;">
                                <i class="fa-solid fa-trash"></i> Xóa
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    function filterSupportTickets() {
        renderSupportTickets();
    }

    function escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    function openAdminResolveModal(ticketId) {
        const ticket = supportTicketsList.find(t => t.id === ticketId);
        if (!ticket) return;

        document.getElementById('adminResolveTicketId').value = ticket.id;
        document.getElementById('adminResolveAthlete').textContent = ticket.athlete_name || 'Ẩn danh';
        document.getElementById('adminResolveContact').textContent = ticket.contact_info || '-';
        document.getElementById('adminResolveContent').textContent = ticket.content;
        document.getElementById('adminResolveStatus').value = ticket.status;
        document.getElementById('adminResolveNotes').value = ticket.admin_notes || '';
        document.getElementById('adminResolveMsg').style.display = 'none';

        const modal = document.getElementById('adminResolveSupportModal');
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    function closeAdminResolveModal() {
        const modal = document.getElementById('adminResolveSupportModal');
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    // Submit handler for Admin Resolve form
    document.getElementById('adminResolveForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        const msg = document.getElementById('adminResolveMsg');
        msg.style.display = 'none';

        const ticketId = document.getElementById('adminResolveTicketId').value;
        const status = document.getElementById('adminResolveStatus').value;
        const notes = document.getElementById('adminResolveNotes').value.trim();

        try {
            const response = await fetch(`/admin/api/support/${ticketId}/resolve`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    status: status,
                    admin_notes: notes
                })
            });

            const result = await response.json();
            if (response.ok) {
                msg.className = 'support-form-msg success';
                msg.textContent = 'Lưu thông tin thành công!';
                msg.style.display = 'block';
                
                // Tải lại danh sách sau 1 giây và đóng modal
                setTimeout(() => {
                    closeAdminResolveModal();
                    loadSupportTickets();
                }, 1000);
            } else {
                msg.className = 'support-form-msg error';
                msg.textContent = result.error || 'Cập nhật thất bại.';
                msg.style.display = 'block';
            }
        } catch (err) {
            msg.className = 'support-form-msg error';
            msg.textContent = 'Lỗi kết nối mạng: ' + err.message;
            msg.style.display = 'block';
        }
    });

    async function deleteSupportTicket(ticketId) {
        if (!confirm('Bạn có chắc chắn muốn XÓA phản hồi này vĩnh viễn không?')) {
            return;
        }

        try {
            const response = await fetch(`/admin/api/support/${ticketId}`, {
                method: 'DELETE'
            });

            const result = await response.json();
            if (response.ok) {
                alert('Đã xóa phản hồi thành công.');
                loadSupportTickets();
            } else {
                alert('Lỗi: ' + (result.error || 'Không thể xóa phản hồi.'));
            }
        } catch (err) {
            alert('Lỗi kết nối: ' + err.message);
        }
    }


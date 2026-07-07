
        document.addEventListener("DOMContentLoaded", function() {
            // Chuyển dữ liệu Jinja2 sang mảng Javascript
            const athletes = [
                /* jinja_block */
                {
                    id: "jinja_var",
                    name: ""jinja_var"",
                    dept: ""jinja_var""
                },
                /* jinja_block */
            ];

            const searchInput = document.getElementById("athlete_search");
            const idInput = document.getElementById("athlete_id");
            const listContainer = document.getElementById("autocomplete_list");
            const form = document.getElementById("connect-form");

            // Hiển thị gợi ý dựa trên từ khoá nhập vào
            function renderSuggestions(val) {
                listContainer.innerHTML = "";
                if (!val) {
                    listContainer.style.display = "none";
                    return;
                }

                const filtered = athletes.filter(a => 
                    a.name.toLowerCase().includes(val.toLowerCase()) ||
                    a.dept.toLowerCase().includes(val.toLowerCase())
                );

                if (filtered.length === 0) {
                    listContainer.innerHTML = '<div class="autocomplete-no-result">Không tìm thấy vận động viên nào</div>';
                } else {
                    filtered.forEach(item => {
                        const div = document.createElement("div");
                        div.className = "autocomplete-item";
                        div.innerHTML = `<strong>${item.name}</strong> <span style="font-size:0.8rem; color:var(--text-muted); margin-left:0.5rem;">(${item.dept})</span>`;
                        div.addEventListener("click", function() {
                            searchInput.value = item.name;
                            idInput.value = item.id;
                            listContainer.style.display = "none";
                        });
                        listContainer.appendChild(div);
                    });
                }
                listContainer.style.display = "block";
            }

            // Lắng nghe sự kiện gõ phím
            searchInput.addEventListener("input", function(e) {
                // Xoá id cũ đi nếu người dùng gõ thay đổi
                idInput.value = "";
                renderSuggestions(this.value);
            });

            // Hiển thị toàn bộ danh sách khi click vào ô input
            searchInput.addEventListener("focus", function() {
                renderSuggestions(this.value || " ");
            });

            // Ẩn danh sách khi click ra ngoài
            document.addEventListener("click", function(e) {
                if (e.target !== searchInput && e.target !== listContainer && !listContainer.contains(e.target)) {
                    listContainer.style.display = "none";
                }
            });

            // Kiểm tra trước khi submit form
            form.addEventListener("submit", function(e) {
                if (!idInput.value) {
                    e.preventDefault();
                    alert("Vui lòng chọn chính xác tên vận động viên từ danh sách gợi ý!");
                    searchInput.focus();
                }
            });
        });
        
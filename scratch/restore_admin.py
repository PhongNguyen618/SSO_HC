"""
Khoi phuc admin.html tu git va apply lai cac thay doi can thiet.
"""
import subprocess

# 1. Lay file tu git
result = subprocess.run(['git', 'show', '6184914:templates/admin.html'], 
                       capture_output=True, cwd='.')
content = result.stdout  # binary

# 2. Fix UTF-8 byte error (chu "se" bi hong)
bad_bytes = b's\xe1\xba '
good_bytes = b's\xe1\xba\xbd '
if bad_bytes in content:
    content = content.replace(bad_bytes, good_bytes)
    print("Fixed UTF-8 byte for 'se'")

# Decode
text = content.decode('utf-8')

# 3. Apply change: Add table IDs for run-walk tables
text = text.replace(
    """🏃 BXH Chạy & Đi Bộ – {{ gender }} (Top 5)""",
    """🏃 BXH Chạy & Đi Bộ – {{ gender }} <span class="no-print">(Top 5)</span>"""
)
print("Applied: no-print span for (Top 5)")

text = text.replace(
    """<table style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                            <thead>
                                <tr style="border-bottom: 2px solid rgba({% if gender == 'Nam' %}76,175,80{% else %}233,30,99{% endif %},0.2);">
                                    <th style="text-align: center; padding: 0.5rem; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; width: 45px;">Hạng</th>""",
    """<table id="table-run-walk-{{ 'nam' if gender == 'Nam' else 'nu' }}" style="width: 100%; border-collapse: collapse; font-size: 0.85rem;">
                            <thead>
                                <tr style="border-bottom: 2px solid rgba({% if gender == 'Nam' %}76,175,80{% else %}233,30,99{% endif %},0.2);">
                                    <th style="text-align: center; padding: 0.5rem; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; width: 45px;">Hạng</th>"""
)
print("Applied: table IDs")

# 4. Add CSS media queries after the page-break-inside rule
old_css = """            .glass-card, table, tr {
                page-break-inside: avoid;
            }
        }"""
new_css = """            .glass-card, table, tr {
                page-break-inside: avoid;
            }
            /* Hiển thị toàn bộ danh sách khi in PDF */
            #table-run-walk-nam tbody tr,
            #table-run-walk-nu tbody tr {
                display: table-row !important;
            }
        }

        @media screen {
            /* Chỉ hiển thị tối đa 5 VĐV mỗi bảng Run/Walk Nam/Nữ trên giao diện web */
            #table-run-walk-nam tbody tr:nth-child(n+6),
            #table-run-walk-nu tbody tr:nth-child(n+6) {
                display: none !important;
            }
        }"""
text = text.replace(old_css, new_css)
print("Applied: CSS media queries")

# 5. Apply .slice(0, 5) in copyZaloSummary for Nam
text = text.replace(
    "statsData.run_walk_top.Nam.forEach((a, i) =>",
    "statsData.run_walk_top.Nam.slice(0, 5).forEach((a, i) =>"
)
print("Applied: .slice(0,5) for Nam")

# 6. Apply .slice(0, 5) in copyZaloSummary for Nu  
text = text.replace(
    "statsData.run_walk_top.N\u1eef.forEach((a, i) =>",
    "statsData.run_walk_top.N\u1eef.slice(0, 5).forEach((a, i) =>"
)
print("Applied: .slice(0,5) for Nu")

# 7. Add beforeprint/afterprint handlers with scope switch
# Insert them after the afterprint handler that already exists in git version
old_afterprint = """    window.addEventListener('afterprint', () => {
        const defaultFont = "'Be Vietnam Pro'";
        if (adminKcalChartInstance) {
            // Khôi phục Line Chart
            adminKcalChartInstance.options.scales.x.ticks.color = '#94B5DE';
            adminKcalChartInstance.options.scales.x.ticks.font = { family: defaultFont };
            adminKcalChartInstance.options.scales.y.ticks.color = '#94B5DE';
            adminKcalChartInstance.options.scales.y.ticks.font = { family: defaultFont };
            adminKcalChartInstance.options.scales.y.grid.color = 'rgba(255, 255, 255, 0.05)';
            adminKcalChartInstance.update('none');
        }
        if (adminSportChartInstance) {
            // Khôi phục Doughnut Chart
            adminSportChartInstance.options.plugins.legend.labels.color = '#e4e3e8';
            adminSportChartInstance.options.plugins.legend.labels.font = { family: defaultFont, size: 11 };
            adminSportChartInstance.update('none');
        }
    });"""

new_print_handlers = """    // Biến lưu trữ scope trước khi in để khôi phục sau in
    let scopeBeforePrint = 'all';

    // Tự động chuyển đổi màu và font nhãn biểu đồ Chart.js khi in ấn
    window.addEventListener('beforeprint', () => {
        // Tạm thời chuyển scope sang 'all' để bản in PDF luôn chứa đầy đủ thông tin (ALL)
        scopeBeforePrint = currentScope;
        switchScope('all');

        const brandFont = "'Outfit', 'Be Vietnam Pro', sans-serif";
        if (adminKcalChartInstance) {
            // Line Chart ticks, grids & font
            adminKcalChartInstance.options.scales.x.ticks.color = '#111111';
            adminKcalChartInstance.options.scales.x.ticks.font = { family: brandFont, size: 10, weight: 'bold' };
            adminKcalChartInstance.options.scales.y.ticks.color = '#111111';
            adminKcalChartInstance.options.scales.y.ticks.font = { family: brandFont, size: 10, weight: 'bold' };
            adminKcalChartInstance.options.scales.y.grid.color = 'rgba(0, 0, 0, 0.12)';
            adminKcalChartInstance.update('none'); // Cập nhật đồng bộ không hiệu ứng để chụp ảnh in tức thời
        }
        if (adminSportChartInstance) {
            // Doughnut Chart legend text, font & size
            adminSportChartInstance.options.plugins.legend.labels.color = '#111111';
            adminSportChartInstance.options.plugins.legend.labels.font = { family: brandFont, size: 11, weight: '600' };
            adminSportChartInstance.update('none'); // Cập nhật đồng bộ
        }
    });

    window.addEventListener('afterprint', () => {
        // Khôi phục lại scope ban đầu người dùng đang chọn xem
        switchScope(scopeBeforePrint);

        const defaultFont = "'Be Vietnam Pro'";
        if (adminKcalChartInstance) {
            // Khôi phục Line Chart
            adminKcalChartInstance.options.scales.x.ticks.color = '#94B5DE';
            adminKcalChartInstance.options.scales.x.ticks.font = { family: defaultFont };
            adminKcalChartInstance.options.scales.y.ticks.color = '#94B5DE';
            adminKcalChartInstance.options.scales.y.ticks.font = { family: defaultFont };
            adminKcalChartInstance.options.scales.y.grid.color = 'rgba(255, 255, 255, 0.05)';
            adminKcalChartInstance.update('none');
        }
        if (adminSportChartInstance) {
            // Khôi phục Doughnut Chart
            adminSportChartInstance.options.plugins.legend.labels.color = '#e4e3e8';
            adminSportChartInstance.options.plugins.legend.labels.font = { family: defaultFont, size: 11 };
            adminSportChartInstance.update('none');
        }
    });"""

text = text.replace(old_afterprint, new_print_handlers)
print("Applied: beforeprint/afterprint handlers with scope switch")

# Write output
with open('templates/admin.html', 'w', encoding='utf-8', newline='\n') as f:
    f.write(text)
print("\nFile saved! Verifying...")

# Verify bracket balance
import re
scripts = re.findall(r'<script[^>]*>(.*?)</script>', text, re.DOTALL)
big_script = max(scripts, key=len)
curly_o = big_script.count('{')
curly_c = big_script.count('}')
paren_o = big_script.count('(')
paren_c = big_script.count(')')
print(f"Big script: curly {curly_o}/{curly_c}, paren {paren_o}/{paren_c}")
if curly_o == curly_c and paren_o == paren_c:
    print("BALANCED! All good!")
else:
    print("WARNING: Still imbalanced!")

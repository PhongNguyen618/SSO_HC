import sqlite3
import unicodedata
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def normalize_name(name):
    if not name:
        return ""
    name_nfc = unicodedata.normalize("NFC", name)
    return name_nfc.replace("*", "").strip().lower()

def test_name_matching():
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    db_live = "SSO_HC_backup_v1.4.0_1783345876.db"
    
    # 1. Lấy tên từ backup
    conn_b = sqlite3.connect(db_backup)
    cur_b = conn_b.cursor()
    cur_b.execute("SELECT full_name FROM athletes WHERE id = 44")
    name_b = cur_b.fetchone()[0]
    conn_b.close()
    
    # 2. Lấy tên từ live
    conn_l = sqlite3.connect(db_live)
    cur_l = conn_l.cursor()
    cur_l.execute("SELECT full_name FROM athletes WHERE id = 44")
    name_l = cur_l.fetchone()[0]
    conn_l.close()
    
    norm_b = normalize_name(name_b)
    norm_l = normalize_name(name_l)
    
    print(f"Tên trong backup: '{name_b}' -> Chuẩn hóa: '{norm_b}'")
    print(f"Tên trong live  : '{name_l}' -> Chuẩn hóa: '{norm_l}'")
    print(f"Kết quả so khớp: {'KHỚP NHAU! ✅' if norm_b == norm_l else 'LỆCH NHAU! ❌'}")

if __name__ == "__main__":
    test_name_matching()

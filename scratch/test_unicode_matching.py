import sqlite3
import unicodedata

def test_matching():
    db_live = "SSO_HC.db"
    db_backup = "SSO_HC_backup_v1.4.0_1783059852.db"
    
    conn_l = sqlite3.connect(db_live)
    cur_l = conn_l.cursor()
    cur_l.execute("SELECT id, full_name FROM athletes WHERE id = 51")
    live_ath = cur_l.fetchone()
    conn_l.close()
    
    conn_b = sqlite3.connect(db_backup)
    cur_b = conn_b.cursor()
    cur_b.execute("SELECT id, full_name FROM athletes WHERE id = 51")
    backup_ath = cur_b.fetchone()
    conn_b.close()
    
    if not live_ath or not backup_ath:
        print("Athlete 51 not found in one of the databases.")
        return
        
    name_l = live_ath[1]
    name_b = backup_ath[1]
    
    print(f"Live Name len: {len(name_l)}")
    print(f"Backup Name len: {len(name_b)}")
    
    print(f"Exact match: {name_l == name_b}")
    
    # Normalize NFC
    nfc_l = unicodedata.normalize("NFC", name_l)
    nfc_b = unicodedata.normalize("NFC", name_b)
    print(f"NFC match: {nfc_l == nfc_b}")
    
    # Normalize NFD
    nfd_l = unicodedata.normalize("NFD", name_l)
    nfd_b = unicodedata.normalize("NFD", name_b)
    print(f"NFD match: {nfd_l == nfd_b}")

if __name__ == "__main__":
    test_matching()

import os
import json

def check_deleted_file():
    backup_file = "static/uploads/deleted_activities_backup.jsonl"
    if not os.path.exists(backup_file):
        print(f"File {backup_file} does not exist!")
        return
        
    print(f"File {backup_file} exists. Size: {os.path.getsize(backup_file)} bytes.")
    
    with open(backup_file, "r", encoding="utf-8") as f:
        lines = f.readlines()
        
    print(f"Total deleted activities logged: {len(lines)}")
    
    matches = 0
    for line in lines:
        try:
            data = json.loads(line)
            # Check if matching athlete_id = 51 or name
            if data.get("athlete_id") == 51 or "Ha" in str(data.get("athlete_name_raw")) or "Hà" in str(data.get("athlete_name_raw")):
                matches += 1
                print(f"Match {matches}:")
                print(f"  ID: {data.get('id')[:15]}... | Date: {data.get('activity_date')} | Name Raw: {data.get('athlete_name_raw')} | Title: {data.get('name')} | Reason: {data.get('reason')}")
        except Exception as e:
            print("Error parsing line:", e)
            
    print(f"Total matching deleted activities: {matches}")

if __name__ == "__main__":
    check_deleted_file()

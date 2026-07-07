import json

def read_first_lines():
    backup_file = "static/uploads/deleted_activities_backup.jsonl"
    with open(backup_file, "r", encoding="utf-8") as f:
        for idx in range(5):
            line = f.readline()
            if not line:
                break
            data = json.loads(line)
            print(f"Line {idx+1}: {data.get('athlete_name_raw')} | ID: {data.get('id')[:10]}... | Date: {data.get('activity_date')} | Reason: {data.get('reason')}")

if __name__ == "__main__":
    read_first_lines()

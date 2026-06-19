import requests
import os
import time

url = "http://127.0.0.1:8000/api/avatar/sync-profile"

# Find a valid athlete_id
# We will use athlete_id = 1 as default
athlete_id = 1

# Fake Base64 image data (1px red PNG)
image_data_1 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
# Fake Base64 image data (1px green PNG)
image_data_2 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="

print("--- TEST SYNC AVATAR AND REPLACE OLD IMAGE ---")

# Step 1: Send sync request 1
print(f"\n[Step 1] Sending sync request 1 for athlete ID {athlete_id}...")
payload = {
    "athlete_id": athlete_id,
    "image_data": image_data_1
}
response1 = requests.post(url, data=payload)
print(f"Response 1 status code: {response1.status_code}")
if response1.status_code == 200:
    res_data1 = response1.json()
    avatar_url1 = res_data1.get("avatar_url")
    print(f"Avatar URL 1: {avatar_url1}")
    
    file_path1 = avatar_url1.lstrip("/")
    if os.path.exists(file_path1):
        print(f"-> File 1 CREATED on disk: {file_path1}")
    else:
        print(f"-> Error: File 1 not found on disk: {file_path1}")
        exit(1)
else:
    print(f"Error sync 1: {response1.text}")
    exit(1)

# Wait 1 second to ensure timestamp changes
time.sleep(1)

# Step 2: Send sync request 2
print(f"\n[Step 2] Sending sync request 2 for athlete ID {athlete_id}...")
payload["image_data"] = image_data_2
response2 = requests.post(url, data=payload)
print(f"Response 2 status code: {response2.status_code}")
if response2.status_code == 200:
    res_data2 = response2.json()
    avatar_url2 = res_data2.get("avatar_url")
    print(f"Avatar URL 2: {avatar_url2}")
    
    file_path2 = avatar_url2.lstrip("/")
    if os.path.exists(file_path2):
        print(f"-> File 2 CREATED on disk: {file_path2}")
    else:
        print(f"-> Error: File 2 not found on disk: {file_path2}")
        exit(1)
        
    # Step 3: Check if file 1 has been deleted
    print("\n[Step 3] Checking if old file 1 has been deleted from disk...")
    if not os.path.exists(file_path1):
        print(f"-> SUCCESS: Old file ({file_path1}) has been deleted successfully!")
    else:
        print(f"-> FAILURE: Old file ({file_path1}) still exists on disk!")
else:
    print(f"Error sync 2: {response2.text}")
    exit(1)

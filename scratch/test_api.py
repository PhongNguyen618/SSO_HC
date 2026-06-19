import requests

url = "http://127.0.0.1:8000/api/avatar/sync-profile"
data = {
    "athlete_id": 52,  # ID VĐV Huynh Nht Bo trong DB
    "image_data": "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////wgALCAABAAEBAREA/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAgBAQABPxA="
}

try:
    response = requests.post(url, data=data)
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {response.headers}")
    print(f"Body: {response.text}")
except Exception as e:
    print(f"Error: {e}")

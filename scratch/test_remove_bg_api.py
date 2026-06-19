import requests
import os

url = "http://127.0.0.1:8000/api/avatar/remove-bg"
image_path = "avatar.png"
output_path = "scratch/avatar_nobg.png"

if not os.path.exists(image_path):
    print(f"Khong tim thay file {image_path} de test.")
else:
    print(f"Dang gui request POST toi {url} voi file {image_path}...")
    try:
        with open(image_path, "rb") as f:
            files = {"file": (image_path, f, "image/png")}
            response = requests.post(url, files=files, timeout=60)
            
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            with open(output_path, "wb") as out_f:
                out_f.write(response.content)
            print(f"Xoa nen thanh cong! Da luu ket qua vao {output_path}")
            print(f"Kich thuoc file ket qua: {len(response.content)} bytes")
        else:
            print("Loi tu server:")
            print(response.text)
    except Exception as e:
        print(f"Loi khi gui request: {str(e)}")

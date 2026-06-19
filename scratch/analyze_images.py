import os
from PIL import Image

def analyze():
    base_dir = r"c:\Users\PC\Desktop\SSO_HC"
    path_frame = os.path.join(base_dir, "frame.png")
    path_avatar = os.path.join(base_dir, "avatar.jpg")
    
    print("--- Analyze Frame ---")
    if os.path.exists(path_frame):
        img = Image.open(path_frame)
        print(f"Format: {img.format}")
        print(f"Mode: {img.mode}")
        print(f"Size: {img.size}")
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Kiem tra xem co pixel nao trong suot khong
            alpha = img.convert("RGBA").split()[-1]
            extrema = alpha.getextrema()
            print(f"Alpha channel range: {extrema}")
            # extrema la (min, max). Neu min == max == 255 nghia la anh hoan toan duc (khong co pixel trong suot)
            if extrema[0] == 255:
                print("Canh bao: Anh frame hoan toan duc (khong co pixel trong suot)!")
            else:
                # Dem so pixel trong suot
                transparent_pixels = sum(1 for p in alpha.getdata() if p < 128)
                total_pixels = img.size[0] * img.size[1]
                print(f"So pixel trong suot (< 128 alpha): {transparent_pixels} / {total_pixels} ({transparent_pixels/total_pixels*100:.2f}%)")
        else:
            print("Canh bao: Anh frame khong co kenh alpha!")
    else:
        print("Khong tim thay frame.png")
        
    print("\n--- Analyze Avatar ---")
    if os.path.exists(path_avatar):
        img = Image.open(path_avatar)
        print(f"Format: {img.format}")
        print(f"Mode: {img.mode}")
        print(f"Size: {img.size}")
    else:
        print("Khong tim thay avatar.jpg")

if __name__ == "__main__":
    analyze()

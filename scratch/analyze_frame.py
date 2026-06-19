import os
from PIL import Image

image_path = "static/uploads/frames/event_3_frame.png"
if os.path.exists(image_path):
    img = Image.open(image_path)
    print(f"Format: {img.format}")
    print(f"Size: {img.size}")
    print(f"Mode: {img.mode}")
    
    # Kiểm tra một số pixel ở vùng giữa để xem có phải là màu trắng đặc (255, 255, 255) hay trong suốt
    # Thử quét từ tâm ra ngoài theo trục X
    width, height = img.size
    center_y = height // 2
    
    # Lấy thông tin màu sắc dọc theo đường nằm ngang đi qua tâm
    pixels_info = []
    for x in range(0, width, width // 20):
        pixel = img.getpixel((x, center_y))
        pixels_info.append((x, pixel))
    
    print("Pixels doc theo truc X o tam:")
    for x, px in pixels_info:
        print(f"x={x}: {px}")
else:
    print(f"File {image_path} does not exist.")

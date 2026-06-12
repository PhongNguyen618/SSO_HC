FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Chỉ cài đặt curl để phục vụ healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Copy và cài đặt Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy toàn bộ mã nguồn ứng dụng
COPY . /app

# Tạo thư mục chứa database SQLite riêng biệt để mount Volume an toàn
RUN mkdir -p /app/data
ENV DATABASE_URL=sqlite:///./data/SSO_HC.db

# Expose port cho uvicorn
EXPOSE 8000

# Thiết lập volume cho database và tệp tin tải lên (uploads) để tránh mất dữ liệu
VOLUME ["/app/data", "/app/static/uploads"]

# Khởi chạy ứng dụng
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
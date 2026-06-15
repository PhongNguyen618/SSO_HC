FROM python:3.11-slim

# Tắt buffering log Python để xuất log thời gian thực
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Cài curl để phục vụ healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Cài Python dependencies trước (tận dụng Docker layer cache)
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy toàn bộ mã nguồn ứng dụng
# Lưu ý: .env và SSO_HC.db được loại trừ bởi .dockerignore
# và sẽ được inject/mount qua docker-compose.yml
COPY . /app

# Expose port uvicorn
EXPOSE 8000

# Volume cho uploads để tránh mất dữ liệu khi rebuild image
VOLUME ["/app/static/uploads"]

# Khởi chạy ứng dụng
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
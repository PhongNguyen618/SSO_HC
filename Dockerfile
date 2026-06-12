FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install build deps for packages like pandas if needed
RUN apt-get update && apt-get install -y --no-install-recommends build-essential gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*

# Copy and install Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy app
COPY . /app

# Database path (SQLite file will be created under /app)
ENV DATABASE_URL=sqlite:///./SSO_HC.db

# Expose port for uvicorn
EXPOSE 8000

# Ensure upload dir exists (will be created by app startup as well)
VOLUME ["/app/static/uploads"]

# Run uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
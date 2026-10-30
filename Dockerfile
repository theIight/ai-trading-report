FROM python:3.12-slim

# Thiết lập biến môi trường
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUTF8=1 \
    TRADINGAGENTS_LLM_MAX_RETRIES=10

WORKDIR /app

# Cài đặt các công cụ hệ thống cơ bản
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn
COPY main.py .

# Thư mục lưu kết quả và cache
RUN mkdir -p /app/Kết\ quả /app/cache

VOLUME ["/app/Kết quả", "/app/cache"]

ENTRYPOINT ["python", "main.py", "--headless"]

# Build stage
FROM python:3.12-slim AS builder

WORKDIR /build

# System deps for native extensions (argon2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install Node.js 20 for Tailwind CSS build
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node deps + CSS build
COPY package.json tailwind.config.js ./
RUN npm ci
COPY static/css/input.css static/css/input.css
COPY templates/ templates/
RUN npx tailwindcss -i static/css/input.css -o static/css/app.css --minify

# ------------------------------------------------------------------
# Runtime stage
FROM python:3.12-slim

WORKDIR /app

# Copy Python packages
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

# Copy built CSS
COPY --from=builder /build/static/css/app.css static/css/app.css

# Copy application code
COPY app/ app/
COPY templates/ templates/
COPY static/js/ static/js/

# Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]

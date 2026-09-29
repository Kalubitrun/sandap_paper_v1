# PaperCreate: Question Paper Studio + FastAPI document engine.
#
# Single-container deployment for Render:
#   - Next.js serves the UI on 0.0.0.0:$PORT (public).
#   - FastAPI serves on 127.0.0.1:8000 (internal only).
#   - Next.js rewrites /api/* -> FastAPI (see web/next.config.ts).
#   - supervisord runs and supervises both processes.
#
# Build:  docker build -t papercreate .
# Run:    docker run --rm -p 3000:3000 -e PORT=3000 papercreate
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=3000 \
    BACKEND_URL=http://127.0.0.1:8000

# System dependencies: LibreOffice (DOCX conversion), Node.js 22.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates curl gnupg \
        libreoffice-writer --no-install-recommends \
        fonts-dejavu \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg \
    && echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list \
    && apt-get update && apt-get install -y --no-install-recommends nodejs \
    && node --version && npm --version \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Python dependencies first (better layer caching).
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Backend source + school logo (required by the renderer).
COPY app ./app
COPY logo.webp ./

# Frontend: install with a frozen lockfile, then build.
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

WORKDIR /app

# Process supervision (supervisord itself comes from requirements.txt).
COPY supervisord.conf start.sh ./
RUN chmod +x start.sh

EXPOSE 3000

CMD ["/app/start.sh"]

FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    APP_DATA_DIR=/data \
    DESTINATION_DB=/data/destinations.sqlite3 \
    API_LIMIT_DB=/data/api-limits.sqlite3 \
    MAP_TRANSLATION_CACHE=/data/map-translations.sqlite3
WORKDIR /app/backend
COPY backend/requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock && \
    useradd --uid 10001 --create-home app && mkdir -p /data && chown app:app /data
COPY backend/ ./
COPY --from=frontend /build/dist /app/frontend/dist
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-server-header"]

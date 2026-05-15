# syntax=docker/dockerfile:1
# Single container: FastAPI + optimized React SPA (same origin). No Streamlit.

FROM node:22-alpine AS frontend
WORKDIR /app/desktop
COPY desktop/package.json desktop/package-lock.json ./
RUN npm ci
COPY desktop/ ./
# Same-origin API (browser talks to the same host serving this image).
ENV VITE_API_BASE=
RUN npm run build

FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY manpower_app ./manpower_app
COPY manpower_api ./manpower_api

COPY --from=frontend /app/desktop/dist ./static

ENV PYTHONUNBUFFERED=1
ENV STATIC_ROOT=/app/static

COPY scripts/docker_entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]

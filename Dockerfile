# --- 1) painel React ------------------------------------------------------------------------------
FROM node:22-alpine AS painel
WORKDIR /painel
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- 2) API + worker ------------------------------------------------------------------------------
FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 OCUPABOT_PAINEL_DIR=/app/painel
WORKDIR /app/backend
RUN useradd --create-home --uid 1000 ocupabot
COPY backend/pyproject.toml ./
COPY backend/ocupabot ./ocupabot
RUN pip install --no-cache-dir .
COPY backend/migracoes ./migracoes
COPY backend/alembic.ini ./
COPY --from=painel /painel/dist /app/painel
RUN mkdir -p /app/backend/data && chown -R ocupabot /app/backend/data
USER ocupabot
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/saude')"
CMD ["sh", "-c", "python -m ocupabot.cli migrar && uvicorn ocupabot.api.app:app --host 0.0.0.0 --port 8000 --proxy-headers"]

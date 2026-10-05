FROM node:22-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install --legacy-peer-deps --ignore-scripts
COPY frontend/ ./
ENV CI=true
RUN npm run build

FROM python:3.11-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.selfhost.txt .
RUN pip install --no-cache-dir -r requirements.selfhost.txt
COPY backend/ ./
COPY --from=frontend-build /frontend/build /app/static
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /data/files \
    && chown -R appuser:appuser /app /data/files
ENV STORAGE_DIR=/data/files
EXPOSE 8001
USER 10001:10001
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8001"]

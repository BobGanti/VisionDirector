# ---- UI build stage (Node) ----
FROM node:20-slim AS ui-build
WORKDIR /app

COPY package.json ./
# If you have a lockfile, use it; otherwise npm install is fine.
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY . .
RUN npm run build


# ---- Runtime stage (Python) ----
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
# Copy the built JS artefact from the UI stage
COPY --from=ui-build /app/index.js /app/index.js

# Cloud Run provides $PORT; gunicorn will bind to it
CMD exec gunicorn -b 0.0.0.0:${PORT:-8080} app:app

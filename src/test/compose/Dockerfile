# Development image – optimised for fast iteration, NOT for production.
#
# Differences from the production Dockerfile:
#   - python:3.12-slim instead of distroless  → has shell, easier to debug
#   - Source is volume-mounted at runtime      → code changes need only
#     `docker compose restart exporter`, NOT a full rebuild
#   - Dependencies are installed at build time → only rebuild if requirements.txt changes
#
# To test the PRODUCTION build instead:
#   docker compose -f src/test/compose/compose.yaml build --build-arg TARGET=prod exporter
#   (see the override in compose.yaml)

FROM python:3.12-slim

WORKDIR /app

# Install dependencies first (cached layer – only invalidated when requirements.txt changes)
COPY src/main/python/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source is NOT copied here – it is volume-mounted by compose.yaml.
# This means: edit code → docker compose restart exporter → changes are live.

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Non-root even in dev – keep parity with production
RUN useradd --no-create-home --shell /bin/false exporter
USER exporter

EXPOSE 8000

CMD ["python3", "src/main.py"]

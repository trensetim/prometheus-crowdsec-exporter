FROM python:3.12-slim AS builder

WORKDIR /build

RUN --mount=type=bind,source=src/main/python/requirements.txt,target=requirements.txt \
    pip install --no-cache-dir --target=/deps -r requirements.txt

FROM gcr.io/distroless/python3-debian12:nonroot

ARG APP_VERSION=unknown
ARG GIT_COMMIT=unknown
ENV APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    PYTHONPATH=/deps \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /deps /deps
COPY src/main/python /app/src/

WORKDIR /app

USER nonroot

EXPOSE 8000

ENTRYPOINT ["python3", "-m", "src.main"]

ARG APP_VERSION=unknown
ARG GIT_COMMIT=unknown

FROM python:3.14-alpine

ARG APP_VERSION
ARG GIT_COMMIT
ENV APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT}

RUN --mount=type=secret,id=host_openssl_cacerts,target=/etc/ssl/certs/ca-certificates.crt \
    --mount=type=bind,source=src/main/python/requirements.txt,target=requirements.txt \
    pip install --no-cache -r requirements.txt

WORKDIR /app
COPY --chown=nobody:nobody src/main/python/ /app

ENV PYTHONUNBUFFERED="1"
EXPOSE 8000
USER nobody

ENTRYPOINT ["python3", "/app/main.py"]

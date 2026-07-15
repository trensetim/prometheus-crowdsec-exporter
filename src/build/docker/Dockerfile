ARG VERSION=0.0.0-00000000

FROM python:3.14-alpine

ARG VERSION
ENV VERSION=${VERSION}

RUN --mount=type=secret,id=host_openssl_cacerts,target=/etc/ssl/certs/ca-certificates.crt \
    --mount=type=bind,source=src/main/python/requirements.txt,target=requirements.txt \
    pip install --no-cache -r requirements.txt

WORKDIR /app
USER nobody
ENV PYTHONUNBUFFERED="1"
EXPOSE 8000

COPY --chown=nobody:nobody src/main/python/ /app
RUN echo "${VERSION}" >/app/version.txt

ENTRYPOINT ["python3", "/app/main.py"]

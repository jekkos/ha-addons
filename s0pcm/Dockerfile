FROM ghcr.io/home-assistant/base:3.24

ARG TARGETARCH

RUN apk add --no-cache python3 py3-pip

COPY app/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt --break-system-packages

COPY app/ /app/
COPY rootfs /

WORKDIR /app

FROM --platform=$BUILDPLATFORM ghcr.io/home-assistant/base:3.24

ARG TARGETARCH

# Install Node.js and npm
RUN apk add --no-cache nodejs npm

WORKDIR /app

# Copy package files from dummycloud/
COPY dummycloud/package.json dummycloud/package-lock.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy application code from dummycloud/
COPY dummycloud/. ./

# Copy run script
COPY run.sh /
COPY rootfs /

EXPOSE 10000

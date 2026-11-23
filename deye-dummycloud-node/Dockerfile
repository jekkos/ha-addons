FROM --platform=$BUILDPLATFORM ghcr.io/home-assistant/base:3.24

ARG TARGETARCH

# Install Node.js and npm
RUN apk add --no-cache nodejs npm

WORKDIR /app

# Copy package files from dummycloud/
COPY deye-dummycloud-node/dummycloud/package.json deye-dummycloud-node/dummycloud/package-lock.json ./

# Install dependencies
RUN npm ci --only=production && npm cache clean --force

# Copy application code from dummycloud/
COPY deye-dummycloud-node/dummycloud/. ./

# Copy run script
COPY deye-dummycloud-node/run.sh /
COPY deye-dummycloud-node/rootfs /

EXPOSE 10000

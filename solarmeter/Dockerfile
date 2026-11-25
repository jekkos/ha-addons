# Stage 1: Build C++ binary
FROM --platform=$BUILDPLATFORM gcc:12-bookworm AS builder

ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends \
    git make g++ libmosquitto-dev \
    && rm -rf /var/lib/apt/lists/*

# Clone and build libabbaurora
RUN git clone --depth 1 https://github.com/ahpohl/libabbaurora.git /tmp/libabbaurora \
    && cd /tmp/libabbaurora \
    && sed -i 's/ln\s-sr\(.*\)/ln -s \1/g' Makefile \
    && PREFIX=/tmp/stage make install \
    && rm -rf /tmp/libabbaurora

# Build solarmeter
COPY include /tmp/solarmeter/include
COPY src /tmp/solarmeter/src
COPY Makefile /tmp/solarmeter/Makefile
WORKDIR /tmp/solarmeter
RUN LDFLAGS="-L/tmp/stage/lib" CFLAGS="-I/tmp/stage/include" \
    make install PREFIX=/tmp/stage && rm -rf /tmp/solarmeter

# Stage 2: Runtime
FROM debian:bookworm-slim

# Install s6-overlay
COPY --from=ghcr.io/just-containers/s6-overlay:latest / /

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmosquitto1 \
    && rm -rf /var/lib/apt/lists/*

# Copy built binary and libs
COPY --from=builder /tmp/stage/bin/solarmeter /usr/local/bin/solarmeter
COPY --from=builder /tmp/stage/lib/libabbaurora.so* /usr/local/lib/
RUN ldconfig

# Copy example config
COPY resources/config/solarmeter_example.conf /etc/solarmeter.conf

# Copy service definition
COPY rootfs/ /

ENTRYPOINT ["/init"]

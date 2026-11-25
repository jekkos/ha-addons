FROM --platform=$BUILDPLATFORM ghcr.io/home-assistant/base:3.24

# Install build dependencies
RUN apk add --no-cache gcc g++ musl-dev mosquitto-dev git make

# Clone and build libabbaurora
RUN git clone --depth 1 https://github.com/ahpohl/libabbaurora.git /tmp/libabbaurora \
    && cd /tmp/libabbaurora \
    && sed -i 's/ln\s-sr\(.*\)/ln -s \1/g' Makefile \
    && PREFIX=/usr make install \
    && rm -rf /tmp/libabbaurora

# Build solarmeter
COPY include /tmp/solarmeter/include
COPY src /tmp/solarmeter/src
COPY Makefile /tmp/solarmeter/Makefile
WORKDIR /tmp/solarmeter
RUN make install PREFIX=/usr && rm -rf /tmp/solarmeter

# Install runtime dependencies
RUN apk add --no-cache mosquitto-libs

# Copy example config
COPY resources/config/solarmeter_example.conf /etc/solarmeter.conf

# Copy service definition
COPY rootfs/ /

ENTRYPOINT ["/init"]

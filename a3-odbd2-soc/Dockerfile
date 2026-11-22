FROM ghcr.io/home-assistant/base:3.24

RUN apk add --no-cache python3 py3-pip bluez bluez-dev

COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt --break-system-packages

COPY scripts /app
COPY run.sh /
RUN chmod a+x /run.sh

WORKDIR /app

CMD [ "/run.sh" ]

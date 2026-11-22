#!/command/with-contenv bashio

bashio::log.info "Starting A3 PHEV HV SOC app..."

# Read configuration
BLE_MAC=$(bashio::config 'ble_mac')
OBD_PID=$(bashio::config 'obd_pid')
READ_WAIT=$(bashio::config 'read_wait')
READ_RETRIES=$(bashio::config 'read_retries')
NET_USABLE_KWH=$(bashio::config 'net_usable_kwh')
MQTT_HOST=$(bashio::config 'mqtt_host')
MQTT_PORT=$(bashio::config 'mqtt_port')
MQTT_USERNAME=$(bashio::config 'mqtt_username')
MQTT_PASSWORD=$(bashio::config 'mqtt_password')

# Use built-in Mosquitto if no external broker configured
if [ -z "$MQTT_HOST" ]; then
    MQTT_HOST="core-mosquitto"
fi

bashio::log.info "BLE MAC: $BLE_MAC"
bashio::log.info "OBD PID: $OBD_PID"
bashio::log.info "MQTT: $MQTT_HOST:$MQTT_PORT"
bashio::log.info "Net usable kWh: $NET_USABLE_KWH"

# Check MQTT connectivity
bashio::log.info "Checking MQTT broker at $MQTT_HOST:$MQTT_PORT ..."
if ! timeout 3 bash -c "echo > /dev/tcp/$MQTT_HOST/$MQTT_PORT" 2>/dev/null; then
    bashio::log.error "Cannot connect to MQTT broker at $MQTT_HOST:$MQTT_PORT"
    bashio::log.error "Enable built-in Mosquitto in HA settings or configure external MQTT."
    exit 1
fi
bashio::log.info "MQTT broker reachable"

# Export env vars for Python script
export BLE_MAC
export OBD_PID
export READ_WAIT
export READ_RETRIES
export NET_USABLE_KWH
export MQTT_HOST
export MQTT_PORT
export MQTT_USERNAME
export MQTT_PASSWORD

# Run the Python script
exec python3 /app/ble_soc_mqtt.py

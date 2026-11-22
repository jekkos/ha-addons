#!/command/with-contenv bashio

# Read configuration
LOG_LEVEL=$(bashio::config 'log_level')
MQTT_BROKER_URL=$(bashio::config 'mqtt_broker_url')
MQTT_USERNAME=$(bashio::config 'mqtt_username')
MQTT_PASSWORD=$(bashio::config 'mqtt_password')
MQTT_CHECK_CERT=$(bashio::config 'mqtt_check_cert')
TOPIC_PREFIX=$(bashio::config 'topic_prefix')

# Set environment variables
export LOGLEVEL="${LOG_LEVEL:-info}"
export MQTT_BROKER_URL="${MQTT_BROKER_URL:-mqtt://core-mosquitto:1883}"
export MQTT_USERNAME
export MQTT_PASSWORD
export MQTT_CHECK_CERT="${MQTT_CHECK_CERT:-false}"
export TOPIC_PREFIX="${TOPIC_PREFIX:-deye-dummycloud}"

bashio::log.info "Starting Deye Dummy Cloud Node..."
bashio::log.info "LOG_LEVEL: $LOG_LEVEL"
bashio::log.info "MQTT_BROKER_URL: $MQTT_BROKER_URL"
bashio::log.info "TOPIC_PREFIX: $TOPIC_PREFIX"

# Run the application
exec npm start

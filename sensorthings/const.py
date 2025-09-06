DOMAIN = "sensorthings"
STAPI_VERSION = "v1.1"
CONF_URL = f"http://your-ip:your-port/FROST-Server/{STAPI_VERSION}"

# Configuration options
CONF_SCAN_INTERVAL = "scan_interval"
CONF_MQTT_ENABLED = "mqtt_enabled"
CONF_MQTT_PORT = "mqtt_port"

# Default values
DEFAULT_SCAN_INTERVAL = 60
DEFAULT_MQTT_ENABLED = True
DEFAULT_MQTT_PORT = 1883

# Service names
SERVICE_REFRESH_ALL = "refresh_all"
SERVICE_RECONNECT_MQTT = "reconnect_mqtt"

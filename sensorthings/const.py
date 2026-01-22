"""
Constants for the SensorThings integration.

This module defines all constants used throughout the integration,
including domain name, API version, configuration keys, defaults, and service names.
"""

# Integration domain identifier (used in Home Assistant)
DOMAIN = "sensorthings"

# SensorThings API version supported by this integration
STAPI_VERSION = "v1.1"

# Example URL format (used in documentation/placeholders)
CONF_URL = f"http://your-ip:your-port/FROST-Server/{STAPI_VERSION}"

# Configuration option keys (used in config flow and options flow)
CONF_SCAN_INTERVAL = "scan_interval"  # Polling interval in seconds
CONF_MQTT_ENABLED = "mqtt_enabled"    # Whether to use MQTT for real-time updates
CONF_MQTT_PORT = "mqtt_port"           # MQTT broker port number

# Default values for configuration options
DEFAULT_SCAN_INTERVAL = 60      # Default: poll every 60 seconds
DEFAULT_MQTT_ENABLED = True     # Default: MQTT enabled
DEFAULT_MQTT_PORT = 1883        # Default: standard MQTT port

# Service names (exposed to Home Assistant)
SERVICE_REFRESH_ALL = "refresh_all"        # Service to refresh all sensors
SERVICE_RECONNECT_MQTT = "reconnect_mqtt"   # Service to reconnect MQTT listeners

"""
SensorThings Integration for Home Assistant.

This module provides the main integration setup for the OGC SensorThings API.
It handles configuration entry setup, platform initialization, and service registration.
"""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, SERVICE_REFRESH_ALL, SERVICE_RECONNECT_MQTT

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """
    Set up the SensorThings integration.
    
    Note: YAML configuration is not supported; only UI setup via config flow.
    
    Args:
        hass: Home Assistant instance
        config: Configuration dictionary (not used)
        
    Returns:
        True to indicate successful setup
    """
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """
    Set up SensorThings from a config entry.
    
    This function is called when a user configures the SensorThings integration
    through the UI. It initializes the sensor and binary_sensor platforms and
    sets up the integration services.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry containing user-provided settings
        
    Returns:
        True if setup was successful
    """
    # Initialize domain data structure if it doesn't exist
    hass.data.setdefault(DOMAIN, {})
    # Store entry data for later use by platforms
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Forward setup to sensor and binary_sensor platforms
    # This will call async_setup_entry in sensor.py and binary_sensor.py
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor"])
    
    # Set up services (refresh_all and reconnect_mqtt)
    await async_setup_services(hass)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """
    Unload SensorThings config entry.
    
    Called when the integration is removed or disabled. Cleans up all
    platforms and removes stored data.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry to unload
        
    Returns:
        True if unload was successful
    """
    # Unload all platforms (sensor and binary_sensor)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor"])
    if unload_ok:
        # Clean up stored data for this entry
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup_services(hass: HomeAssistant):
    """
    Set up SensorThings services.
    
    Registers two services:
    - refresh_all: Manually refresh all SensorThings sensors
    - reconnect_mqtt: Reconnect MQTT listeners for all entries
    
    Args:
        hass: Home Assistant instance
    """
    
    async def handle_refresh_all(call):
        """
        Handle refresh_all service call.
        
        Triggers a refresh of all SensorThings coordinators across all
        configured entries. Useful for manual updates or troubleshooting.
        
        Args:
            call: Service call object (not used)
        """
        _LOGGER.info("Refreshing all SensorThings sensors")
        
        # Iterate through all configured entries
        for entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][entry_id]
            coordinator = entry_data.get("coordinator")
            
            # Request refresh if coordinator exists
            if coordinator:
                await coordinator.async_request_refresh()
                _LOGGER.debug("Refreshed coordinator for entry %s", entry_id)
    
    async def handle_reconnect_mqtt(call):
        """
        Handle reconnect_mqtt service call.
        
        Reconnects all MQTT listeners by stopping and restarting them.
        Useful when MQTT connection is lost or needs to be reset.
        
        Args:
            call: Service call object (not used)
        """
        _LOGGER.info("Reconnecting MQTT for all SensorThings entries")
        
        # Iterate through all configured entries
        for entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][entry_id]
            mqtt_listener = entry_data.get("mqtt_listener")
            
            # Reconnect MQTT listener if it exists
            if mqtt_listener:
                await mqtt_listener.stop()
                await mqtt_listener.start()
                _LOGGER.debug("Reconnected MQTT for entry %s", entry_id)
    
    # Register services with Home Assistant
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_ALL, handle_refresh_all)
    hass.services.async_register(DOMAIN, SERVICE_RECONNECT_MQTT, handle_reconnect_mqtt)
    
    _LOGGER.info("SensorThings services registered")

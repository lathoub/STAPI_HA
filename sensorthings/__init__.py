import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import DOMAIN, SERVICE_REFRESH_ALL, SERVICE_RECONNECT_MQTT

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    """YAML not supported; only UI setup via config flow."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up SensorThings from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data
    
    # Forward setup to sensor and binary_sensor platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "binary_sensor"])
    
    # Set up services
    await async_setup_services(hass)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload SensorThings config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, ["sensor", "binary_sensor"])
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_setup_services(hass: HomeAssistant):
    """Set up SensorThings services."""
    
    async def handle_refresh_all(call):
        """Handle refresh_all service call."""
        _LOGGER.info("Refreshing all SensorThings sensors")
        
        for entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][entry_id]
            coordinator = entry_data.get("coordinator")
            
            if coordinator:
                await coordinator.async_request_refresh()
                _LOGGER.debug("Refreshed coordinator for entry %s", entry_id)
    
    async def handle_reconnect_mqtt(call):
        """Handle reconnect_mqtt service call."""
        _LOGGER.info("Reconnecting MQTT for all SensorThings entries")
        
        for entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][entry_id]
            mqtt_listener = entry_data.get("mqtt_listener")
            
            if mqtt_listener:
                await mqtt_listener.stop()
                await mqtt_listener.start()
                _LOGGER.debug("Reconnected MQTT for entry %s", entry_id)
    
    # Register services
    hass.services.async_register(DOMAIN, SERVICE_REFRESH_ALL, handle_refresh_all)
    hass.services.async_register(DOMAIN, SERVICE_RECONNECT_MQTT, handle_reconnect_mqtt)
    
    _LOGGER.info("SensorThings services registered")

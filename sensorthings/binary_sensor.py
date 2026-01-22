"""
Binary sensor platform for SensorThings.

This module provides binary sensors that indicate the connectivity status
of SensorThings devices via MQTT. Each Thing gets a connectivity sensor
that shows whether it's currently connected to the MQTT broker.
"""
import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, CONF_URL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """
    Set up SensorThings binary sensors from a config entry.
    
    Creates a connectivity binary sensor for each Thing discovered by the
    coordinator. The sensor indicates whether the device is connected via MQTT.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        async_add_entities: Callback to add entities to Home Assistant
    """
    url = entry.data[CONF_URL]
    
    # Get the MQTT listener from hass data (set up by sensor platform)
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.warning("No MQTT listener found for entry %s", entry.entry_id)
        return
    
    mqtt_data = hass.data[DOMAIN][entry.entry_id]
    mqtt_listener = mqtt_data.get("mqtt_listener")
    
    if not mqtt_listener:
        _LOGGER.warning("No MQTT listener found for entry %s", entry.entry_id)
        return
    
    # Get coordinator data to find things
    # The coordinator is set up by the sensor platform and contains all Things
    coordinator = mqtt_data.get("coordinator")
    if not coordinator or not coordinator.data:
        _LOGGER.warning("No coordinator data found for entry %s", entry.entry_id)
        return
    
    binary_sensors = []
    
    # Create a connectivity binary sensor for each Thing
    for thing in coordinator.data:
        # Add connectivity binary sensor for each thing
        binary_sensors.append(
            SensorThingsConnectivity(thing, mqtt_listener, url)
        )
    
    # Add all binary sensors to Home Assistant
    async_add_entities(binary_sensors, True)


class SensorThingsConnectivity(BinarySensorEntity):
    """
    Binary sensor for SensorThings device connectivity status.
    
    This entity represents the MQTT connectivity status of a SensorThings Thing.
    It shows "on" when the MQTT listener is connected to the broker, and "off"
    when disconnected. This helps users monitor the real-time connection status
    of their SensorThings devices.
    """
    
    def __init__(self, thing, mqtt_listener, sensorthings_url):
        """
        Initialize the connectivity binary sensor.
        
        Args:
            thing: SensorThings Thing object from the API
            mqtt_listener: MQTT listener instance to check connection status
            sensorthings_url: Base URL of the SensorThings API server
        """
        self._thing = thing
        self._mqtt_listener = mqtt_listener
        self._sensorthings_url = sensorthings_url
        
        # Build device info for Home Assistant device registry
        # This links the binary sensor to the same device as the regular sensors
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
            "sw_version": thing.get("properties", {}).get("firmware_version", "1.3.2"),
        }
        # Add configuration URL if available (links to SensorThings server)
        if sensorthings_url:
            self._device_info["configuration_url"] = sensorthings_url

    @property
    def name(self):
        """
        Return the name of the binary sensor.
        
        Returns:
            String name for the entity (e.g., "Temperature Sensor Connected")
        """
        return f"{self._thing.get('name')} Connected"

    @property
    def unique_id(self):
        """
        Return a unique ID for the binary sensor.
        
        The unique ID is used by Home Assistant to identify this entity
        across restarts and configuration changes.
        
        Returns:
            Unique identifier string
        """
        return f"sensorthings_connectivity_{self._thing.get('@iot.id')}"

    @property
    def device_info(self):
        """
        Return device information.
        
        This links the binary sensor to the device in Home Assistant's
        device registry, grouping it with other sensors from the same Thing.
        
        Returns:
            Dictionary with device information
        """
        return self._device_info

    @property
    def entity_category(self):
        """
        Return the entity category.
        
        Marked as diagnostic since connectivity status is a technical metric
        rather than a primary sensor reading.
        
        Returns:
            EntityCategory.DIAGNOSTIC
        """
        return EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        """
        Return True if the device is connected via MQTT.
        
        This property determines the binary sensor's state. When True, the
        device is connected to the MQTT broker and can receive real-time updates.
        
        Returns:
            True if MQTT listener is connected, False otherwise
        """
        if not self._mqtt_listener:
            return False
        return self._mqtt_listener.is_connected()

    @property
    def icon(self):
        """
        Return the icon for the binary sensor.
        
        Uses wifi icon when connected, wifi-off when disconnected for
        visual indication of connection status.
        
        Returns:
            Material Design Icon name
        """
        return "mdi:wifi" if self.is_on else "mdi:wifi-off"

    @property
    def translation_key(self):
        """
        Return the translation key.
        
        Used for internationalization support. The translation key
        "connectivity" maps to translated strings in the translations directory.
        
        Returns:
            Translation key string
        """
        return "connectivity"

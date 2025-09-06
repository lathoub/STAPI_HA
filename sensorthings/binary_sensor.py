"""Binary sensor platform for SensorThings."""

import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, CONF_URL

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SensorThings binary sensors from a config entry."""
    url = entry.data[CONF_URL]
    
    # Get the MQTT listener from hass data
    if DOMAIN not in hass.data or entry.entry_id not in hass.data[DOMAIN]:
        _LOGGER.warning("No MQTT listener found for entry %s", entry.entry_id)
        return
    
    mqtt_data = hass.data[DOMAIN][entry.entry_id]
    mqtt_listener = mqtt_data.get("mqtt_listener")
    
    if not mqtt_listener:
        _LOGGER.warning("No MQTT listener found for entry %s", entry.entry_id)
        return
    
    # Get coordinator data to find things
    coordinator = mqtt_data.get("coordinator")
    if not coordinator or not coordinator.data:
        _LOGGER.warning("No coordinator data found for entry %s", entry.entry_id)
        return
    
    binary_sensors = []
    
    for thing in coordinator.data:
        # Add connectivity binary sensor for each thing
        binary_sensors.append(
            SensorThingsConnectivity(thing, mqtt_listener, url)
        )
    
    async_add_entities(binary_sensors, True)


class SensorThingsConnectivity(BinarySensorEntity):
    """Binary sensor for SensorThings device connectivity status."""
    
    def __init__(self, thing, mqtt_listener, sensorthings_url):
        """Initialize the connectivity binary sensor."""
        self._thing = thing
        self._mqtt_listener = mqtt_listener
        self._sensorthings_url = sensorthings_url
        
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
            "sw_version": thing.get("properties", {}).get("firmware_version", "1.3.2"),
        }
        if sensorthings_url:
            self._device_info["configuration_url"] = sensorthings_url

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return f"{self._thing.get('name')} Connected"

    @property
    def unique_id(self):
        """Return a unique ID for the binary sensor."""
        return f"sensorthings_connectivity_{self._thing.get('@iot.id')}"

    @property
    def device_info(self):
        """Return device information."""
        return self._device_info

    @property
    def entity_category(self):
        """Return the entity category."""
        return EntityCategory.DIAGNOSTIC

    @property
    def is_on(self):
        """Return True if the device is connected via MQTT."""
        if not self._mqtt_listener:
            return False
        return self._mqtt_listener.is_connected()

    @property
    def icon(self):
        """Return the icon for the binary sensor."""
        return "mdi:wifi" if self.is_on else "mdi:wifi-off"

    @property
    def translation_key(self):
        """Return the translation key."""
        return "connectivity"

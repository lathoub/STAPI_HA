"""
Sensor platform for SensorThings.

This module provides sensor entities for SensorThings datastreams. It supports
both polling (via coordinator) and real-time updates (via MQTT). Battery level
datastreams are automatically detected and shown as diagnostic sensors.
"""
import aiohttp
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.translation import async_get_translations
from .const import (
    DOMAIN, CONF_URL, CONF_SCAN_INTERVAL, CONF_MQTT_ENABLED, CONF_MQTT_PORT,
    DEFAULT_SCAN_INTERVAL, DEFAULT_MQTT_ENABLED, DEFAULT_MQTT_PORT
)
from .mqtt_listener import SensorThingsMQTTListener

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

def _is_battery_datastream(datastream):
    """
    Check if a specific datastream represents battery level.
    
    Identifies battery datastreams by checking if the name contains
    "battery" or "power" (case-insensitive).
    
    Args:
        datastream: Datastream dictionary from SensorThings API
        
    Returns:
        True if this appears to be a battery datastream, False otherwise
    """
    ds_name = datastream.get("name", "").lower()
    return "battery" in ds_name or "power" in ds_name

def _has_battery_datastream(thing):
    """
    Check if a thing has a datastream that represents battery level.
    
    Args:
        thing: Thing dictionary from SensorThings API
        
    Returns:
        True if the thing has at least one battery datastream, False otherwise
    """
    for ds in thing.get("Datastreams", []):
        if _is_battery_datastream(ds):
            return True
    return False

async def async_setup_entry(hass, entry, async_add_entities):
    """
    Set up SensorThings sensors from a config entry.
    
    This function:
    1. Initializes the MQTT listener if enabled
    2. Creates a coordinator for polling the SensorThings API
    3. Creates sensor entities for each datastream
    4. Creates diagnostic battery sensors for things with battery datastreams
    5. Stores coordinator and MQTT listener for use by other platforms and services
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry
        async_add_entities: Callback to add entities to Home Assistant
    """
    url = entry.data[CONF_URL]
    session = aiohttp.ClientSession()
    
    # Get configuration options from entry
    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    mqtt_enabled = entry.options.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)
    mqtt_port = entry.options.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
    
    # Initialize MQTT listener if enabled
    # MQTT provides real-time updates, reducing the need for frequent polling
    mqtt_listener = None
    if mqtt_enabled:
        mqtt_listener = SensorThingsMQTTListener(hass, url, mqtt_port)
        await mqtt_listener.start()
    
    async def async_fetch_data():
        """
        Fetch data from SensorThings API.
        
        Uses OData $expand to get Things with their Datastreams and the
        most recent Observation for each Datastream in a single request.
        
        Returns:
            List of Thing objects with expanded datastreams and observations
            
        Raises:
            UpdateFailed: If the API request fails
        """
        try:
            # OData query: expand Datastreams, and for each Datastream expand
            # Observations (get top 1, ordered by phenomenonTime descending)
            async with session.get(f"{url}/Things?$expand=Datastreams($expand=Observations($top=1;$orderby=phenomenonTime desc))") as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Bad status code {resp.status}")
                data = await resp.json()
                return data.get("value", [])
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
    
    # Create coordinator with configured scan interval
    # The coordinator handles periodic polling of the API
    update_interval = timedelta(seconds=scan_interval)
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="SensorThings", update_method=async_fetch_data, update_interval=update_interval)
    await coordinator.async_config_entry_first_refresh()
    
    sensors = []
    diagnostic_sensors = []
    
    # Create sensor entities for each datastream
    for thing in coordinator.data:
        for ds in thing.get("Datastreams", []):
            # Skip battery datastreams - they will be shown as diagnostic sensors
            # This prevents duplicate sensors and provides better UX
            if not _is_battery_datastream(ds):
                sensors.append(SensorThingsDatastream(ds, thing, coordinator, mqtt_listener, url))
        
        # Add battery level diagnostic sensor only if device has battery datastream
        # Battery sensors are shown as diagnostic entities with special icons
        if _has_battery_datastream(thing):
            diagnostic_sensors.append(SensorThingsBatteryLevel(thing, coordinator, mqtt_listener, url))
    
    # Add all sensors to Home Assistant
    async_add_entities(sensors + diagnostic_sensors, True)
    
    # Store coordinator and MQTT listener in hass data for:
    # - Services (refresh_all, reconnect_mqtt)
    # - Binary sensor platform (needs MQTT listener for connectivity status)
    # - Cleanup on unload
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {
        "mqtt_listener": mqtt_listener,
        "coordinator": coordinator
    }

async def async_unload_entry(hass, entry):
    """
    Unload the integration and cleanup MQTT listener.
    
    Called when the integration is removed or disabled. Stops the MQTT
    listener and cleans up stored data.
    
    Args:
        hass: Home Assistant instance
        entry: Configuration entry being unloaded
        
    Returns:
        True to indicate successful unload
    """
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        mqtt_data = hass.data[DOMAIN][entry.entry_id]
        # Stop MQTT listener to clean up connections
        if "mqtt_listener" in mqtt_data:
            await mqtt_data["mqtt_listener"].stop()
        # Remove stored data
        del hass.data[DOMAIN][entry.entry_id]
    return True

class SensorThingsDatastream(SensorEntity):
    """
    Sensor entity for a SensorThings datastream.
    
    Represents a single datastream from a SensorThings Thing. Supports both
    polling (via coordinator) and real-time updates (via MQTT). MQTT values
    take priority over coordinator data when available.
    """
    def __init__(self, datastream, thing, coordinator, mqtt_listener=None, sensorthings_url=None):
        """
        Initialize the datastream sensor.
        
        Args:
            datastream: Datastream dictionary from SensorThings API
            thing: Thing dictionary that owns this datastream
            coordinator: DataUpdateCoordinator for polling updates
            mqtt_listener: Optional MQTT listener for real-time updates
            sensorthings_url: Base URL of the SensorThings API server
        """
        self.coordinator = coordinator
        self._datastream_id = datastream.get("@iot.id")
        self._name = datastream.get("name", f"Datastream {self._datastream_id}")
        self._unit = datastream.get("unitOfMeasurement", {}).get("symbol", "")
        self._thing = thing
        self._mqtt_listener = mqtt_listener
        self._mqtt_value = None  # Latest value from MQTT
        self._mqtt_timestamp = None  # Timestamp of latest MQTT value
        
        # Build device info for Home Assistant device registry
        # This groups all sensors from the same Thing together
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
        }
        # Only add firmware version if it exists (optional field)
        firmware_version = thing.get("properties", {}).get("firmware_version")
        if firmware_version:
            self._device_info["sw_version"] = firmware_version
        # Add configuration URL if available (links to SensorThings server)
        if sensorthings_url:
            self._device_info["configuration_url"] = sensorthings_url
        
        # Subscribe to MQTT updates if available
        # This enables real-time updates without waiting for the next poll
        if self._mqtt_listener:
            self._mqtt_listener.subscribe(self._datastream_id, self._on_mqtt_update)

    @property
    def name(self):
        """
        Return the name of the sensor.
        
        Combines Thing name and datastream name for clarity.
        
        Returns:
            Sensor name string
        """
        return f"{self._thing.get('name')} {self._name}"

    @property
    def unique_id(self):
        """
        Return a unique ID for the sensor.
        
        Uses the datastream ID to ensure uniqueness across Home Assistant.
        
        Returns:
            Unique identifier string
        """
        return f"sensorthings_{self._datastream_id}"

    @property
    def device_info(self):
        """
        Return device information.
        
        Links this sensor to the device in Home Assistant's device registry.
        
        Returns:
            Dictionary with device information
        """
        return self._device_info

    @property
    def native_unit_of_measurement(self):
        """
        Return the unit of measurement.
        
        Extracted from the datastream's unitOfMeasurement property.
        
        Returns:
            Unit symbol string (e.g., "°C", "m/s", "%")
        """
        return self._unit

    @property
    def native_value(self):
        """
        Return the current sensor value.
        
        Prioritizes MQTT values (real-time) over coordinator data (polled).
        This ensures users get the most up-to-date readings when MQTT is available.
        
        Returns:
            Current sensor value, or None if no data available
        """
        # Prioritize MQTT value if available (real-time updates)
        if self._mqtt_value is not None:
            return self._mqtt_value
        
        # Fall back to coordinator data (polled from API)
        # Search through coordinator data to find this datastream's latest observation
        for thing in self.coordinator.data:
            if thing.get("@iot.id") == self._thing.get("@iot.id"):
                for ds in thing.get("Datastreams", []):
                    if ds.get("@iot.id") == self._datastream_id:
                        obs = ds.get("Observations", [])
                        if obs:
                            # Return the most recent observation result
                            return obs[0].get("result")
        return None

    @callback
    def _on_mqtt_update(self, value, timestamp=None):
        """
        Handle MQTT update for this sensor.
        
        Called by the MQTT listener when a new observation is received.
        Updates the cached value and schedules a state update in Home Assistant.
        
        Args:
            value: New sensor value from MQTT
            timestamp: Optional timestamp when the value was measured
        """
        _LOGGER.debug(f"MQTT update for {self.unique_id}: {value}")
        self._mqtt_value = value
        self._mqtt_timestamp = timestamp
        # Schedule entity update to refresh the displayed value
        self.async_schedule_update_ha_state()

    async def async_update(self):
        """
        Update the sensor value.
        
        Only requests a coordinator refresh if MQTT is not available or
        not connected. This avoids unnecessary API calls when real-time
        updates are working via MQTT.
        """
        # Only request coordinator refresh if MQTT is not available or not connected
        if not self._mqtt_listener or not self._mqtt_listener.is_connected():
            await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self):
        """
        Clean up MQTT subscription when entity is removed.
        
        Called by Home Assistant when the entity is being removed. Unsubscribes
        from MQTT updates to prevent memory leaks and unnecessary processing.
        """
        if self._mqtt_listener:
            self._mqtt_listener.unsubscribe(self._datastream_id)


class SensorThingsBatteryLevel(SensorEntity):
    """
    Diagnostic sensor for battery level.
    
    Special sensor entity for battery level that:
    - Is marked as diagnostic (not a primary sensor)
    - Shows battery icon that changes based on level
    - Uses percentage units
    - Supports both polling and MQTT updates
    """
    
    def __init__(self, thing, coordinator, mqtt_listener=None, sensorthings_url=None):
        """
        Initialize the battery level sensor.
        
        Args:
            thing: Thing dictionary that owns the battery datastream
            coordinator: DataUpdateCoordinator for polling updates
            mqtt_listener: Optional MQTT listener for real-time updates
            sensorthings_url: Base URL of the SensorThings API server
        """
        self.coordinator = coordinator
        self._thing = thing
        self._mqtt_listener = mqtt_listener
        # Find the battery datastream for this thing
        self._battery_datastream = self._find_battery_datastream(thing)
        self._mqtt_value = None  # Latest value from MQTT
        self._mqtt_timestamp = None  # Timestamp of latest MQTT value
        
        # Build device info (same as regular sensors)
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
        }
        # Only add firmware version if it exists (optional field)
        firmware_version = thing.get("properties", {}).get("firmware_version")
        if firmware_version:
            self._device_info["sw_version"] = firmware_version
        # Add configuration URL if available
        if sensorthings_url:
            self._device_info["configuration_url"] = sensorthings_url
        
        # Subscribe to MQTT updates if available and we have a battery datastream
        if self._mqtt_listener and self._battery_datastream:
            battery_datastream_id = self._battery_datastream.get("@iot.id")
            if battery_datastream_id:
                self._mqtt_listener.subscribe(battery_datastream_id, self._on_mqtt_update)
    
    def _find_battery_datastream(self, thing):
        """
        Find the battery datastream for this thing.
        
        Searches through all datastreams to find one that represents battery level.
        
        Args:
            thing: Thing dictionary to search
            
        Returns:
            Battery datastream dictionary, or None if not found
        """
        for ds in thing.get("Datastreams", []):
            if _is_battery_datastream(ds):
                return ds
        return None
    
    
    @property
    def translation_key(self):
        """
        Return the translation key for the entity name.
        
        Used for internationalization. The name will be translated based on
        the translation files in the translations directory.
        
        Returns:
            Translation key string
        """
        return "battery_level"
    
    @property
    def has_entity_name(self):
        """
        Indicate that this entity uses a translated name.
        
        When True, Home Assistant will use the translation_key to generate
        the entity name, which will be combined with the device name.
        
        Returns:
            True
        """
        return True
    
    @property
    def unique_id(self):
        """
        Return a unique ID for the battery sensor.
        
        Uses the Thing ID to ensure uniqueness. Only one battery sensor
        per Thing is created.
        
        Returns:
            Unique identifier string
        """
        return f"sensorthings_battery_level_{self._thing.get('@iot.id')}"
    
    @property
    def device_info(self):
        """
        Return device information.
        
        Links this sensor to the device in Home Assistant's device registry.
        
        Returns:
            Dictionary with device information
        """
        return self._device_info
    
    @property
    def entity_category(self):
        """
        Return the entity category.
        
        Marked as diagnostic since battery level is a technical metric
        rather than a primary sensor reading.
        
        Returns:
            EntityCategory.DIAGNOSTIC
        """
        return EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self):
        """
        Return the current battery level.
        
        Prioritizes MQTT values (real-time) over coordinator data (polled).
        
        Returns:
            Battery level as percentage (0-100), or None if no data available
        """
        # Prioritize MQTT value if available (real-time updates)
        if self._mqtt_value is not None:
            return self._mqtt_value
        
        # Fall back to coordinator data (polled from API)
        if self._battery_datastream:
            obs = self._battery_datastream.get("Observations", [])
            if obs:
                # Return the most recent observation result
                return obs[0].get("result")
        return None
    
    @property
    def native_unit_of_measurement(self):
        """
        Return the unit of measurement.
        
        Battery level is always shown as a percentage.
        
        Returns:
            "%"
        """
        return "%"
    
    @property
    def icon(self):
        """
        Return the icon for the battery sensor.
        
        Icon changes based on battery level to provide visual feedback:
        - Unknown: battery-unknown
        - >75%: battery (full)
        - >50%: battery-75
        - >25%: battery-50
        - >10%: battery-25
        - <=10%: battery-alert (low battery warning)
        
        Returns:
            Material Design Icon name
        """
        battery_level = self.native_value
        if battery_level is None:
            return "mdi:battery-unknown"
        elif battery_level > 75:
            return "mdi:battery"
        elif battery_level > 50:
            return "mdi:battery-75"
        elif battery_level > 25:
            return "mdi:battery-50"
        elif battery_level > 10:
            return "mdi:battery-25"
        else:
            return "mdi:battery-alert"
    
    @callback
    def _on_mqtt_update(self, value, timestamp=None):
        """
        Handle MQTT update for battery level.
        
        Called by the MQTT listener when a new battery observation is received.
        Updates the cached value and schedules a state update in Home Assistant.
        
        Args:
            value: New battery level value from MQTT
            timestamp: Optional timestamp when the value was measured
        """
        _LOGGER.debug(f"MQTT battery update for {self.unique_id}: {value}")
        self._mqtt_value = value
        self._mqtt_timestamp = timestamp
        # Schedule entity update to refresh the displayed value and icon
        self.async_schedule_update_ha_state()
    
    async def async_update(self):
        """
        Update the sensor value.
        
        Only requests a coordinator refresh if MQTT is not available or
        not connected. This avoids unnecessary API calls when real-time
        updates are working via MQTT.
        """
        # Only request coordinator refresh if MQTT is not available or not connected
        if not self._mqtt_listener or not self._mqtt_listener.is_connected():
            await self.coordinator.async_request_refresh()
    
    async def async_will_remove_from_hass(self):
        """
        Clean up MQTT subscription when entity is removed.
        
        Called by Home Assistant when the entity is being removed. Unsubscribes
        from MQTT updates to prevent memory leaks and unnecessary processing.
        """
        if self._mqtt_listener and self._battery_datastream:
            battery_datastream_id = self._battery_datastream.get("@iot.id")
            if battery_datastream_id:
                self._mqtt_listener.unsubscribe(battery_datastream_id)

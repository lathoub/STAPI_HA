import aiohttp
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.translation import async_get_translations
from .const import DOMAIN, CONF_URL
from .mqtt_listener import SensorThingsMQTTListener

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

def _is_battery_datastream(datastream):
    """Check if a specific datastream represents battery level."""
    ds_name = datastream.get("name", "").lower()
    return "battery" in ds_name or "power" in ds_name

def _has_battery_datastream(thing):
    """Check if a thing has a datastream that represents battery level."""
    for ds in thing.get("Datastreams", []):
        if _is_battery_datastream(ds):
            return True
    return False

async def async_setup_entry(hass, entry, async_add_entities):
    url = entry.data[CONF_URL]
    session = aiohttp.ClientSession()
    
    # Initialize MQTT listener for built-in FROST MQTT broker
    mqtt_listener = SensorThingsMQTTListener(hass, url)
    await mqtt_listener.start()
    
    async def async_fetch_data():
        try:
            async with session.get(f"{url}/Things?$expand=Datastreams($expand=Observations($top=1;$orderby=phenomenonTime desc))") as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"Bad status code {resp.status}")
                data = await resp.json()
                return data.get("value", [])
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
    
    coordinator = DataUpdateCoordinator(hass, _LOGGER, name="SensorThings", update_method=async_fetch_data, update_interval=SCAN_INTERVAL)
    await coordinator.async_config_entry_first_refresh()
    
    sensors = []
    diagnostic_sensors = []
    
    for thing in coordinator.data:
        for ds in thing.get("Datastreams", []):
            # Skip battery datastreams - they will be shown as diagnostic sensors
            if not _is_battery_datastream(ds):
                sensors.append(SensorThingsDatastream(ds, thing, coordinator, mqtt_listener, url))
        
        # Add battery level diagnostic sensor only if device has battery datastream
        if _has_battery_datastream(thing):
            diagnostic_sensors.append(SensorThingsBatteryLevel(thing, coordinator, mqtt_listener, url))
    
    async_add_entities(sensors + diagnostic_sensors, True)
    
    # Store MQTT listener in hass data for cleanup
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {"mqtt_listener": mqtt_listener}

async def async_unload_entry(hass, entry):
    """Unload the integration and cleanup MQTT listener."""
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        mqtt_data = hass.data[DOMAIN][entry.entry_id]
        if "mqtt_listener" in mqtt_data:
            await mqtt_data["mqtt_listener"].stop()
        del hass.data[DOMAIN][entry.entry_id]
    return True

class SensorThingsDatastream(SensorEntity):
    def __init__(self, datastream, thing, coordinator, mqtt_listener=None, sensorthings_url=None):
        self.coordinator = coordinator
        self._datastream_id = datastream.get("@iot.id")
        self._name = datastream.get("name", f"Datastream {self._datastream_id}")
        self._unit = datastream.get("unitOfMeasurement", {}).get("symbol", "")
        self._thing = thing
        self._mqtt_listener = mqtt_listener
        self._mqtt_value = None
        self._mqtt_timestamp = None
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
            "sw_version": thing.get("properties", {}).get("firmware_version", "1.3.2"),
        }
        if sensorthings_url:
            self._device_info["configuration_url"] = sensorthings_url
        
        # Subscribe to MQTT updates if available
        if self._mqtt_listener:
            self._mqtt_listener.subscribe(self._datastream_id, self._on_mqtt_update)

    @property
    def name(self):
        return f"{self._thing.get('name')} {self._name}"

    @property
    def unique_id(self):
        return f"sensorthings_{self._datastream_id}"

    @property
    def device_info(self):
        return self._device_info

    @property
    def native_unit_of_measurement(self):
        return self._unit

    @property
    def native_value(self):
        # Prioritize MQTT value if available
        if self._mqtt_value is not None:
            return self._mqtt_value
        
        # Fall back to coordinator data
        for thing in self.coordinator.data:
            if thing.get("@iot.id") == self._thing.get("@iot.id"):
                for ds in thing.get("Datastreams", []):
                    if ds.get("@iot.id") == self._datastream_id:
                        obs = ds.get("Observations", [])
                        if obs:
                            return obs[0].get("result")
        return None

    @callback
    def _on_mqtt_update(self, value, timestamp=None):
        """Handle MQTT update for this sensor."""
        _LOGGER.debug(f"MQTT update for {self.unique_id}: {value}")
        self._mqtt_value = value
        self._mqtt_timestamp = timestamp
        # Schedule entity update
        self.async_schedule_update_ha_state()

    async def async_update(self):
        # Only request coordinator refresh if MQTT is not available or not connected
        if not self._mqtt_listener or not self._mqtt_listener.is_connected():
            await self.coordinator.async_request_refresh()

    async def async_will_remove_from_hass(self):
        """Clean up MQTT subscription when entity is removed."""
        if self._mqtt_listener:
            self._mqtt_listener.unsubscribe(self._datastream_id)


class SensorThingsBatteryLevel(SensorEntity):
    """Diagnostic sensor for battery level."""
    
    def __init__(self, thing, coordinator, mqtt_listener=None, sensorthings_url=None):
        self.coordinator = coordinator
        self._thing = thing
        self._mqtt_listener = mqtt_listener
        self._battery_datastream = self._find_battery_datastream(thing)
        self._mqtt_value = None
        self._mqtt_timestamp = None
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
            "sw_version": thing.get("properties", {}).get("firmware_version", "1.3.2"),
        }
        if sensorthings_url:
            self._device_info["configuration_url"] = sensorthings_url
        
        # Subscribe to MQTT updates if available and we have a battery datastream
        if self._mqtt_listener and self._battery_datastream:
            battery_datastream_id = self._battery_datastream.get("@iot.id")
            if battery_datastream_id:
                self._mqtt_listener.subscribe(battery_datastream_id, self._on_mqtt_update)
    
    def _find_battery_datastream(self, thing):
        """Find the battery datastream for this thing."""
        for ds in thing.get("Datastreams", []):
            if _is_battery_datastream(ds):
                return ds
        return None
    
    @property
    def name(self):
        return f"{self._thing.get('name')} Battery Level"
    
    @property
    def unique_id(self):
        return f"sensorthings_battery_level_{self._thing.get('@iot.id')}"
    
    @property
    def device_info(self):
        return self._device_info
    
    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC
    
    @property
    def native_value(self):
        # Prioritize MQTT value if available
        if self._mqtt_value is not None:
            return self._mqtt_value
        
        # Fall back to coordinator data
        if self._battery_datastream:
            obs = self._battery_datastream.get("Observations", [])
            if obs:
                return obs[0].get("result")
        return None
    
    @property
    def native_unit_of_measurement(self):
        return "%"
    
    @property
    def icon(self):
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
        """Handle MQTT update for battery level."""
        _LOGGER.debug(f"MQTT battery update for {self.unique_id}: {value}")
        self._mqtt_value = value
        self._mqtt_timestamp = timestamp
        # Schedule entity update
        self.async_schedule_update_ha_state()
    
    async def async_update(self):
        # Only request coordinator refresh if MQTT is not available or not connected
        if not self._mqtt_listener or not self._mqtt_listener.is_connected():
            await self.coordinator.async_request_refresh()
    
    async def async_will_remove_from_hass(self):
        """Clean up MQTT subscription when entity is removed."""
        if self._mqtt_listener and self._battery_datastream:
            battery_datastream_id = self._battery_datastream.get("@iot.id")
            if battery_datastream_id:
                self._mqtt_listener.unsubscribe(battery_datastream_id)

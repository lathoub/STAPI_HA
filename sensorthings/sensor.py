import aiohttp
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import callback
from .const import DOMAIN, CONF_URL
from .mqtt_listener import SensorThingsMQTTListener

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

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
    for thing in coordinator.data:
        for ds in thing.get("Datastreams", []):
            sensors.append(SensorThingsDatastream(ds, thing, coordinator, mqtt_listener))
    
    async_add_entities(sensors, True)
    
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
    def __init__(self, datastream, thing, coordinator, mqtt_listener=None):
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

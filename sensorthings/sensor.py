import aiohttp
import logging
from datetime import timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import DOMAIN, CONF_URL

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=60)

async def async_setup_entry(hass, entry, async_add_entities):
    url = entry.data[CONF_URL]
    session = aiohttp.ClientSession()
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
            sensors.append(SensorThingsDatastream(ds, thing, coordinator))
    async_add_entities(sensors, True)

class SensorThingsDatastream(SensorEntity):
    def __init__(self, datastream, thing, coordinator):
        self.coordinator = coordinator
        self._datastream_id = datastream.get("@iot.id")
        self._name = datastream.get("name", f"Datastream {self._datastream_id}")
        self._unit = datastream.get("unitOfMeasurement", {}).get("symbol", "")
        self._thing = thing
        self._device_info = {
            "identifiers": {(DOMAIN, thing.get("@iot.id"))},
            "name": thing.get("name", f"Thing {thing.get('@iot.id')}"),
            "model": thing.get("properties", {}).get("model", "SensorThings Thing"),
            "manufacturer": thing.get("properties", {}).get("manufacturer", "Unknown"),
        }

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
        for thing in self.coordinator.data:
            if thing.get("@iot.id") == self._thing.get("@iot.id"):
                for ds in thing.get("Datastreams", []):
                    if ds.get("@iot.id") == self._datastream_id:
                        obs = ds.get("Observations", [])
                        if obs:
                            return obs[0].get("result")
        return None

    async def async_update(self):
        await self.coordinator.async_request_refresh()

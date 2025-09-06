"""Test the SensorThings sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.sensorthings.sensor import (
    SensorThingsDatastream,
    SensorThingsBatteryLevel,
    _is_battery_datastream,
    _has_battery_datastream,
    async_setup_entry,
    async_unload_entry,
)


class TestSensorThingsDatastream:
    """Test SensorThingsDatastream sensor."""

    @pytest.fixture
    def datastream_data(self):
        """Sample datastream data."""
        return {
            "@iot.id": "1",
            "name": "Temperature",
            "unitOfMeasurement": {"symbol": "°C"},
            "Observations": [{"result": 22.5}]
        }

    @pytest.fixture
    def thing_data(self):
        """Sample thing data."""
        return {
            "@iot.id": "1",
            "name": "Test Thing",
            "properties": {
                "model": "Test Model",
                "manufacturer": "Test Manufacturer",
                "firmware_version": "1.0.0"
            }
        }

    @pytest.fixture
    def sensor(self, datastream_data, thing_data, mock_coordinator, mock_mqtt_listener, mock_sensorthings_url):
        """Create SensorThingsDatastream instance."""
        return SensorThingsDatastream(
            datastream_data,
            thing_data,
            mock_coordinator,
            mock_mqtt_listener,
            mock_sensorthings_url
        )

    def test_name(self, sensor, datastream_data, thing_data):
        """Test sensor name."""
        expected_name = f"{thing_data['name']} {datastream_data['name']}"
        assert sensor.name == expected_name

    def test_unique_id(self, sensor, datastream_data):
        """Test sensor unique ID."""
        expected_id = f"sensorthings_{datastream_data['@iot.id']}"
        assert sensor.unique_id == expected_id

    def test_native_unit_of_measurement(self, sensor, datastream_data):
        """Test native unit of measurement."""
        assert sensor.native_unit_of_measurement == datastream_data["unitOfMeasurement"]["symbol"]

    def test_native_value_from_coordinator(self, sensor, datastream_data):
        """Test native value from coordinator data."""
        assert sensor.native_value == 22.5

    def test_native_value_from_mqtt(self, sensor):
        """Test native value from MQTT."""
        sensor._mqtt_value = 25.0
        assert sensor.native_value == 25.0

    def test_device_info(self, sensor, thing_data, mock_sensorthings_url):
        """Test device info."""
        device_info = sensor.device_info
        assert device_info["identifiers"] == {("sensorthings", thing_data["@iot.id"])}
        assert device_info["name"] == thing_data["name"]
        assert device_info["model"] == thing_data["properties"]["model"]
        assert device_info["manufacturer"] == thing_data["properties"]["manufacturer"]
        assert device_info["sw_version"] == thing_data["properties"]["firmware_version"]
        assert device_info["configuration_url"] == mock_sensorthings_url

    def test_mqtt_update_callback(self, sensor):
        """Test MQTT update callback."""
        sensor._on_mqtt_update(30.0, "2024-01-01T12:00:00Z")
        assert sensor._mqtt_value == 30.0
        assert sensor._mqtt_timestamp == "2024-01-01T12:00:00Z"

    async def test_async_update_with_mqtt_connected(self, sensor, mock_mqtt_listener):
        """Test async_update when MQTT is connected."""
        mock_mqtt_listener.is_connected.return_value = True
        await sensor.async_update()
        # Should not request coordinator refresh when MQTT is connected
        sensor.coordinator.async_request_refresh.assert_not_called()

    async def test_async_update_without_mqtt(self, sensor, mock_mqtt_listener):
        """Test async_update when MQTT is not connected."""
        mock_mqtt_listener.is_connected.return_value = False
        await sensor.async_update()
        sensor.coordinator.async_request_refresh.assert_called_once()

    async def test_async_will_remove_from_hass(self, sensor, mock_mqtt_listener):
        """Test cleanup when entity is removed."""
        await sensor.async_will_remove_from_hass()
        mock_mqtt_listener.unsubscribe.assert_called_once_with("1")


class TestSensorThingsBatteryLevel:
    """Test SensorThingsBatteryLevel sensor."""

    @pytest.fixture
    def thing_with_battery(self):
        """Sample thing data with battery datastream."""
        return {
            "@iot.id": "1",
            "name": "Test Thing",
            "properties": {
                "model": "Test Model",
                "manufacturer": "Test Manufacturer",
                "firmware_version": "1.0.0"
            },
            "Datastreams": [
                {
                    "@iot.id": "2",
                    "name": "Battery Level",
                    "unitOfMeasurement": {"symbol": "%"},
                    "Observations": [{"result": 85}]
                }
            ]
        }

    @pytest.fixture
    def battery_sensor(self, thing_with_battery, mock_coordinator, mock_mqtt_listener, mock_sensorthings_url):
        """Create SensorThingsBatteryLevel instance."""
        return SensorThingsBatteryLevel(
            thing_with_battery,
            mock_coordinator,
            mock_mqtt_listener,
            mock_sensorthings_url
        )

    def test_translation_key(self, battery_sensor):
        """Test translation key."""
        assert battery_sensor.translation_key == "battery_level"

    def test_has_entity_name(self, battery_sensor):
        """Test has_entity_name property."""
        assert battery_sensor.has_entity_name is True

    def test_unique_id(self, battery_sensor, thing_with_battery):
        """Test unique ID."""
        expected_id = f"sensorthings_battery_level_{thing_with_battery['@iot.id']}"
        assert battery_sensor.unique_id == expected_id

    def test_entity_category(self, battery_sensor):
        """Test entity category."""
        assert battery_sensor.entity_category == EntityCategory.DIAGNOSTIC

    def test_native_unit_of_measurement(self, battery_sensor):
        """Test native unit of measurement."""
        assert battery_sensor.native_unit_of_measurement == "%"

    def test_native_value_from_coordinator(self, battery_sensor):
        """Test native value from coordinator data."""
        assert battery_sensor.native_value == 85

    def test_native_value_from_mqtt(self, battery_sensor):
        """Test native value from MQTT."""
        battery_sensor._mqtt_value = 90
        assert battery_sensor.native_value == 90

    def test_icon_high_battery(self, battery_sensor):
        """Test icon for high battery level."""
        battery_sensor._mqtt_value = 80
        assert battery_sensor.icon == "mdi:battery"

    def test_icon_medium_battery(self, battery_sensor):
        """Test icon for medium battery level."""
        battery_sensor._mqtt_value = 60
        assert battery_sensor.icon == "mdi:battery-75"

    def test_icon_low_battery(self, battery_sensor):
        """Test icon for low battery level."""
        battery_sensor._mqtt_value = 20
        assert battery_sensor.icon == "mdi:battery-25"

    def test_icon_critical_battery(self, battery_sensor):
        """Test icon for critical battery level."""
        battery_sensor._mqtt_value = 5
        assert battery_sensor.icon == "mdi:battery-alert"

    def test_icon_unknown_battery(self, battery_sensor):
        """Test icon for unknown battery level."""
        battery_sensor._mqtt_value = None
        assert battery_sensor.icon == "mdi:battery-unknown"


class TestHelperFunctions:
    """Test helper functions."""

    def test_is_battery_datastream_battery_name(self):
        """Test _is_battery_datastream with battery in name."""
        datastream = {"name": "Battery Level"}
        assert _is_battery_datastream(datastream) is True

    def test_is_battery_datastream_power_name(self):
        """Test _is_battery_datastream with power in name."""
        datastream = {"name": "Power Level"}
        assert _is_battery_datastream(datastream) is True

    def test_is_battery_datastream_other_name(self):
        """Test _is_battery_datastream with other name."""
        datastream = {"name": "Temperature"}
        assert _is_battery_datastream(datastream) is False

    def test_has_battery_datastream_with_battery(self):
        """Test _has_battery_datastream with battery datastream."""
        thing = {
            "Datastreams": [
                {"name": "Temperature"},
                {"name": "Battery Level"}
            ]
        }
        assert _has_battery_datastream(thing) is True

    def test_has_battery_datastream_without_battery(self):
        """Test _has_battery_datastream without battery datastream."""
        thing = {
            "Datastreams": [
                {"name": "Temperature"},
                {"name": "Humidity"}
            ]
        }
        assert _has_battery_datastream(thing) is False


class TestSensorSetup:
    """Test sensor setup functions."""

    async def test_async_setup_entry(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test async_setup_entry."""
        with patch("custom_components.sensorthings.sensor.aiohttp.ClientSession") as mock_session, \
             patch("custom_components.sensorthings.sensor.SensorThingsMQTTListener") as mock_mqtt_class, \
             patch("custom_components.sensorthings.sensor.DataUpdateCoordinator") as mock_coordinator_class:
            
            # Setup mocks
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_sensorthings_data)
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            mock_mqtt_instance = AsyncMock()
            mock_mqtt_class.return_value = mock_mqtt_instance
            
            mock_coordinator_instance = AsyncMock()
            mock_coordinator_instance.data = mock_sensorthings_data["value"]
            mock_coordinator_class.return_value = mock_coordinator_instance
            
            # Mock async_add_entities
            async_add_entities = AsyncMock()
            
            await async_setup_entry(hass, mock_config_entry, async_add_entities)
            
            # Verify MQTT listener was started
            mock_mqtt_instance.start.assert_called_once()
            
            # Verify entities were added
            async_add_entities.assert_called_once()

    async def test_async_unload_entry(self, hass: HomeAssistant, mock_config_entry):
        """Test async_unload_entry."""
        # Setup hass data with MQTT listener
        mock_mqtt_listener = AsyncMock()
        hass.data = {
            "sensorthings": {
                mock_config_entry.entry_id: {
                    "mqtt_listener": mock_mqtt_listener
                }
            }
        }
        
        result = await async_unload_entry(hass, mock_config_entry)
        
        assert result is True
        mock_mqtt_listener.stop.assert_called_once()
        assert mock_config_entry.entry_id not in hass.data["sensorthings"]

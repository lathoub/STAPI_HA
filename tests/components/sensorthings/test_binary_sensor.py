"""Test the SensorThings binary sensor platform."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.sensorthings.binary_sensor import (
    SensorThingsConnectivity,
    async_setup_entry,
)


class TestSensorThingsConnectivity:
    """Test SensorThingsConnectivity binary sensor."""

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
    def binary_sensor(self, thing_data, mock_mqtt_listener, mock_sensorthings_url):
        """Create SensorThingsConnectivity instance."""
        return SensorThingsConnectivity(
            thing_data,
            mock_mqtt_listener,
            mock_sensorthings_url
        )

    def test_name(self, binary_sensor, thing_data):
        """Test binary sensor name."""
        expected_name = f"{thing_data['name']} Connected"
        assert binary_sensor.name == expected_name

    def test_unique_id(self, binary_sensor, thing_data):
        """Test binary sensor unique ID."""
        expected_id = f"sensorthings_connectivity_{thing_data['@iot.id']}"
        assert binary_sensor.unique_id == expected_id

    def test_device_info(self, binary_sensor, thing_data, mock_sensorthings_url):
        """Test device info."""
        device_info = binary_sensor.device_info
        assert device_info["identifiers"] == {("sensorthings", thing_data["@iot.id"])}
        assert device_info["name"] == thing_data["name"]
        assert device_info["model"] == thing_data["properties"]["model"]
        assert device_info["manufacturer"] == thing_data["properties"]["manufacturer"]
        assert device_info["sw_version"] == thing_data["properties"]["firmware_version"]
        assert device_info["configuration_url"] == mock_sensorthings_url

    def test_entity_category(self, binary_sensor):
        """Test entity category."""
        assert binary_sensor.entity_category == EntityCategory.DIAGNOSTIC

    def test_translation_key(self, binary_sensor):
        """Test translation key."""
        assert binary_sensor.translation_key == "connectivity"

    def test_is_on_connected(self, binary_sensor, mock_mqtt_listener):
        """Test is_on when MQTT is connected."""
        mock_mqtt_listener.is_connected.return_value = True
        assert binary_sensor.is_on is True

    def test_is_on_disconnected(self, binary_sensor, mock_mqtt_listener):
        """Test is_on when MQTT is disconnected."""
        mock_mqtt_listener.is_connected.return_value = False
        assert binary_sensor.is_on is False

    def test_is_on_no_mqtt_listener(self, thing_data, mock_sensorthings_url):
        """Test is_on when no MQTT listener."""
        binary_sensor = SensorThingsConnectivity(thing_data, None, mock_sensorthings_url)
        assert binary_sensor.is_on is False

    def test_icon_connected(self, binary_sensor, mock_mqtt_listener):
        """Test icon when connected."""
        mock_mqtt_listener.is_connected.return_value = True
        assert binary_sensor.icon == "mdi:wifi"

    def test_icon_disconnected(self, binary_sensor, mock_mqtt_listener):
        """Test icon when disconnected."""
        mock_mqtt_listener.is_connected.return_value = False
        assert binary_sensor.icon == "mdi:wifi-off"


class TestBinarySensorSetup:
    """Test binary sensor setup functions."""

    async def test_async_setup_entry_success(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test successful async_setup_entry."""
        # Setup hass data with MQTT listener and coordinator
        hass.data = {
            "sensorthings": {
                mock_config_entry.entry_id: {
                    "mqtt_listener": MagicMock(),
                    "coordinator": MagicMock(data=mock_sensorthings_data["value"])
                }
            }
        }
        
        async_add_entities = AsyncMock()
        
        await async_setup_entry(hass, mock_config_entry, async_add_entities)
        
        # Verify entities were added
        async_add_entities.assert_called_once()
        call_args = async_add_entities.call_args[0]
        entities = call_args[0]
        update_before_add = call_args[1]
        
        # Should have 1 connectivity binary sensor
        assert len(entities) == 1
        assert update_before_add is True
        assert isinstance(entities[0], SensorThingsConnectivity)

    async def test_async_setup_entry_no_hass_data(self, hass: HomeAssistant, mock_config_entry):
        """Test async_setup_entry with no hass data."""
        async_add_entities = AsyncMock()
        
        await async_setup_entry(hass, mock_config_entry, async_add_entities)
        
        # Should not add any entities
        async_add_entities.assert_not_called()

    async def test_async_setup_entry_no_mqtt_listener(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test async_setup_entry with no MQTT listener."""
        # Setup hass data without MQTT listener
        hass.data = {
            "sensorthings": {
                mock_config_entry.entry_id: {
                    "coordinator": MagicMock(data=mock_sensorthings_data["value"])
                }
            }
        }
        
        async_add_entities = AsyncMock()
        
        await async_setup_entry(hass, mock_config_entry, async_add_entities)
        
        # Should not add any entities
        async_add_entities.assert_not_called()

    async def test_async_setup_entry_no_coordinator_data(self, hass: HomeAssistant, mock_config_entry):
        """Test async_setup_entry with no coordinator data."""
        # Setup hass data without coordinator data
        hass.data = {
            "sensorthings": {
                mock_config_entry.entry_id: {
                    "mqtt_listener": MagicMock(),
                    "coordinator": MagicMock(data=None)
                }
            }
        }
        
        async_add_entities = AsyncMock()
        
        await async_setup_entry(hass, mock_config_entry, async_add_entities)
        
        # Should not add any entities
        async_add_entities.assert_not_called()

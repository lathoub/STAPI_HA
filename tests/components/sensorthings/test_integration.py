"""Integration tests for SensorThings."""

from unittest.mock import AsyncMock, patch
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sensorthings.const import DOMAIN, CONF_URL


class TestSensorThingsIntegration:
    """Integration tests for SensorThings."""

    async def test_config_flow_integration(self, hass: HomeAssistant, mock_sensorthings_url):
        """Test complete config flow integration."""
        # Start config flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"

        # Submit form with valid URL
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_URL: mock_sensorthings_url}
            )
            
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "SensorThings (192.168.1.100)"
            assert result["data"][CONF_URL] == mock_sensorthings_url

    async def test_setup_and_unload_integration(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test complete setup and unload integration."""
        # Mock the sensor setup
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
            
            # Setup integration
            from custom_components.sensorthings import async_setup_entry, async_unload_entry
            
            result = await async_setup_entry(hass, mock_config_entry)
            assert result is True
            
            # Verify data is set
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            
            # Unload integration
            result = await async_unload_entry(hass, mock_config_entry)
            assert result is True
            
            # Verify data is cleaned up
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_sensor_platform_setup(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test sensor platform setup."""
        from custom_components.sensorthings.sensor import async_setup_entry
        
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
            
            # Verify the call was made with the correct number of entities
            call_args = async_add_entities.call_args[0]
            entities = call_args[0]
            update_before_add = call_args[1]
            
            # Should have 1 regular sensor (temperature) + 1 battery sensor
            assert len(entities) == 2
            assert update_before_add is True

    async def test_mqtt_integration(self, hass: HomeAssistant, mock_sensorthings_url, mock_mqtt_observation):
        """Test MQTT integration with sensor updates."""
        from custom_components.sensorthings.mqtt_listener import SensorThingsMQTTListener
        
        listener = SensorThingsMQTTListener(hass, mock_sensorthings_url)
        
        # Mock MQTT client
        mock_client = AsyncMock()
        listener.client = mock_client
        listener.connected = True
        
        # Setup subscriber
        callback = AsyncMock()
        listener.subscribers["1"] = callback
        
        # Simulate MQTT message
        import json
        msg = AsyncMock()
        msg.topic = "v1.1/Observations(123)"
        msg.payload = json.dumps(mock_mqtt_observation).encode('utf-8')
        
        with patch("custom_components.sensorthings.mqtt_listener.asyncio.run_coroutine_threadsafe") as mock_run:
            listener._on_message(None, None, msg)
            
            # Verify callback was scheduled
            mock_run.assert_called_once()

    async def test_error_handling_integration(self, hass: HomeAssistant, mock_sensorthings_url):
        """Test error handling in integration."""
        # Test config flow with invalid URL
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_session.return_value.get.side_effect = Exception("Connection error")
            
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_URL: "http://invalid-url"}
            )
            
            assert result["type"] == FlowResultType.FORM
            assert "base" in result["errors"]

    async def test_multiple_config_entries(self, hass: HomeAssistant, mock_sensorthings_url):
        """Test handling multiple config entries."""
        # Create first config entry
        result1 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result1 = await hass.config_entries.flow.async_configure(
                result1["flow_id"], {CONF_URL: mock_sensorthings_url}
            )
            
            assert result1["type"] == FlowResultType.CREATE_ENTRY
        
        # Create second config entry with different URL
        result2 = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        different_url = "http://192.168.1.101:8080/FROST-Server/v1.1"
        result2 = await hass.config_entries.flow.async_configure(
            result2["flow_id"], {CONF_URL: different_url}
        )
        
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["data"][CONF_URL] == different_url

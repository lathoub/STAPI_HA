"""Test Gold tier features for SensorThings integration."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sensorthings.const import (
    DOMAIN, CONF_URL, CONF_SCAN_INTERVAL, CONF_MQTT_ENABLED, CONF_MQTT_PORT,
    DEFAULT_SCAN_INTERVAL, DEFAULT_MQTT_ENABLED, DEFAULT_MQTT_PORT,
    SERVICE_REFRESH_ALL, SERVICE_RECONNECT_MQTT
)


class TestGoldTierFeatures:
    """Test Gold tier features integration."""

    async def test_options_flow_integration(self, hass: HomeAssistant, mock_sensorthings_url):
        """Test complete options flow integration."""
        # First create a config entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_URL: mock_sensorthings_url}
            )
            
            assert result["type"] == FlowResultType.CREATE_ENTRY
            config_entry = result["result"]
        
        # Now test options flow
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        
        # Submit options
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 120,
                CONF_MQTT_ENABLED: False,
                CONF_MQTT_PORT: 1884
            }
        )
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_SCAN_INTERVAL] == 120
        assert result["data"][CONF_MQTT_ENABLED] is False
        assert result["data"][CONF_MQTT_PORT] == 1884

    async def test_service_calls_integration(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test service calls integration."""
        # Setup integration with mock data
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
            from custom_components.sensorthings import async_setup_entry
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Test refresh_all service
            await hass.services.async_call(DOMAIN, SERVICE_REFRESH_ALL, {})
            await hass.async_block_till_done()
            
            # Verify coordinator was refreshed
            mock_coordinator_instance.async_request_refresh.assert_called()
            
            # Test reconnect_mqtt service
            await hass.services.async_call(DOMAIN, SERVICE_RECONNECT_MQTT, {})
            await hass.async_block_till_done()
            
            # Verify MQTT was reconnected
            mock_mqtt_instance.stop.assert_called()
            mock_mqtt_instance.start.assert_called()

    async def test_binary_sensor_integration(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test binary sensor integration."""
        # Setup integration with mock data
        with patch("custom_components.sensorthings.sensor.aiohttp.ClientSession") as mock_session, \
             patch("custom_components.sensorthings.sensor.SensorThingsMQTTListener") as mock_mqtt_class, \
             patch("custom_components.sensorthings.sensor.DataUpdateCoordinator") as mock_coordinator_class:
            
            # Setup mocks
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_sensorthings_data)
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            mock_mqtt_instance = AsyncMock()
            mock_mqtt_instance.is_connected.return_value = True
            mock_mqtt_class.return_value = mock_mqtt_instance
            
            mock_coordinator_instance = AsyncMock()
            mock_coordinator_instance.data = mock_sensorthings_data["value"]
            mock_coordinator_class.return_value = mock_coordinator_instance
            
            # Setup integration
            from custom_components.sensorthings import async_setup_entry
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify binary sensor was created
            from custom_components.sensorthings.binary_sensor import async_setup_entry as setup_binary_sensor
            
            async_add_entities = AsyncMock()
            await setup_binary_sensor(hass, mock_config_entry, async_add_entities)
            
            # Verify binary sensor was added
            async_add_entities.assert_called_once()
            call_args = async_add_entities.call_args[0]
            entities = call_args[0]
            
            assert len(entities) == 1
            assert entities[0].is_on is True  # MQTT connected

    async def test_configuration_options_usage(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test that configuration options are properly used."""
        # Set custom options
        mock_config_entry.options = {
            CONF_SCAN_INTERVAL: 30,
            CONF_MQTT_ENABLED: False,
            CONF_MQTT_PORT: 1885
        }
        
        with patch("custom_components.sensorthings.sensor.aiohttp.ClientSession") as mock_session, \
             patch("custom_components.sensorthings.sensor.SensorThingsMQTTListener") as mock_mqtt_class, \
             patch("custom_components.sensorthings.sensor.DataUpdateCoordinator") as mock_coordinator_class:
            
            # Setup mocks
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_sensorthings_data)
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            mock_coordinator_instance = AsyncMock()
            mock_coordinator_instance.data = mock_sensorthings_data["value"]
            mock_coordinator_class.return_value = mock_coordinator_instance
            
            # Setup integration
            from custom_components.sensorthings import async_setup_entry
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify MQTT listener was not created (disabled)
            mock_mqtt_class.assert_not_called()
            
            # Verify coordinator was created with custom scan interval
            mock_coordinator_class.assert_called_once()
            call_args = mock_coordinator_class.call_args
            update_interval = call_args[1]["update_interval"]
            assert update_interval.total_seconds() == 30

    async def test_mqtt_port_configuration(self, hass: HomeAssistant, mock_config_entry, mock_sensorthings_data):
        """Test MQTT port configuration."""
        # Set custom MQTT port
        mock_config_entry.options = {
            CONF_MQTT_ENABLED: True,
            CONF_MQTT_PORT: 1886
        }
        
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
            from custom_components.sensorthings import async_setup_entry
            
            await async_setup_entry(hass, mock_config_entry)
            
            # Verify MQTT listener was created with custom port
            mock_mqtt_class.assert_called_once()
            call_args = mock_mqtt_class.call_args
            mqtt_port = call_args[0][2]  # Third argument is mqtt_port
            assert mqtt_port == 1886

    async def test_gold_tier_complete_workflow(self, hass: HomeAssistant, mock_sensorthings_url, mock_sensorthings_data):
        """Test complete Gold tier workflow."""
        # 1. Create config entry
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], {CONF_URL: mock_sensorthings_url}
            )
            
            config_entry = result["result"]
        
        # 2. Configure options
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: 45,
                CONF_MQTT_ENABLED: True,
                CONF_MQTT_PORT: 1887
            }
        )
        
        # 3. Setup integration with options
        with patch("custom_components.sensorthings.sensor.aiohttp.ClientSession") as mock_session, \
             patch("custom_components.sensorthings.sensor.SensorThingsMQTTListener") as mock_mqtt_class, \
             patch("custom_components.sensorthings.sensor.DataUpdateCoordinator") as mock_coordinator_class:
            
            # Setup mocks
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json = AsyncMock(return_value=mock_sensorthings_data)
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            mock_mqtt_instance = AsyncMock()
            mock_mqtt_instance.is_connected.return_value = True
            mock_mqtt_class.return_value = mock_mqtt_instance
            
            mock_coordinator_instance = AsyncMock()
            mock_coordinator_instance.data = mock_sensorthings_data["value"]
            mock_coordinator_class.return_value = mock_coordinator_instance
            
            # Setup integration
            from custom_components.sensorthings import async_setup_entry
            
            await async_setup_entry(hass, config_entry)
            
            # 4. Test services
            await hass.services.async_call(DOMAIN, SERVICE_REFRESH_ALL, {})
            await hass.async_block_till_done()
            
            await hass.services.async_call(DOMAIN, SERVICE_RECONNECT_MQTT, {})
            await hass.async_block_till_done()
            
            # 5. Verify everything worked
            mock_mqtt_class.assert_called_once()
            mock_coordinator_class.assert_called_once()
            mock_coordinator_instance.async_request_refresh.assert_called()
            mock_mqtt_instance.stop.assert_called()
            mock_mqtt_instance.start.assert_called()
            
            # Verify hass data is properly set
            assert DOMAIN in hass.data
            assert config_entry.entry_id in hass.data[DOMAIN]
            entry_data = hass.data[DOMAIN][config_entry.entry_id]
            assert "mqtt_listener" in entry_data
            assert "coordinator" in entry_data

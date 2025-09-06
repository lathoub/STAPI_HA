"""Test the SensorThings services."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant

from custom_components.sensorthings import async_setup_services
from custom_components.sensorthings.const import DOMAIN, SERVICE_REFRESH_ALL, SERVICE_RECONNECT_MQTT


class TestSensorThingsServices:
    """Test SensorThings services."""

    async def test_async_setup_services(self, hass: HomeAssistant):
        """Test service registration."""
        await async_setup_services(hass)
        
        # Check that services are registered
        assert hass.services.has_service(DOMAIN, SERVICE_REFRESH_ALL)
        assert hass.services.has_service(DOMAIN, SERVICE_RECONNECT_MQTT)

    async def test_refresh_all_service(self, hass: HomeAssistant):
        """Test refresh_all service call."""
        # Setup mock coordinators
        mock_coordinator1 = AsyncMock()
        mock_coordinator2 = AsyncMock()
        
        hass.data = {
            DOMAIN: {
                "entry1": {"coordinator": mock_coordinator1},
                "entry2": {"coordinator": mock_coordinator2},
                "entry3": {"mqtt_listener": MagicMock()},  # No coordinator
            }
        }
        
        await async_setup_services(hass)
        
        # Call the service
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_ALL, {})
        await hass.async_block_till_done()
        
        # Verify coordinators were refreshed
        mock_coordinator1.async_request_refresh.assert_called_once()
        mock_coordinator2.async_request_refresh.assert_called_once()

    async def test_refresh_all_service_no_coordinators(self, hass: HomeAssistant):
        """Test refresh_all service with no coordinators."""
        hass.data = {
            DOMAIN: {
                "entry1": {"mqtt_listener": MagicMock()},
                "entry2": {"some_other_data": "value"},
            }
        }
        
        await async_setup_services(hass)
        
        # Call the service - should not raise exception
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_ALL, {})
        await hass.async_block_till_done()

    async def test_refresh_all_service_empty_data(self, hass: HomeAssistant):
        """Test refresh_all service with empty hass data."""
        hass.data = {}
        
        await async_setup_services(hass)
        
        # Call the service - should not raise exception
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_ALL, {})
        await hass.async_block_till_done()

    async def test_reconnect_mqtt_service(self, hass: HomeAssistant):
        """Test reconnect_mqtt service call."""
        # Setup mock MQTT listeners
        mock_mqtt1 = AsyncMock()
        mock_mqtt2 = AsyncMock()
        
        hass.data = {
            DOMAIN: {
                "entry1": {"mqtt_listener": mock_mqtt1},
                "entry2": {"mqtt_listener": mock_mqtt2},
                "entry3": {"coordinator": MagicMock()},  # No MQTT listener
            }
        }
        
        await async_setup_services(hass)
        
        # Call the service
        await hass.services.async_call(DOMAIN, SERVICE_RECONNECT_MQTT, {})
        await hass.async_block_till_done()
        
        # Verify MQTT listeners were reconnected
        mock_mqtt1.stop.assert_called_once()
        mock_mqtt1.start.assert_called_once()
        mock_mqtt2.stop.assert_called_once()
        mock_mqtt2.start.assert_called_once()

    async def test_reconnect_mqtt_service_no_listeners(self, hass: HomeAssistant):
        """Test reconnect_mqtt service with no MQTT listeners."""
        hass.data = {
            DOMAIN: {
                "entry1": {"coordinator": MagicMock()},
                "entry2": {"some_other_data": "value"},
            }
        }
        
        await async_setup_services(hass)
        
        # Call the service - should not raise exception
        await hass.services.async_call(DOMAIN, SERVICE_RECONNECT_MQTT, {})
        await hass.async_block_till_done()

    async def test_reconnect_mqtt_service_empty_data(self, hass: HomeAssistant):
        """Test reconnect_mqtt service with empty hass data."""
        hass.data = {}
        
        await async_setup_services(hass)
        
        # Call the service - should not raise exception
        await hass.services.async_call(DOMAIN, SERVICE_RECONNECT_MQTT, {})
        await hass.async_block_till_done()

    async def test_service_error_handling(self, hass: HomeAssistant):
        """Test service error handling."""
        # Setup mock coordinator that raises exception
        mock_coordinator = AsyncMock()
        mock_coordinator.async_request_refresh.side_effect = Exception("Test error")
        
        hass.data = {
            DOMAIN: {
                "entry1": {"coordinator": mock_coordinator},
            }
        }
        
        await async_setup_services(hass)
        
        # Call the service - should not raise exception
        await hass.services.async_call(DOMAIN, SERVICE_REFRESH_ALL, {})
        await hass.async_block_till_done()

    async def test_mqtt_reconnect_error_handling(self, hass: HomeAssistant):
        """Test MQTT reconnect error handling."""
        # Setup mock MQTT listener that raises exception
        mock_mqtt = AsyncMock()
        mock_mqtt.stop.side_effect = Exception("Test error")
        
        hass.data = {
            DOMAIN: {
                "entry1": {"mqtt_listener": mock_mqtt},
            }
        }
        
        await async_setup_services(hass)
        
        # Call the service - should not raise exception
        await hass.services.async_call(DOMAIN, SERVICE_RECONNECT_MQTT, {})
        await hass.async_block_till_done()

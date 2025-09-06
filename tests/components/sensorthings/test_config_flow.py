"""Test the SensorThings config flow."""

from unittest.mock import AsyncMock, patch
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import aiohttp

from custom_components.sensorthings.config_flow import SensorThingsConfigFlow
from custom_components.sensorthings.const import DOMAIN, CONF_URL


class TestSensorThingsConfigFlow:
    """Test SensorThings config flow."""

    @pytest.fixture
    def flow(self, hass: HomeAssistant):
        """Create config flow instance."""
        flow = SensorThingsConfigFlow()
        flow.hass = hass
        return flow

    async def test_async_step_user(self, flow):
        """Test async_step_user."""
        result = await flow.async_step_user()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"

    async def test_async_step_manual_no_input(self, flow):
        """Test async_step_manual with no input."""
        result = await flow.async_step_manual()
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "manual"
        assert CONF_URL in result["data_schema"].schema

    async def test_async_step_manual_success(self, flow, mock_sensorthings_url):
        """Test successful async_step_manual."""
        with patch.object(flow, "_validate_and_create_entry") as mock_validate:
            mock_validate.return_value = {"type": FlowResultType.CREATE_ENTRY}
            
            result = await flow.async_step_manual({CONF_URL: mock_sensorthings_url})
            
            mock_validate.assert_called_once_with(mock_sensorthings_url)

    async def test_validate_and_create_entry_success(self, flow, mock_sensorthings_url):
        """Test successful validation and entry creation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await flow._validate_and_create_entry(mock_sensorthings_url)
            
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "SensorThings (192.168.1.100)"
            assert result["data"][CONF_URL] == mock_sensorthings_url

    async def test_validate_and_create_entry_bad_status(self, flow, mock_sensorthings_url):
        """Test validation with bad HTTP status."""
        mock_response = AsyncMock()
        mock_response.status = 404
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await flow._validate_and_create_entry(mock_sensorthings_url)
            
            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "cannot_connect"

    async def test_validate_and_create_entry_client_error(self, flow, mock_sensorthings_url):
        """Test validation with client error."""
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_session.return_value.get.side_effect = aiohttp.ClientError()
            
            result = await flow._validate_and_create_entry(mock_sensorthings_url)
            
            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "cannot_connect"

    async def test_validate_and_create_entry_with_port(self, flow):
        """Test validation with URL containing port."""
        url_with_port = "http://192.168.1.100:8080/FROST-Server/v1.1"
        mock_response = AsyncMock()
        mock_response.status = 200
        
        with patch("custom_components.sensorthings.config_flow.aiohttp_client.async_get_clientsession") as mock_session:
            mock_session.return_value.get.return_value.__aenter__.return_value = mock_response
            
            result = await flow._validate_and_create_entry(url_with_port)
            
            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "SensorThings (192.168.1.100)"

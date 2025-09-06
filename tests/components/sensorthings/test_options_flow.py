"""Test the SensorThings options flow."""

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.sensorthings.config_flow import SensorThingsOptionsFlow
from custom_components.sensorthings.const import (
    CONF_SCAN_INTERVAL, CONF_MQTT_ENABLED, CONF_MQTT_PORT,
    DEFAULT_SCAN_INTERVAL, DEFAULT_MQTT_ENABLED, DEFAULT_MQTT_PORT
)


class TestSensorThingsOptionsFlow:
    """Test SensorThings options flow."""

    @pytest.fixture
    def options_flow(self, mock_config_entry):
        """Create options flow instance."""
        return SensorThingsOptionsFlow(mock_config_entry)

    async def test_async_step_init_no_input(self, options_flow):
        """Test async_step_init with no input."""
        result = await options_flow.async_step_init()
        
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        assert CONF_SCAN_INTERVAL in result["data_schema"].schema
        assert CONF_MQTT_ENABLED in result["data_schema"].schema
        assert CONF_MQTT_PORT in result["data_schema"].schema

    async def test_async_step_init_with_input(self, options_flow):
        """Test async_step_init with user input."""
        user_input = {
            CONF_SCAN_INTERVAL: 120,
            CONF_MQTT_ENABLED: False,
            CONF_MQTT_PORT: 1884
        }
        
        result = await options_flow.async_step_init(user_input)
        
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"] == user_input

    async def test_async_step_init_defaults(self, options_flow):
        """Test async_step_init with default values."""
        result = await options_flow.async_step_init()
        
        # Check that defaults are set correctly
        schema = result["data_schema"].schema
        scan_interval_field = next(f for f in schema if f.schema == CONF_SCAN_INTERVAL)
        mqtt_enabled_field = next(f for f in schema if f.schema == CONF_MQTT_ENABLED)
        mqtt_port_field = next(f for f in schema if f.schema == CONF_MQTT_PORT)
        
        assert scan_interval_field.default == DEFAULT_SCAN_INTERVAL
        assert mqtt_enabled_field.default == DEFAULT_MQTT_ENABLED
        assert mqtt_port_field.default == DEFAULT_MQTT_PORT

    async def test_async_step_init_with_existing_options(self, mock_config_entry):
        """Test async_step_init with existing options."""
        # Set existing options
        mock_config_entry.options = {
            CONF_SCAN_INTERVAL: 90,
            CONF_MQTT_ENABLED: False,
            CONF_MQTT_PORT: 1885
        }
        
        options_flow = SensorThingsOptionsFlow(mock_config_entry)
        result = await options_flow.async_step_init()
        
        # Check that existing values are used as defaults
        schema = result["data_schema"].schema
        scan_interval_field = next(f for f in schema if f.schema == CONF_SCAN_INTERVAL)
        mqtt_enabled_field = next(f for f in schema if f.schema == CONF_MQTT_ENABLED)
        mqtt_port_field = next(f for f in schema if f.schema == CONF_MQTT_PORT)
        
        assert scan_interval_field.default == 90
        assert mqtt_enabled_field.default is False
        assert mqtt_port_field.default == 1885

    async def test_scan_interval_validation(self, options_flow):
        """Test scan interval validation."""
        # Test minimum value
        user_input = {CONF_SCAN_INTERVAL: 5}  # Below minimum
        result = await options_flow.async_step_init(user_input)
        assert result["type"] == FlowResultType.FORM
        assert "errors" in result

    async def test_mqtt_port_validation(self, options_flow):
        """Test MQTT port validation."""
        # Test invalid port
        user_input = {CONF_MQTT_PORT: 70000}  # Above maximum
        result = await options_flow.async_step_init(user_input)
        assert result["type"] == FlowResultType.FORM
        assert "errors" in result

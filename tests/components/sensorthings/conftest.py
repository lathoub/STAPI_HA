"""Test configuration and fixtures for SensorThings integration."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from custom_components.sensorthings.const import DOMAIN, CONF_URL


@pytest.fixture
def mock_sensorthings_url():
    """Mock SensorThings API URL."""
    return "http://192.168.1.100:8080/FROST-Server/v1.1"


@pytest.fixture
def mock_config_entry(mock_sensorthings_url):
    """Mock config entry for SensorThings."""
    return ConfigEntry(
        version=1,
        domain=DOMAIN,
        title="SensorThings (192.168.1.100)",
        data={CONF_URL: mock_sensorthings_url},
        source="user",
        options={},
        entry_id="test_entry_id",
    )


@pytest.fixture
def mock_sensorthings_data():
    """Mock SensorThings API response data."""
    return {
        "value": [
            {
                "@iot.id": "1",
                "name": "Test Thing",
                "properties": {
                    "model": "Test Model",
                    "manufacturer": "Test Manufacturer",
                    "firmware_version": "1.0.0"
                },
                "Datastreams": [
                    {
                        "@iot.id": "1",
                        "name": "Temperature",
                        "unitOfMeasurement": {"symbol": "°C"},
                        "Observations": [
                            {
                                "result": 22.5,
                                "phenomenonTime": "2024-01-01T12:00:00Z"
                            }
                        ]
                    },
                    {
                        "@iot.id": "2",
                        "name": "Battery Level",
                        "unitOfMeasurement": {"symbol": "%"},
                        "Observations": [
                            {
                                "result": 85,
                                "phenomenonTime": "2024-01-01T12:00:00Z"
                            }
                        ]
                    }
                ]
            }
        ]
    }


@pytest.fixture
def mock_mqtt_observation():
    """Mock MQTT observation message."""
    return {
        "@iot.id": "123",
        "result": 23.1,
        "phenomenonTime": "2024-01-01T12:01:00Z",
        "Datastream": {
            "@iot.id": "1"
        }
    }


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for API calls."""
    session = AsyncMock()
    response = AsyncMock()
    response.status = 200
    response.json = AsyncMock(return_value={"value": []})
    session.get.return_value.__aenter__.return_value = response
    return session


@pytest.fixture
def mock_mqtt_client():
    """Mock MQTT client."""
    client = MagicMock()
    client.loop_start = MagicMock()
    client.loop_stop = MagicMock()
    client.connect_async = MagicMock()
    client.disconnect = MagicMock()
    client.subscribe = MagicMock()
    return client


@pytest.fixture
def mock_coordinator(hass: HomeAssistant, mock_sensorthings_data):
    """Mock data update coordinator."""
    coordinator = DataUpdateCoordinator(
        hass,
        logger=MagicMock(),
        name="SensorThings",
        update_method=AsyncMock(return_value=mock_sensorthings_data["value"]),
        update_interval=None,
    )
    coordinator.data = mock_sensorthings_data["value"]
    return coordinator


@pytest.fixture
def mock_mqtt_listener():
    """Mock MQTT listener."""
    listener = MagicMock()
    listener.start = AsyncMock()
    listener.stop = AsyncMock()
    listener.subscribe = MagicMock()
    listener.unsubscribe = MagicMock()
    listener.is_connected = MagicMock(return_value=True)
    return listener


@pytest.fixture
def hass():
    """Create Home Assistant instance for testing."""
    from homeassistant.core import HomeAssistant
    return HomeAssistant("")


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(hass: HomeAssistant):
    """Enable custom integrations defined in the test dir."""
    hass.config.components.add(DOMAIN)

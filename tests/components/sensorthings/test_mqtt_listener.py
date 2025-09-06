"""Test the SensorThings MQTT listener."""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.core import HomeAssistant

from custom_components.sensorthings.mqtt_listener import SensorThingsMQTTListener


class TestSensorThingsMQTTListener:
    """Test SensorThingsMQTTListener."""

    @pytest.fixture
    def listener(self, hass: HomeAssistant, mock_sensorthings_url):
        """Create SensorThingsMQTTListener instance."""
        return SensorThingsMQTTListener(hass, mock_sensorthings_url)

    def test_init(self, listener, hass: HomeAssistant, mock_sensorthings_url):
        """Test initialization."""
        assert listener.hass == hass
        assert listener.sensorthings_url == mock_sensorthings_url
        assert listener.mqtt_host == "192.168.1.100"
        assert listener.mqtt_port == 1883
        assert listener.connected is False
        assert listener.subscribers == {}

    async def test_start_success(self, listener, mock_mqtt_client):
        """Test successful MQTT connection."""
        with patch("custom_components.sensorthings.mqtt_listener.mqtt.Client") as mock_client_class:
            mock_client_class.return_value = mock_mqtt_client
            
            # Mock successful connection
            def mock_on_connect(client, userdata, flags, rc):
                listener._on_connect(client, userdata, flags, 0)
            
            mock_mqtt_client.on_connect = mock_on_connect
            
            await listener.start()
            
            mock_mqtt_client.connect_async.assert_called_once_with("192.168.1.100", 1883, 60)
            mock_mqtt_client.loop_start.assert_called_once()

    async def test_start_connection_failure(self, listener, mock_mqtt_client):
        """Test MQTT connection failure."""
        with patch("custom_components.sensorthings.mqtt_listener.mqtt.Client") as mock_client_class:
            mock_client_class.return_value = mock_mqtt_client
            
            # Mock connection failure (timeout)
            await listener.start()
            
            # Should not be connected after timeout
            assert listener.connected is False

    async def test_stop(self, listener, mock_mqtt_client):
        """Test stopping MQTT listener."""
        listener.client = mock_mqtt_client
        listener.connected = True
        
        await listener.stop()
        
        mock_mqtt_client.loop_stop.assert_called_once()
        mock_mqtt_client.disconnect.assert_called_once()
        assert listener.client is None
        assert listener.connected is False

    def test_on_connect_success(self, listener, mock_mqtt_client):
        """Test successful connection callback."""
        listener._on_connect(mock_mqtt_client, None, None, 0)
        
        assert listener.connected is True
        mock_mqtt_client.subscribe.assert_called_once()

    def test_on_connect_failure(self, listener, mock_mqtt_client):
        """Test failed connection callback."""
        listener._on_connect(mock_mqtt_client, None, None, 1)
        
        assert listener.connected is False

    def test_on_disconnect_expected(self, listener):
        """Test expected disconnection callback."""
        listener.connected = True
        listener._on_disconnect(None, None, 0)
        
        assert listener.connected is False

    def test_on_disconnect_unexpected(self, listener):
        """Test unexpected disconnection callback."""
        listener.connected = True
        listener._on_disconnect(None, None, 1)
        
        assert listener.connected is False

    def test_on_message_valid_observation(self, listener, mock_mqtt_observation):
        """Test handling valid observation message."""
        # Setup subscriber
        callback = MagicMock()
        listener.subscribers["1"] = callback
        
        # Create message
        msg = MagicMock()
        msg.topic = "v1.1/Observations(123)"
        msg.payload = json.dumps(mock_mqtt_observation).encode('utf-8')
        
        with patch("custom_components.sensorthings.mqtt_listener.asyncio.run_coroutine_threadsafe") as mock_run:
            listener._on_message(None, None, msg)
            
            mock_run.assert_called_once()

    def test_on_message_invalid_json(self, listener):
        """Test handling message with invalid JSON."""
        msg = MagicMock()
        msg.topic = "v1.1/Observations(123)"
        msg.payload = b"invalid json"
        
        # Should not raise exception
        listener._on_message(None, None, msg)

    def test_on_message_missing_observation_id(self, listener):
        """Test handling message without observation ID."""
        msg = MagicMock()
        msg.topic = "v1.1/Observations(123)"
        msg.payload = json.dumps({"result": 25.0}).encode('utf-8')
        
        # Should not raise exception
        listener._on_message(None, None, msg)

    async def test_notify_subscriber_async_callback(self, listener):
        """Test notifying async callback."""
        async def async_callback(value, timestamp):
            pass
        
        callback = MagicMock(side_effect=async_callback)
        
        await listener._notify_subscriber(callback, 25.0, "2024-01-01T12:00:00Z")
        
        callback.assert_called_once_with(25.0, "2024-01-01T12:00:00Z")

    async def test_notify_subscriber_sync_callback(self, listener):
        """Test notifying sync callback."""
        def sync_callback(value, timestamp):
            pass
        
        callback = MagicMock(side_effect=sync_callback)
        
        await listener._notify_subscriber(callback, 25.0, "2024-01-01T12:00:00Z")
        
        callback.assert_called_once_with(25.0, "2024-01-01T12:00:00Z")

    async def test_notify_subscriber_exception(self, listener):
        """Test notifying subscriber with exception."""
        def callback_with_exception(value, timestamp):
            raise Exception("Test exception")
        
        # Should not raise exception
        await listener._notify_subscriber(callback_with_exception, 25.0, "2024-01-01T12:00:00Z")

    def test_subscribe(self, listener):
        """Test subscribing to datastream."""
        callback = MagicMock()
        listener.subscribe("1", callback)
        
        assert "1" in listener.subscribers
        assert listener.subscribers["1"] == callback

    def test_unsubscribe(self, listener):
        """Test unsubscribing from datastream."""
        callback = MagicMock()
        listener.subscribers["1"] = callback
        
        listener.unsubscribe("1")
        
        assert "1" not in listener.subscribers

    def test_unsubscribe_nonexistent(self, listener):
        """Test unsubscribing from nonexistent datastream."""
        # Should not raise exception
        listener.unsubscribe("nonexistent")

    def test_is_connected_true(self, listener, mock_mqtt_client):
        """Test is_connected when connected."""
        listener.client = mock_mqtt_client
        listener.connected = True
        
        assert listener.is_connected() is True

    def test_is_connected_false_no_client(self, listener):
        """Test is_connected when no client."""
        listener.client = None
        listener.connected = True
        
        assert listener.is_connected() is False

    def test_is_connected_false_not_connected(self, listener, mock_mqtt_client):
        """Test is_connected when not connected."""
        listener.client = mock_mqtt_client
        listener.connected = False
        
        assert listener.is_connected() is False

"""
MQTT listener for SensorThings sensor updates.

This module provides real-time sensor updates via MQTT using the built-in
FROST MQTT broker. It subscribes to observation topics and notifies
registered callbacks when new sensor values are received.
"""
import asyncio
import json
import logging
from typing import Dict, Callable, Optional
import paho.mqtt.client as mqtt
from homeassistant.core import HomeAssistant
from urllib.parse import urlparse
from .const import STAPI_VERSION

_LOGGER = logging.getLogger(__name__)

class SensorThingsMQTTListener:
    """
    MQTT listener for SensorThings sensor updates using built-in FROST MQTT broker.
    
    This class manages the MQTT connection to the FROST server's built-in MQTT broker.
    It subscribes to observation topics and provides a callback mechanism for
    sensors to receive real-time updates without polling.
    """
    
    def __init__(self, hass: HomeAssistant, sensorthings_url: str, mqtt_port: int = 1883):
        """
        Initialize the MQTT listener.
        
        Args:
            hass: Home Assistant instance
            sensorthings_url: Base URL of the SensorThings API server
            mqtt_port: Port number for the MQTT broker (default: 1883)
        """
        self.hass = hass
        self.sensorthings_url = sensorthings_url
        self.client: Optional[mqtt.Client] = None  # MQTT client instance
        self.subscribers: Dict[str, Callable] = {}  # Map of datastream_id -> callback
        self.connected = False  # Connection status flag
        
        # Extract hostname from SensorThings URL for MQTT broker
        # FROST typically runs MQTT on the same host as the HTTP API
        parsed_url = urlparse(sensorthings_url)
        self.mqtt_host = parsed_url.hostname
        self.mqtt_port = mqtt_port
        
    async def start(self):
        """
        Start the MQTT listener.
        
        Creates an MQTT client, connects to the FROST broker, and subscribes
        to observation topics. If connection fails, the integration will
        fall back to polling mode.
        """
        try:
            # Create MQTT client instance
            self.client = mqtt.Client()
            
            # Set up callbacks for connection events and messages
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Connect to the built-in MQTT broker
            # Using async connect with 60 second keepalive
            _LOGGER.info(f"Connecting to FROST MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.client.connect_async(self.mqtt_host, self.mqtt_port, 60)
            
            # Start the client loop in a separate thread
            # This handles network I/O without blocking the event loop
            self.client.loop_start()
            
            # Wait for connection (with 10 second timeout)
            # The _on_connect callback will set self.connected = True
            timeout = 10
            while timeout > 0 and not self.connected:
                await asyncio.sleep(0.1)
                timeout -= 0.1
            
            if not self.connected:
                _LOGGER.warning("Failed to connect to FROST MQTT broker, will use polling only")
                return
                
            _LOGGER.info("Successfully connected to FROST MQTT broker")
            
        except Exception as e:
            # If connection fails, log warning but don't crash
            # Integration will continue using polling mode
            _LOGGER.warning(f"Failed to start MQTT listener: {e}, will use polling only")
    
    async def stop(self):
        """
        Stop the MQTT listener.
        
        Disconnects from the MQTT broker and cleans up the client.
        Should be called during integration unload or shutdown.
        """
        if self.client:
            _LOGGER.info("Disconnecting from FROST MQTT broker")
            # Stop the network loop
            self.client.loop_stop()
            # Disconnect from broker
            self.client.disconnect()
            self.client = None
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """
        Handle MQTT connection callback.
        
        Called by paho-mqtt when the client connects (or fails to connect).
        On successful connection, subscribes to observation topics.
        
        Args:
            client: MQTT client instance
            userdata: User data (not used)
            flags: Connection flags (not used)
            rc: Return code (0 = success, non-zero = error)
        """
        if rc == 0:
            # Connection successful
            self.connected = True
            _LOGGER.info("Connected to FROST MQTT broker")
            
            # Subscribe to FROST observation topics
            # FROST typically uses topics like: v1.1/Observations(123)
            # The topic pattern matches all observations for the API version
            topic_pattern = f"{STAPI_VERSION}/Observations?$expand=Datastream($select=id)"
            client.subscribe(topic_pattern)
            _LOGGER.info(f"Subscribed to FROST observation topics: {topic_pattern}")
        else:
            # Connection failed
            _LOGGER.warning(f"Failed to connect to FROST MQTT broker with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """
        Handle MQTT disconnection callback.
        
        Called by paho-mqtt when the client disconnects. Updates the
        connection status flag.
        
        Args:
            client: MQTT client instance
            userdata: User data (not used)
            rc: Return code (0 = normal disconnect, non-zero = error)
        """
        self.connected = False
        if rc != 0:
            # Unexpected disconnection (network error, etc.)
            _LOGGER.warning(f"Unexpected MQTT disconnection with code {rc}")
        else:
            # Normal disconnection
            _LOGGER.info("Disconnected from FROST MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """
        Handle incoming MQTT messages.
        
        Called by paho-mqtt when a message is received on a subscribed topic.
        Parses the observation data and notifies the appropriate subscriber.
        
        Args:
            client: MQTT client instance
            userdata: User data (not used)
            msg: MQTT message object containing topic and payload
        """
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            _LOGGER.debug(f"Received MQTT message on topic {topic}: {payload}")
            
            # Parse JSON payload
            observation_data = json.loads(payload)
            observation_id = observation_data.get("@iot.id")

            # Parse FROST observation topic: v1.1/Observations(123)
            if observation_id is not None:
                
                try:
                    # Parse the observation data structure
                    # FROST observations include expanded datastream information
                    datastream_data = observation_data.get("Datastream")
                    
                    # Extract relevant information from the observation
                    datastream_id = datastream_data.get("@iot.id")
                    result = observation_data.get("result")  # The actual sensor value
                    phenomenon_time = observation_data.get("phenomenonTime")  # When it was measured

                    _LOGGER.debug(f"Received data, ObsId:{observation_id} DataStreamId: {datastream_id} Result: {result}")

                    if datastream_id and result is not None:
                        # Check if we have a subscriber for this datastream
                        if datastream_id in self.subscribers:
                            callback = self.subscribers[datastream_id]
                            # Schedule the callback in the Home Assistant event loop
                            # This is necessary because MQTT callbacks run in a different thread
                            _LOGGER.debug(f"Notify subscriber for datastream {datastream_id}")
                            asyncio.run_coroutine_threadsafe(
                                self._notify_subscriber(callback, result, phenomenon_time),
                                self.hass.loop
                            )
                        else:
                            _LOGGER.debug(f"No subscriber found for datastream {datastream_id}")
                    
                except (json.JSONDecodeError, KeyError) as e:
                    # Invalid JSON or missing expected fields
                    _LOGGER.debug(f"Could not parse observation data: {e}")
            else:
                # Missing observation ID
                _LOGGER.warning(f"Could not retrieve observation_id from payload")
                
        except Exception as e:
            # Catch-all for any unexpected errors
            _LOGGER.error(f"Error processing MQTT message: {e}")
    
    async def _notify_subscriber(self, callback: Callable, value, timestamp=None):
        """
        Notify a subscriber about a new sensor value.
        
        Calls the registered callback with the new value and optional timestamp.
        Handles both async and sync callbacks.
        
        Args:
            callback: Callback function to invoke
            value: New sensor value
            timestamp: Optional timestamp when the value was measured
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                # Callback is async, await it
                await callback(value, timestamp)
            else:
                # Callback is sync, call directly
                callback(value, timestamp)
        except Exception as e:
            _LOGGER.error(f"Error notifying subscriber: {e}")
    
    def subscribe(self, datastream_id: str, callback: Callable):
        """
        Subscribe to updates for a specific datastream.
        
        Registers a callback function that will be called whenever a new
        observation is received for the specified datastream.
        
        Args:
            datastream_id: ID of the datastream to subscribe to
            callback: Function to call when new data arrives
        """
        self.subscribers[datastream_id] = callback
        _LOGGER.debug(f"Subscribed to MQTT updates for datastream {datastream_id}")
    
    def unsubscribe(self, datastream_id: str):
        """
        Unsubscribe from updates for a specific datastream.
        
        Removes the callback registration for the specified datastream.
        Should be called when a sensor entity is removed.
        
        Args:
            datastream_id: ID of the datastream to unsubscribe from
        """
        if datastream_id in self.subscribers:
            del self.subscribers[datastream_id]
            _LOGGER.debug(f"Unsubscribed from MQTT updates for datastream {datastream_id}")
    
    def is_connected(self) -> bool:
        """
        Check if MQTT client is connected.
        
        Returns:
            True if connected to the MQTT broker, False otherwise
        """
        return self.connected and self.client is not None

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
    """MQTT listener for SensorThings sensor updates using built-in FROST MQTT broker."""
    
    def __init__(self, hass: HomeAssistant, sensorthings_url: str):
        self.hass = hass
        self.sensorthings_url = sensorthings_url
        self.client: Optional[mqtt.Client] = None
        self.subscribers: Dict[str, Callable] = {}
        self.connected = False
        
        # Extract hostname from SensorThings URL for MQTT broker
        parsed_url = urlparse(sensorthings_url)
        self.mqtt_host = parsed_url.hostname
        self.mqtt_port = 1883  # Default MQTT port
        
    async def start(self):
        """Start the MQTT listener."""
        try:
            self.client = mqtt.Client()
            
            # Set up callbacks
            self.client.on_connect = self._on_connect
            self.client.on_disconnect = self._on_disconnect
            self.client.on_message = self._on_message
            
            # Connect to the built-in MQTT broker
            _LOGGER.info(f"Connecting to FROST MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.client.connect_async(self.mqtt_host, self.mqtt_port, 60)
            
            # Start the client loop in a separate thread
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            while timeout > 0 and not self.connected:
                await asyncio.sleep(0.1)
                timeout -= 0.1
            
            if not self.connected:
                _LOGGER.warning("Failed to connect to FROST MQTT broker, will use polling only")
                return
                
            _LOGGER.info("Successfully connected to FROST MQTT broker")
            
        except Exception as e:
            _LOGGER.warning(f"Failed to start MQTT listener: {e}, will use polling only")
    
    async def stop(self):
        """Stop the MQTT listener."""
        if self.client:
            _LOGGER.info("Disconnecting from FROST MQTT broker")
            self.client.loop_stop()
            self.client.disconnect()
            self.client = None
            self.connected = False
    
    def _on_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self.connected = True
            _LOGGER.info("Connected to FROST MQTT broker")
            
            # Subscribe to FROST observation topics
            # FROST typically uses topics like: v1.1/Observations(123)
            topic_pattern = f"{STAPI_VERSION}/Observations?$expand=Datastream($select=id)"
            client.subscribe(topic_pattern)
            _LOGGER.info(f"Subscribed to FROST observation topics: {topic_pattern}")
        else:
            _LOGGER.warning(f"Failed to connect to FROST MQTT broker with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self.connected = False
        if rc != 0:
            _LOGGER.warning(f"Unexpected MQTT disconnection with code {rc}")
        else:
            _LOGGER.info("Disconnected from FROST MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Handle incoming MQTT messages."""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            
            _LOGGER.debug(f"Received MQTT message on topic {topic}: {payload}")
            
            observation_data = json.loads(payload)
            observation_id = observation_data.get("@iot.id")

            # Parse FROST observation topic: v1.1/Observations(123)
            if observation_id is not None:
                
                try:
                    # Parse the observation data
                    datastream_data = observation_data.get("Datastream")
                    
                    # Extract relevant information
                    datastream_id = datastream_data.get("@iot.id")
                    result = observation_data.get("result")
                    phenomenon_time = observation_data.get("phenomenonTime")

                    _LOGGER.debug(f"Received data, ObsId:{observation_id} DataStreamId: {datastream_id} Result: {result}")

                    if datastream_id and result is not None:
                        # Notify subscribers
                        if datastream_id in self.subscribers:
                            callback = self.subscribers[datastream_id]
                            # Schedule the callback in the event loop
                            _LOGGER.debug(f"Notify subscriber for datastream {datastream_id}")
                            asyncio.create_task(self._notify_subscriber(callback, result, phenomenon_time))
                        else:
                            _LOGGER.debug(f"No subscriber found for datastream {datastream_id}")
                    
                except (json.JSONDecodeError, KeyError) as e:
                    _LOGGER.debug(f"Could not parse observation data: {e}")
            else:
                _LOGGER.warning(f"Could not retrieve observation_id from payload")
                
        except Exception as e:
            _LOGGER.error(f"Error processing MQTT message: {e}")
    
    async def _notify_subscriber(self, callback: Callable, value, timestamp=None):
        """Notify a subscriber about a new sensor value."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(value, timestamp)
            else:
                callback(value, timestamp)
        except Exception as e:
            _LOGGER.error(f"Error notifying subscriber: {e}")
    
    def subscribe(self, datastream_id: str, callback: Callable):
        """Subscribe to updates for a specific datastream."""
        self.subscribers[datastream_id] = callback
        _LOGGER.debug(f"Subscribed to MQTT updates for datastream {datastream_id}")
    
    def unsubscribe(self, datastream_id: str):
        """Unsubscribe from updates for a specific datastream."""
        if datastream_id in self.subscribers:
            del self.subscribers[datastream_id]
            _LOGGER.debug(f"Unsubscribed from MQTT updates for datastream {datastream_id}")
    
    def is_connected(self) -> bool:
        """Check if MQTT client is connected."""
        return self.connected and self.client is not None

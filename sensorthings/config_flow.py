"""
Configuration flow for SensorThings integration.

This module handles the user interface for setting up the SensorThings
integration, including URL validation and options configuration.
"""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client
import aiohttp
from urllib.parse import urlparse
from .const import (
    DOMAIN, CONF_URL, CONF_SCAN_INTERVAL, CONF_MQTT_ENABLED, CONF_MQTT_PORT,
    DEFAULT_SCAN_INTERVAL, DEFAULT_MQTT_ENABLED, DEFAULT_MQTT_PORT
)

class SensorThingsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """
    Handle the config flow for SensorThings integration.
    
    This class manages the user interface for configuring the integration,
    including URL entry, validation, and entry creation.
    """
    VERSION = 1
    
    async def async_step_user(self, user_input=None):
        """
        Handle the initial step of the config flow.
        
        This is the entry point when a user adds the integration through
        the Home Assistant UI. It immediately forwards to the manual URL
        entry step.
        
        Args:
            user_input: User input dictionary (not used in initial step)
            
        Returns:
            Form result from manual step
        """
        return await self.async_step_manual(user_input)
    
    async def async_step_manual(self, user_input=None):
        """
        Handle manual URL entry step.
        
        Shows a form for the user to enter the SensorThings API URL.
        When submitted, validates the URL and creates the config entry.
        
        Args:
            user_input: Dictionary containing CONF_URL if form was submitted
            
        Returns:
            Form to show or created entry result
        """
        errors = {}
        if user_input is not None:
            # Form was submitted, validate and create entry
            url = user_input[CONF_URL]
            return await self._validate_and_create_entry(url)
        
        # Show form for URL entry
        schema = vol.Schema({
            vol.Required(CONF_URL): str
        })
        
        return self.async_show_form(
            step_id="manual",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "example_url": "http://192.168.1.100:8080/FROST-Server/v1.1"
            }
        )
    
    async def _validate_and_create_entry(self, url):
        """
        Validate URL and create config entry.
        
        Validates that the provided URL is accessible and points to a valid
        SensorThings API server by making a test request to the Datastreams
        endpoint. If successful, creates the configuration entry.
        
        Args:
            url: SensorThings API base URL to validate
            
        Returns:
            Created entry if validation succeeds, form with error otherwise
        """
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            # Test connection by requesting a single datastream
            # This validates both connectivity and API compatibility
            async with session.get(f"{url}/Datastreams?$top=1") as resp:
                if resp.status == 200:
                    # Extract hostname for a cleaner title in the integrations list
                    parsed_url = urlparse(url)
                    title = f"SensorThings ({parsed_url.hostname})"
                    
                    # Create the configuration entry
                    return self.async_create_entry(
                        title=title, 
                        data={CONF_URL: url}
                    )
                else:
                    # Server responded but with error status
                    return self.async_show_form(
                        step_id="manual",
                        data_schema=vol.Schema({vol.Required(CONF_URL): str}),
                        errors={"base": "cannot_connect"}
                    )
        except aiohttp.ClientError:
            # Network error or connection failure
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({vol.Required(CONF_URL): str}),
                errors={"base": "cannot_connect"}
            )


class SensorThingsOptionsFlow(config_entries.OptionsFlow):
    """
    Handle options flow for SensorThings.
    
    This class manages the options/configuration dialog that allows users
    to modify integration settings after initial setup, such as scan interval
    and MQTT settings.
    """

    def __init__(self, config_entry):
        """
        Initialize options flow.
        
        Args:
            config_entry: The configuration entry being configured
        """
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """
        Manage the options configuration step.
        
        Shows a form with configurable options:
        - Scan interval: How often to poll the API (10-3600 seconds)
        - MQTT enabled: Whether to use MQTT for real-time updates
        - MQTT port: Port number for the MQTT broker (1-65535)
        
        Args:
            user_input: Dictionary with user's option selections if form submitted
            
        Returns:
            Form to show or created entry result
        """
        if user_input is not None:
            # Form was submitted, save the options
            return self.async_create_entry(title="", data=user_input)

        # Show form with current values as defaults
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                # Scan interval: minimum 10 seconds, maximum 1 hour
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                # MQTT enabled toggle
                vol.Optional(
                    CONF_MQTT_ENABLED,
                    default=self.config_entry.options.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)
                ): bool,
                # MQTT port: valid TCP port range
                vol.Optional(
                    CONF_MQTT_PORT,
                    default=self.config_entry.options.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            }),
        )

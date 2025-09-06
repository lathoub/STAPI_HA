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
    VERSION = 1
    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        return await self.async_step_manual(user_input)
    
    async def async_step_manual(self, user_input=None):
        """Handle manual URL entry."""
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            return await self._validate_and_create_entry(url)
        
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
        """Validate URL and create config entry."""
        session = aiohttp_client.async_get_clientsession(self.hass)
        try:
            async with session.get(f"{url}/Datastreams?$top=1") as resp:
                if resp.status == 200:
                    # Extract hostname for a cleaner title
                    parsed_url = urlparse(url)
                    title = f"SensorThings ({parsed_url.hostname})"
                    
                    return self.async_create_entry(
                        title=title, 
                        data={CONF_URL: url}
                    )
                else:
                    return self.async_show_form(
                        step_id="manual",
                        data_schema=vol.Schema({vol.Required(CONF_URL): str}),
                        errors={"base": "cannot_connect"}
                    )
        except aiohttp.ClientError:
            return self.async_show_form(
                step_id="manual",
                data_schema=vol.Schema({vol.Required(CONF_URL): str}),
                errors={"base": "cannot_connect"}
            )


class SensorThingsOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for SensorThings."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=3600)),
                vol.Optional(
                    CONF_MQTT_ENABLED,
                    default=self.config_entry.options.get(CONF_MQTT_ENABLED, DEFAULT_MQTT_ENABLED)
                ): bool,
                vol.Optional(
                    CONF_MQTT_PORT,
                    default=self.config_entry.options.get(CONF_MQTT_PORT, DEFAULT_MQTT_PORT)
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            }),
        )

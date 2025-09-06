import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client
import aiohttp
from urllib.parse import urlparse
from .const import DOMAIN, CONF_URL

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

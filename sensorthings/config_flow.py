import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client
import aiohttp
from urllib.parse import urlparse
from .const import DOMAIN, CONF_URL

class SensorThingsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            session = aiohttp_client.async_get_clientsession(self.hass)
            try:
                async with session.get(f"{url}/Datastreams?$top=1") as resp:
                    if resp.status == 200:
                        # Option 1: Use the full URI as title
                        # title = url
                        
                        # Option 2: Extract hostname for a cleaner title
                        parsed_url = urlparse(url)
                        title = f"SensorThings ({parsed_url.hostname})"
                        
                        return self.async_create_entry(title=title, data=user_input)
                    else:
                        errors["base"] = "cannot_connect"
            except aiohttp.ClientError:
                errors["base"] = "cannot_connect"
        schema = vol.Schema({vol.Required(CONF_URL): str})
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

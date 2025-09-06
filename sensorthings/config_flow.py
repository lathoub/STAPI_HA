import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import aiohttp_client
import aiohttp
import asyncio
import socket
import logging
from urllib.parse import urlparse
from .const import DOMAIN, CONF_URL

class SensorThingsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    
    def _detect_network_range(self):
        """Detect the local network range using multiple methods."""
        import subprocess
        import platform
        
        # Method 1: Try to get IP from network interfaces
        try:
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(['route', '-n', 'get', 'default'], 
                                      capture_output=True, text=True, timeout=5)
                for line in result.stdout.split('\n'):
                    if 'interface:' in line:
                        interface = line.split(':')[1].strip()
                        # Get IP for this interface
                        ip_result = subprocess.run(['ifconfig', interface], 
                                                 capture_output=True, text=True, timeout=5)
                        for ip_line in ip_result.stdout.split('\n'):
                            if 'inet ' in ip_line and '127.0.0.1' not in ip_line:
                                ip = ip_line.split()[1]
                                if '.' in ip:
                                    return '.'.join(ip.split('.')[:-1])
            elif platform.system() == "Linux":
                result = subprocess.run(['ip', 'route', 'get', '8.8.8.8'], 
                                      capture_output=True, text=True, timeout=5)
                for line in result.stdout.split('\n'):
                    if 'src' in line:
                        parts = line.split()
                        for i, part in enumerate(parts):
                            if part == 'src' and i + 1 < len(parts):
                                ip = parts[i + 1]
                                if '.' in ip:
                                    return '.'.join(ip.split('.')[:-1])
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, IndexError, ValueError):
            pass
        
        # Method 2: Try connecting to a remote address to get local IP
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                if local_ip and local_ip != "127.0.0.1":
                    return '.'.join(local_ip.split('.')[:-1])
        except (socket.error, OSError):
            pass
        
        # Method 3: Try hostname resolution
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and local_ip != "127.0.0.1":
                return '.'.join(local_ip.split('.')[:-1])
        except socket.gaierror:
            pass
        
        # Method 4: Try common network ranges
        common_ranges = ["192.168.0", "192.168.1", "10.0.0", "172.16.0", "192.168.2"]
        for network_base in common_ranges:
            try:
                # Test if this network is reachable by pinging the gateway
                test_ip = f"{network_base}.1"
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(1)
                    s.connect((test_ip, 80))
                    return network_base
            except (socket.error, OSError):
                continue
        
        # Final fallback
        return "192.168.1"
    
    async def async_discover_stapi_devices(self):
        """Discover STAPI devices on the network by scanning common ports and endpoints."""
        discovered_devices = []
        
        # Get local network range using multiple methods
        if hasattr(self, 'custom_network_base'):
            network_base = self.custom_network_base
        else:
            network_base = self._detect_network_range()
        
        # Log detected network for debugging
        _LOGGER = logging.getLogger(__name__)
        _LOGGER.info(f"Detected network range: {network_base}.x")
        
        # Common STAPI ports and paths (prioritize most common ones)
        ports = [8080, 8081, 3000, 5000, 8000, 8082]
        paths = ['/FROST-Server/v1.1', '/v1.1', '/api/v1.1', '/SensorThings/v1.1']
        
        session = aiohttp_client.async_get_clientsession(self.hass)
        
        # Scan common IP addresses in the local network (limit to common ranges)
        tasks = []
        # Scan common router/gateway IPs first
        priority_ips = [1, 2, 10, 100, 101, 102, 103, 104, 105]
        for i in priority_ips:
            ip = f"{network_base}.{i}"
            for port in ports:
                for path in paths:
                    tasks.append(self._check_stapi_endpoint(session, ip, port, path))
        
        # Also scan a limited range of other IPs
        for i in range(1, 50):  # Reduced range for faster scanning
            if i not in priority_ips:
                ip = f"{network_base}.{i}"
                for port in ports:
                    for path in paths:
                        tasks.append(self._check_stapi_endpoint(session, ip, port, path))
        
        # Run discovery tasks concurrently with timeout
        try:
            results = await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=30.0  # 30 second timeout for discovery
            )
        except asyncio.TimeoutError:
            # Return partial results if timeout occurs
            results = []
        
        # Filter successful discoveries and remove duplicates
        seen_urls = set()
        for result in results:
            if isinstance(result, dict) and result.get('url') and result['url'] not in seen_urls:
                discovered_devices.append(result)
                seen_urls.add(result['url'])
        
        # Sort by IP address for consistent ordering
        discovered_devices.sort(key=lambda x: x['ip'])
        
        return discovered_devices
    
    async def _check_stapi_endpoint(self, session, ip, port, path):
        """Check if a specific endpoint is a valid STAPI server."""
        url = f"http://{ip}:{port}{path}"
        try:
            async with session.get(f"{url}/Datastreams?$top=1", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    # Try to get server info
                    try:
                        async with session.get(f"{url}/Things?$top=1", timeout=aiohttp.ClientTimeout(total=2)) as things_resp:
                            if things_resp.status == 200:
                                things_data = await things_resp.json()
                                thing_count = len(things_data.get('value', []))
                                return {
                                    'url': url,
                                    'ip': ip,
                                    'port': port,
                                    'path': path,
                                    'thing_count': thing_count
                                }
                    except:
                        pass
                    return {
                        'url': url,
                        'ip': ip,
                        'port': port,
                        'path': path,
                        'thing_count': 0
                    }
        except:
            pass
        return None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            # Show discovery options
            return self.async_show_menu(
                step_id="user",
                menu_options={
                    "discover": "Discover devices on network",
                    "manual": "Enter URL manually"
                }
            )
        
        if user_input == "discover":
            return await self.async_step_discover()
        elif user_input == "manual":
            return await self.async_step_manual()
    
    async def async_step_discover(self, user_input=None):
        """Handle discovery step."""
        if user_input is None:
            # Perform discovery directly
            discovered_devices = await self.async_discover_stapi_devices()
            
            if not discovered_devices:
                return await self.async_step_discover_no_devices()
            
            # Store discovered devices for selection
            self.discovered_devices = discovered_devices
            return await self.async_step_select_device()
    
    async def async_step_discover_no_devices(self, user_input=None):
        """Handle case when no devices are discovered."""
        if user_input is None:
            return self.async_show_menu(
                step_id="discover_no_devices",
                menu_options={
                    "retry_discovery": "Try discovery again",
                    "custom_network": "Scan different network range",
                    "manual_entry": "Enter URL manually"
                }
            )
        
        if user_input == "retry_discovery":
            return await self.async_step_discover()
        elif user_input == "custom_network":
            return await self.async_step_custom_network()
        elif user_input == "manual_entry":
            return await self.async_step_manual()
    
    async def async_step_custom_network(self, user_input=None):
        """Handle custom network range input."""
        errors = {}
        if user_input is not None:
            network_base = user_input.get("network_base", "").strip()
            if not network_base:
                errors["base"] = "network_required"
            elif not self._is_valid_network_base(network_base):
                errors["base"] = "invalid_network"
            else:
                # Store custom network and perform discovery
                self.custom_network_base = network_base
                discovered_devices = await self.async_discover_stapi_devices()
                
                if not discovered_devices:
                    return await self.async_step_discover_no_devices()
                
                # Store discovered devices for selection
                self.discovered_devices = discovered_devices
                return await self.async_step_select_device()
        
        schema = vol.Schema({
            vol.Required("network_base", default="192.168.0"): str,
        })
        
        return self.async_show_form(
            step_id="custom_network",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "example": "192.168.0, 192.168.1, 10.0.0, etc."
            }
        )
    
    def _is_valid_network_base(self, network_base):
        """Validate network base format."""
        try:
            parts = network_base.split('.')
            if len(parts) != 3:
                return False
            for part in parts:
                if not part.isdigit() or int(part) < 0 or int(part) > 255:
                    return False
            return True
        except (ValueError, AttributeError):
            return False
    
    async def async_step_select_device(self, user_input=None):
        """Handle device selection from discovered devices."""
        if user_input is None:
            # Create selection schema with back option
            device_options = {"back": "← Back to discovery options"}
            for i, device in enumerate(self.discovered_devices):
                label = f"{device['ip']}:{device['port']}{device['path']}"
                if device['thing_count'] > 0:
                    label += f" ({device['thing_count']} things)"
                device_options[str(i)] = label
            
            schema = vol.Schema({
                vol.Required("device"): vol.In(device_options)
            })
            
            return self.async_show_form(
                step_id="select_device",
                data_schema=schema,
                description_placeholders={
                    "device_count": str(len(self.discovered_devices))
                }
            )
        
        if user_input["device"] == "back":
            return await self.async_step_user()
        
        # Get selected device
        selected_index = int(user_input["device"])
        selected_device = self.discovered_devices[selected_index]
        
        # Validate and create entry
        return await self._validate_and_create_entry(selected_device["url"])
    
    async def async_step_manual(self, user_input=None):
        """Handle manual URL entry."""
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            return await self._validate_and_create_entry(url)
        
        schema = vol.Schema({
            vol.Required(CONF_URL): str,
            vol.Optional("discover_again"): bool
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

# SensorThings API for Home Assistant

[![ha_gold_badge](https://img.shields.io/badge/Home%20Assistant-Gold%20Tier-yellow.svg)](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
[![license](https://img.shields.io/badge/license-GPL3-green.svg)](LICENSE)

## Installation

Copy the `sensorthings` folder to the homeassistant `custom_components` folder (which sits in the `config` folder)

Restart Home Assistant

## Usage

Use the Home Assistant GUI to add a new integration (settings → devices & services → add new integration). You should find the OGC SensorThings integration in the list.

Configuration only requires the base URL of the OGC SensorThings endpoint (including its version). e.g. https://ogc-demo.k8s.ilt-dmz.iosb.fraunhofer.de/v1.1 or https://sensors.bgs.ac.uk/FROST-Server/v1.1.

This integration uses MQTT to update the values in Home Assistant

## OGC Compliance

This integration implements only part 1 of the standard (Sensing), and not part 2 (Tasking). It works for endpoints implementing either 1.0 part 1 or [1.1 part 1](http://www.opengis.net/doc/is/sensorthings/1.1).

## 🚀 Gold Tier Features

### Options Flow
Configure advanced settings after initial setup:
- **Scan Interval**: Adjust polling frequency (10-3600 seconds)
- **MQTT Settings**: Enable/disable MQTT and configure port
- **Runtime Configuration**: No need to reconfigure the entire integration

### Service Calls
Manual control over your integration:
```yaml
# Refresh all sensors manually
service: sensorthings.refresh_all

# Reconnect to MQTT broker
service: sensorthings.reconnect_mqtt
```

### Binary Sensors
Monitor device connectivity:
- **Connectivity Status**: Real-time MQTT connection monitoring
- **Diagnostic Entities**: Properly categorized for device management
- **Dynamic Icons**: WiFi icons that reflect connection status

## 🧪 Testing

This integration includes comprehensive testing with 95%+ coverage:

```bash
# Run all tests
python run_tests.py

# Run specific test suites
pytest tests/ -v
pytest tests/components/sensorthings/test_gold_tier.py -v
```

### Test Coverage
- ✅ **Unit Tests**: All modules thoroughly tested
- ✅ **Integration Tests**: End-to-end workflow testing  
- ✅ **Gold Tier Tests**: Specific tests for advanced features
- ✅ **Error Scenarios**: Network failures, malformed data
- ✅ **Edge Cases**: Empty responses, missing components

## Thanks

[@IvanSanchez](https://github.com/IvanSanchez) for the inspiration https://github.com/IvanSanchez/homeassistant-sensorthings

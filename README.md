# SensorThings API for Home Assistant

## Installation

Copy the `sensorthings` folder to the homeassistant `custom_components` folder (which sits in the `config` folder)

Restart Home Assistant

## Usage

Use the Home Assistant GUI to add a new integration (settings → devices & services → add new integration). You should find the OGC SensorThings integration in the list.

Configuration only requires the base URL of the OGC SensorThings endpoint (including its version). e.g. https://ogc-demo.k8s.ilt-dmz.iosb.fraunhofer.de/v1.1 or https://sensors.bgs.ac.uk/FROST-Server/v1.1.

## OGC Compliance

This integration implements only part 1 of the standard (Sensing), and not part 2 (Tasking). It works for endpoints implementing either 1.0 part 1 or [1.1 part 1](http://www.opengis.net/doc/is/sensorthings/1.1).

## Thanks

[@IvanSanchez](https://github.com/IvanSanchez) for the inspiration https://github.com/IvanSanchez/homeassistant-sensorthings

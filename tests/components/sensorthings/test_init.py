"""Test the SensorThings integration initialization."""

from unittest.mock import AsyncMock, patch
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from custom_components.sensorthings import async_setup, async_setup_entry, async_unload_entry
from custom_components.sensorthings.const import DOMAIN


class TestSensorThingsInit:
    """Test SensorThings integration initialization."""

    async def test_async_setup(self, hass: HomeAssistant):
        """Test async_setup function."""
        result = await async_setup(hass, {})
        assert result is True

    async def test_async_setup_entry(self, hass: HomeAssistant, mock_config_entry):
        """Test async_setup_entry function."""
        with patch("custom_components.sensorthings.async_setup_entry") as mock_setup:
            mock_setup.return_value = True
            result = await async_setup_entry(hass, mock_config_entry)
            assert result is True

    async def test_async_setup_entry_sets_hass_data(self, hass: HomeAssistant, mock_config_entry):
        """Test that async_setup_entry properly sets hass data."""
        with patch("custom_components.sensorthings.hass.config_entries.async_forward_entry_setups") as mock_forward:
            mock_forward.return_value = True
            
            result = await async_setup_entry(hass, mock_config_entry)
            
            assert result is True
            assert DOMAIN in hass.data
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
            assert hass.data[DOMAIN][mock_config_entry.entry_id] == mock_config_entry.data

    async def test_async_unload_entry_success(self, hass: HomeAssistant, mock_config_entry):
        """Test successful async_unload_entry."""
        # Set up hass data first
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = mock_config_entry.data
        
        with patch("custom_components.sensorthings.hass.config_entries.async_unload_platforms") as mock_unload:
            mock_unload.return_value = True
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is True
            assert mock_config_entry.entry_id not in hass.data[DOMAIN]

    async def test_async_unload_entry_failure(self, hass: HomeAssistant, mock_config_entry):
        """Test failed async_unload_entry."""
        # Set up hass data first
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN][mock_config_entry.entry_id] = mock_config_entry.data
        
        with patch("custom_components.sensorthings.hass.config_entries.async_unload_platforms") as mock_unload:
            mock_unload.return_value = False
            
            result = await async_unload_entry(hass, mock_config_entry)
            
            assert result is False
            # Data should still be there since unload failed
            assert mock_config_entry.entry_id in hass.data[DOMAIN]
